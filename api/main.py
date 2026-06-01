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
import logging
from datetime import date as _date
import asyncio

# Load .env before importing modules that read env vars (REDIS_URL, etc.) at
# import time — utils.oembed / utils.creator_map create their Redis clients on
# import, so the variables must be present beforehand.
from dotenv import load_dotenv
# Explicit repo-root path (robust to CWD; avoids find_dotenv frame issues).
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import anthropic
import google.generativeai as genai

from parsers.tiktok import parse_tiktok_export_from_bytes
from api.ghost_profile import build_ghost_profile
from exporters.llm_export import generate_llm_export
from api.narratives import build_narrative_blocks, generate_narrative_blocks_llm
from utils.ip_geo import enrich_logins_with_geo
from utils.creators import enrich_creators_with_llm, cluster_creators_llm
from utils import oembed
from utils import youtube_bridge
from utils import creator_map
from utils import psychographic
from utils import pillar_categories

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
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_metrics = {
    "enrich_requests_total": 0,
    "enrich_requested_videos_total": 0,
    "enrich_fetched_videos_total": 0,
}

@app.get("/health")
async def health():
    return {"status": "online", "service": "algorithmic-forensics-api"}

@app.get("/metrics")
async def metrics():
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
    sleep_start: Optional[int] = Query(None, ge=0, le=23),
    sleep_end: Optional[int] = Query(None, ge=0, le=23),
    api_key: Optional[str] = Query(None),
    provider: str = Query("claude", pattern="^(claude|gemini-pro|gemini-flash)$"),
):
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be a .json export.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        parsed = parse_tiktok_export_from_bytes(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse export: {exc}")

    exclude_hours = ()
    if sleep_start is not None and sleep_end is not None:
        if sleep_start <= sleep_end:
            exclude_hours = tuple(range(sleep_start, sleep_end + 1))
        else:
            exclude_hours = tuple(range(sleep_start, 24)) + tuple(range(0, sleep_end + 1))

    # 1. First pass — build to obtain the watch-link sets.
    ghost_profile = build_ghost_profile(parsed, exclude_hours=exclude_hours)

    # 2. Resolve a bounded, cache-backed budget of still-unresolved creators.
    #    TikTok strips @handles + rate-limits oEmbed, so we resolve a small budget
    #    per run and persist forever (utils/creator_map). Coverage grows across runs.
    sw = ghost_profile.get("stopwatch_metrics", {})
    creator_links = list(sw.get("_linger_links", [])) + list(sw.get("_graveyard_links", []))
    creator_vids = [v for v in (oembed.extract_video_id(l) for l in creator_links) if v]
    resolution = await creator_map.resolve_and_fill(creator_vids)

    # 3. Second pass — re-derive every handle-dependent field from the resolved map
    #    (vibe_cluster, graveyard, echo-chamber, social-graph split, archetype).
    if resolution["resolved"]:
        ghost_profile = build_ghost_profile(parsed, exclude_hours=exclude_hours, link_handle_map=resolution["handles"])
    ghost_profile["creator_resolution"] = {
        "resolved": resolution["resolved"],
        "total": resolution["total"],
        "pct": resolution["pct"],
        "newly_resolved": resolution["newly_resolved"],
        "persistent": creator_map.using_redis(),
    }

    # Attach display name + thumbnail (from the same resolved map) to the ledgers.
    meta_by_handle = {m["handle"].lower(): m for m in resolution["meta"].values()}
    for c in (ghost_profile.get("creator_entities", {}).get("vibe_cluster", [])
              + ghost_profile.get("creator_entities", {}).get("graveyard", [])):
        h = (c.get("handle") or "").lstrip("@").lower()
        m = meta_by_handle.get(h)
        if m:
            if m.get("display_name"):
                c.setdefault("display_name", m["display_name"])
            if m.get("thumbnail"):
                c.setdefault("thumbnail", m["thumbnail"])

    # 4. Geo Enrichment (after the final build)
    raw_logins = ghost_profile.get("digital_footprint", {}).get("recent_logins", [])
    if raw_logins:
        enriched_logins = await enrich_logins_with_geo(raw_logins)
        ghost_profile["digital_footprint"]["recent_logins"] = enriched_logins

    vibe = ghost_profile.get("creator_entities", {}).get("vibe_cluster", [])

    # 5. PROTOTYPE — Cross-platform entity resolution: TikTok @handle -> YouTube
    # channel topic tags. Opt-in via ENABLE_YOUTUBE_BRIDGE or YOUTUBE_API_KEY.
    # See utils/youtube_bridge.py. Best-effort; never blocks the response.
    if youtube_bridge.is_enabled():
        try:
            resolvable = [
                c for c in vibe
                if c.get("handle") and c["handle"] != "Unknown"
            ][:10]  # cap fan-out, same spirit as the oEmbed cap
            handles = [c["handle"].lstrip("@") for c in resolvable]
            names = {
                c["handle"].lstrip("@"): (c.get("display_name") or "")
                for c in resolvable
            }
            if handles:
                yt_results = await youtube_bridge.resolve_many(handles, concurrency=4, display_names=names)
                by_handle = {r["handle"]: r for r in yt_results}
                for c in resolvable:
                    r = by_handle.get(c["handle"].lstrip("@"))
                    if r and r.get("status") == "ok":
                        d = r["data"]
                        c["youtube"] = {
                            "channel_title": d.get("channel_title", ""),
                            "channel_url": d.get("channel_url", ""),
                            "topics": d.get("topics", []),
                            "description": d.get("description", ""),
                            "subscriber_text": d.get("subscriber_text", ""),
                            "match": r.get("match"),
                            "source": d.get("source", ""),
                        }
        except Exception as exc:
            logging.warning("YouTube bridge enrichment failed: %s", exc)

    # 3. Automated Vibe & Narrative (if API key provided)
    if api_key:
        # Enrich creators
        vibe = ghost_profile.get("creator_entities", {}).get("vibe_cluster", [])
        enriched_vibe = await enrich_creators_with_llm(vibe, api_key, provider)
        ghost_profile["creator_entities"]["vibe_cluster"] = enriched_vibe
        
        # New: Shadow Clusters
        ghost_profile["shadow_clusters"] = await cluster_creators_llm(enriched_vibe, api_key, provider)
        
        # Generate LLM narratives
        narrative_blocks = await generate_narrative_blocks_llm(ghost_profile, api_key, provider)
        if not narrative_blocks:
            narrative_blocks = build_narrative_blocks(ghost_profile, parsed)
    else:
        narrative_blocks = build_narrative_blocks(ghost_profile, parsed)

    return {**ghost_profile, "narrative_blocks": narrative_blocks}


@app.post("/api/export/llm")
async def export_llm(file: UploadFile = File(...)):
    """Parse a TikTok export and return a privacy-safe LLM analysis JSON."""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be a .json export.")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw) > _LLM_EXPORT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 100 MB).")
    try:
        parsed = parse_tiktok_export_from_bytes(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse export: {exc}")

    ghost = build_ghost_profile(parsed)
    payload = generate_llm_export(parsed, ghost)
    return Response(
        content=json.dumps(payload, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="tiktok_analysis_{_date.today().isoformat()}.json"'},
    )

@app.post("/api/analyze/llm")
async def analyze_llm(
    file: UploadFile = File(...),
    provider: str = Query(..., pattern="^(claude|gemini-pro|gemini-flash)$"),
    api_key: str = Query(...),
):
    """Stream an LLM analysis using the user's API key. Key lives in memory only."""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be a .json export.")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        parsed = parse_tiktok_export_from_bytes(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse export: {exc}")

    ghost = build_ghost_profile(parsed)
    payload = generate_llm_export(parsed, ghost)
    meta = payload["_meta"]
    prompt = (
        f"{meta['instructions_for_llm']}\n\n"
        f"DATA_EXPORT_JSON:\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n\n"
        f"{meta['suggested_opening']}"
    )

    async def stream_claude():
        try:
            client = anthropic.AsyncAnthropic(api_key=api_key)
            async with client.messages.stream(
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
                model="claude-opus-4-5",
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
            response = await model.generate_content_async(prompt, stream=True)
            async for chunk in response:
                if chunk.text:
                    yield f"data: {chunk.text}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"

    if provider == "claude":
        return StreamingResponse(stream_claude(), media_type="text/event-stream")
    model = "gemini-3-pro" if provider == "gemini-pro" else "gemini-3-flash"
    return StreamingResponse(stream_gemini(model), media_type="text/event-stream")


class EnrichRequest(BaseModel):
    lingered: list[dict]
    graveyard: list[dict]
    sandbox: list[dict]
    night_lingered: list[dict]
    following_usernames: list[str]
    api_key: Optional[str] = None
    provider: str = "claude"

@app.post("/api/enrich")
async def enrich(req: EnrichRequest):
    buckets = {"lingered": req.lingered, "graveyard": req.graveyard, "sandbox": req.sandbox, "night_lingered": req.night_lingered}
    all_ids = []
    seen = set()
    for events in buckets.values():
        for ev in events:
            vid = ev.get("video_id")
            if vid and vid not in seen:
                seen.add(vid); all_ids.append(vid)

    fetched_results = await oembed.fetch_many(all_ids, concurrency=8)
    videos_map = {r["video_id"]: (r.get("data") or {}) for r in fetched_results if r.get("video_id")}
    video_results = {r["video_id"]: {"status": r.get("status"), "error": r.get("error")} for r in fetched_results if r.get("video_id")}

    enriched = {}
    for key, events in buckets.items():
        enriched_list = []
        for ev in events:
            vid = ev.get("video_id")
            meta = videos_map.get(vid, {"title": "Title Hidden", "author": "Unknown", "author_name": "Unknown", "thumbnail": ""})
            enriched_list.append({**ev, **meta})
        enriched[key] = enriched_list[:24]

    def top_creators(items: list[dict], limit: int = 12) -> list[dict]:
        agg = {}
        for it in items:
            author = (it.get("author") or "").lower()
            if not author: continue
            if author not in agg: agg[author] = {"author": author, "author_name": it.get("author_name") or author, "count": 0}
            agg[author]["count"] += 1
        return sorted(agg.values(), key=lambda x: x["count"], reverse=True)[:limit]

    following_set = {u.lower().lstrip("@") for u in req.following_usernames}
    matched = followed_n = algo_n = 0
    for key in ("lingered", "sandbox", "graveyard"):
        for it in enriched[key]:
            author = (it.get("author") or "").lower().lstrip("@")
            if not author: continue
            matched += 1
            if author in following_set: followed_n += 1
            else: algo_n += 1
    
    followed_pct = round((followed_n / matched) * 100, 1) if matched > 0 else 0.0
    algo_pct = round((algo_n / matched) * 100, 1) if matched > 0 else 0.0

    def titles(items: list[dict]) -> list[str]:
        return [it.get("title", "") for it in items if it.get("title")]

    # ── Theme extraction ──────────────────────────────────────────────────────
    p_themes = psychographic.extract_themes(titles(enriched["lingered"]))
    a_themes = psychographic.extract_themes(titles(enriched["graveyard"]))
    s_themes = psychographic.extract_themes(titles(enriched["sandbox"]))
    n_themes = psychographic.extract_themes(titles(enriched["night_lingered"]))

    # ── Optional LLM keyword categorization ──
    # Currently advisory-only — surfaces an `llm_categories` map for the frontend
    # to override deterministic categories. Wire into build_pillar_narrative when
    # the rendering layer needs it.
    llm_categories: dict[str, str] = {}
    if req.api_key:
        try:
            llm_categories = await pillar_categories.categorize_keywords_llm(
                p_themes["top_keywords"] + a_themes["top_keywords"] + s_themes["top_keywords"] + n_themes["top_keywords"],
                req.api_key,
                req.provider,
            )
        except Exception as e:
            # Never let an LLM failure take the route down.
            logger_msg = f"LLM keyword categorization failed: {e}"
            print(logger_msg)
            llm_categories = {}

    anti_signature = psychographic.build_anti_profile_signature(a_themes["top_keywords"], p_themes["top_keywords"])

    def _narr(pillar: str, themes: dict, items: list[dict]) -> dict:
        return psychographic.build_pillar_narrative(pillar, themes["top_keywords"], themes["top_phrases"], themes["top_emojis"], [it.get("title", "") for it in items if it.get("title")])

    themes_out = {
        "psychographic": {**p_themes, "narrative": _narr("psychographic", p_themes, enriched["lingered"])},
        "anti_profile": {**a_themes, "raw": a_themes["top_keywords"], "signature": anti_signature, "narrative": _narr("anti_profile", a_themes, enriched["graveyard"])},
        "sandbox": {**s_themes, "narrative": _narr("sandbox", s_themes, enriched["sandbox"])},
        "night": {**n_themes, "narrative": _narr("night", n_themes, enriched["night_lingered"])},
    }

    # cache metrics + enrich counters
    try:
        cache_metrics = oembed.get_cache_metrics()
    except Exception:
        cache_metrics = {"hits": 0, "misses": 0, "evictions": 0}

    fetched_ok = sum(1 for r in fetched_results if r.get("status") == "ok")
    try:
        _metrics["enrich_requests_total"] += 1
        _metrics["enrich_requested_videos_total"] += len(all_ids)
        _metrics["enrich_fetched_videos_total"] += fetched_ok
    except Exception:
        pass

    return {
        "videos": enriched,
        "video_results": video_results,
        "cache_metrics": cache_metrics,
        "top_creators": {"lingered": top_creators(enriched["lingered"]), "graveyard": top_creators(enriched["graveyard"])},
        "themes": themes_out,
        "llm_categories": llm_categories,
        "following_ratio": {"followed_pct": followed_pct, "algorithmic_pct": algo_pct, "matched_videos": matched},
        "fetched_count": fetched_ok,
        "requested_count": len(all_ids),
    }
