"""Keep a copy of every thumbnail, because the platforms' copies expire.

A TikTok thumbnail URL is signed with an ``x-expires`` timestamp. On a real
library every one of 738 thumbnails carried one, and all of them lapsed on the
same day -- a day or two after they were resolved. Instagram's expire faster.
Once a link lapses the image stops loading, and a card just goes blank: no
error, nothing to notice, a museum whose pictures fade out one by one.

So the image itself is kept, inside the library file, the moment it is fetched.
That keeps the library one file you can back up by copying, it keeps working
offline, and it keeps the picture after the original is gone -- which is what a
museum is for. A deleted TikTok still has its placard *and* its picture.

Run ``python -m favorites.thumbnails`` once on an existing library. From then
on saves and backfills keep their own copies as they go.
"""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
import time
from typing import Optional

import httpx

from . import db
from .resolve import TIMEOUT, USER_AGENT, resolve

CONCURRENCY = 4

# A ceiling against something absurd, not a judgement on size. TikTok serves
# some covers as full-resolution PNGs -- 3.3 MB and 4.3 MB on a real library,
# refused by an earlier 3 MB cap that assumed a thumbnail is always small.
MAX_BYTES = 10_000_000

# Raster formats only. An SVG is a document that can carry script, and this one
# would be served from the library's own address -- so it is refused outright.
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"}


async def fetch_explained(
    url: Optional[str], client: httpx.AsyncClient
) -> tuple[Optional[tuple[bytes, str]], str]:
    """Download one image, saying why when it fails. Never raises.

    The reason matters: "the video is gone" and "this code refused a real
    picture" look identical from outside, and only one of them is a bug.
    """
    if not url:
        return None, "no link"
    try:
        async with client.stream(
            "GET", url, follow_redirects=True, timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as resp:
            if resp.status_code != 200:
                return None, "unavailable"
            ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            if ctype not in ALLOWED_TYPES:
                return None, f"not an image we keep ({ctype or 'no type'})"
            chunks, size = [], 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    return None, f"over {MAX_BYTES // 1_000_000} MB"
                chunks.append(chunk)
    except Exception:
        return None, "network error"
    data = b"".join(chunks)
    return ((data, ctype), "ok") if data else (None, "empty")


async def fetch(url: Optional[str], client: httpx.AsyncClient) -> Optional[tuple[bytes, str]]:
    """Download one image. Returns ``(bytes, content_type)`` or None. Never raises."""
    return (await fetch_explained(url, client))[0]


def store(conn: sqlite3.Connection, item_id: int, image: tuple[bytes, str],
          source_url: Optional[str]) -> None:
    data, ctype = image
    conn.execute(
        "INSERT OR REPLACE INTO thumbnails (item_id, content_type, data, source_url, fetched_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (item_id, ctype, data, source_url, db.now_iso()),
    )
    conn.commit()


def get(conn: sqlite3.Connection, item_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT content_type, data FROM thumbnails WHERE item_id = ?", (item_id,)
    ).fetchone()


def missing(conn: sqlite3.Connection, limit: Optional[int] = None) -> list[dict]:
    """Resolved items with a thumbnail link but no kept copy, newest first."""
    sql = (
        "SELECT i.id, i.canonical_url, i.thumbnail_url FROM items i"
        " LEFT JOIN thumbnails t ON t.item_id = i.id"
        " WHERE t.item_id IS NULL AND i.resolve_status = 'ok'"
        " AND i.thumbnail_url IS NOT NULL AND i.thumbnail_url != ''"
        " ORDER BY i.saved_at DESC, i.id DESC"
    )
    params: tuple = ()
    if limit:
        sql += " LIMIT ?"
        params = (limit,)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def counts(conn: sqlite3.Connection) -> dict:
    with_link = conn.execute(
        "SELECT count(*) FROM items WHERE resolve_status = 'ok'"
        " AND thumbnail_url IS NOT NULL AND thumbnail_url != ''").fetchone()[0]
    kept = conn.execute("SELECT count(*) FROM thumbnails").fetchone()[0]
    return {"with_link": with_link, "kept": kept}


async def _one(item: dict, client: httpx.AsyncClient, sem: asyncio.Semaphore):
    """Try the stored link; if it has lapsed, ask the platform for a fresh one."""
    async with sem:
        image, why = await fetch_explained(item["thumbnail_url"], client)
        if image:
            return item, image, item["thumbnail_url"], False, why
        if why != "unavailable":
            # The picture is there and was refused -- asking for a fresh link
            # would only fetch the same picture and refuse it again.
            return item, None, None, False, why
        try:
            fresh = await resolve(item["canonical_url"], client)
        except Exception:
            fresh = None
        if fresh is None or fresh.resolve_status != "ok" or not fresh.thumbnail_url:
            return item, None, None, True, "unavailable (usually a deleted video)"
        image, why = await fetch_explained(fresh.thumbnail_url, client)
        return item, image, fresh.thumbnail_url, True, why


async def run(conn: sqlite3.Connection, limit: Optional[int] = None, quiet: bool = False) -> dict:
    queue = missing(conn, limit)
    result = {"attempted": len(queue), "kept": 0, "refreshed": 0, "failed": 0, "why": {}}
    if not queue:
        return result

    started = time.monotonic()
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient() as client:
        tasks = [_one(item, client, sem) for item in queue]
        for done, coro in enumerate(asyncio.as_completed(tasks), 1):
            item, image, source, refreshed, why = await coro
            if image:
                store(conn, item["id"], image, source)
                result["kept"] += 1
                if refreshed:
                    result["refreshed"] += 1
                    # Keep the fresh link too, so the fallback path works.
                    conn.execute("UPDATE items SET thumbnail_url = ? WHERE id = ?",
                                 (source, item["id"]))
                    conn.commit()
            else:
                result["failed"] += 1
                result["why"][why] = result["why"].get(why, 0) + 1
            if not quiet and (done % 50 == 0 or done == len(queue)):
                rate = done / max(time.monotonic() - started, 1e-9) * 60
                print(f"  {done}/{len(queue)}  kept {result['kept']}  ~{rate:.0f}/min", flush=True)
    return result


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, help="stop after this many (default: all)")
    ap.add_argument("--stats", action="store_true", help="report and exit")
    ap.add_argument("--db", help="library path (default: $FAVORITES_DB)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    conn, where = db.connect_announced(args.db)
    print(where + "\n")
    try:
        if not args.stats:
            r = asyncio.run(run(conn, args.limit, quiet=args.quiet))
            if r["attempted"]:
                print(f"\nkept {r['kept']} of {r['attempted']}"
                      + (f" ({r['refreshed']} needed a fresh link first)" if r["refreshed"] else ""))
                if r["failed"]:
                    print(f"{r['failed']} could not be saved:")
                    for why, n in sorted(r["why"].items(), key=lambda kv: -kv[1]):
                        print(f"  {n:>4}  {why}")
                    print("Re-running tries them again.")
            else:
                print("every thumbnail is already kept.")
        c = counts(conn)
        print(f"\nthumbnails kept      : {c['kept']} of {c['with_link']}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
