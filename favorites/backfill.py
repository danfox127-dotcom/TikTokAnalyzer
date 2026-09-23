"""Fill in the items an import could not describe.

An imported favourite is a dated URL and nothing else. This resolves it the same
way a share does -- oEmbed, then OpenGraph -- and writes back a title, creator
and thumbnail.

Three things make a multi-thousand-item backfill survivable:

**Newest first.** Recent videos are likeliest to still exist, and they are what
the digest and the "recently saved" shelf need. The museum starts working after
the first batch instead of after the last one.

**Resumable.** Progress lives in the database, not in the process. Interrupt it,
re-run it, run it in batches over a week -- it picks up where it stopped.

**Budgeted.** TikTok throttles hard (measured around 700/hour in this repo's
own creator map). Concurrency stays low deliberately; going faster gets you
rate-limited, not finished sooner.

Items that fail are counted and retried on later runs up to ``MAX_ATTEMPTS``,
after which they are left alone -- a video deleted three years ago will not
come back, and re-asking costs the budget that live items need.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import sqlite3
import time
from typing import Optional

import httpx

from . import db, tagging, transcript
from .resolve import _is_placeholder_title, resolve

CONCURRENCY = 3       # deliberately low; higher trips TikTok's throttle
MAX_ATTEMPTS = 3      # after this, treat the item as permanently gone


def pending(conn: sqlite3.Connection, limit: Optional[int] = None) -> list[dict]:
    """Unresolved items, newest first, excluding ones that have failed too often."""
    sql = (
        "SELECT * FROM items"
        " WHERE resolve_status != 'ok' AND resolve_attempts < ?"
        " ORDER BY saved_at DESC, id DESC"
    )
    params: list = [MAX_ATTEMPTS]
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return db.rows_to_dicts(conn.execute(sql, params).fetchall())


def requeue_placeholders(conn: sqlite3.Connection) -> dict:
    """Undo resolutions that an earlier, too-lenient check let through.

    Before the placeholder guard existed, a deleted video's "TikTok" page was
    accepted as a successful resolution. Those rows have to be corrected in
    place, because a library that reports itself fully resolved will never
    retry them and the failure stays invisible.

    A junk title is cleared outright. A row left with neither a title nor a
    creator is put back in the queue so the fixed logic can rule on it.
    """
    rows = db.rows_to_dicts(conn.execute(
        "SELECT id, platform, title, creator_name, creator_handle"
        " FROM items WHERE resolve_status = 'ok'").fetchall())

    cleared = requeued = 0
    for row in rows:
        if not _is_placeholder_title(row["title"], row["platform"]):
            continue
        conn.execute("UPDATE items SET title = NULL WHERE id = ?", (row["id"],))
        cleared += 1
        if not (row["creator_name"] or row["creator_handle"]):
            conn.execute(
                "UPDATE items SET resolve_status = 'pending', resolve_attempts = 0,"
                " resolve_error = NULL WHERE id = ?", (row["id"],))
            requeued += 1
    conn.commit()
    return {"cleared_titles": cleared, "requeued": requeued}


def stats(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT resolve_status AS s, count(*) AS n FROM items GROUP BY s"
    ).fetchall()
    by_status = {r["s"]: r["n"] for r in rows}
    exhausted = conn.execute(
        "SELECT count(*) AS n FROM items WHERE resolve_status != 'ok' AND resolve_attempts >= ?",
        (MAX_ATTEMPTS,),
    ).fetchone()["n"]
    total = sum(by_status.values())
    resolved = by_status.get("ok", 0)
    # Whether YouTube items are Shorts is learned by asking YouTube, and that
    # rule was written without a live check. A split that looks wrong for your
    # own saves -- everything a Short, say -- is the sign it needs revisiting.
    formats = {
        (r["f"] or "unknown"): r["n"] for r in conn.execute(
            "SELECT format AS f, count(*) AS n FROM items"
            " WHERE platform = 'youtube' AND resolve_status = 'ok' GROUP BY format")
    }
    return {
        "youtube_formats": formats,
        "total": total,
        "resolved": resolved,
        "by_status": by_status,
        "gave_up": exhausted,
        "remaining": total - resolved - exhausted,
        "hit_rate": (resolved / total) if total else 0.0,
    }


async def _resolve_one(
    item: dict, client: httpx.AsyncClient, sem: asyncio.Semaphore
) -> tuple[dict, Optional[object]]:
    async with sem:
        try:
            return item, await resolve(item["canonical_url"], client)
        except Exception:
            # resolve() is written not to raise, but a backfill must not die on
            # one bad row regardless.
            return item, None


def _write_back(
    conn: sqlite3.Connection, item: dict, resolved, transcripts: bool = True
) -> bool:
    """Persist one resolution. Returns True if it produced usable metadata."""
    attempts = int(item.get("resolve_attempts") or 0) + 1

    if resolved is None or resolved.resolve_status != "ok":
        conn.execute(
            "UPDATE items SET resolve_attempts = ?, resolve_status = ?,"
            " resolve_error = ?, resolved_at = ? WHERE id = ?",
            (attempts, "unresolved",
             (resolved.resolve_error if resolved else "resolver raised"),
             db.now_iso(), item["id"]),
        )
        conn.commit()
        return False

    payload = dataclasses.asdict(resolved)
    # The export's date is when *you* saved it, which is the truth the museum
    # arranges itself by. Never let a resolution overwrite it.
    payload.pop("shared_url", None)
    payload["resolve_attempts"] = attempts
    payload["resolved_at"] = db.now_iso()

    text = transcript.fetch(resolved.platform, resolved.external_id) if transcripts else None
    payload["transcript"] = text
    payload["tags"], payload["terms"] = tagging.enrich(
        title=resolved.title, description=resolved.description,
        note=item.get("note"), transcript=text,
    )
    db.upsert_item(conn, payload)
    return True


async def run(
    conn: sqlite3.Connection, limit: Optional[int], quiet: bool = False,
    transcripts: bool = True,
) -> dict:
    queue = pending(conn, limit)
    if not queue:
        return {"attempted": 0, "resolved": 0, "failed": 0, "seconds": 0.0}

    started = time.monotonic()
    sem = asyncio.Semaphore(CONCURRENCY)
    done = resolved_n = 0

    async with httpx.AsyncClient() as client:
        tasks = [_resolve_one(item, client, sem) for item in queue]
        for coro in asyncio.as_completed(tasks):
            item, result = await coro
            if _write_back(conn, item, result, transcripts):
                resolved_n += 1
            done += 1
            if not quiet and (done % 25 == 0 or done == len(queue)):
                rate = done / max(time.monotonic() - started, 1e-9) * 60
                print(f"  {done}/{len(queue)}  resolved {resolved_n}"
                      f"  ({resolved_n / done:.0%})  ~{rate:.0f}/min", flush=True)

    return {
        "attempted": done,
        "resolved": resolved_n,
        "failed": done - resolved_n,
        "seconds": time.monotonic() - started,
    }


def _print_stats(s: dict) -> None:
    print(f"library total        : {s['total']}")
    print(f"  resolved           : {s['resolved']}  ({s['hit_rate']:.0%})")
    print(f"  still to try       : {s['remaining']}")
    print(f"  given up on        : {s['gave_up']}  (failed {MAX_ATTEMPTS}x)")
    yf = s.get("youtube_formats") or {}
    if yf:
        print(f"YouTube resolved     : {yf.get('short', 0)} Shorts, "
              f"{yf.get('video', 0)} long videos, {yf.get('unknown', 0)} not yet known")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=100,
                    help="how many to attempt this run (default 100)")
    ap.add_argument("--all", action="store_true",
                    help="keep going until nothing is left to try")
    ap.add_argument("--stats", action="store_true", help="report and exit")
    ap.add_argument("--recheck", action="store_true",
                    help="re-test items an earlier run resolved to a placeholder")
    ap.add_argument("--no-transcripts", action="store_true",
                    help="skip YouTube caption tracks this run -- one extra request per "
                         "video, which adds up across a few thousand")
    ap.add_argument("--db", help="library path (default: $FAVORITES_DB)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    conn = db.connect(args.db)
    if args.stats:
        _print_stats(stats(conn))
        conn.close()
        return 0

    if args.recheck:
        fixed = requeue_placeholders(conn)
        print(f"placeholder titles cleared : {fixed['cleared_titles']}")
        print(f"put back in the queue      : {fixed['requeued']}\n")

    limit = None if args.all else args.limit
    result = asyncio.run(run(conn, limit, quiet=args.quiet,
                             transcripts=not args.no_transcripts))

    if result["attempted"] == 0:
        print("nothing left to resolve.")
    else:
        mins = result["seconds"] / 60
        print(f"\nattempted {result['attempted']} in {mins:.1f} min — "
              f"resolved {result['resolved']}, failed {result['failed']} "
              f"({result['resolved'] / result['attempted']:.0%} hit rate)")
    print()
    _print_stats(stats(conn))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
