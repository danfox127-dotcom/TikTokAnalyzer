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
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
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


#: What TikTok calls the file inside its export: user_data_tiktok.json, or
#: user_data.json in older ones.
EXPORT_FILE = re.compile(r"user_data(?:_tiktok)?\.json$", re.I)


def _export_text(path: str | Path) -> str:
    """The export's JSON, from the file itself, the folder it is in, or the .zip."""
    p = Path(path).expanduser()
    if p.is_file() and p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            for name in z.namelist():
                if EXPORT_FILE.search(PurePosixPath(name).name):
                    return z.read(name).decode("utf-8")
        raise FileNotFoundError(f"no user_data_tiktok.json in {p}")
    if p.is_dir():
        for f in sorted(p.rglob("*.json")):
            if EXPORT_FILE.search(f.name):
                return f.read_text(encoding="utf-8")
        raise FileNotFoundError(f"no user_data_tiktok.json in {p}")
    return p.read_text(encoding="utf-8")


def _data(source: str | Path | dict) -> dict:
    """The export's JSON: given already read, or read from ``source``."""
    return source if isinstance(source, dict) else json.loads(_export_text(source))


def read_export(path: str | Path | dict) -> dict[str, list[dict]]:
    """Return ``{"favorites": [...], "likes": [...]}`` of ``{date, link}`` rows.

    ``path`` is user_data_tiktok.json, the folder it came in, or the .zip
    (or the JSON, already read).
    """
    data = _data(path)

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


#: Where each list of activity has lived in the exports TikTok has shipped.
ACTIVITY_PATHS = {
    "watch": [("Your Activity", "Video Browsing History", "VideoList"),
              ("Activity", "Video Browsing History", "VideoList"),
              ("Your Activity", "Watch History", "VideoList")],
    "like": [("Likes and Favorites", "Like List", "ItemFavoriteList"),
             ("Your Activity", "Like List", "ItemFavoriteList"),
             ("Activity", "Like List", "ItemFavoriteList")],
    "search": [("Your Activity", "Searches", "SearchList"),
               ("Activity", "Searches", "SearchList"),
               ("Your Activity", "Search", "SearchList")],
}


def read_activity(path: str | Path | dict) -> dict[str, list[tuple[str, str]]]:
    """What you did, for Rewind: ``{"watch": [(at, video id)], "like": [...],
    "search": [(at, words)]}``, every time in ISO-8601 UTC.

    Rows without a usable date, video id or search words are left out.
    """
    data = _data(path)
    out: dict[str, list[tuple[str, str]]] = {}
    for kind, paths in ACTIVITY_PATHS.items():
        rows = []
        for row in _first_list(data, paths):
            if not isinstance(row, dict):
                continue
            at = parse_date(row.get("Date") or row.get("date") or "")
            if kind == "search":
                ref = str(row.get("SearchTerm") or row.get("searchTerm") or row.get("Content") or "").strip()
            else:
                m = VIDEO_ID.search(row.get("Link") or row.get("link") or row.get("VideoLink") or "")
                ref = m.group(1) if m else ""
            if at and ref:
                rows.append((at, ref[:300]))
        out[kind] = rows
    return out


def import_activity(conn: sqlite3.Connection, activity: dict[str, list[tuple[str, str]]]) -> dict[str, int]:
    """Keep the activity; returns how many of each kind were new. An export
    overlapping an earlier one adds only what the earlier one didn't have."""
    added = {}
    for kind, rows in activity.items():
        before = conn.execute("SELECT count(*) FROM activity WHERE platform = 'tiktok' AND kind = ?",
                              (kind,)).fetchone()[0]
        conn.executemany(
            "INSERT INTO activity (platform, kind, at, ref) VALUES ('tiktok', ?, ?, ?) ON CONFLICT DO NOTHING",
            [(kind, at, ref) for at, ref in rows])
        conn.commit()
        added[kind] = conn.execute("SELECT count(*) FROM activity WHERE platform = 'tiktok' AND kind = ?",
                                   (kind,)).fetchone()[0] - before
    return added


# --- what the export says TikTok keeps about you ("What TikTok knows") -------
#
# Only a summary is kept: how many of each kind, how far back, which devices
# and companies -- never a message, a comment, an IP address or a contact
# detail itself.

#: Profile fields, in the page's words. Only *whether* each is on file is
#: kept, except the two in SHOWN.
PROFILE_FIELDS = {
    "userName": "username", "displayName": "display name", "nickName": "display name",
    "birthDate": "birth date", "emailAddress": "email address", "email": "email address",
    "telephoneNumber": "phone number", "phoneNumber": "phone number",
    "bioDescription": "bio", "profilePhoto": "profile photo", "profileVideo": "profile video",
    "accountRegion": "region", "inferredGender": "a guess at your gender", "gender": "gender",
}
SHOWN = {"userName": "username", "accountRegion": "region"}

#: Each kind of record, in the page's words, and where it has lived.
RECORDS = {
    "Videos you opened": ACTIVITY_PATHS["watch"],
    "Likes": ACTIVITY_PATHS["like"],
    "Favourites": [("Likes and Favorites", "Favorite Videos", "FavoriteVideoList"),
                   ("Your Activity", "Favorite Videos", "FavoriteVideoList"),
                   ("Activity", "Favorite Videos", "FavoriteVideoList")],
    "Searches": ACTIVITY_PATHS["search"],
    "Shares": [("Your Activity", "Share History", "ShareHistoryList"),
               ("Activity", "Share History", "ShareHistoryList")],
    "Comments": [("Comment", "Comments", "CommentsList"), ("Comments", "Comments", "CommentsList")],
    "Accounts you follow": [("Profile And Settings", "Following", "Following"),
                            ("Your Activity", "Following List", "Following"),
                            ("Profile And Settings", "Following List", "Following")],
    "Followers": [("Profile And Settings", "Follower", "FansList"),
                  ("Your Activity", "Follower List", "FansList"),
                  ("Profile And Settings", "Follower List", "FansList")],
    "Accounts you blocked": [("Profile And Settings", "Block List", "BlockList"),
                             ("Your Activity", "Block List", "BlockList"),
                             ("Activity", "Block List", "BlockList")],
    "Logins": [("Your Activity", "Login History", "LoginHistoryList"),
               ("Activity", "Login History", "LoginHistoryList")],
    "Activity from other apps and websites": [
        ("Your Activity", "Off TikTok Activity", "OffTikTokActivityDataList"),
        ("Profile And Settings", "Off TikTok Activity", "OffTikTokActivityDataList"),
        ("Activity", "Off TikTok Activity", "OffTikTokActivityDataList")],
    "Shop orders": [("TikTok Shop", "Order", "OrderList"), ("TikTok Shop", "Orders", "OrderList")],
    "Products you looked at in the Shop": [("TikTok Shop", "Product Browsing History", "ProductBrowsingHistories")],
}
_WHEN_FORMATS = (EXPORT_DATE, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d")
_DATE_KEYS = ("Date", "date", "TimeStamp", "Timestamp", "timestamp", "CreateTime", "browsing_date", "BrowsingDate")


def _first(data: dict, paths: Iterable[tuple[str, ...]]):
    """The first of ``paths`` that holds anything."""
    for path in paths:
        found = _dig(data, *path)
        if found:
            return found
    return None


def _when(raw) -> Optional[str]:
    """A date in any of the shapes the export uses, as ISO-8601 UTC."""
    raw = str(raw or "").strip()
    for fmt in _WHEN_FORMATS:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def _pick(row: dict, keys: Iterable[str]) -> str:
    for key in keys:
        if str(row.get(key) or "").strip():
            return str(row[key]).strip()
    return ""


def _span(rows: list) -> tuple[Optional[str], Optional[str]]:
    dates = sorted(d for d in (_when(_pick(r, _DATE_KEYS)) for r in rows if isinstance(r, dict)) if d)
    return (dates[0], dates[-1]) if dates else (None, None)


def _top(counter: Counter, n: int = 12) -> list[list]:
    return [[k, v] for k, v in counter.most_common(n) if k]


def _messages(data: dict) -> tuple[int, int, list]:
    """Conversations and messages, counted -- and the messages' dates, for
    how far back they go. Never their words."""
    chats = _first(data, [("Direct Message", "Direct Messages", "ChatHistory"),
                          ("Direct Messages", "Direct Messages", "ChatHistory")]) or {}
    threads = list(chats.values()) if isinstance(chats, dict) else chats if isinstance(chats, list) else []
    conversations, rows = 0, []
    for chat in threads:
        msgs = chat if isinstance(chat, list) else (chat.get("Messages") or chat.get("messages") or []) \
            if isinstance(chat, dict) else []
        if isinstance(msgs, list) and msgs:
            conversations += 1
            rows += [{"Date": m.get("Date") or m.get("date")} for m in msgs if isinstance(m, dict)]
    return conversations, len(rows), rows


def read_dossier(path: str | Path | dict) -> dict:
    """A summary of what the export says TikTok keeps about you.

    Counts, spans and names of devices and companies; never message or
    comment text, IP addresses, or contact details (only that they're on file).
    """
    data = _data(path)
    profile = _first(data, [("Profile And Settings", "Profile Info", "ProfileMap"),
                            ("Profile And Settings", "ProfileMap"),
                            ("Profile", "Profile Information", "ProfileMap")]) or {}
    profile = profile if isinstance(profile, dict) else {}
    held = sorted({label for key, label in PROFILE_FIELDS.items() if str(profile.get(key) or "").strip()})
    shown = {label: str(profile[key]).strip()[:80] for key, label in SHOWN.items()
             if str(profile.get(key) or "").strip()}

    raw_ads = _first(data, [("Your Activity", "Ad Interests", "AdInterestCategories"),
                            ("Ad Interests", "AdInterestCategories")])
    if isinstance(raw_ads, str):
        raw_ads = raw_ads.split(",")
    ads = list(dict.fromkeys(str(a).strip() for a in (raw_ads or []) if str(a).strip()))
    settings = _first(data, [("Profile And Settings", "Settings", "SettingsMap"),
                             ("Profile And Settings", "SettingsMap")]) or {}
    picked = str((settings.get("Interests") if isinstance(settings, dict) else "") or "")
    declared = [i.strip() for i in picked.split("|") if i.strip()]

    logins = [r for r in _first_list(data, RECORDS["Logins"]) if isinstance(r, dict)]
    devices: Counter[str] = Counter()
    networks: Counter[str] = Counter()
    carriers: Counter[str] = Counter()
    addresses: set[str] = set()
    for r in logins:
        device = " · ".join(p for p in (_pick(r, ("DeviceModel", "deviceModel")),
                                        _pick(r, ("DeviceSystem", "deviceSystem"))) if p)
        devices[device] += 1
        networks[_pick(r, ("NetworkType", "networkType"))] += 1
        carriers[_pick(r, ("Carrier", "carrier"))] += 1
        ip = _pick(r, ("IP", "ip"))
        if ip:
            addresses.add(ip)          # counted here, and only the count is kept
    first_login, last_login = _span(logins)

    off = [r for r in _first_list(data, RECORDS["Activity from other apps and websites"]) if isinstance(r, dict)]
    sources: Counter[str] = Counter(_pick(r, ("Source", "SourceName", "source", "App", "Website")) for r in off)
    events: Counter[str] = Counter(_pick(r, ("Event", "EventType", "event", "event_type")) for r in off)
    off_first, off_last = _span(off)

    records, newest = [], []
    for kind, paths in RECORDS.items():
        rows = _first_list(data, paths)
        if not rows:
            continue
        first, last = _span(rows)
        records.append({"kind": kind, "count": len(rows), "since": first})
        newest.append(last)
    conversations, messages, message_rows = _messages(data)
    if messages:
        first, last = _span(message_rows)
        records.append({"kind": "Messages", "count": messages, "since": first})
        newest.append(last)
    return {
        "latest": max((d for d in newest if d), default=None),
        "profile": {"held": held, **shown},
        "ad_interests": ads, "declared_interests": declared,
        "logins": {"count": len(logins), "first": first_login, "last": last_login,
                   "devices": _top(devices), "networks": _top(networks), "carriers": _top(carriers),
                   "addresses": len(addresses)},
        "off_tiktok": {"count": len(off), "first": off_first, "last": off_last,
                       "sources": _top(sources), "source_count": len([s for s in sources if s]),
                       "events": _top(events)},
        "messages": {"conversations": conversations, "messages": messages},
        "records": records,
    }


def store_dossier(conn: sqlite3.Connection, dossier: dict) -> Optional[str]:
    """Keep an export's summary, once per export (by its newest record).
    Returns that date, or None when the export held nothing to summarise."""
    made_at = dossier.get("latest")
    if not made_at:
        return None
    conn.execute(
        "INSERT INTO dossiers (platform, made_at, read_at, data) VALUES ('tiktok', ?, ?, ?)"
        " ON CONFLICT (platform, made_at) DO UPDATE SET read_at = excluded.read_at, data = excluded.data",
        (made_at, db.now_iso(), json.dumps(dossier)))
    conn.commit()
    return made_at


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
    data = _data(path)
    lists = read_export(data)
    result = {
        "favorites_in_export": len(lists["favorites"]),
        "likes_in_export": len(lists["likes"]),
        "favorites": import_rows(conn, lists["favorites"], "export"),
        "likes": None,
    }
    if include_likes:
        result["likes"] = import_rows(conn, lists["likes"], "export-like")
    result["activity"] = import_activity(conn, read_activity(data))
    result["dossier"] = store_dossier(conn, read_dossier(data))
    return result


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("export", help="user_data_tiktok.json, its folder, or the .zip")
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
