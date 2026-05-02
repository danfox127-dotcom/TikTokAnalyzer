"""
Algorithmic Forensics — FastAPI Micro-Backend
Headless threat assessment engine for the Next.js frontend.
"""
import sys
import os

# Ensure repo root is on the path when running from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from typing import Optional
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import json
from datetime import date as _date
import asyncio

import anthropic
import google.generativeai as genai

from parsers.tiktok import parse_tiktok_export_from_bytes
from ghost_profile import build_ghost_profile
from exporters.llm_export import generate_llm_export
from api.narratives import build_narrative_blocks
from utils.ip_geo import enrich_logins_with_geo
import oembed
import psychographic

_LLM_EXPORT_MAX_BYTES = 100 * 1024 * 1024  # 100 MB

# ---------------------------------------------------------------------------
# App & CORS
# ---------------------------------------------------------------------------

_DEFAULT_ORIGINS = "http://localhost:3000,http://localhost:3001,http://localhost:3005"
_allowed_origins = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]

app = FastAPI(
    title="Algorithmic Forensics API",
    description="Threat assessment engine — exposes how the algorithm sees you.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-process metrics (counters)
_metrics = {
    "enrich_requests_total": 0,
    "enrich_requested_videos_total": 0,
    "enrich_fetched_videos_total": 0,
}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "online", "service": "algorithmic-forensics-api"}


@app.get("/metrics")
async def metrics():
    """Prometheus-style plaintext metrics for quick scraping.
    Contains basic enrich counters and oEmbed cache metrics.
    """
    try:
        cache_metrics = oembed.get_cache_metrics()
    except Exception:
        cache_metrics = {"hits": 0, "misses": 0, "evictions": 0}

    lines = [
        "# HELP algorithmic_enrich_requests_total Number of /api/enrich calls",
        "# TYPE algorithmic_enrich_requests_total counter",
        f"algorithmic_enrich_requests_total {_metrics.get('enrich_requests_total', 0)}",
        "# HELP algorithmic_enrich_requested_videos_total Total requested video ids",
        "# TYPE algorithmic_enrich_requested_videos_total counter",
        f"algorithmic_enrich_requested_videos_total {_metrics.get('enrich_requested_videos_total', 0)}",
        "# HELP algorithmic_enrich_fetched_videos_total Total successfully fetched oEmbed responses",
        "# TYPE algorithmic_enrich_fetched_videos_total counter",
        f"algorithmic_enrich_fetched_videos_total {_metrics.get('enrich_fetched_videos_total', 0)}",
        "# HELP algorithmic_oembed_cache_hits Cache hits",
        "# TYPE algorithmic_oembed_cache_hits counter",
        f"algorithmic_oembed_cache_hits {cache_metrics.get('hits', 0)}",
        "# HELP algorithmic_oembed_cache_misses Cache misses",
        "# TYPE algorithmic_oembed_cache_misses counter",
        f"algorithmic_oembed_cache_misses {cache_metrics.get('misses', 0)}",
        "# HELP algorithmic_oembed_cache_evictions Cache evictions",
        "# TYPE algorithmic_oembed_cache_evictions counter",
        f"algorithmic_oembed_cache_evictions {cache_metrics.get('evictions', 0)}",
    ]

    return PlainTextResponse("\n".join(lines), media_type="text/plain; version=0.0.4")


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    sleep_start: Optional[int] = Query(None, ge=0, le=23, description="Sleep window start hour (0–23)"),
    sleep_end: Optional[int] = Query(None, ge=0, le=23, description="Sleep window end hour (0–23)"),
):
    """
    Accept a TikTok user_data_tiktok.json upload and return the Ghost Profile payload.
    Pass ?sleep_start=1&sleep_end=7 to exclude a custom sleep window from behavioral metrics.
    Supports wrap-around (e.g. sleep_start=22, sleep_end=6 covers 10PM–6AM).
    """
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be a .json export.")

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        parsed = parse_tiktok_export_from_bytes(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse export: {exc}")

    if sleep_start is not None and sleep_end is not None:
        if sleep_start <= sleep_end:
            exclude_hours = tuple(range(sleep_start, sleep_end + 1))
        else:
            # Wrap-around midnight (e.g. 11PM–6AM)
            exclude_hours = tuple(range(sleep_start, 24)) + tuple(range(0, sleep_end + 1))
    else:
        exclude_hours = ()

    ghost_profile = build_ghost_profile(parsed, exclude_hours=exclude_hours)

    # Enrich recent_logins with geolocation data (async, cached, fallback-safe)
    raw_logins: list[dict] = ghost_profile.get("digital_footprint", {}).get("recent_logins", [])
    if raw_logins:
        enriched_logins = await enrich_logins_with_geo(raw_logins)
        ghost_profile["digital_footprint"]["recent_logins"] = enriched_logins

    narrative_blocks = build_narrative_blocks(ghost_profile, parsed)

    return {**ghost_profile, "narrative_blocks": narrative_blocks}


@app.post("/api/export/llm")
async def export_llm(file: UploadFile = File(...)):
    """
    Parse a TikTok export and return a privacy-safe LLM analysis JSON.
    Suitable for uploading directly to Claude.ai or Gemini.
    """
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be a .json export.")

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw) > _LLM_EXPORT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 100 MB).")

    try:
        parsed = parse_tiktok_export_from_bytes(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse export: {exc}")

    ghost = build_ghost_profile(parsed)
    payload = generate_llm_export(parsed, ghost)

    filename = f"tiktok_analysis_{_date.today().isoformat()}.json"
    content = json.dumps(payload, indent=2, ensure_ascii=False)

    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/analyze/llm")
async def analyze_llm(
    file: UploadFile = File(...),
    provider: str = Query(..., pattern="^(claude|gemini-pro|gemini-flash)$"),
    api_key: str = Query(...),
):
    """
    Stream an LLM analysis of the TikTok behavioral profile using a user-provided API key.
    The key is used only for this request and never logged or stored.
    """
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be a .json export.")

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        parsed = parse_tiktok_export_from_bytes(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse export: {exc}")

    ghost = build_ghost_profile(parsed)
    payload = generate_llm_export(parsed, ghost)
    
    # Construct the prompt
    meta = payload["_meta"]
    profile_json = json.dumps(payload, indent=2, ensure_ascii=False)
    
    prompt = (
        f"{meta['instructions_for_llm']}\n\n"
        f"DATA_EXPORT_JSON:\n{profile_json}\n\n"
        f"{meta['suggested_opening']}"
    )

    async def stream_claude():
        try:
            client = anthropic.AsyncAnthropic(api_key=api_key)
            async with client.messages.stream(
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
                model="claude-4-5-opus-latest",
            ) as stream:
                async for text in stream.text_stream:
                    yield f"data: {text}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"

    async def stream_gemini(model_name: str):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            # generate_content_async with stream=True
            response = await model.generate_content_async(prompt, stream=True)
            async for chunk in response:
                if chunk.text:
                    yield f"data: {chunk.text}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"

    if provider == "claude":
        return StreamingResponse(stream_claude(), media_type="text/event-stream")
    elif provider == "gemini-pro":
        return StreamingResponse(stream_gemini("gemini-3.1-pro"), media_type="text/event-stream")
    else: # gemini-flash
        return StreamingResponse(stream_gemini("gemini-3.1-flash"), media_type="text/event-stream")


class EnrichRequest(BaseModel):
    lingered: list[dict]
    graveyard: list[dict]
    sandbox: list[dict]
    night_lingered: list[dict]
    following_usernames: list[str]


@app.post("/api/enrich")
async def enrich(req: EnrichRequest):
    buckets = {
        "lingered": req.lingered,
        "graveyard": req.graveyard,
        "sandbox": req.sandbox,
        "night_lingered": req.night_lingered,
    }

    all_ids: list[str] = []
    seen: set[str] = set()
    for events in buckets.values():
        for ev in events:
            vid = ev.get("video_id")
            if vid and vid not in seen:
                seen.add(vid)
                all_ids.append(vid)

    fetched_results = await oembed.fetch_many(all_ids, concurrency=8)
    # Map of video_id -> result dict returned by oembed.fetch_oembed
    results_map: dict[str, dict] = {r["video_id"]: r for r in fetched_results if r.get("video_id")}
    # videos_map keeps only the metadata (data) for easy merging into events
    videos_map: dict[str, dict] = {vid: (res.get("data") or {}) for vid, res in results_map.items()}
    # Per-video status summary for UI/diagnostics
    video_results: dict[str, dict] = {vid: {"status": res.get("status"), "error": res.get("error")} for vid, res in results_map.items()}

    enriched: dict[str, list[dict]] = {}
    for key, events in buckets.items():
        enriched_list = []
        for ev in events:
            vid = ev.get("video_id")
            if not vid:
                continue
            meta = videos_map.get(vid, {"title": "Title Hidden", "author": "Unknown", "author_name": "Unknown", "thumbnail": ""})
            enriched_list.append({**ev, **meta})
        enriched[key] = enriched_list[:24]

    def top_creators(items: list[dict], limit: int = 12) -> list[dict]:
        agg: dict[str, dict] = {}
        for it in items:
            author = (it.get("author") or "").lower()
            if not author:
                continue
            if author not in agg:
                agg[author] = {"author": author, "author_name": it.get("author_name") or author, "count": 0}
            agg[author]["count"] += 1
        return sorted(agg.values(), key=lambda x: x["count"], reverse=True)[:limit]

    following_set = {u.lower().lstrip("@") for u in req.following_usernames}
    followed_n = 0
    algo_n = 0
    for key in ("lingered", "sandbox", "graveyard"):
        for it in enriched[key]:
            author = (it.get("author") or "").lower().lstrip("@")
            if not author:
                continue
            if author in following_set:
                followed_n += 1
            else:
                algo_n += 1
    matched = followed_n + algo_n
    if matched > 0:
        followed_pct = round((followed_n / matched) * 100, 1)
        algo_pct = round((algo_n / matched) * 100, 1)
    else:
        followed_pct = 0.0
        algo_pct = 0.0

    def titles(items: list[dict]) -> list[str]:
        return [it.get("title", "") for it in items if it.get("title")]

    fetched_ok = sum(1 for r in fetched_results if r.get("status") == "ok")
    # update simple enrich counters
    try:
        _metrics["enrich_requests_total"] += 1
        _metrics["enrich_requested_videos_total"] += len(all_ids)
        _metrics["enrich_fetched_videos_total"] += fetched_ok
    except Exception:
        pass

    # include simple cache metrics from oembed helper
    try:
        cache_metrics = oembed.get_cache_metrics()
    except Exception:
        cache_metrics = {"hits": 0, "misses": 0, "evictions": 0}

    # ── Theme extraction ──────────────────────────────────────────────────────
    psychographic_themes = psychographic.extract_themes(titles(enriched["lingered"]))
    anti_profile_themes  = psychographic.extract_themes(titles(enriched["graveyard"]))
    sandbox_themes       = psychographic.extract_themes(titles(enriched["sandbox"]))
    night_themes         = psychographic.extract_themes(titles(enriched["night_lingered"]))

    # ── Anti-profile signature (rejection contrast) ───────────────────────────
    anti_signature = psychographic.build_anti_profile_signature(
        anti_keywords=anti_profile_themes["top_keywords"],
        pro_keywords=psychographic_themes["top_keywords"],
    )

    # ── Per-pillar narratives (deterministic) ────────────────────────────────
    def _narrative(pillar: str, themes: dict, bucket_items: list[dict]) -> dict:
        sample_titles = [it.get("title", "") for it in bucket_items if it.get("title")]
        return psychographic.build_pillar_narrative(
            pillar=pillar,
            keywords=themes["top_keywords"],
            phrases=themes["top_phrases"],
            emojis=themes["top_emojis"],
            sample_titles=sample_titles,
        )

    themes_out = {
        "psychographic": {
            **psychographic_themes,
            "narrative": _narrative("psychographic", psychographic_themes, enriched["lingered"]),
        },
        "anti_profile": {
            **anti_profile_themes,
            "raw": anti_profile_themes["top_keywords"],
            "signature": anti_signature,
            "narrative": _narrative("anti_profile", anti_profile_themes, enriched["graveyard"]),
        },
        "sandbox": {
            **sandbox_themes,
            "narrative": _narrative("sandbox", sandbox_themes, enriched["sandbox"]),
        },
        "night": {
            **night_themes,
            "narrative": _narrative("night", night_themes, enriched["night_lingered"]),
        },
    }

    return {
        "videos": enriched,
        "video_results": video_results,
        "cache_metrics": cache_metrics,
        "top_creators": {
            "lingered": top_creators(enriched["lingered"]),
            "graveyard": top_creators(enriched["graveyard"]),
        },
        "themes": themes_out,
        "following_ratio": {
            "followed_pct": followed_pct,
            "algorithmic_pct": algo_pct,
            "matched_videos": matched,
        },
        "fetched_count": fetched_ok,
        "requested_count": len(all_ids),
    }
