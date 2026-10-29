"""The phone's inbox: a safety net for links shared while Faves was away.

The "Save to Faves" shortcut writes every link to a small text file in
iCloud Drive *before* it sends the link to Faves. Writing to the file works
with no connection at all, and iCloud carries it to the Mac later. Faves reads
that file every minute and saves whatever never arrived -- with the date it
was really shared, not the date the Mac caught up.

One line per share, made by the shortcut:

    2026-10-22T13:48:00-04:00 <tab> https://www.tiktok.com/t/ZT... <tab> optional note

Only the link is required; a line with no date gets the time Faves first saw
it. Lines are remembered by a hash (the ``inbox_seen`` table), so editing or
clearing the file never re-saves anything, and links that did reach Faves
directly are skipped without being looked up again.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import db
from .resolve import extract_url

#: Where the shortcut's "Append to Text File" lands on the Mac: the Shortcuts
#: folder of iCloud Drive.
DEFAULT_INBOX = (Path.home() / "Library" / "Mobile Documents"
                 / "iCloud~is~workflow~my~workflows" / "Documents" / "Faves inbox.txt")

_DATE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)\s*")


def path() -> Path:
    raw = os.environ.get("FAVORITES_INBOX", "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_INBOX


@dataclass
class Line:
    raw: str
    link: str
    saved_at: Optional[str]
    note: Optional[str]

    @property
    def key(self) -> str:
        return hashlib.sha1(self.raw.strip().encode("utf-8")).hexdigest()


@dataclass
class Status:
    """What the inbox reader last did, for the Keep it in sync page."""
    path: str = ""
    found: bool = False
    last_read: Optional[str] = None
    rescued: int = 0
    recent: list = field(default_factory=list)


STATUS = Status()


def _iso(text: str) -> Optional[str]:
    """An ISO date from the shortcut, as UTC ISO -- or None if it isn't one."""
    try:
        when = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.astimezone()  # the Mac's own time zone
    return when.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse(raw: str) -> Optional[Line]:
    """One inbox line, or None when it holds no link."""
    text = raw.strip()
    if not text:
        return None
    saved_at = None
    m = _DATE.match(text)
    if m:
        saved_at = _iso(m.group(1))
        if saved_at:
            text = text[m.end():]
    parts = [p.strip() for p in text.split("\t")]
    link_part = next((p for p in parts if extract_url(p)), None)
    if not link_part:
        return None
    link = extract_url(link_part)
    rest = [p for p in parts if p and p is not link_part]
    return Line(raw=raw, link=link, saved_at=saved_at, note=" ".join(rest) or None)


def _placeholder(p: Path) -> Path:
    """iCloud's stand-in for a file it has moved off this Mac to save space."""
    return p.with_name(f".{p.name}.icloud")


def read(p: Optional[Path] = None) -> Optional[str]:
    """The inbox's text, or None while it isn't on this Mac (yet)."""
    p = p or path()
    STATUS.path = str(p)
    if p.is_file():
        STATUS.found = True
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    if _placeholder(p).exists():
        # Ask iCloud to bring it back; the next look will find it.
        try:
            subprocess.run(["brctl", "download", str(p)], timeout=10,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            pass
    STATUS.found = _placeholder(p).exists()
    return None


def pending(conn: sqlite3.Connection, text: str) -> list[Line]:
    """Lines not dealt with yet, oldest first."""
    out, keys = [], set()
    for raw in text.splitlines():
        line = parse(raw)
        if line is None or line.key in keys:
            continue
        keys.add(line.key)
        if not conn.execute("SELECT 1 FROM inbox_seen WHERE line_hash = ?", (line.key,)).fetchone():
            out.append(line)
    return out


def already_saved(conn: sqlite3.Connection, link: str) -> bool:
    """Did this link reach Faves directly (or arrive some other way)?"""
    return conn.execute(
        "SELECT 1 FROM items WHERE shared_url = ? OR canonical_url = ? LIMIT 1", (link, link)
    ).fetchone() is not None


def mark(conn: sqlite3.Connection, line: Line) -> None:
    conn.execute("INSERT INTO inbox_seen (line_hash, seen_at) VALUES (?, ?) ON CONFLICT DO NOTHING",
                 (line.key, db.now_iso()))
    conn.commit()
