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

**Collections** come from ``saved_collections.json`` beside it, and become
categories of the same name -- the same way YouTube playlists do. A post in no
collection is "just saved".

**Meta's exports garble every non-ASCII character.** Each byte of the UTF-8 is
written as if it were a character of its own, so an apostrophe comes out as
"â€™" and an emoji as four symbols of noise. On a real export that was every
curly quote, dash and emoji -- 239 strings in the saved posts and 36 in the
collections, with none stored correctly. Garbled text also defeats search:
"don't" stored as "donâ€™t" matches nothing anyone types. Every string is
repaired on read (:func:`_unmangle`).

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
COLLECTIONS_FILE = "saved_collections.json"


def _unmangle(text: str) -> str:
    """Undo Meta's double encoding: UTF-8 bytes written out as Latin-1 characters.

    Only applied when the whole string turns back into valid UTF-8, so text
    that was stored correctly -- "café" with a real é -- is left as it is.
    """
    if not any(0x80 <= ord(c) <= 0xFF for c in text):
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _repair(node: Any) -> Any:
    if isinstance(node, str):
        return _unmangle(node)
    if isinstance(node, list):
        return [_repair(v) for v in node]
    if isinstance(node, dict):
        return {k: _repair(v) for k, v in node.items()}
    return node


def _load(path: str | Path, filename: str = SAVED_FILE, required: bool = True) -> Any:
    """One export file, from itself, a file beside it, a folder, or the .zip.

    Pointing at saved_posts.json finds saved_collections.json next to it, so
    either file, the folder or the zip all work as the one argument.
    """
    p = Path(path).expanduser()
    raw: Optional[str] = None
    if p.is_file() and p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            for name in z.namelist():
                if PurePosixPath(name).name == filename:
                    raw = z.read(name).decode("utf-8")
                    break
    elif p.is_dir():
        found = sorted(p.rglob(filename))
        raw = found[0].read_text(encoding="utf-8") if found else None
    elif p.is_file():
        target = p if p.name == filename else p.with_name(filename)
        raw = target.read_text(encoding="utf-8") if target.is_file() else None
    else:
        raise FileNotFoundError(f"nothing at {p}")
    if raw is None:
        if required:
            raise FileNotFoundError(f"no {filename} in {p}")
        return None
    return _repair(json.loads(raw))


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


def read_collections(path: str | Path) -> list[tuple[str, list[str]]]:
    """``[(collection name, [post URLs])]``, or [] when there are none.

    Each collection lists its posts under a group titled ``Media``; every item
    there has a ``URL``. Everything else about the post is already in
    saved_posts.json.
    """
    data = _load(path, COLLECTIONS_FILE, required=False)
    if not isinstance(data, list):
        return []
    out = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name, urls = None, []
        for lv in entry.get("label_values") or []:
            if lv.get("label") == "Name":
                name = (lv.get("value") or "").strip()
            elif lv.get("label") is None and lv.get("title") == "Media":
                for item in lv.get("dict") or []:
                    for f in item.get("dict") or []:
                        if f.get("label") == "URL" and (f.get("href") or f.get("value")):
                            urls.append(f.get("href") or f.get("value"))
        if name:
            out.append((name, urls))
    return out


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


def import_collections(
    conn: sqlite3.Connection, collections: Iterable[tuple[str, list[str]]],
    saved_at: Optional[dict[str, str]] = None,
) -> dict[str, int]:
    """File each post under its collection's name. Posts not in the library are counted."""
    saved_at = saved_at or {}
    stats = {"filings": 0, "not_in_library": 0}
    for name, urls in collections:
        for url in urls:
            canonical, _ = canonical_form(url, "instagram")
            row = conn.execute(
                "SELECT id FROM items WHERE canonical_url = ?", (canonical,)).fetchone()
            if row is None:
                stats["not_in_library"] += 1
                continue
            # Meta does not say when a post went into a collection, so the date
            # you saved it stands in -- filing happens at save time or after.
            db.file_under(conn, int(row["id"]), name, saved_at.get(url))
            stats["filings"] += 1
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
        collections = read_collections(args.export)
    except FileNotFoundError as exc:
        print(f"{exc}. Point this at saved_posts.json, or the folder or .zip it came in.")
        return 1
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Could not read that file: {exc}")
        return 1

    _print_listing(posts)
    if collections:
        print(f"\ncollections: {len(collections)}")
        for name, urls in sorted(collections, key=lambda c: -len(c[1])):
            print(f"  {name[:40]:<40}  {len(urls):>4}")
    else:
        print(f"\ncollections: none found ({COLLECTIONS_FILE} was not beside it)")
    if args.list:
        return 0

    conn, where = db.connect_announced(args.db)
    print(f"\n{where}")
    try:
        stats = import_saved(conn, posts)
        filed = import_collections(
            conn, collections, {p["url"]: p["saved_at"] for p in posts})
        total = db.count(conn)
    finally:
        conn.close()
    print(f"\nposts imported       : {stats['imported']}")
    print(f"already in library   : {stats['already_present']}")
    if collections:
        print(f"filed into categories: {filed['filings']}")
        if filed["not_in_library"]:
            print(f"  not filed          : {filed['not_in_library']} (in a collection "
                  "but not in saved posts)")
    for key, label in (("undated", "skipped, no date"), ("not_instagram", "skipped, not Instagram")):
        if stats[key]:
            print(f"{label:<21}: {stats[key]}")
    print(f"\nlibrary total        : {total}")
    print("\nThese arrive with their captions, authors and dates, and show in the museum")
    print("straight away -- without pictures, which the export does not include.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
