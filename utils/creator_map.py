"""
Durable video_id -> creator identity map for incremental, rate-limit-friendly fill.

TikTok strips @handles from export links and rate-limits oEmbed, so resolving all
watch-history videos in one request is infeasible (measured ~5 min / 60 videos
under throttle). This map persists every resolved handle FOREVER (Redis), so each
analyze run only needs to resolve a small budget of *still-unresolved* videos;
coverage grows across runs without ever re-paying for a known creator.

  • Hits  -> stored without expiry: {handle, display_name, thumbnail}
  • Misses-> stored with a short TTL so transient failures retry later
  • No Redis -> process-local dict fallback (no cross-restart persistence)

Resolution is time-boxed so it can never hang /api/analyze beyond a deadline.
"""
import os
import json
import time
import asyncio
import logging
from typing import Optional

import httpx

from utils import oembed

try:
    import redis.asyncio as redis_async
except ImportError:
    redis_async = None

logger = logging.getLogger(__name__)

# Per-run resolution controls (all env-tunable)
RESOLVE_BUDGET = int(os.environ.get("CREATOR_RESOLVE_BUDGET", "40"))      # max new videos per run
RESOLVE_CONCURRENCY = int(os.environ.get("CREATOR_RESOLVE_CONCURRENCY", "3"))  # low → avoid throttle
RESOLVE_DEADLINE_S = float(os.environ.get("CREATOR_RESOLVE_DEADLINE_S", "45"))  # hard wall-time cap
MISS_TTL_S = int(os.environ.get("CREATOR_MISS_TTL_S", "604800"))         # retry misses after a week

_NS = "crmap:"
REDIS_URL = os.environ.get("REDIS_URL")
_redis = redis_async.from_url(REDIS_URL, decode_responses=True) if (REDIS_URL and redis_async) else None

# process-local fallback: vid -> (expiry_or_None, entry)
_local: dict[str, tuple[Optional[float], dict]] = {}

_MISS = {"status": "miss"}


def using_redis() -> bool:
    return _redis is not None


async def _get(vid: str) -> Optional[dict]:
    if _redis:
        try:
            val = await _redis.get(f"{_NS}{vid}")
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning("creator_map redis get failed: %s", e)
            return None
    entry = _local.get(vid)
    if not entry:
        return None
    expiry, value = entry
    if expiry is not None and time.time() > expiry:
        _local.pop(vid, None)
        return None
    return value


async def _set(vid: str, value: dict, ttl: Optional[int]) -> None:
    if _redis:
        try:
            if ttl:
                await _redis.setex(f"{_NS}{vid}", ttl, json.dumps(value))
            else:
                await _redis.set(f"{_NS}{vid}", json.dumps(value))  # no expiry = permanent
        except Exception as e:
            logger.warning("creator_map redis set failed: %s", e)
        return
    _local[vid] = (time.time() + ttl if ttl else None, value)


async def get_known(video_ids: list[str]) -> dict[str, dict]:
    """Return {vid: entry} for videos already in the map (hits and recorded misses)."""
    out: dict[str, dict] = {}
    for vid in set(video_ids):
        e = await _get(vid)
        if e is not None:
            out[vid] = e
    return out


async def resolve_and_fill(
    video_ids: list[str],
    budget: int = RESOLVE_BUDGET,
    concurrency: int = RESOLVE_CONCURRENCY,
    deadline_s: float = RESOLVE_DEADLINE_S,
) -> dict:
    """
    Resolve up to `budget` still-unresolved video ids (time-boxed by `deadline_s`),
    persist results, and return the full known map + coverage stats.

    Returns:
      {
        "handles": {vid: handle},          # resolved hits only
        "meta": {vid: {handle, display_name, thumbnail}},
        "total": int, "resolved": int, "pct": float,
        "newly_resolved": int, "attempted": int, "timed_out": bool,
      }
    """
    unique = [v for v in dict.fromkeys(video_ids) if v]
    known = await get_known(unique)

    # Pick videos we've never recorded at all (skip hits AND fresh misses).
    unresolved = [v for v in unique if v not in known]
    targets = unresolved[:max(0, budget)]

    newly_resolved = 0
    timed_out = False
    if targets:
        try:
            results = await asyncio.wait_for(
                oembed.fetch_many(targets, concurrency=concurrency),
                timeout=deadline_s,
            )
        except asyncio.TimeoutError:
            timed_out = True
            results = []
            logger.info("creator_map: resolution hit %.0fs deadline; partial fill", deadline_s)

        for r in results:
            vid = r.get("video_id")
            if not vid:
                continue
            if r.get("status") == "ok" and (r.get("data") or {}).get("author") not in (None, "", "Unknown"):
                d = r["data"]
                entry = {
                    "status": "ok",
                    "handle": d["author"],
                    "display_name": d.get("author_name", ""),
                    "thumbnail": d.get("thumbnail", ""),
                }
                await _set(vid, entry, ttl=None)      # permanent
                known[vid] = entry
                newly_resolved += 1
            else:
                await _set(vid, _MISS, ttl=MISS_TTL_S)  # retry after TTL
                known[vid] = _MISS

    handles = {v: e["handle"] for v, e in known.items() if e.get("status") == "ok"}
    meta = {v: e for v, e in known.items() if e.get("status") == "ok"}
    total = len(unique)
    resolved = len(handles)
    return {
        "handles": handles,
        "meta": meta,
        "total": total,
        "resolved": resolved,
        "pct": round((resolved / total) * 100, 1) if total else 0.0,
        "newly_resolved": newly_resolved,
        "attempted": len(targets),
        "timed_out": timed_out,
    }
