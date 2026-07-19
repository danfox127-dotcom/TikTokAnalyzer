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

import anthropic
import google.generativeai as genai

from utils import oembed
from utils import creator_map

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


_CACHE_TTL_S = 60 * 60 * 24 * 30  # 30 days; results are content-hash keyed

# Reuse creator_map's async cache helpers — they already handle Redis (namespaced,
# decode_responses) AND the process-local (expiry, value)-tuple fallback correctly.
# Our keys start with "topics:" so there is no collision with creator entries.


def _build_prompt(weighted_titles: list[tuple[str, str, float]]) -> str:
    lines = "\n".join(f"- [{vid}] ({w:.0f}) {t}" for vid, t, w in weighted_titles)
    cats = ", ".join(taxonomy_names())
    return f"""You are grouping someone's watched TikTok video titles into topics.
Each title is prefixed with its id in [brackets], followed by a watch-weight in
parentheses — higher means they watched it longer.

TITLES:
{lines}

Cluster these into 3-8 topics. For each cluster give a short plain-English name,
and return the exact [id] values (as strings) of the titles belonging to that
cluster in its "video_ids" array — copy the ids verbatim from the brackets above,
do not invent or renumber them. Also pick the SINGLE closest category from this
advertiser taxonomy (or null if none fit):
{cats}

Respond with a JSON array only, no markdown:
[{{"name":"...","video_ids":["..."],"taxonomy_hint":"exact category name or null"}}]"""


async def _call_llm(prompt: str, api_key: str, provider: str) -> tuple[str, dict]:
    """Relay to the user's own LLM. Returns (raw_text, usage)."""
    if provider == "claude":
        client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            max_tokens=2048, model="claude-haiku-4-5",
            messages=[{"role": "user", "content": prompt}],
        )
        usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
        try:
            text = resp.content[0].text
        except (IndexError, AttributeError) as e:
            raise ValueError(f"empty or blocked LLM response: {e}")
        return text, usage
    if provider.startswith("gemini"):
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3-flash" if "flash" in provider else "gemini-3-pro")
        resp = await model.generate_content_async(prompt)
        try:
            text = resp.text
        except (IndexError, AttributeError) as e:
            raise ValueError(f"empty or blocked LLM response: {e}")
        return text, {"input_tokens": 0, "output_tokens": 0}
    raise ValueError(f"unknown provider: {provider}")


def _extract_json_array(raw_text: str) -> object:
    start, end = raw_text.find("["), raw_text.rfind("]") + 1
    if start == -1 or end <= start:
        raise ValueError("no JSON array in LLM response")
    return json.loads(raw_text[start:end])


async def cluster_topics(videos: list[dict], api_key: str, provider: str,
                         prompt_version: str = PROMPT_VERSION) -> dict:
    # Dedup by video_id, cap at 800.
    seen: dict[str, dict] = {}
    for v in videos:
        vid = str(v["video_id"])
        if vid not in seen:
            seen[vid] = {"video_id": vid, "weight": float(v.get("weight", 0.0))}
    deduped = list(seen.values())[:800]

    key = cache_key(deduped, prompt_version)
    hit = await creator_map._get(key)
    if hit is not None:
        return {**hit, "cached": True}

    fetched = await oembed.fetch_many([v["video_id"] for v in deduped])
    title_by_id = {r["video_id"]: (r.get("data") or {}).get("title", "") for r in fetched if r.get("video_id")}
    weighted = [(v["video_id"], title_by_id[v["video_id"]], v["weight"])
                for v in deduped if title_by_id.get(v["video_id"])]

    if not weighted:
        result = {"source": "llm", "clusters": [], "prompt_version": prompt_version,
                  "cached": False, "usage": {"input_tokens": 0, "output_tokens": 0}}
        return result

    input_ids = {v["video_id"] for v in deduped}
    prompt = _build_prompt(weighted)
    last_err: Exception | None = None
    for _ in range(2):  # one retry
        raw_text, usage = await _call_llm(prompt, api_key, provider)
        try:
            clusters = validate_clusters(_extract_json_array(raw_text), input_ids)
            break
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            clusters = None
    if clusters is None:
        raise ValueError(f"LLM returned unparseable clusters: {last_err}")

    result = {"source": "llm", "clusters": clusters, "prompt_version": prompt_version,
              "cached": False, "usage": usage}
    await creator_map._set(key, result, _CACHE_TTL_S)
    return result
