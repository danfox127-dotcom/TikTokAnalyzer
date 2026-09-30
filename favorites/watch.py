"""The watched folder: exports import themselves.

Requesting a data export is the one step a platform won't let anyone skip.
Everything after it can be automatic: point the museum at the folder your
downloads land in (``FAVORITES_WATCH``, ~/Downloads by default when you start
it with start.command), and a TikTok, Instagram or Google Takeout export is
imported the moment it arrives -- then the museum starts filling in titles and
pictures for what is new.

What it looks at, at the top level of each watched folder:

- ``.zip`` files, and unzipped folders whose names say what they are
  (``Takeout``, ``instagram-…``, ``TikTok…``, ``user_data…``);
- ``user_data_tiktok.json`` and ``saved_posts.json`` on their own.

Only favourites and saves come in: likes and Liked videos stay out, as they do
from the command line. Each file is imported once (it is remembered by name,
size and date, in the ``imports`` table); **files are never moved, changed or
deleted**. A file still being written -- changed in the last 30 seconds -- is
left for the next look.

Run it by hand with ``python -m favorites.watch ~/Downloads --once``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional

from . import db
from .importers import instagram_export, tiktok_export, youtube_takeout

logger = logging.getLogger(__name__)

#: How recently a file may have changed and still be "being downloaded".
SETTLE_SECONDS = 30

#: Unzipped folders are only looked inside when their name says what they
#: are: walking every folder in Downloads each minute would be slow and rude.
_FOLDER_NAMES = re.compile(r"takeout|instagram|tiktok|user_data|meta-", re.I)

PLATFORM_OF = {"tiktok": "tiktok", "instagram": "instagram", "takeout": "youtube"}
LABEL = {"tiktok": "TikTok export", "instagram": "Instagram export", "takeout": "Google Takeout"}


def folders_from_env() -> list[Path]:
    """The folders in FAVORITES_WATCH (several separated by ":"), that exist."""
    raw = os.environ.get("FAVORITES_WATCH", "")
    out = []
    for part in raw.split(os.pathsep):
        part = part.strip()
        if part:
            p = Path(part).expanduser()
            if p.is_dir():
                out.append(p)
    return out


def _names_in(path: Path) -> list[str]:
    """The file names (not paths) an export holds, zipped or unzipped."""
    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            return z.namelist()
    if path.is_dir():
        return [f.relative_to(path).as_posix() for f in path.rglob("*") if f.is_file()]
    return [path.name]


def detect(path: Path) -> Optional[str]:
    """``tiktok``, ``instagram``, ``takeout`` -- or None for anything else."""
    name = path.name
    if path.is_file() and path.suffix.lower() == ".json":
        if tiktok_export.EXPORT_FILE.search(name):
            return "tiktok"
        if name == instagram_export.SAVED_FILE:
            return "instagram"
        return None
    if path.is_dir() and not _FOLDER_NAMES.search(name):
        return None
    if not (path.is_dir() or (path.is_file() and path.suffix.lower() == ".zip")):
        return None
    names = _names_in(path)
    bases = {PurePosixPath(n).name for n in names}
    if any(tiktok_export.EXPORT_FILE.search(b) for b in bases):
        return "tiktok"
    if instagram_export.SAVED_FILE in bases:
        return "instagram"
    if any(n.lower().endswith(".csv") and youtube_takeout._in_playlists_folder(n) for n in names):
        return "takeout"
    return None


def fingerprint(path: Path) -> str:
    """Name, size and date: enough to know a file was seen, without reading
    a multi-gigabyte Takeout through a hash every minute."""
    st = path.stat()
    size = st.st_size if path.is_file() else sum(
        f.stat().st_size for f in path.rglob("*") if f.is_file())
    return hashlib.sha1(f"{path.name}|{size}|{int(st.st_mtime)}".encode()).hexdigest()


def settled(path: Path, now: Optional[float] = None) -> bool:
    now = time.time() if now is None else now
    newest = path.stat().st_mtime
    if path.is_dir():
        newest = max([newest] + [f.stat().st_mtime for f in path.rglob("*")])
    return now - newest >= SETTLE_SECONDS


def import_one(conn: sqlite3.Connection, path: Path, kind: str) -> dict:
    """Run the importer for one export. Returns ``{"added": n, ...}``."""
    if kind == "tiktok":
        r = tiktok_export.import_export(conn, path)
        return {"added": r["favorites"]["imported"],
                "already": r["favorites"]["skipped_existing"],
                "in_export": r["favorites_in_export"]}
    if kind == "instagram":
        posts = instagram_export.read_saved(path)
        collections = instagram_export.read_collections(path)
        r = instagram_export.import_saved(conn, posts)
        instagram_export.import_collections(
            conn, collections, {p["url"]: p["saved_at"] for p in posts})
        return {"added": r["imported"], "already": r["already_present"], "in_export": len(posts)}
    if kind == "takeout":
        chosen = youtube_takeout._selected(youtube_takeout.read_takeout(path), include_likes=False)
        r = youtube_takeout.import_playlists(conn, chosen)
        return {"added": r["imported"], "already": r["already_present"],
                "in_export": sum(len(p.entries) for p in chosen)}
    raise ValueError(kind)


@dataclass
class Found:
    path: str
    kind: str
    added: int = 0
    already: int = 0
    error: Optional[str] = None


@dataclass
class Status:
    """What the watcher last did, for the Keep it in sync page."""
    folders: list[str] = field(default_factory=list)
    last_scan: Optional[str] = None
    found: list[Found] = field(default_factory=list)


STATUS = Status()


def scan(conn: sqlite3.Connection, folders: Iterable[Path], now: Optional[float] = None) -> list[Found]:
    """Import every new, settled export in ``folders``. Returns what it found."""
    found: list[Found] = []
    for folder in folders:
        try:
            entries = sorted(folder.iterdir())
        except OSError as exc:
            logger.warning("can't look in %s: %s", folder, exc)
            continue
        for path in entries:
            if path.name.startswith("."):
                continue
            try:
                kind = detect(path)
                if kind is None:
                    continue
                key = fingerprint(path)
                if conn.execute("SELECT 1 FROM imports WHERE key = ?", (key,)).fetchone():
                    continue
                if not settled(path, now):
                    continue
            except (OSError, zipfile.BadZipFile):
                continue  # still downloading, or unreadable for now: try again later
            item = Found(str(path), kind)
            try:
                r = import_one(conn, path, kind)
                item.added, item.already = r["added"], r["already"]
            except (ValueError, KeyError, json.JSONDecodeError, FileNotFoundError) as exc:
                # Not the export it looked like: remember it, so it is not retried every minute.
                item.error = str(exc)[:200]
            conn.execute(
                "INSERT OR REPLACE INTO imports (key, filename, platform, imported_at, added, detail)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (key, path.name, PLATFORM_OF[kind], db.now_iso(), item.added,
                 json.dumps({"already": item.already, "error": item.error})))
            conn.commit()
            logger.info("imported %s from %s: %s new", LABEL[kind], path.name, item.added)
            found.append(item)
    return found


def last_imports(conn: sqlite3.Connection) -> dict[str, dict]:
    """platform -> {"at": iso, "via": "..."} for the latest import of each.

    Counts the watched folder's imports and the command-line importers
    (whose saves carry ``imported_at``), whichever is newer.
    """
    out: dict[str, dict] = {}
    for platform, where in (("tiktok", "source IN ('export', 'export-like')"),
                            ("instagram", "source LIKE 'instagram%'"),
                            ("youtube", "source LIKE 'youtube%'")):
        row = conn.execute(f"SELECT max(imported_at) AS at FROM items WHERE {where}").fetchone()
        if row and row["at"]:
            out[platform] = {"at": row["at"], "via": "an import"}
    for row in conn.execute("SELECT platform, max(imported_at) AS at, filename FROM imports"
                            " GROUP BY platform"):
        if row["at"] and (row["platform"] not in out or row["at"] > out[row["platform"]]["at"]):
            out[row["platform"]] = {"at": row["at"], "via": row["filename"]}
    return out


#: A platform's export is "due" this long after its last import.
DUE_DAYS = 60
SNOOZE_DAYS = 30
NAMES = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube"}


def _days_since(iso: str, now: datetime) -> int:
    then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return max(0, (now - then).days)


def reminders(conn: sqlite3.Connection, now: Optional[datetime] = None) -> list[dict]:
    """Platforms whose last export is more than DUE_DAYS old, not snoozed.

    Only platforms you have imported from before: nobody is nagged about a
    platform they don't use.
    """
    now = now or datetime.now(timezone.utc)
    out = []
    for platform, last in last_imports(conn).items():
        days = _days_since(last["at"], now)
        if days <= DUE_DAYS:
            continue
        until = db.get_meta(conn, f"snooze_{platform}")
        if until and until > now.isoformat():
            continue
        out.append({"platform": platform, "name": NAMES[platform], "days": days})
    return out


def snooze(conn: sqlite3.Connection, platform: str, now: Optional[datetime] = None) -> None:
    if platform in NAMES:
        now = now or datetime.now(timezone.utc)
        db.set_meta(conn, f"snooze_{platform}", (now + timedelta(days=SNOOZE_DAYS)).isoformat())


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Import any exports waiting in a folder.")
    ap.add_argument("folders", nargs="*", help="folders to look in (default: $FAVORITES_WATCH)")
    ap.add_argument("--once", action="store_true", help="look once and stop (the default)")
    ap.add_argument("--db", help="library path (default: $FAVORITES_DB)")
    args = ap.parse_args(argv)
    folders = [Path(f).expanduser() for f in args.folders] or folders_from_env()
    if not folders:
        print("Which folder? e.g.  python -m favorites.watch ~/Downloads")
        return 1
    conn, where = db.connect_announced(args.db)
    print(where)
    try:
        found = scan(conn, folders)
    finally:
        conn.close()
    if not found:
        print("No new exports in " + ", ".join(str(f) for f in folders) + ".")
    for f in found:
        what = f"error: {f.error}" if f.error else f"{f.added} new, {f.already} already here"
        print(f"  {LABEL[f.kind]:<17} {Path(f.path).name}: {what}")
    if any(f.added for f in found):
        print("\nTitles and pictures fill in with:  python -m favorites.backfill --all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
