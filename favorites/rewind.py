"""Rewind: a month on TikTok, told from your own data export.

The export lists every video you opened, every like and every search, each
with the time in UTC -- and nothing more. A watched or liked video is a bare
id: no creator, no caption. So:

- How much, and when, comes straight from the export: videos opened, a
  week-by-hour clock (in your own time zone), likes, searches.
- Who and what comes from the videos you liked or saved. Saves already carry
  their creator and topics; likes are looked up by the Mac a few at a time
  (:func:`look_up_likes`) and kept in ``videos``, apart from the library, so
  a month of likes never buries what you chose to keep.

Every number is a count of rows you own. The one estimate -- hours -- says
what it assumed.
"""

from __future__ import annotations

import asyncio
import calendar
import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from . import backfill, db, tagging
from . import themes as theme_vocabulary
from .museum import MONTH_NAMES
from .resolve import resolve

#: Likes looked up per pass of the Mac's minute loop.
LOOKUP_BATCH = 20
#: A like that couldn't be looked up is tried again after this long.
RETRY_AFTER = timedelta(days=1)
#: Where the time zone the page last reported is kept.
TZ_KEY = "timezone"
#: The estimate's bounds, in seconds per video opened.
GUESS_SECONDS, MOST_SECONDS = 30, 90
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# --- looking up likes (the Mac) ------------------------------------------------

def likes_to_look_up(conn: sqlite3.Connection, limit: int = LOOKUP_BATCH,
                     now: Optional[datetime] = None) -> list[str]:
    """Liked video ids still without details, newest like first.

    A like that is also a save is skipped: the save has its details. One
    that failed waits a day before another try, and gives up after
    ``backfill.MAX_ATTEMPTS``.
    """
    retry = ((now or datetime.now(timezone.utc)) - RETRY_AFTER).replace(microsecond=0).isoformat()
    rows = conn.execute(
        "SELECT a.ref, max(a.at) AS latest FROM activity a"
        " WHERE a.platform = 'tiktok' AND a.kind = 'like'"
        " AND NOT EXISTS (SELECT 1 FROM videos v WHERE v.platform = 'tiktok' AND v.external_id = a.ref"
        "   AND (v.status = 'ok' OR v.attempts >= ? OR v.looked_at > ?))"
        " AND NOT EXISTS (SELECT 1 FROM items i WHERE i.platform = 'tiktok' AND i.external_id = a.ref)"
        " GROUP BY a.ref ORDER BY latest DESC LIMIT ?",
        (backfill.MAX_ATTEMPTS, retry, limit)).fetchall()
    return [r[0] for r in rows]


def _store(conn: sqlite3.Connection, video_id: str, found, rules) -> bool:
    ok = found is not None and found.resolve_status == "ok"
    themes: list[str] = []
    if ok:
        tags, _ = tagging.enrich(title=found.title, description=found.description)
        themes = theme_vocabulary.themes_for(
            tags, (found.title, found.description),
            creator=theme_vocabulary.creator_key(found.creator_handle, found.creator_name), rules=rules)
    conn.execute(
        "INSERT INTO videos (platform, external_id, creator_handle, creator_name, title, themes,"
        " status, attempts, looked_at) VALUES ('tiktok', ?, ?, ?, ?, ?, ?, 1, ?)"
        " ON CONFLICT (platform, external_id) DO UPDATE SET creator_handle = excluded.creator_handle,"
        " creator_name = excluded.creator_name, title = excluded.title, themes = excluded.themes,"
        " status = excluded.status, attempts = videos.attempts + 1, looked_at = excluded.looked_at",
        (video_id, found.creator_handle if ok else None, found.creator_name if ok else None,
         found.title if ok else None, json.dumps(themes), "ok" if ok else "unresolved", db.now_iso()))
    return ok


async def look_up_likes(conn: sqlite3.Connection, limit: int = LOOKUP_BATCH) -> int:
    """Look up a few liked videos; returns how many were found."""
    ids = likes_to_look_up(conn, limit)
    if not ids:
        return 0
    sem = asyncio.Semaphore(backfill.CONCURRENCY)

    async def one(video_id: str, client: httpx.AsyncClient):
        async with sem:
            try:
                return video_id, await resolve(f"https://www.tiktok.com/video/{video_id}", client)
            except Exception:  # resolve() doesn't raise; a background job must not die on one like regardless
                return video_id, None

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(one(v, client) for v in ids))
    rules = db.load_rules(conn)
    found = sum(_store(conn, video_id, r, rules) for video_id, r in results)
    conn.commit()
    return found


# --- a month's numbers -----------------------------------------------------------

def zone(name: Optional[str]) -> Optional[ZoneInfo]:
    """A time zone by its name ("America/New_York"), or None if it isn't one."""
    if not name or len(name) > 64:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def latest(conn: sqlite3.Connection, tz: Optional[ZoneInfo] = None) -> Optional[str]:
    """``YYYY-MM`` of the newest month with TikTok activity, if any."""
    found = months(conn, tz)
    return found[0] if found else None


def months(conn: sqlite3.Connection, tz: Optional[ZoneInfo] = None) -> list[str]:
    """``YYYY-MM`` of every month with TikTok activity in your time zone,
    newest first. Times are kept in UTC, so a late evening on the 31st in New
    York is the 1st in UTC: each UTC month and its neighbours are checked
    against the local month's own bounds."""
    tz = tz or timezone.utc
    utc = {r[0] for r in conn.execute(
        "SELECT DISTINCT substr(at, 1, 7) AS m FROM activity"
        " WHERE platform = 'tiktok' AND kind IN ('watch', 'like')")}
    out = []
    for key in sorted(utc | {_previous(k) for k in utc} | {_next(k) for k in utc}, reverse=True):
        lo, hi = (_utc(t) for t in _bounds(key, tz))
        if conn.execute(
                "SELECT 1 FROM activity WHERE platform = 'tiktok' AND kind IN ('watch', 'like')"
                " AND at >= ? AND at < ? LIMIT 1", (lo, hi)).fetchone():
            out.append(key)
    return out


def _bounds(key: str, tz: ZoneInfo) -> tuple[datetime, datetime]:
    year, month = (int(p) for p in key.split("-"))
    start = datetime(year, month, 1, tzinfo=tz)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=tz)
    return start, end


def _utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _when(iso: str, tz: ZoneInfo) -> datetime:
    return datetime.fromisoformat(iso).astimezone(tz)


def _previous(key: str) -> str:
    year, month = (int(p) for p in key.split("-"))
    return f"{year - (month == 1)}-{(month - 2) % 12 + 1:02d}"


def _next(key: str) -> str:
    year, month = (int(p) for p in key.split("-"))
    return f"{year + (month == 12)}-{month % 12 + 1:02d}"


def month_name(key: str) -> str:
    return MONTH_NAMES[int(key[5:7]) - 1]


def _videos(conn: sqlite3.Connection, start: str, end: str) -> tuple[dict[str, dict], dict]:
    """The month's liked and saved TikToks with what's known of them, by
    video id; and the likes (all, kept, still being looked up)."""
    out: dict[str, dict] = {}
    for r in conn.execute(
            "SELECT external_id, creator_handle, creator_name, themes FROM items"
            " WHERE platform = 'tiktok' AND resolve_status = 'ok' AND external_id IS NOT NULL"
            " AND saved_at >= ? AND saved_at < ?", (start, end)):
        out[r["external_id"]] = dict(r)
    liked = {r[0] for r in conn.execute(
        "SELECT DISTINCT ref FROM activity WHERE platform = 'tiktok' AND kind = 'like'"
        " AND at >= ? AND at < ?", (start, end))}
    kept: set[str] = set()
    waiting = 0
    for chunk in _chunks(sorted(liked), 500):
        marks = ", ".join("?" * len(chunk))
        saves = {r["external_id"]: dict(r) for r in conn.execute(
            f"SELECT external_id, creator_handle, creator_name, themes, resolve_status FROM items"
            f" WHERE platform = 'tiktok' AND external_id IN ({marks})", chunk)}
        kept |= set(saves)
        known = {r["external_id"]: dict(r) for r in conn.execute(
            f"SELECT external_id, creator_handle, creator_name, themes, status, attempts FROM videos"
            f" WHERE platform = 'tiktok' AND external_id IN ({marks})", chunk)}
        for vid in chunk:
            if vid in saves:
                if saves[vid]["resolve_status"] == "ok":
                    out.setdefault(vid, saves[vid])
            elif vid in known and known[vid]["status"] == "ok":
                out.setdefault(vid, known[vid])
            elif vid not in known or known[vid]["attempts"] < backfill.MAX_ATTEMPTS:
                waiting += 1
    return out, {"liked": len(liked), "kept": len(kept), "waiting": waiting}


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _themes(raw) -> list[str]:
    if not raw:
        return []
    return json.loads(raw) if isinstance(raw, str) else list(raw)


def _mix(videos: dict[str, dict]) -> tuple[Counter, dict[str, str], Counter, int]:
    """Who and what: creators by count (and their names), and each video's
    main topic by count."""
    creators: Counter[str] = Counter()
    names: dict[str, str] = {}
    topics: Counter[str] = Counter()
    for v in videos.values():
        key = (v.get("creator_handle") or v.get("creator_name") or "").strip()
        if key:
            creators[key.lower()] += 1
            # A name from any of their videos beats the handle.
            if v.get("creator_name") or key.lower() not in names:
                names[key.lower()] = v.get("creator_name") or key
        first = (_themes(v.get("themes")) or [None])[0]
        topics[first or ""] += 1
    return creators, names, topics, len(videos)


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def month(conn: sqlite3.Connection, key: str, tz: Optional[ZoneInfo] = None,
          now: Optional[datetime] = None) -> Optional[dict]:
    """Everything Rewind says about one month, or None with nothing to say."""
    tz = tz or timezone.utc
    now = now or datetime.now(timezone.utc)
    start, end = _bounds(key, tz)
    lo, hi = _utc(start), _utc(end)
    rows = conn.execute(
        "SELECT kind, at, ref FROM activity WHERE platform = 'tiktok' AND at >= ? AND at < ?",
        (lo, hi)).fetchall()
    watched = [_when(r["at"], tz) for r in rows if r["kind"] == "watch"]
    searches = [r["ref"] for r in rows if r["kind"] == "search"]
    if not watched and not any(r["kind"] == "like" for r in rows):
        return None

    prev = _previous(key)
    p_start, p_end = _bounds(prev, tz)
    p_lo, p_hi = _utc(p_start), _utc(p_end)
    prev_opened = conn.execute(
        "SELECT count(*) FROM activity WHERE platform = 'tiktok' AND kind = 'watch' AND at >= ? AND at < ?",
        (p_lo, p_hi)).fetchone()[0]

    # When: a week of hours, and how much of the month the export covers.
    clock = [[0] * 24 for _ in range(7)]
    for t in watched:
        clock[t.weekday()][t.hour] += 1
    busiest = max(((d, h) for d in range(7) for h in range(24)), key=lambda dh: clock[dh[0]][dh[1]])
    last_day = calendar.monthrange(start.year, start.month)[1]
    first_seen = min(watched).day if watched else None
    last_seen = max(watched).day if watched else None
    ongoing = start <= now.astimezone(tz) < end
    partial = bool(watched) and (first_seen > 1 or (last_seen < last_day and not ongoing))
    short = MONTH_NAMES[start.month - 1][:3]
    coverage = (f"{short} {first_seen}–{last_seen}" if partial else
                f"{short} 1–{last_seen}, so far" if ongoing and watched else "")

    # Who and what, from likes and saves -- this month's and last month's.
    videos, likes = _videos(conn, lo, hi)
    creators, names, topics, total = _mix(videos)
    p_videos, _ = _videos(conn, p_lo, p_hi)
    p_creators, _, p_topics, p_total = _mix(p_videos)
    p_rank = {k: i + 1 for i, (k, _) in enumerate(p_creators.most_common())}
    top = []
    for i, (k, n) in enumerate(creators.most_common(5)):
        before = p_rank.get(k)
        top.append({"name": names[k], "handle": k if k.startswith("@") else "", "count": n,
                    "was": ("new" if not before else f"up from {_ordinal(before)}" if before > i + 1 else "")})

    named = [(t, n) for t, n in topics.most_common() if t]
    shown = named[:5]
    rest = total - sum(n for _, n in shown)
    themes = [{"name": t, "count": n, "share": round(100 * n / total)} for t, n in shown]
    if rest and total:
        themes.append({"name": "Everything else", "count": rest, "share": round(100 * rest / total), "rest": True})
    jump = None
    if p_total:
        for t, n in named:
            share, before = n / total, p_topics.get(t, 0) / p_total
            if n >= 3 and share >= 0.05 and share >= max(1.5 * before, before + 0.04):
                if not jump or share - before > jump["by"]:
                    jump = {"name": t, "share": round(100 * share), "before": round(100 * before),
                            "by": share - before}

    # The one estimate: hours, from the length of what you saved that month.
    lengths = [r[0] for r in conn.execute(
        "SELECT duration FROM items WHERE platform = 'tiktok' AND duration > 0"
        " AND saved_at >= ? AND saved_at < ?", (lo, hi))]
    seconds = min(int(median(lengths)), MOST_SECONDS) if lengths else GUESS_SECONDS
    hours = len(watched) * seconds / 3600

    words = Counter(s.strip().lower() for s in searches if s.strip())
    return {
        "key": key, "name": MONTH_NAMES[start.month - 1], "year": start.year,
        "prev": prev, "prev_name": month_name(prev),
        "opened": len(watched), "prev_opened": prev_opened,
        "change": round(100 * (len(watched) - prev_opened) / prev_opened) if prev_opened else None,
        "coverage": coverage, "ongoing": ongoing,
        "hours": round(hours), "seconds": seconds, "seconds_guessed": not lengths,
        "clock": clock, "peak": max(max(r) for r in clock),
        "busiest": {"day": DAYS[busiest[0]], "hour": busiest[1]} if watched else None,
        "liked": likes["liked"], "kept": likes["kept"], "waiting": likes["waiting"],
        "saved": conn.execute(
            "SELECT count(*) FROM items WHERE platform = 'tiktok' AND saved_at >= ? AND saved_at < ?",
            (lo, hi)).fetchone()[0],
        "creators": top, "looked_at": total,
        "themes": themes, "jump": jump,
        "searched": len(searches), "searches": [w for w, _ in words.most_common(8)],
        "tz": getattr(tz, "key", "UTC"),
    }
