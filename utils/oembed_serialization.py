"""Helpers to normalize and (de)serialize oEmbed fetch results.

This module provides:
- `normalize_oembed_result` to convert raw results (e.g. from `oembed.fetch_oembed`)
  into a stable dictionary with known keys.
- `serialize_oembed_result` / `deserialize_oembed_result` for compact JSON roundtrips.

Usage:
    norm = normalize_oembed_result(raw)
    s = serialize_oembed_result(norm)
    obj = deserialize_oembed_result(s)
"""
import json
import time
from typing import Dict, Any


def _ensure_str(v: Any) -> str:
    """Coerce a value to a string, using '' for None or unrepresentable values."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    try:
        return str(v)
    except Exception:
        return ""


def normalize_oembed_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a raw oEmbed-like result into a stable structure.

    The returned dict always contains:
      - `video_id` (str)
      - `status` ("ok" or "failed")
      - `data` (dict with string keys: `title`, `author`, `author_name`, `thumbnail`)
      - `error` (str or None)
      - `fetched_at` (float timestamp)

    Sensible defaults are applied for missing fields.
    """
    raw = raw or {}
    # If there is an embedded `data` dict, prefer it for field lookups.
    data_src = raw.get("data") if isinstance(raw.get("data"), dict) else raw

    video_id = _ensure_str(
        raw.get("video_id")
        or raw.get("id")
        or data_src.get("video_id")
        or data_src.get("id")
        or ""
    )

    # Determine status: treat explicit 'failed' or presence of an error as failed.
    raw_status = raw.get("status")
    status = "ok"
    if isinstance(raw_status, str):
        s_l = raw_status.lower()
        if s_l in ("failed", "error"):
            status = "failed"
        else:
            status = "ok"
    elif raw.get("error") or raw.get("error_message") or raw.get("message"):
        status = "failed"

    title = _ensure_str(
        data_src.get("title")
        or raw.get("title")
        or data_src.get("name")
        or raw.get("name")
        or ""
    )

    author_name = _ensure_str(
        data_src.get("author_name")
        or raw.get("author_name")
        or data_src.get("author")
        or raw.get("author")
        or ""
    )

    author = _ensure_str(
        data_src.get("author")
        or raw.get("author")
        or data_src.get("author_name")
        or raw.get("author_name")
        or ""
    )

    thumbnail = _ensure_str(
        data_src.get("thumbnail")
        or data_src.get("thumbnail_url")
        or raw.get("thumbnail_url")
        or raw.get("thumbnail")
        or ""
    )

    # Error message only meaningful when failed; keep None otherwise.
    if status == "failed":
        err = raw.get("error") or raw.get("error_message") or raw.get("message")
        error = _ensure_str(err) if err is not None else None
    else:
        error = None

    fetched_at_raw = raw.get("fetched_at")
    try:
        fetched_at = float(fetched_at_raw) if fetched_at_raw is not None else time.time()
    except Exception:
        fetched_at = time.time()

    return {
        "video_id": video_id,
        "status": status,
        "data": {
            "title": title,
            "author": author,
            "author_name": author_name,
            "thumbnail": thumbnail,
        },
        "error": error,
        "fetched_at": fetched_at,
    }


def serialize_oembed_result(obj: Dict[str, Any]) -> str:
    """
    Serialize a normalized oEmbed result to a compact, ASCII-safe JSON string.

    Uses separators=(',',':') to keep the string compact.
    """
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":"))


def deserialize_oembed_result(s: str) -> Dict[str, Any]:
    """Deserialize a JSON string produced by `serialize_oembed_result`."""
    return json.loads(s)
