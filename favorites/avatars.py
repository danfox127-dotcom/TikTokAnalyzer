"""Creators' own pictures, for Browse's Creators tab.

A TikTok video's page names the account that posted it and links that
account's picture. The Mac (TikTok shows its pages only to a home connection,
not to the cloud) visits one video page per creator, a few a minute in the
background, the creators you save from most first, and keeps a small copy
of the picture by their handle. Until a creator has one, Browse shows their
initials.

A visit that finds no picture (a private or deleted video, a page laid out
some new way) is noted, and tried again a week later, at most three times.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from . import db, lengths, platforms, thumbnails
from .resolve import browsable_url

#: Pages read per minute in the background, gentle on TikTok.
PER_MINUTE = 4
#: The longest side a picture is kept at: sharp at Browse's largest size.
SIZE = 192
#: A picture already that small and no heavier than this is kept as it is.
LIGHT = 30_000
#: Tries before a creator with no picture to be found is left alone, and the
#: wait between them.
TRIES = 3
AGAIN_AFTER = timedelta(days=7)


def key(handle: Optional[str]) -> Optional[str]:
    """How a creator's picture is filed: their handle, "@lowercase"."""
    handle = (handle or "").strip().lstrip("@").lower()
    return "@" + handle if handle else None


def known(conn: sqlite3.Connection) -> set[str]:
    """The creators with a picture kept."""
    return {r["key"] for r in conn.execute("SELECT key FROM avatars WHERE data IS NOT NULL")}


def get(conn: sqlite3.Connection, handle: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT content_type, data FROM avatars WHERE key = ? AND data IS NOT NULL",
                        (key(handle),)).fetchone()


def missing(conn: sqlite3.Connection, limit: Optional[int] = None,
            now: Optional[datetime] = None) -> list[dict]:
    """One recent TikTok save for each creator still without a picture: the
    ones you save from most first. Each comes back with its ``key``."""
    now = now or datetime.now(timezone.utc)
    rows = conn.execute(
        "SELECT lower(creator_handle) AS k, count(*) AS n, max(saved_at) AS latest FROM items"
        " WHERE platform = 'tiktok' AND resolve_status = 'ok'"
        " AND coalesce(nullif(creator_handle, '@'), '') != '' GROUP BY lower(creator_handle)"
        " ORDER BY n DESC, latest DESC").fetchall()
    tried = {r["key"]: r for r in conn.execute("SELECT key, data IS NOT NULL AS got, fetched_at, tries FROM avatars")}
    again = (now - AGAIN_AFTER).isoformat()
    out = []
    for r in rows:
        k = key(r["k"])
        t = tried.get(k)
        if t is not None and (t["got"] or t["tries"] >= TRIES or t["fetched_at"] > again):
            continue
        item = conn.execute(
            "SELECT * FROM items WHERE platform = 'tiktok' AND resolve_status = 'ok'"
            " AND lower(creator_handle) = ? ORDER BY saved_at DESC, id DESC LIMIT 1", (r["k"],)).fetchone()
        if item is not None:
            out.append({**dict(item), "key": k})
        if limit and len(out) >= limit:
            break
    return out


def store(conn: sqlite3.Connection, handle: str, image: Optional[tuple[bytes, str]],
          source_url: Optional[str] = None) -> None:
    """Keep a creator's picture -- or, with none, that one wasn't found this time."""
    k = key(handle)
    if not k:
        return
    if image is not None:
        data, ctype = thumbnails.shrink(*image, to=SIZE, light=LIGHT)
        conn.execute(
            "INSERT INTO avatars (key, content_type, data, source_url, fetched_at, tries) VALUES (?, ?, ?, ?, ?, 1)"
            " ON CONFLICT (key) DO UPDATE SET content_type = excluded.content_type, data = excluded.data,"
            " source_url = excluded.source_url, fetched_at = excluded.fetched_at, tries = avatars.tries + 1",
            (k, ctype, data, source_url, db.now_iso()))
    else:
        conn.execute(
            "INSERT INTO avatars (key, fetched_at, tries) VALUES (?, ?, 1)"
            " ON CONFLICT (key) DO UPDATE SET fetched_at = excluded.fetched_at, tries = avatars.tries + 1",
            (k, db.now_iso()))
    conn.commit()


async def picture_for(item: dict, client: httpx.AsyncClient) -> tuple[Optional[tuple[bytes, str]], Optional[str]]:
    """(picture, its link) of the account behind one TikTok save. Never raises."""
    try:
        resp = await client.get(
            browsable_url(item), timeout=lengths.TIMEOUT, follow_redirects=True,
            headers={"User-Agent": lengths.USER_AGENT, "Accept-Language": "en;q=0.9"})
    except Exception:
        return None, None
    if resp.status_code != 200:
        return None, None
    found = platforms.tiktok_author(resp.text)
    if not found:
        return None, None
    return await thumbnails.fetch(found[1], client), found[1]


async def run(conn: sqlite3.Connection, limit: int = PER_MINUTE) -> dict:
    """Look for a few creators' pictures."""
    queue = missing(conn, limit)
    result = {"kept": 0, "none": 0}
    if not queue:
        return result
    async with httpx.AsyncClient() as client:
        for n, item in enumerate(queue):
            image, link = await picture_for(item, client)
            store(conn, item["key"], image, link)
            result["kept" if image else "none"] += 1
            if n < len(queue) - 1:
                await lengths._sleep(lengths.PAUSE)
    return result
