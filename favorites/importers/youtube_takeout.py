"""Backfill your YouTube saves from a Google Takeout export.

YouTube's save button puts a video in **Watch later** or in a playlist you
choose -- the same "just save, or file it under something" choice TikTok's
favourites offer. Takeout exports each playlist as a CSV of video ids and the
date each was added, so an import produces what the TikTok one does: dated ids
that :mod:`favorites.backfill` resolves afterwards.

How playlists map onto the library:

- **Watch later** is "just saved". Its items come in with no category.
- **Every other playlist you made is a category**, and becomes a collection of
  the same name. That is your own filing, and the museum uses it as a shelf.
- **Liked videos** are a tap, not a keep -- the same line drawn for TikTok's
  like list. Opt in with ``--include-likes``; they arrive tagged
  ``source='youtube-takeout-like'`` so they can be told apart later.

Takeout has shipped two CSV layouts over the years -- a metadata block followed
by ``Video Id,Time Added``, and the newer ``Video ID,Playlist Video Creation
Timestamp`` -- and this reads either. Only files inside a ``playlists`` folder
are read: newer exports also carry ``comments.csv``, which has a ``Video ID``
column too, and would otherwise file every video you ever commented on under a
category called "comments".

Run ``--list`` first. It reads the export, imports nothing, and shows every
playlist with its size, which is the cheapest way to find out whether your
export looks the way this module expects.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sqlite3
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator, Optional

from .. import db
from ..resolve import canonical_form

# Every YouTube video id is exactly eleven of these.
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")

# Matched against both a playlist's id and its name, lower-cased. Names are
# the English ones; the ids are what identify them in any language.
WATCH_LATER = {"wl", "watch later"}
LIKES = {"ll", "lm", "liked videos", "liked music"}

SOURCE = "youtube-takeout"
SOURCE_LIKE = "youtube-takeout-like"


@dataclass
class Playlist:
    name: str
    playlist_id: Optional[str] = None
    entries: list[tuple[str, Optional[str]]] = field(default_factory=list)
    unusable: int = 0

    @property
    def kind(self) -> str:
        """``watch-later``, ``likes`` or ``category``."""
        keys = {self.name.strip().lower(), (self.playlist_id or "").strip().lower()}
        if keys & WATCH_LATER:
            return "watch-later"
        if keys & LIKES:
            return "likes"
        return "category"


def _norm(cell: str) -> str:
    return re.sub(r"\s+", " ", (cell or "").strip().lower())


def parse_timestamp(raw: Optional[str]) -> Optional[str]:
    """A Takeout timestamp -> the ISO-8601 UTC string the library sorts on.

    Seen in the wild: ``2019-01-02 03:04:05 UTC`` and
    ``2024-01-02T03:04:05+00:00``, with or without fractional seconds. Written
    not to lean on Python 3.11's more forgiving ``fromisoformat``.
    """
    text = (raw or "").strip()
    if not text:
        return None
    text = re.sub(r"\s*UTC$", "+00:00", text)
    text = re.sub(r"Z$", "+00:00", text)
    text = re.sub(r"(\d{2}:\d{2}:\d{2})\.\d+", r"\1", text)  # drop fractions
    parsed = None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _name_from_filename(filename: str) -> str:
    stem = PurePosixPath(filename).stem
    return re.sub(r"-videos$", "", stem).strip() or stem


def parse_playlist_csv(text: str, filename: str) -> Optional[Playlist]:
    """One playlist file -> a :class:`Playlist`, or None if it is not one.

    Rather than trusting a fixed layout, this looks for the row that names a
    ``Video ID`` column and reads from there. That covers both layouts, and
    ``playlists.csv`` -- the index of playlists, which has no such column --
    comes back as None and is skipped.
    """
    meta_header: Optional[list[str]] = None
    meta: dict[str, str] = {}
    vid_col: Optional[int] = None
    time_col: Optional[int] = None
    entries: list[tuple[str, Optional[str]]] = []
    unusable = 0

    for row in csv.reader(io.StringIO(text.lstrip("﻿"))):
        cells = [c.strip() for c in row]
        if not any(cells):
            continue
        norm = [_norm(c) for c in cells]

        if vid_col is None:
            if "video id" in norm:
                vid_col = norm.index("video id")
                time_col = next(
                    (j for j, n in enumerate(norm) if j != vid_col
                     and any(w in n for w in ("time", "added", "created", "date"))),
                    None,
                )
            elif "playlist id" in norm and meta_header is None:
                meta_header = norm
            elif meta_header is not None and not meta:
                meta = dict(zip(meta_header, cells))
            continue

        video_id = cells[vid_col] if vid_col < len(cells) else ""
        if not VIDEO_ID.fullmatch(video_id):
            unusable += 1
            continue
        stamp = cells[time_col] if time_col is not None and time_col < len(cells) else ""
        entries.append((video_id, parse_timestamp(stamp)))

    if vid_col is None:
        return None
    return Playlist(
        name=(meta.get("title") or _name_from_filename(filename)).strip(),
        playlist_id=meta.get("playlist id") or None,
        entries=entries,
        unusable=unusable,
    )


def _in_playlists_folder(path: str) -> bool:
    return "playlists" in (part.lower() for part in PurePosixPath(path).parts[:-1])


def iter_playlist_files(path: str | Path) -> Iterator[tuple[str, str]]:
    """Yield ``(filename, text)`` for each playlist CSV in a Takeout.

    Accepts the downloaded ``.zip``, the unzipped folder at any level, or a
    single CSV. A single file is taken on trust -- you pointed at it.
    """
    p = Path(path).expanduser()
    if p.is_file() and p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            for info in z.infolist():
                if info.filename.lower().endswith(".csv") and _in_playlists_folder(info.filename):
                    yield info.filename, z.read(info).decode("utf-8-sig", errors="replace")
    elif p.is_file():
        yield p.name, p.read_text(encoding="utf-8-sig", errors="replace")
    elif p.is_dir():
        inside = p.name.lower() == "playlists"
        for f in sorted(p.rglob("*.csv")):
            rel = f.relative_to(p).as_posix()
            if inside or _in_playlists_folder(rel):
                yield rel, f.read_text(encoding="utf-8-sig", errors="replace")
    else:
        raise FileNotFoundError(f"no Takeout at {p}")


def read_takeout(path: str | Path) -> list[Playlist]:
    playlists = []
    for filename, text in iter_playlist_files(path):
        parsed = parse_playlist_csv(text, filename)
        if parsed is not None:
            playlists.append(parsed)
    return playlists


def _selected(playlists: Iterable[Playlist], include_likes: bool,
              only: Iterable[str] = (), skip: Iterable[str] = ()) -> list[Playlist]:
    only_set = {_norm(n) for n in only}
    skip_set = {_norm(n) for n in skip}
    chosen = []
    for pl in playlists:
        name = _norm(pl.name)
        if only_set and name not in only_set:
            continue
        if name in skip_set:
            continue
        if pl.kind == "likes" and not include_likes:
            continue
        chosen.append(pl)
    return chosen


def plan(playlists: Iterable[Playlist]) -> dict[str, dict]:
    """Fold playlists into one entry per video.

    A video in Watch later and in "Recipes" is one item filed under "Recipes".
    Its save date is the earliest *keep* -- a like is not a keep, so a like's
    date counts only for a video that was never saved anywhere else.
    """
    videos: dict[str, dict] = {}
    for pl in playlists:
        for video_id, stamp in pl.entries:
            entry = videos.setdefault(video_id, {
                "kept": [], "liked": [], "collections": {},
            })
            (entry["liked"] if pl.kind == "likes" else entry["kept"]).append(stamp)
            if pl.kind == "category":
                prior = entry["collections"].get(pl.name)
                if stamp and (prior is None or stamp < prior):
                    entry["collections"][pl.name] = stamp
                else:
                    entry["collections"].setdefault(pl.name, prior)

    for entry in videos.values():
        kept = [s for s in entry["kept"] if s]
        liked = [s for s in entry["liked"] if s]
        entry["saved_at"] = min(kept) if kept else (min(liked) if liked else None)
        entry["source"] = SOURCE if entry["kept"] else SOURCE_LIKE
    return videos


def import_playlists(conn: sqlite3.Connection, playlists: Iterable[Playlist]) -> dict[str, int]:
    """Insert unresolved items and file them into their collections.

    An item already in the library is never overwritten -- it may carry a title
    from the share sheet and a note only you could have written. It is still
    filed into its playlists, because that adds your categories without
    touching anything you wrote.
    """
    imported_at = db.now_iso()
    stats = {"imported": 0, "already_present": 0, "undated": 0, "filings": 0}

    for video_id, entry in plan(playlists).items():
        if not entry["saved_at"]:
            stats["undated"] += 1
            continue
        link = f"https://www.youtube.com/watch?v={video_id}"
        canonical, external_id = canonical_form(link, "youtube")

        row = conn.execute(
            "SELECT id FROM items WHERE canonical_url = ?", (canonical,)).fetchone()
        if row:
            item_id = int(row["id"])
            stats["already_present"] += 1
        else:
            item_id, _ = db.upsert_item(conn, {
                "canonical_url": canonical,
                "shared_url": link,
                "platform": "youtube",
                "external_id": external_id,
                "saved_at": entry["saved_at"],
                "source": entry["source"],
                "imported_at": imported_at,
                "resolve_status": "pending",
            })
            stats["imported"] += 1

        for name, stamp in entry["collections"].items():
            db.file_under(conn, item_id, name, stamp)
            stats["filings"] += 1

    return stats


KIND_LABEL = {"watch-later": "just saved", "category": "category", "likes": "likes"}


def _print_listing(playlists: list[Playlist], chosen: list[Playlist]) -> None:
    chosen_ids = {id(p) for p in chosen}
    width = max((len(p.name) for p in playlists), default=10)
    width = min(max(width, 10), 40)
    print(f"playlists in export: {len(playlists)}")
    order = {"watch-later": 0, "category": 1, "likes": 2}
    for pl in sorted(playlists, key=lambda p: (order[p.kind], -len(p.entries))):
        note = ""
        if id(pl) not in chosen_ids:
            note = "  — not imported" + (" (--include-likes to add)" if pl.kind == "likes" else "")
        extra = f"  ({pl.unusable} unreadable rows)" if pl.unusable else ""
        print(f"  {pl.name[:width]:<{width}}  {len(pl.entries):>6}  "
              f"{KIND_LABEL[pl.kind]}{note}{extra}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("takeout", help="the Takeout .zip, its unzipped folder, or one playlist CSV")
    ap.add_argument("--list", action="store_true",
                    help="show the playlists found and import nothing")
    ap.add_argument("--include-likes", action="store_true",
                    help="also import Liked videos (a tap, not a keep)")
    ap.add_argument("--only", action="append", default=[], metavar="NAME",
                    help="import just this playlist (repeatable)")
    ap.add_argument("--skip", action="append", default=[], metavar="NAME",
                    help="leave this playlist out (repeatable)")
    ap.add_argument("--db", help="library path (default: $FAVORITES_DB)")
    args = ap.parse_args(argv)

    try:
        playlists = read_takeout(args.takeout)
    except FileNotFoundError:
        print(f"Nothing at {args.takeout}.")
        print("If it is still unzipping, wait for that to finish. To see what is there:")
        print("  ls -d ~/Downloads/*akeout*")
        return 1
    except zipfile.BadZipFile:
        print(f"{args.takeout} is not a complete zip -- it may still be downloading.")
        return 1

    if not playlists:
        print("No playlists in there.")
        print("Google often splits an export across several downloads, and a Mac unzips")
        print("the second one as 'Takeout 2'. Look for it with:")
        print("  ls -d ~/Downloads/*akeout*")
        print("and point this at whichever folder has 'YouTube and YouTube Music' inside.")
        return 1

    chosen = _selected(playlists, args.include_likes, args.only, args.skip)
    _print_listing(playlists, chosen)
    if args.list:
        return 0

    conn, where = db.connect_announced(args.db)
    print(f"\n{where}")
    try:
        stats = import_playlists(conn, chosen)
        pending = conn.execute(
            "SELECT count(*) AS n FROM items WHERE resolve_status != 'ok'").fetchone()["n"]
        total = db.count(conn)
    finally:
        conn.close()

    print(f"\nvideos imported      : {stats['imported']}")
    print(f"already in library   : {stats['already_present']}")
    print(f"filed into categories: {stats['filings']}")
    if stats["undated"]:
        print(f"skipped, no date     : {stats['undated']}")
    print(f"\nlibrary total        : {total}")
    print(f"awaiting resolution  : {pending}")
    print("\nNext: python -m favorites.backfill --limit 100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
