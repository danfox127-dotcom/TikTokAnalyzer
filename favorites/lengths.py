"""How long each video is, read from its own page.

No platform's quick lookup (oEmbed) or data export says how long a video is,
but YouTube's and TikTok's own pages do. Instagram's does not -- tested on a
real library, 0 of 3 -- so Instagram saves have no length and sit outside the
Length filter rather than being guessed at.

New saves from the share sheet get their length as they are saved. For a
library saved before this existed, catch up once:

    python -m favorites.lengths

It reads one page at a time with a pause between, because that is a page view
per video and there are hundreds of them.
"""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
import time
from typing import Optional

import httpx

from . import db, platforms
from .resolve import TIMEOUT, USER_AGENT, browsable_url

PAUSE = 1.0
_sleep = asyncio.sleep  # replaced in tests


def readable_platforms() -> tuple[str, ...]:
    return tuple(p.name for p in platforms.PLATFORMS if p.length_from_page)


async def fetch_explained(item: dict, client: httpx.AsyncClient) -> tuple[Optional[int], str]:
    """(seconds, why) for one item. Never raises."""
    reader = platforms.get(item.get("platform") or "").length_from_page
    if reader is None:
        return None, "this platform does not say"
    try:
        resp = await client.get(
            browsable_url(item), timeout=TIMEOUT, follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en;q=0.9"})
    except Exception:
        return None, "network error"
    if resp.status_code != 200:
        return None, "unavailable (usually a deleted video)"
    seconds = reader(resp.text)
    return (seconds, "ok") if seconds else (None, "not on the page")


async def fetch(item: dict, client: httpx.AsyncClient) -> Optional[int]:
    return (await fetch_explained(item, client))[0]


def missing(conn: sqlite3.Connection, limit: Optional[int] = None) -> list[dict]:
    """Identified videos on a platform that states length, with none recorded yet."""
    names = readable_platforms()
    sql = (f"SELECT * FROM items WHERE duration IS NULL AND resolve_status = 'ok'"
           f" AND platform IN ({', '.join('?' * len(names))})"
           f" ORDER BY saved_at DESC, id DESC")
    params: tuple = names
    if limit:
        sql += " LIMIT ?"
        params = params + (limit,)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def counts(conn: sqlite3.Connection) -> list[tuple[str, int, int]]:
    """(platform, with a length, could have one) per readable platform."""
    names = readable_platforms()
    rows = conn.execute(
        f"SELECT platform, count(duration), count(*) FROM items WHERE resolve_status = 'ok'"
        f" AND platform IN ({', '.join('?' * len(names))}) GROUP BY platform"
        f" ORDER BY count(*) DESC", names).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


async def run(conn: sqlite3.Connection, limit: Optional[int] = None, quiet: bool = False) -> dict:
    queue = missing(conn, limit)
    result = {"attempted": len(queue), "found": 0, "failed": 0, "why": {}}
    if not queue:
        return result
    if not quiet:
        minutes = max(1, round(len(queue) * (PAUSE + 0.8) / 60))
        print(f"  {len(queue)} to read, one at a time (about {minutes} min)", flush=True)
    started = time.monotonic()
    async with httpx.AsyncClient() as client:
        for done, item in enumerate(queue, 1):
            seconds, why = await fetch_explained(item, client)
            if seconds:
                conn.execute("UPDATE items SET duration = ? WHERE id = ?", (seconds, item["id"]))
                conn.commit()
                result["found"] += 1
            else:
                result["failed"] += 1
                result["why"][why] = result["why"].get(why, 0) + 1
            if not quiet and (done % 25 == 0 or done == len(queue)):
                rate = done / max(time.monotonic() - started, 1e-9) * 60
                print(f"  {done}/{len(queue)}  found {result['found']}  ~{rate:.0f}/min", flush=True)
            if done < len(queue):
                await _sleep(PAUSE)
    return result


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, help="stop after this many (default: all)")
    ap.add_argument("--stats", action="store_true", help="report and exit")
    ap.add_argument("--db", help="library path (default: ~/favorites.db)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    conn, where = db.connect_announced(args.db)
    print(where + "\n")
    try:
        if not args.stats:
            r = asyncio.run(run(conn, args.limit, quiet=args.quiet))
            if r["attempted"]:
                print(f"\nfound the length of {r['found']} of {r['attempted']}")
                if r["failed"]:
                    print(f"{r['failed']} without one:")
                    for why, n in sorted(r["why"].items(), key=lambda kv: -kv[1]):
                        print(f"  {n:>4}  {why}")
                    print("Re-running tries them again.")
            else:
                print("every video that can have a length has one.")
        print()
        for name, have, could in counts(conn):
            print(f"  {platforms.get(name).label:<10}: {have} of {could} have a length")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
