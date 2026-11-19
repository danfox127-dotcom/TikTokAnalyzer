"""The platforms' own labels for your saves: TikTok's topic labels and search
suggestions, YouTube's category and tags.

They're read from the same page Faves visits for a video's length, so a new
save gets them with no extra visit. For saves made before, the Mac catches
up a few pages a minute in the background (``run``), the saves with no topic
first. Each one read is filed again at once, and the move shows in "What
changed" (/topics/changes).

TikTok shows its pages only to a home connection, not to the cloud, so a page
that comes back without the video's data stores nothing and is tried again
later -- by the Mac.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Optional

import httpx

from . import db, lengths, platforms

#: Pages read per minute in the background: gentle on the platforms, and
#: about two hours for a library of 800 TikToks.
PER_MINUTE = 8

#: Saves whose page came back without the video in it this time Faves ran
#: (deleted, private, or a page TikTok wouldn't show): not asked for again
#: until the next start.
_skipped: set[int] = set()


def readable() -> tuple[str, ...]:
    return tuple(p.name for p in platforms.PLATFORMS if p.labels_from_page)


def missing(conn: sqlite3.Connection, limit: Optional[int] = None) -> list[dict]:
    """Identified saves on a platform with labels, none read yet: the ones
    with no topic first, then newest first."""
    names = readable()
    sql = (f"SELECT * FROM items WHERE labels IS NULL AND resolve_status = 'ok'"
           f" AND platform IN ({', '.join('?' * len(names))})"
           f" ORDER BY (coalesce(nullif(themes, ''), '[]') = '[]') DESC, saved_at DESC, id DESC")
    rows = [dict(r) for r in conn.execute(sql, names).fetchall() if r["id"] not in _skipped]
    return rows[:limit] if limit else rows


def counts(conn: sqlite3.Connection) -> tuple[int, int]:
    """(read, could be read): for the progress line on Sort things out."""
    names = readable()
    row = conn.execute(
        f"SELECT count(labels), count(*) FROM items WHERE resolve_status = 'ok'"
        f" AND platform IN ({', '.join('?' * len(names))})", names).fetchone()
    return int(row[0]), int(row[1])


def store(conn: sqlite3.Connection, item_id: int, found: dict) -> bool:
    """Keep one save's labels and file it again. Returns whether its topics
    changed; a change is added to "What changed"."""
    before = conn.execute("SELECT themes FROM items WHERE id = ?", (item_id,)).fetchone()
    if before is None:
        return False
    conn.execute("UPDATE items SET labels = ? WHERE id = ?",
                 (json.dumps(found, ensure_ascii=False), item_id))
    db.index_item(conn, item_id)             # works its themes out again
    after = conn.execute("SELECT themes FROM items WHERE id = ?", (item_id,)).fetchone()["themes"]
    moved = set(db.loads_list(before["themes"])) != set(db.loads_list(after))
    if moved:
        _note_change(conn, item_id, before["themes"] or "[]", after)
    conn.commit()
    return moved


def _note_change(conn: sqlite3.Connection, item_id: int, was: str, became: str) -> None:
    """Add a move to "What changed": from where it was before the latest
    change to the rules, if it's already listed, so the list still says
    where it started."""
    row = conn.execute("SELECT was FROM theme_changes WHERE item_id = ?", (item_id,)).fetchone()
    start = row["was"] if row is not None else was
    if set(db.loads_list(start)) == set(db.loads_list(became)):
        conn.execute("DELETE FROM theme_changes WHERE item_id = ?", (item_id,))
        return
    conn.execute(
        "INSERT INTO theme_changes (item_id, was, became, at) VALUES (?, ?, ?, ?)"
        " ON CONFLICT (item_id) DO UPDATE SET became = excluded.became, at = excluded.at",
        (item_id, start, became, db.now_iso()))


async def run(conn: sqlite3.Connection, limit: int = PER_MINUTE) -> dict:
    """Read a few saves' pages for their labels (and length, while there)."""
    queue = missing(conn, limit)
    result = {"read": 0, "moved": 0, "skipped": 0}
    if not queue:
        return result
    async with httpx.AsyncClient() as client:
        for n, item in enumerate(queue):
            seconds, found, _ = await lengths.page_facts(item, client)
            if seconds and not item.get("duration"):
                conn.execute("UPDATE items SET duration = ? WHERE id = ?", (seconds, item["id"]))
                conn.commit()
            if found is None:
                _skipped.add(item["id"])
                result["skipped"] += 1
            else:
                result["read"] += 1
                result["moved"] += store(conn, item["id"], found)
            if n < len(queue) - 1:
                await lengths._sleep(lengths.PAUSE)
    return result
