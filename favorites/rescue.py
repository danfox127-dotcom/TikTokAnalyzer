"""Rescue: the saves you forgot to make.

Your TikTok export says, without your having said so, which videos mattered:
the ones you sent someone, the ones you came back to in another session, the
ones you stayed on for minutes. Some you liked; most you never saved. Rescue
lists the ones that aren't in Faves, best first, to keep or pass on.

Everything here is read from rows you already have (``activity``, ``items``,
``videos``); nothing is looked up until you keep one.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from . import db, rewind

#: Staying this long on a video you liked counts as a reason to keep it. A
#: gap that hit the cap is more likely a phone set down than watching, so it
#: doesn't count.
LONG = 90
#: Coming back to a video counts when you watched it at least this long each
#: time: TikTok shows the same video again, and flicking past it twice isn't
#: coming back to it.
WATCHED = 10
#: Most cards a deck shows at once.
LIMIT = 150


def _secs(n: float) -> str:
    n = int(round(n))
    return f"{n // 60}m {n % 60:02d}s" if n >= 60 else f"{n}s"


def candidates(conn: sqlite3.Connection, limit: Optional[int] = LIMIT) -> list[dict]:
    """Videos you valued and never saved, best first: each with its reasons
    in words (shared, came back to, stayed long on, liked)."""
    rows = conn.execute(
        "SELECT at, ref FROM activity WHERE platform = 'tiktok' AND kind = 'watch' ORDER BY at").fetchall()
    times = [rewind._when(r["at"], timezone.utc) for r in rows]
    refs = [r["ref"] for r in rows]
    seen: dict[str, dict] = {}
    if rows:
        dwell, sessions = rewind._dwell(times)
        for n, s in enumerate(sessions):
            for i in s:
                v = seen.setdefault(refs[i], {"sessions": set(), "longest": 0.0, "last": times[i]})
                if dwell[i] >= WATCHED:
                    v["sessions"].add(n)
                if dwell[i] < rewind.CAP:
                    v["longest"] = max(v["longest"], dwell[i])
                v["last"] = max(v["last"], times[i])

    shared: Counter[str] = Counter()
    shared_at: dict[str, str] = {}
    for r in conn.execute("SELECT at, ref FROM activity WHERE platform = 'tiktok' AND kind = 'share'"):
        shared[r["ref"]] += 1
        shared_at[r["ref"]] = max(shared_at.get(r["ref"], ""), r["at"])
    liked = {r[0] for r in conn.execute(
        "SELECT DISTINCT ref FROM activity WHERE platform = 'tiktok' AND kind = 'like'")}
    kept = {r[0] for r in conn.execute(
        "SELECT external_id FROM items WHERE platform = 'tiktok' AND external_id IS NOT NULL")}
    passed = {r[0] for r in conn.execute("SELECT ref FROM rescue_skipped WHERE platform = 'tiktok'")}

    out = []
    for ref in set(seen) | set(shared):
        if ref in kept or ref in passed or not ref.isdigit():
            continue
        v = seen.get(ref, {"sessions": set(), "longest": 0.0, "last": None})
        back, long, sent, like = len(v["sessions"]), v["longest"] >= LONG, shared[ref], ref in liked
        if not (sent or back > 1 or (long and like)):
            continue
        why = []
        if sent:
            why.append("You shared it" + (f" {sent} times" if sent > 1 else ""))
        if back > 1:
            why.append(f"Watched in {back} different sessions")
        if long:
            why.append(f"You stayed {_secs(v['longest'])}")
        if like:
            why.append("You liked it")
        last = v["last"] or rewind._when(shared_at[ref], timezone.utc)
        out.append({"ref": ref, "why": why, "score": 3 * min(sent, 3) + 2 * min(max(back - 1, 0), 4) + long + like / 2,
                     "last": last.isoformat()})
    out.sort(key=lambda c: (c["score"], c["last"]), reverse=True)
    out = out[:limit] if limit else out

    # What's known of each: a like the Mac looked up carries its creator and caption.
    known = {}
    for chunk in rewind._chunks([c["ref"] for c in out], 500):
        marks = ",".join("?" * len(chunk))
        for r in conn.execute(f"SELECT external_id, creator_handle, creator_name, title FROM videos"
                              f" WHERE platform = 'tiktok' AND status = 'ok' AND external_id IN ({marks})", chunk):
            known[r["external_id"]] = r
    for c in out:
        r = known.get(c["ref"])
        c.update({"id": None, "platform": "tiktok", "external_id": c["ref"], "thumbnail_url": None,
                  "shared_url": share_link(c["ref"]), "canonical_url": f"https://www.tiktok.com/video/{c['ref']}",
                  "title": r["title"] if r else None, "creator_handle": r["creator_handle"] if r else None,
                  "creator_name": r["creator_name"] if r else None, "saved_at": c["last"], "duration": None,
                  "format": "short"})
    return out


def share_link(ref: str) -> str:
    """The link a TikTok export gives a video: one Faves can look up."""
    return f"https://www.tiktokv.com/share/video/{ref}/"


def skip(conn: sqlite3.Connection, ref: str) -> None:
    conn.execute("INSERT INTO rescue_skipped (platform, ref, at) VALUES ('tiktok', ?, ?) ON CONFLICT DO NOTHING",
                 (ref, db.now_iso()))
    conn.commit()


def count(conn: sqlite3.Connection) -> int:
    return len(candidates(conn, None))
