"""
Cross-platform entity resolution — TikTok creator → YouTube channel (PROTOTYPE).

Hop 2 of the bridge described in the early concept notes:
    TikTok video id --(oembed)--> @handle --(this module)--> YouTube channel tags

Creators reuse the same @handle across TikTok / YouTube Shorts for branding, so
we look the handle up on YouTube and pull *topical* signal (channel title,
description, keywords, topic categories). This is the publicly-buildable version
of the concept: it yields topic/interest tags, NOT the facial/demographic CV tags
the original chat fantasised about (those live in Google-internal systems).

Two modes, auto-selected:
  • API mode   — when YOUTUBE_API_KEY is set: search.list + channels.list with
                 topicDetails (clean Wikipedia topic categories) + statistics.
  • Keyless    — fallback: GET youtube.com/@handle and scrape og:title /
                 og:description / keywords / subscriber count. No key required,
                 so the prototype runs out of the box, but it is best-effort.

Caveat carried in every result: a handle match is NOT identity proof. Different
people can hold the same handle on different platforms (collision). We surface a
`match` confidence and, when a TikTok display name is supplied, upgrade it.

Mirrors utils/oembed.py: async httpx, TTL/LRU cache (+ optional Redis), fetch_many.
"""
import os
import re
import json
import time
import html
import asyncio
import logging
from typing import Optional
from collections import OrderedDict

import httpx

try:
    import redis.asyncio as redis_async
except ImportError:
    redis_async = None

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 8.0
MAX_RETRIES = 2
BACKOFF_FACTOR = 0.5
_UA = "Mozilla/5.0 (compatible; AlgorithmicMirror/0.1 cross-platform-entity-resolution-prototype)"

YT_API_KEY = os.environ.get("YOUTUBE_API_KEY")
CACHE_TTL = int(os.environ.get("YT_BRIDGE_CACHE_TTL", "86400"))  # channels change slowly
CACHE_MAX = int(os.environ.get("YT_BRIDGE_CACHE_MAX", "2000"))

REDIS_URL = os.environ.get("REDIS_URL")
redis_client = redis_async.from_url(REDIS_URL, decode_responses=True) if (REDIS_URL and redis_async) else None

_cache: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()
_cache_lock = asyncio.Lock()
_metrics = {"hits": 0, "misses": 0, "evictions": 0}


# --------------------------------------------------------------------------- #
# cache (mirrors oembed.py)
# --------------------------------------------------------------------------- #
async def _cache_get(key: str) -> Optional[dict]:
    if redis_client:
        try:
            val = await redis_client.get(f"ytbridge:{key}")
            if val:
                _metrics["hits"] += 1
                return json.loads(val)
            _metrics["misses"] += 1
            return None
        except Exception as e:
            logger.warning("Redis get error for %s: %s", key, e)
            return None
    async with _cache_lock:
        entry = _cache.get(key)
        if not entry:
            _metrics["misses"] += 1
            return None
        expiry, value = entry
        if time.time() > expiry:
            _cache.pop(key, None)
            _metrics["misses"] += 1
            return None
        _cache.move_to_end(key)
        _metrics["hits"] += 1
        return dict(value)


async def _cache_set(key: str, value: dict) -> None:
    if redis_client:
        try:
            await redis_client.setex(f"ytbridge:{key}", CACHE_TTL, json.dumps(value))
        except Exception as e:
            logger.warning("Redis set error for %s: %s", key, e)
        return
    async with _cache_lock:
        _cache.pop(key, None)
        while len(_cache) >= CACHE_MAX:
            try:
                _cache.popitem(last=False)
                _metrics["evictions"] += 1
            except Exception:
                break
        _cache[key] = (time.time() + CACHE_TTL, dict(value))


def get_cache_metrics() -> dict:
    return dict(_metrics)


def is_enabled() -> bool:
    """The bridge is opt-in. Enabled by an explicit flag or by providing an API key."""
    return bool(YT_API_KEY) or os.environ.get("ENABLE_YOUTUBE_BRIDGE", "").lower() in ("1", "true", "yes")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def normalize_handle(handle: str) -> str:
    """@dakota.johnson / 'Dakota Johnson' -> 'dakotajohnson' style YT handle guess."""
    if not handle:
        return ""
    h = handle.strip().lstrip("@").strip()
    # YouTube handles allow a-z0-9._- ; drop everything else (spaces, emoji)
    return re.sub(r"[^a-zA-Z0-9._-]", "", h)


def _topics_from_wikipedia_urls(urls: list[str]) -> list[str]:
    """topicDetails returns Wikipedia URLs; turn the last path segment into a label."""
    out = []
    for u in urls or []:
        seg = u.rstrip("/").rsplit("/", 1)[-1]
        label = seg.replace("_", " ").strip()
        if label and label not in out:
            out.append(label)
    return out


def _name_similarity(a: str, b: str) -> float:
    """Cheap token-overlap similarity for display-name vs YT title (0..1)."""
    ta = {t for t in re.split(r"\W+", (a or "").lower()) if t}
    tb = {t for t in re.split(r"\W+", (b or "").lower()) if t}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# --------------------------------------------------------------------------- #
# keyless lookup (default — no API key needed)
# --------------------------------------------------------------------------- #
# YouTube injects these site-wide default meta keywords on channels that set none.
# Treat their presence as "no custom keywords" rather than real topic signal.
_YT_DEFAULT_KEYWORDS = {"video", "sharing", "camera phone", "video phone", "free", "upload"}


def _search(pattern: str, text: str) -> Optional[str]:
    m = re.search(pattern, text)
    return html.unescape(m.group(1)) if m else None


async def _keyless_lookup(handle: str, client: httpx.AsyncClient) -> Optional[dict]:
    url = f"https://www.youtube.com/@{handle}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.get(url, headers={"User-Agent": _UA}, follow_redirects=True, timeout=DEFAULT_TIMEOUT)
            if resp.status_code == 404:
                return {"found": False}
            if resp.status_code == 200:
                t = resp.text
                title = _search(r'<meta property="og:title" content="([^"]*)"', t)
                if not title:
                    return {"found": False}
                desc = _search(r'<meta property="og:description" content="([^"]*)"', t) or ""
                keywords = _search(r'<meta name="keywords" content="([^"]*)"', t) or ""
                subs = _search(r'"subscriberCountText".*?"simpleText":"([^"]*)"', t)
                kw_tags = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []
                # drop YouTube's default-keyword boilerplate (means the channel set none)
                if {k.lower() for k in kw_tags} <= _YT_DEFAULT_KEYWORDS:
                    kw_tags = []
                kw_tags = kw_tags[:12]
                return {
                    "found": True,
                    "channel_title": title,
                    "channel_url": str(resp.url),
                    "description": desc[:280],
                    "topics": kw_tags,           # keyless: channel keywords stand in for topics
                    "subscriber_text": subs or "",
                    "source": "keyless",
                }
            last = f"status={resp.status_code}"
            if resp.status_code < 500 and resp.status_code != 429:
                break
        except Exception as e:
            last = str(e)
        await asyncio.sleep(BACKOFF_FACTOR * (2 ** (attempt - 1)))
    logger.debug("YT keyless lookup failed for @%s (%s)", handle, locals().get("last"))
    return None


# --------------------------------------------------------------------------- #
# API lookup (when YOUTUBE_API_KEY is set)
# --------------------------------------------------------------------------- #
async def _api_lookup(handle: str, client: httpx.AsyncClient) -> Optional[dict]:
    base = "https://www.googleapis.com/youtube/v3"
    try:
        # forHandle is the modern, quota-cheap channel lookup (1 unit vs 100 for search)
        r = await client.get(
            f"{base}/channels",
            params={"part": "snippet,topicDetails,statistics", "forHandle": handle, "key": YT_API_KEY},
            timeout=DEFAULT_TIMEOUT,
        )
        if r.status_code != 200:
            logger.debug("YT API channels error %s for @%s: %s", r.status_code, handle, r.text[:200])
            return None
        items = r.json().get("items") or []
        if not items:
            return {"found": False}
        ch = items[0]
        sn = ch.get("snippet", {})
        stats = ch.get("statistics", {})
        topics = _topics_from_wikipedia_urls(ch.get("topicDetails", {}).get("topicCategories", []))
        return {
            "found": True,
            "channel_title": sn.get("title", ""),
            "channel_url": f"https://www.youtube.com/channel/{ch.get('id', '')}",
            "description": (sn.get("description") or "")[:280],
            "topics": topics,
            "subscriber_text": stats.get("subscriberCount", ""),
            "source": "api",
        }
    except Exception as e:
        logger.debug("YT API lookup failed for @%s: %s", handle, e)
        return None


# --------------------------------------------------------------------------- #
# public entrypoints
# --------------------------------------------------------------------------- #
async def resolve_handle(handle: str, client: httpx.AsyncClient, display_name: str = "") -> dict:
    """
    Resolve a TikTok @handle to a YouTube channel.

    Returns: {handle, status: 'ok'|'not_found'|'failed', match, data, error}
      match: 'name_verified' (handle + display-name agree) | 'handle_only' | None
    """
    norm = normalize_handle(handle)
    if not norm:
        return {"handle": handle, "status": "failed", "match": None, "data": None, "error": "empty_handle"}

    cache_key = norm.lower()
    cached = await _cache_get(cache_key)
    if cached is not None:
        return cached

    raw = await (_api_lookup(norm, client) if YT_API_KEY else _keyless_lookup(norm, client))

    if raw is None:
        result = {"handle": handle, "status": "failed", "match": None, "data": None, "error": "lookup_failed"}
        # do not cache transient failures
        return result

    if not raw.get("found"):
        result = {"handle": handle, "status": "not_found", "match": None, "data": None, "error": None}
        await _cache_set(cache_key, result)
        return result

    sim = _name_similarity(display_name, raw.get("channel_title", "")) if display_name else 0.0
    match = "name_verified" if sim >= 0.5 else "handle_only"
    result = {
        "handle": handle,
        "status": "ok",
        "match": match,
        "name_similarity": round(sim, 2),
        "data": raw,
        "error": None,
    }
    await _cache_set(cache_key, result)
    return result


async def resolve_many(handles: list[str], concurrency: int = 4, display_names: Optional[dict] = None) -> list[dict]:
    """Resolve many handles. `display_names` maps handle -> tiktok display name (optional)."""
    display_names = display_names or {}
    sem = asyncio.Semaphore(concurrency)

    async def one(handle, client):
        async with sem:
            return await resolve_handle(handle, client, display_names.get(handle, ""))

    async with httpx.AsyncClient() as client:
        return await asyncio.gather(*[one(h, client) for h in handles])
