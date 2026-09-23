"""Backfill your Instagram saves from a Meta data export.

Unlike TikTok's export, Instagram's carries almost everything the library
needs: for every saved post, the link, when you saved it, the whole caption,
the author's name and username, and the hashtags. So an Instagram import does
not produce dated links waiting on a backfill -- it produces items that can be
searched and shelved the moment they land.

That matters more here than anywhere else. Instagram answers most requests
from anything but a logged-in browser with a login wall, so the lookup that
fills in a TikTok or a YouTube video usually learns nothing about a post. The
export is the one source that is not behind that wall.

What it does not carry is the picture. See ``python -m favorites.thumbnails``.

Two layouts are read:

- **Current** (seen on a real 2026 export): a list of posts, each with a
  ``timestamp`` and ``label_values`` holding ``URL``, ``Caption``, and groups
  titled ``Owner`` and ``Hashtags``.
- **Older**: ``{"saved_saved_media": [{"title": <username>,
  "string_map_data": {"Saved on": {"href", "timestamp"}}}]}``, which has the
  link, date and username but no caption.

Run ``--list`` first: it reads the export and imports nothing.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Optional

from .. import db, tagging
from ..resolve import canonical_form, detect_platform, platforms
from urllib.parse import urlparse

SOURCE = "instagram-export"
SAVED_FILE = "saved_posts.json"


def _load(path: str | Path) -> Any:
    """The saved-posts JSON from a file, an unzipped export folder, or its .zip."""
    p = Path(path).expanduser()
    if p.is_file() and p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            for name in z.namelist():
                if PurePosixPath(name).name == SAVED_FILE:
                    return json.loads(z.read(name).decode("utf-8"))
        raise FileNotFoundError(f"no {SAVED_FILE} inside {p}")
    if p.is_dir():
        found = sorted(p.rglob(SAVED_FILE))
        if not found:
            raise FileNotFoundError(f"no {SAVED_FILE} under {p}")
        p = found[0]
    if not p.is_file():
        raise FileNotFoundError(f"nothing at {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _iso(timestamp: Any) -> Optional[str]:
    try:
        seconds = float(timestamp)
    except (TypeError, ValueError):
        return None
    if seconds > 1e12:  # milliseconds
        seconds /= 1000
    if seconds <= 0:
        return None
    return datetime.fromtimestamp(seconds, timezone.utc).replace(microsecond=0).isoformat()


def _group_fields(group: dict) -> list[dict[str, str]]:
    """``Owner`` / ``Hashtags`` groups nest their fields two levels down."""
    out = []
    for inner in group.get("dict") or []:
        fields = {}
        for f in inner.get("dict") or []:
            if f.get("label"):
                fields[f["label"]] = f.get("value") or ""
        if fields:
            out.append(fields)
    return out


def _current(entry: dict) -> Optional[dict]:
    url = caption = None
    owner: dict[str, str] = {}
    tags: list[str] = []
    for lv in entry.get("label_values") or []:
        label = (lv.get("label") or "").strip().lower()
        if label == "url":
            url = url or lv.get("href") or lv.get("value")
        elif label == "caption" and lv.get("value") and not caption:
            caption = lv["value"]          # later duplicates are identical copies
        elif lv.get("label") is None and lv.get("title") == "Owner":
            fields = _group_fields(lv)
            owner = fields[0] if fields else {}
        elif lv.get("label") is None and lv.get("title") == "Hashtags":
            tags = [f.get("Name", "").lstrip("#") for f in _group_fields(lv) if f.get("Name")]
    if not url:
        return None
    return {
        "url": url, "saved_at": _iso(entry.get("timestamp")), "caption": caption,
        "owner_name": owner.get("Name") or None,
        "owner_username": (owner.get("Username") or "").lstrip("@") or None,
        "hashtags": tags,
    }


def _older(entry: dict) -> Optional[dict]:
    saved = (entry.get("string_map_data") or {}).get("Saved on") or {}
    url = saved.get("href")
    if not url:
        return None
    return {
        "url": url, "saved_at": _iso(saved.get("timestamp")), "caption": None,
        "owner_name": None, "owner_username": (entry.get("title") or "").lstrip("@") or None,
        "hashtags": [],
    }


def read_saved(path: str | Path) -> list[dict]:
    """Every saved post, newest first, as plain dicts."""
    data = _load(path)
    if isinstance(data, dict) and isinstance(data.get("saved_saved_media"), list):
        rows = [_older(e) for e in data["saved_saved_media"] if isinstance(e, dict)]
    elif isinstance(data, list):
        rows = [_current(e) for e in data if isinstance(e, dict)]
    else:
        raise ValueError("not an Instagram saved-posts file this importer recognises")
    return [r for r in rows if r]


def import_saved(conn: sqlite3.Connection, posts: Iterable[dict]) -> dict[str, int]:
    """Insert saved posts. Anything already in the library is left untouched."""
    imported_at = db.now_iso()
    stats = {"imported": 0, "already_present": 0, "undated": 0, "not_instagram": 0}
    fmt = platforms.get("instagram").format_from_url

    for post in posts:
        url = post["url"]
        if detect_platform(url) != "instagram":
            stats["not_instagram"] += 1
            continue
        if not post["saved_at"]:
            stats["undated"] += 1
            continue
        canonical, external_id = canonical_form(url, "instagram")
        if conn.execute("SELECT 1 FROM items WHERE canonical_url = ?", (canonical,)).fetchone():
            stats["already_present"] += 1
            continue

        caption = post["caption"]
        username = post["owner_username"]
        tags, terms = tagging.enrich(title=caption, description=caption)
        for extra in tagging.hashtags(" ".join("#" + t for t in post["hashtags"])):
            if extra not in tags:
                tags.append(extra)
        described = bool(caption or username)

        db.upsert_item(conn, {
            "canonical_url": canonical,
            "shared_url": url,
            "platform": "instagram",
            "external_id": external_id,
            # Instagram has no titles. The caption is the text, the same way a
            # TikTok's oEmbed "title" is its caption.
            "title": caption,
            "description": caption,
            "creator_name": post["owner_name"],
            "creator_handle": f"@{username}" if username else None,
            # The export's owner URL is the bio link (a linktree, a shop), not
            # the account, so the profile is built from the username instead.
            "creator_url": f"https://www.instagram.com/{username}/" if username else None,
            "tags": tags,
            "terms": terms,
            "saved_at": post["saved_at"],
            "format": fmt(urlparse(url)) if fmt else None,
            "source": SOURCE,
            "imported_at": imported_at,
            # Described by the export itself -- there is nothing a lookup
            # behind Instagram's login wall would add but the picture.
            "resolve_status": "ok" if described else "pending",
            "resolved_at": imported_at if described else None,
        })
        stats["imported"] += 1
    return stats


def _print_listing(posts: list[dict]) -> None:
    dates = sorted(p["saved_at"] for p in posts if p["saved_at"])
    reels = sum(1 for p in posts if "/reel" in p["url"])
    print(f"saved posts in export: {len(posts)}")
    if dates:
        print(f"  saved between      : {dates[0][:10]} and {dates[-1][:10]}")
    print(f"  reels / posts      : {reels} / {len(posts) - reels}")
    print(f"  with a caption     : {sum(1 for p in posts if p['caption'])}")
    print(f"  with an author     : {sum(1 for p in posts if p['owner_username'])}")
    print(f"  with hashtags      : {sum(1 for p in posts if p['hashtags'])}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("export", help="saved_posts.json, the unzipped export folder, or its .zip")
    ap.add_argument("--list", action="store_true", help="show what is in the export and import nothing")
    ap.add_argument("--db", help="library path (default: $FAVORITES_DB)")
    args = ap.parse_args(argv)

    try:
        posts = read_saved(args.export)
    except FileNotFoundError as exc:
        print(f"{exc}. Point this at saved_posts.json, or the folder or .zip it came in.")
        return 1
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Could not read that file: {exc}")
        return 1

    _print_listing(posts)
    if args.list:
        return 0

    conn, where = db.connect_announced(args.db)
    print(f"\n{where}")
    try:
        stats = import_saved(conn, posts)
        total = db.count(conn)
    finally:
        conn.close()
    print(f"\nposts imported       : {stats['imported']}")
    print(f"already in library   : {stats['already_present']}")
    for key, label in (("undated", "skipped, no date"), ("not_instagram", "skipped, not Instagram")):
        if stats[key]:
            print(f"{label:<21}: {stats[key]}")
    print(f"\nlibrary total        : {total}")
    print("\nThese arrive with their captions, authors and dates, and show in the museum")
    print("straight away -- without pictures, which the export does not include.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
