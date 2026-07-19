"""
WP-2.1 Semantic Topic Engine — server side.

BYOK title clustering: the client sends {video_id, weight} pairs, we fetch the
public titles via oEmbed and relay them to the user's own LLM for structured-
output clustering, validate against the schema (traceability: every returned
video_id must be one we sent), and cache by content hash so re-runs are free.
"""
from __future__ import annotations

import hashlib
import json
import os

PROMPT_VERSION = "topics-v1"
LLM_CONFIDENCE = 0.7

_TAXONOMY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "tiktok-ad-taxonomy.json",
)
_taxonomy_names_cache: list[str] | None = None


def cache_key(videos: list[dict], prompt_version: str) -> str:
    """Order-independent content hash of the (video_id, weight) set + prompt version."""
    pairs = sorted((str(v["video_id"]), round(float(v.get("weight", 0.0)), 4)) for v in videos)
    blob = json.dumps({"pv": prompt_version, "pairs": pairs}, separators=(",", ":"))
    return "topics:" + prompt_version + ":" + hashlib.sha256(blob.encode()).hexdigest()


def taxonomy_names() -> list[str]:
    """The category names advertisers buy against, from the committed taxonomy file."""
    global _taxonomy_names_cache
    if _taxonomy_names_cache is None:
        with open(_TAXONOMY_PATH) as f:
            data = json.load(f)
        _taxonomy_names_cache = [c["name"] for c in data["categories"] if c.get("name")]
    return _taxonomy_names_cache


def validate_clusters(raw: object, input_ids: set[str]) -> list[dict]:
    """Schema + traceability. Drops empty-name clusters and any video_id we didn't
    send; normalizes each cluster to the full contract. Raises ValueError if `raw`
    is not a list."""
    if not isinstance(raw, list):
        raise ValueError("clusters payload must be a JSON array")
    out: list[dict] = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name", "")).strip()
        if not name:
            continue
        vids = [str(v) for v in (c.get("video_ids") or []) if str(v) in input_ids]
        hint = c.get("taxonomy_hint")
        out.append({
            "name": name,
            "video_ids": vids,
            "taxonomy_hint": hint if isinstance(hint, str) and hint.strip() else None,
            "confidence": LLM_CONFIDENCE,
            "evidence_kind": "video",
        })
    return out
