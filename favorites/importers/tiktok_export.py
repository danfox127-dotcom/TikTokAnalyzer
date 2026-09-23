"""Backfill your TikTok favourites from a data export.

A TikTok export gives two fields per favourite -- ``Date`` and ``Link`` -- and
the link is an id-only share URL on ``tiktokv.com`` with the @handle stripped.
So an import cannot produce a title or a creator; it produces a dated URL that
:mod:`favorites.backfill` resolves afterwards.

The date is the part worth having. Favourites go back years, which is what lets
the museum show months, recurring creators and "from the vault" on day one
instead of after six months of collecting.

**Favourites, not likes.** The export carries both. A favourite is a deliberate
"keep this"; a like is a tap. In a real export the like list is also capped and
covers only recent months, so importing it would bury a multi-year collection of
deliberate saves under a short, shallow burst of taps. Likes are therefore
opt-in via ``--include-likes`` and tagged ``source='export-like'`` so they can be
told apart -- or removed -- later.

This module reads the export JSON directly rather than importing the repo's
``parsers.tiktok``. Keeping ``favorites/`` free of imports from the analyzer is
what makes it a folder that can be lifted into its own project unchanged.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .. import db
from ..resolve import canonical_form, detect_platform

# TikTok writes "2026-03-05 14:22:01", in UTC, with no zone marker.
EXPORT_DATE = "%Y-%m-%d %H:%M:%S"

VIDEO_ID = re.compile(r"/video/(\d+)")


def _dig(data: dict, *path: str, default=None):
    """Follow a key path, tolerating the several shapes TikTok has shipped."""
    node = data
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def _first_list(data: dict, paths: Iterable[tuple[str, ...]]) -> list:
    for path in paths:
        found = _dig(data, *path)
        if isinstance(found, list) and found:
            return found
    return []


def parse_date(raw: str) -> Optional[str]:
    """Export date -> the ISO-8601 UTC string the library sorts on."""
    if not raw:
        return None
    try:
        naive = datetime.strptime(raw.strip(), EXPORT_DATE)
    except ValueError:
        return None
    return naive.replace(tzinfo=timezone.utc).isoformat()


def read_export(path: str | Path) -> dict[str, list[dict]]:
    """Return ``{"favorites": [...], "likes": [...]}`` of ``{date, link}`` rows."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    favorites = _first_list(data, [
        ("Likes and Favorites", "Favorite Videos", "FavoriteVideoList"),
        ("Your Activity", "Favorite Videos", "FavoriteVideoList"),
        ("Activity", "Favorite Videos", "FavoriteVideoList"),
    ])
    likes = _first_list(data, [
        ("Likes and Favorites", "Like List", "ItemFavoriteList"),
        ("Your Activity", "Like List", "ItemFavoriteList"),
        ("Activity", "Like List", "ItemFavoriteList"),
    ])

    def normalise(rows: list) -> list[dict]:
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            # Key casing differs between the two lists in the same file.
            date = row.get("Date") or row.get("date") or ""
            link = row.get("Link") or row.get("link") or row.get("VideoLink") or ""
            if link:
                out.append({"date": date, "link": link})
        return out

    return {"favorites": normalise(favorites), "likes": normalise(likes)}


def import_rows(
    conn: sqlite3.Connection, rows: list[dict], source: str
) -> dict[str, int]:
    """Insert unresolved items. Existing items are left completely alone.

    An item already in the library either came from the share sheet (so it has a
    title, and possibly a note) or was imported by an earlier run. Re-importing
    must never overwrite either, so a collision is skipped rather than merged.
    """
    imported_at = db.now_iso()
    stats = {"imported": 0, "skipped_existing": 0, "skipped_unusable": 0}

    for row in rows:
        link = row["link"]
        if not VIDEO_ID.search(link):
            stats["skipped_unusable"] += 1
            continue
        saved_at = parse_date(row["date"])
        if not saved_at:
            stats["skipped_unusable"] += 1
            continue

        platform = detect_platform(link)
        canonical, external_id = canonical_form(link, platform)

        exists = conn.execute(
            "SELECT 1 FROM items WHERE canonical_url = ?", (canonical,)
        ).fetchone()
        if exists:
            stats["skipped_existing"] += 1
            continue

        db.upsert_item(conn, {
            "canonical_url": canonical,
            "shared_url": link,
            "platform": platform,
            "external_id": external_id,
            "saved_at": saved_at,
            "source": source,
            "imported_at": imported_at,
            "resolve_status": "pending",
        })
        stats["imported"] += 1

    return stats


def import_export(
    conn: sqlite3.Connection, path: str | Path, include_likes: bool = False
) -> dict:
    lists = read_export(path)
    result = {
        "favorites_in_export": len(lists["favorites"]),
        "likes_in_export": len(lists["likes"]),
        "favorites": import_rows(conn, lists["favorites"], "export"),
        "likes": None,
    }
    if include_likes:
        result["likes"] = import_rows(conn, lists["likes"], "export-like")
    return result


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("export", help="path to user_data_tiktok.json")
    ap.add_argument("--db", help="library path (default: $FAVORITES_DB)")
    ap.add_argument("--include-likes", action="store_true",
                    help="also import the Like List (usually capped and shallow)")
    args = ap.parse_args(argv)

    conn, where = db.connect_announced(args.db)
    print(where + "\n")
    result = import_export(conn, args.export, include_likes=args.include_likes)

    fav = result["favorites"]
    print(f"favourites in export : {result['favorites_in_export']}")
    print(f"  imported           : {fav['imported']}")
    print(f"  already present    : {fav['skipped_existing']}")
    print(f"  unusable           : {fav['skipped_unusable']}")
    if result["likes"] is not None:
        lk = result["likes"]
        print(f"likes in export      : {result['likes_in_export']}")
        print(f"  imported           : {lk['imported']}")
        print(f"  already present    : {lk['skipped_existing']}")
        print(f"  unusable           : {lk['skipped_unusable']}")
    else:
        print(f"likes in export      : {result['likes_in_export']} (not imported; --include-likes to add)")

    pending = conn.execute(
        "SELECT count(*) AS n FROM items WHERE resolve_status != 'ok'"
    ).fetchone()["n"]
    print(f"\nlibrary total        : {db.count(conn)}")
    print(f"awaiting resolution  : {pending}")
    print("\nNext: python -m favorites.backfill --limit 100")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
