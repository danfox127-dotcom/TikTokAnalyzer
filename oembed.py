import os
import re
import time
import json
import httpx
import asyncio
import logging
from typing import Optional
from collections import OrderedDict

try:
    import redis.asyncio as redis_async
except ImportError:
    redis_async = None

logger = logging.getLogger(__name__)

# Retry/backoff defaults
DEFAULT_TIMEOUT = 6.0
MAX_RETRIES = 3
BACKOFF_FACTOR = 0.5

# Simple in-memory TTL LRU cache for oEmbed results (async-safe)
# Use environment variables to tune behavior in dev/production.
OEMBED_CACHE_TTL = int(os.environ.get("OEMBED_CACHE_TTL", "3600"))
OEMBED_CACHE_MAX = int(os.environ.get("OEMBED_CACHE_MAX", "2000"))

# Redis configuration
REDIS_URL = os.environ.get("REDIS_URL")
if REDIS_URL and redis_async:
    redis_client = redis_async.from_url(REDIS_URL, decode_responses=True)
    logger.info("oEmbed cache will use Redis at %s", REDIS_URL)
else:
    redis_client = None
    logger.info("oEmbed cache will use local in-memory LRU")

# cache: OrderedDict[key -> (expiry_timestamp, value_dict)]
_cache: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()
_cache_lock = asyncio.Lock()

# Simple metrics for cache observability
_metrics = {"hits": 0, "misses": 0, "evictions": 0}


async def _cache_get(key: str) -> Optional[dict]:
    if redis_client:
        try:
            val = await redis_client.get(f"oembed:{key}")
            if val:
                _metrics["hits"] += 1
                return json.loads(val)
            _metrics["misses"] += 1
            return None
        except Exception as e:
            logger.warning("Redis get error for %s: %s", key, e)
            _metrics["misses"] += 1
            return None

    async with _cache_lock:
        entry = _cache.get(key)
        if not entry:
            _metrics["misses"] += 1
            return None
        expiry, value = entry
        if time.time() > expiry:
            # expired
            try:
                _cache.pop(key)
            except Exception:
                pass
            _metrics["misses"] += 1
            return None
        # move to end (most recently used)
        try:
            _cache.move_to_end(key)
        except Exception:
            pass
        # return a shallow copy to avoid accidental mutation
        _metrics["hits"] += 1
        return dict(value)


async def _cache_set(key: str, value: dict) -> None:
    if redis_client:
        try:
            await redis_client.setex(f"oembed:{key}", OEMBED_CACHE_TTL, json.dumps(value))
            return
        except Exception as e:
            logger.warning("Redis set error for %s: %s", key, e)
            return

    expiry = time.time() + OEMBED_CACHE_TTL
    async with _cache_lock:
        if key in _cache:
            try:
                _cache.pop(key)
            except Exception:
                pass
        # Evict oldest until under max
        while len(_cache) >= OEMBED_CACHE_MAX:
            try:
                _cache.popitem(last=False)
                _metrics["evictions"] += 1
            except Exception:
                break
        _cache[key] = (expiry, dict(value))


def get_cache_metrics() -> dict:
    """Return a shallow copy of cache metrics."""
    return dict(_metrics)

def extract_video_id(url: str) -> Optional[str]:
    if not url:
        return None
    match = re.search(r'/video/(\d+)', url)
    if match:
        return match.group(1)
    return None

async def _expand_short_url_if_needed(identifier: str, client: httpx.AsyncClient) -> str:
    """
    If `identifier` looks like a URL (short tiktok links, vm.tiktok.com, or full tiktok URL),
    follow redirects to the final URL and try to extract the numeric video id.
    If expansion fails, return the original identifier.
    """
    if identifier.startswith("http") or "vm.tiktok.com" in identifier or "tiktok.com" in identifier:
        try:
            # Try HEAD first to follow redirects cheaply; fall back to GET if HEAD is unsupported.
            resp = await client.head(identifier, follow_redirects=True, timeout=DEFAULT_TIMEOUT)
            final = str(resp.url)
        except Exception:
            try:
                resp = await client.get(identifier, follow_redirects=True, timeout=DEFAULT_TIMEOUT)
                final = str(resp.url)
            except Exception as exc:
                logger.debug("Short-url expansion failed for %s: %s", identifier, exc)
                return identifier
        vid = extract_video_id(final)
        if vid:
            return vid
        # Fallback: try to find /video/<id> in the HTML body if allowed
        try:
            text = resp.text if resp is not None else ""
            m = re.search(r'/video/(\d+)', text)
            if m:
                return m.group(1)
        except Exception:
            pass
        return identifier
    return identifier

async def fetch_oembed(video_id: str, client: httpx.AsyncClient) -> dict:
    """
    Fetch oEmbed for a given video id or URL. Returns a result dict containing:
      - video_id: original identifier (or resolved id)
      - status: 'ok' or 'failed'
      - data: metadata dict when status == 'ok'
      - error: optional error message when failed
    """
    # Resolve short/redirecting URLs to a numeric id when possible
    resolved = video_id
    try:
        resolved = await _expand_short_url_if_needed(video_id, client)
    except Exception as e:
        logger.debug("Error expanding url %s: %s", video_id, e)

    # If resolved is not purely digits, try to extract numeric id from it
    numeric = extract_video_id(resolved) or (resolved if resolved.isdigit() else None)
    if numeric:
        resolved_id = numeric
    else:
        # last resort, use the original identifier
        resolved_id = resolved

    oembed_url = f"https://www.tiktok.com/oembed?url=https://www.tiktok.com/@user/video/{resolved_id}"

    # Check cache first
    try:
        cached = await _cache_get(resolved_id)
        if cached is not None:
            return cached
    except Exception:
        # cache failures should not block fetch
        pass

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.get(oembed_url, timeout=DEFAULT_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                result = {
                    "video_id": resolved_id,
                    "status": "ok",
                    "data": {
                        "title": data.get("title", ""),
                        "author": data.get("author_unique_id", ""),
                        "author_name": data.get("author_name", ""),
                        "thumbnail": data.get("thumbnail_url", "")
                    },
                    "error": None,
                }
                # cache successful result
                try:
                    await _cache_set(resolved_id, result)
                except Exception:
                    pass
                return result
            # Treat 4xx/5xx as transient on some codes (e.g., 429) and retry
            last_exc = f"status={resp.status_code}"
            if resp.status_code < 500 and resp.status_code != 429:
                # non-retryable client error (except 429)
                break
        except Exception as e:
            last_exc = str(e)
        # backoff before next retry
        await asyncio.sleep(BACKOFF_FACTOR * (2 ** (attempt - 1)))

    logger.debug("oEmbed fetch failed for %s (%s)", video_id, last_exc)
    result = {
        "video_id": resolved_id,
        "status": "failed",
        "data": {
            "title": "Title Hidden",
            "author": "Unknown",
            "author_name": "Unknown",
            "thumbnail": ""
        },
        "error": str(last_exc) if last_exc else "fetch_failed",
    }
    try:
        await _cache_set(resolved_id, result)
    except Exception:
        pass
    return result

async def fetch_many(video_ids: list[str], concurrency: int = 8) -> list[dict]:
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_with_semaphore(video_id, client):
        async with semaphore:
            return await fetch_oembed(video_id, client)

    async with httpx.AsyncClient() as client:
        tasks = [fetch_with_semaphore(vid, client) for vid in video_ids]
        results = await asyncio.gather(*tasks)
        return results
