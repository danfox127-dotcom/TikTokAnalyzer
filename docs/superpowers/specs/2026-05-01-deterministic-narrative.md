# Deterministic Narrative Block System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 9-block deterministic narrative system that transforms the ghost profile into a human-readable dossier, embedded in `/api/analyze` and rendered in a new "DOSSIER" view in the Next.js frontend.

**Architecture:** A new `api/narratives.py` module builds 9 block dicts from `ghost_profile` + `parsed` data. A new `utils/ip_geo.py` provides async IP geolocation with an in-process cache. The blocks are appended to the `/api/analyze` response as `narrative_blocks`. The frontend renders them via a generic `BlockCard` component (backed by Recharts) in a new `NarrativeReportView`.

**Tech Stack:** Python/FastAPI (backend), httpx (already in requirements.txt), respx (already in requirements.txt, for tests), Next.js 16 / React 19 / TypeScript (frontend), Recharts for charts, Jest + @testing-library/react for frontend tests.

---

## File Structure

**New backend files:**
- `utils/ip_geo.py` — async IP geolocation with in-process cache + graceful fallback
- `api/narratives.py` — 9 block builder functions + `build_narrative_blocks(ghost_profile, parsed)`
- `tests/test_ip_geo.py` — unit tests for ip_geo
- `tests/test_narratives.py` — unit tests for each block builder

**Modified backend files:**
- `api/main.py` — wire `enrich_logins_with_geo` + `build_narrative_blocks` into `/api/analyze`

**New frontend files:**
- `algorithmic-mirror/app/types/narrative.ts` — TypeScript interfaces for blocks
- `algorithmic-mirror/app/components/BlockCard.tsx` — generic block renderer with chart dispatch
- `algorithmic-mirror/app/components/NarrativeReportView.tsx` — full dossier view
- `algorithmic-mirror/__tests__/BlockCard.test.tsx`
- `algorithmic-mirror/__tests__/NarrativeReportView.test.tsx`

**Modified frontend files:**
- `algorithmic-mirror/app/page.tsx` — add `"report"` view, wire narrative blocks state
- `algorithmic-mirror/app/components/TheGlassHouse.tsx` — add `onOpenReport` prop + "DOSSIER →" button

---

## Key Data Fields Available in `ghost_profile`

The plan's code references these fields directly. Know them before reading the task code:

- `ghost_profile["behavioral_nodes"]` → `peak_hour` (str "0"–"23"), `skip_rate_percentage`, `linger_rate_percentage`, `night_shift_ratio`, `social_graph_followed_pct`, `social_graph_algorithmic_pct`
- `ghost_profile["stopwatch_metrics"]` → `total_conscious_videos`, `deep_dives`, `deep_lingers`, `graveyard_skips`, `hourly_heatmap` (dict `{"0": n, ..., "23": n}`)
- `ghost_profile["creator_entities"]["vibe_cluster"]` → list of `{handle, linger_count, ...}`
- `ghost_profile["comment_voice"]` → `total_comments`, `avg_length_chars`, `long_comment_pct`, `emoji_density`, `engagement_style_label`
- `ghost_profile["share_behavior"]` → `total_shares`, `share_methods` (dict), `share_behavior_type`, `primary_share_method`
- `ghost_profile["transparency_gap"]` → `official_ad_interest_count`, `behavioral_interest_count`, `gap_interpretation`
- `ghost_profile["digital_footprint"]` → `login_count`, `unique_ips`, `unique_devices` (list), `recent_logins` (list of `{date, ip, device, system, network, carrier}`)
- `ghost_profile["declared_signals"]` → `following_count`, `ad_interests`, `recent_searches`
- `ghost_profile["search_rhythm"]` → `total_searches`
- `ghost_profile["academic_insights"]` → `echo_chamber_index_pct`
- `parsed.get("likes", [])` → list (use `len()`)
- `parsed.get("comments", [])` → list
- `parsed.get("shares", [])` → list

---

## Task 1: IP Geolocation Module

**Files:**
- Create: `utils/ip_geo.py`
- Create: `tests/test_ip_geo.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ip_geo.py
import pytest
import httpx
import respx

# Reset the module-level cache between tests
import importlib


@pytest.fixture(autouse=True)
def clear_cache():
    import utils.ip_geo as m
    m._CACHE.clear()
    yield
    m._CACHE.clear()


@pytest.mark.asyncio
async def test_geolocate_ip_success():
    from utils.ip_geo import geolocate_ip
    with respx.mock:
        respx.get("https://api.iplocation.net/?ip=1.2.3.4").mock(
            return_value=httpx.Response(200, json={"city": "Paris", "country_name": "France"})
        )
        result = await geolocate_ip("1.2.3.4")
    assert result == {"city": "Paris", "country_name": "France"}


@pytest.mark.asyncio
async def test_geolocate_ip_cache_hit():
    from utils.ip_geo import geolocate_ip, _CACHE
    _CACHE["5.6.7.8"] = {"city": "Berlin", "country_name": "Germany"}
    # No HTTP mock — if it tries to call the API it will raise
    result = await geolocate_ip("5.6.7.8")
    assert result == {"city": "Berlin", "country_name": "Germany"}


@pytest.mark.asyncio
async def test_geolocate_ip_fallback_on_error():
    from utils.ip_geo import geolocate_ip
    with respx.mock:
        respx.get("https://api.iplocation.net/?ip=9.9.9.9").mock(
            side_effect=httpx.ConnectTimeout("timeout")
        )
        result = await geolocate_ip("9.9.9.9")
    assert result == {"city": "Unknown", "country_name": "Unknown"}


@pytest.mark.asyncio
async def test_geolocate_ip_empty_string():
    from utils.ip_geo import geolocate_ip
    # Should return fallback without hitting network
    result = await geolocate_ip("")
    assert result == {"city": "Unknown", "country_name": "Unknown"}


@pytest.mark.asyncio
async def test_enrich_logins_with_geo():
    from utils.ip_geo import enrich_logins_with_geo
    logins = [
        {"date": "2024-01-01", "ip": "1.2.3.4", "device": "iPhone"},
        {"date": "2024-01-02", "ip": "1.2.3.4", "device": "iPhone"},  # same IP, should deduplicate fetch
        {"date": "2024-01-03", "ip": "5.6.7.8", "device": "Android"},
    ]
    call_count = 0
    with respx.mock:
        def make_response(request):
            nonlocal call_count
            call_count += 1
            ip = str(request.url).split("ip=")[1]
            data = {
                "1.2.3.4": {"city": "Paris", "country_name": "France"},
                "5.6.7.8": {"city": "Berlin", "country_name": "Germany"},
            }
            return httpx.Response(200, json=data.get(ip, {"city": "Unknown", "country_name": "Unknown"}))
        respx.get(url__startswith="https://api.iplocation.net/").mock(side_effect=make_response)
        result = await enrich_logins_with_geo(logins)

    # 2 unique IPs → 2 HTTP calls
    assert call_count == 2
    assert result[0]["city"] == "Paris"
    assert result[1]["city"] == "Paris"   # same IP reused from cache
    assert result[2]["city"] == "Berlin"
    assert all("country_name" in r for r in result)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/danweiman/TikTokAnalyzer && pytest tests/test_ip_geo.py -v
```

Expected: `ModuleNotFoundError: No module named 'utils.ip_geo'`

- [ ] **Step 3: Implement `utils/ip_geo.py`**

```python
# utils/ip_geo.py
"""
Async IP geolocation via api.iplocation.net.
In-process cache; 2s timeout; graceful fallback on any error.
"""
from __future__ import annotations

import httpx

_CACHE: dict[str, dict] = {}
_TIMEOUT = 2.0
_FALLBACK = {"city": "Unknown", "country_name": "Unknown"}


async def geolocate_ip(ip: str) -> dict:
    """
    Return {"city": str, "country_name": str} for the given IP.
    Returns _FALLBACK on empty input, cache hit bypass not applicable here.
    Never raises.
    """
    if not ip:
        return _FALLBACK.copy()
    if ip in _CACHE:
        return _CACHE[ip]
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(f"https://api.iplocation.net/?ip={ip}")
            r.raise_for_status()
            data = r.json()
            result = {
                "city": data.get("city") or "Unknown",
                "country_name": data.get("country_name") or "Unknown",
            }
    except Exception:
        result = _FALLBACK.copy()
    _CACHE[ip] = result
    return result


async def enrich_logins_with_geo(logins: list[dict]) -> list[dict]:
    """
    Enrich each login entry that has an "ip" key with "city" and "country_name".
    Deduplicates IPs so each unique IP is fetched at most once.
    Returns a new list; originals are not mutated.
    """
    unique_ips = {login["ip"] for login in logins if login.get("ip")}
    geo_map: dict[str, dict] = {}
    for ip in unique_ips:
        geo_map[ip] = await geolocate_ip(ip)

    enriched = []
    for login in logins:
        ip = login.get("ip", "")
        geo = geo_map.get(ip, _FALLBACK)
        enriched.append({**login, "city": geo["city"], "country_name": geo["country_name"]})
    return enriched
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/danweiman/TikTokAnalyzer && pytest tests/test_ip_geo.py -v
```

Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add utils/ip_geo.py tests/test_ip_geo.py
git commit -m "feat: add async IP geolocation module with cache and fallback"
```

---

## Task 2: Narrative Blocks 1–3 (Algorithmic Identity, Attention Signature, Daily Rhythm)

**Files:**
- Create: `api/narratives.py`
- Create: `tests/test_narratives.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_narratives.py
"""Unit tests for narrative block builders."""
import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _base_ghost() -> dict:
    """Minimal ghost_profile dict covering all blocks."""
    return {
        "behavioral_nodes": {
            "peak_hour": "14",
            "skip_rate_percentage": 30.0,
            "linger_rate_percentage": 15.0,
            "night_shift_ratio": 10.0,
            "night_linger_pct": 8.0,
            "social_graph_followed_pct": 45.0,
            "social_graph_algorithmic_pct": 55.0,
        },
        "stopwatch_metrics": {
            "total_conscious_videos": 500,
            "deep_lingers": 50,
            "deep_dives": 25,
            "graveyard_skips": 150,
            "hourly_heatmap": {str(h): (5 if h == 14 else 1) for h in range(24)},
        },
        "creator_entities": {
            "vibe_cluster": [
                {"handle": "@creator1", "linger_count": 30},
                {"handle": "@creator2", "linger_count": 20},
                {"handle": "@creator3", "linger_count": 10},
            ],
            "graveyard": [],
        },
        "comment_voice": {
            "total_comments": 42,
            "avg_length_chars": 85.0,
            "long_comments_count": 4,
            "long_comment_pct": 9.5,
            "emoji_density": 0.02,
            "engagement_style_label": "Community Participant",
        },
        "share_behavior": {
            "total_shares": 15,
            "share_methods": {"chat": 10, "instagram": 5},
            "share_behavior_type": "Private Curator",
            "primary_share_method": "chat",
            "dm_share_count": 10,
        },
        "transparency_gap": {
            "official_ad_interest_count": 8,
            "behavioral_interest_count": 12,
            "gap_interpretation": "Official interests roughly match behavioral profile.",
        },
        "digital_footprint": {
            "login_count": 25,
            "unique_ips": 3,
            "unique_devices": ["iPhone 14", "MacBook Pro"],
            "recent_logins": [
                {"date": "2024-03-01", "ip": "1.2.3.4", "city": "Paris", "country_name": "France"},
                {"date": "2024-02-01", "ip": "1.2.3.4", "city": "Paris", "country_name": "France"},
            ],
        },
        "declared_signals": {
            "following_count": 120,
            "ad_interests": ["Technology", "Sports"],
            "recent_searches": ["python", "cooking"],
        },
        "search_rhythm": {"total_searches": 200},
        "academic_insights": {"echo_chamber_index_pct": 55.0},
    }


def _base_parsed() -> dict:
    return {
        "likes": [{}] * 80,
        "comments": [{}] * 42,
        "shares": [{}] * 15,
        "following": [{}] * 120,
    }


# ── Block schema helper ───────────────────────────────────────────────────────

def _assert_block_schema(block: dict, expected_id: str):
    assert block["id"] == expected_id
    assert isinstance(block["title"], str) and block["title"]
    assert isinstance(block["icon"], str) and block["icon"]
    assert isinstance(block["prose"], str) and len(block["prose"]) > 20
    assert isinstance(block["accent"], str) and block["accent"].startswith("#")
    assert isinstance(block["stats"], list)
    # chart is either None or has type + data
    if block["chart"] is not None:
        assert block["chart"]["type"] in ("bar", "donut", "line")
        assert isinstance(block["chart"]["data"], list)


# ── Block 1: Algorithmic Identity ─────────────────────────────────────────────

def test_algorithmic_identity_schema():
    from api.narratives import _build_algorithmic_identity_block
    block = _build_algorithmic_identity_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "algorithmic_identity")


def test_algorithmic_identity_high_followed():
    from api.narratives import _build_algorithmic_identity_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["social_graph_followed_pct"] = 75.0
    ghost["behavioral_nodes"]["social_graph_algorithmic_pct"] = 25.0
    block = _build_algorithmic_identity_block(ghost, _base_parsed())
    assert "follow" in block["prose"].lower() or "intentional" in block["prose"].lower()


def test_algorithmic_identity_low_followed():
    from api.narratives import _build_algorithmic_identity_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["social_graph_followed_pct"] = 10.0
    ghost["behavioral_nodes"]["social_graph_algorithmic_pct"] = 90.0
    block = _build_algorithmic_identity_block(ghost, _base_parsed())
    assert "algorithm" in block["prose"].lower()


def test_algorithmic_identity_no_vibe_cluster():
    from api.narratives import _build_algorithmic_identity_block
    ghost = _base_ghost()
    ghost["creator_entities"]["vibe_cluster"] = []
    block = _build_algorithmic_identity_block(ghost, _base_parsed())
    assert block["chart"] is None or block["chart"]["data"] == []


# ── Block 2: Attention Signature ──────────────────────────────────────────────

def test_attention_signature_schema():
    from api.narratives import _build_attention_signature_block
    block = _build_attention_signature_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "attention_signature")
    assert block["chart"] is not None
    assert block["chart"]["type"] == "bar"


def test_attention_signature_high_linger():
    from api.narratives import _build_attention_signature_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["linger_rate_percentage"] = 35.0
    block = _build_attention_signature_block(ghost, _base_parsed())
    assert "deep" in block["prose"].lower() or "extended" in block["prose"].lower()


def test_attention_signature_high_skip():
    from api.narratives import _build_attention_signature_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["skip_rate_percentage"] = 65.0
    ghost["behavioral_nodes"]["linger_rate_percentage"] = 5.0
    block = _build_attention_signature_block(ghost, _base_parsed())
    assert "skip" in block["prose"].lower() or "curator" in block["prose"].lower()


# ── Block 3: Daily Rhythm ──────────────────────────────────────────────────────

def test_daily_rhythm_schema():
    from api.narratives import _build_daily_rhythm_block
    block = _build_daily_rhythm_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "dayparting")
    assert block["chart"] is not None
    assert block["chart"]["type"] == "bar"
    assert len(block["chart"]["data"]) == 24


def test_daily_rhythm_night_owl():
    from api.narratives import _build_daily_rhythm_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["night_shift_ratio"] = 40.0
    block = _build_daily_rhythm_block(ghost, _base_parsed())
    assert "night" in block["prose"].lower()


def test_daily_rhythm_peak_hour_in_stats():
    from api.narratives import _build_daily_rhythm_block
    block = _build_daily_rhythm_block(_base_ghost(), _base_parsed())
    labels = [s["label"] for s in block["stats"]]
    assert "Peak Hour" in labels


# ── build_narrative_blocks smoke test ────────────────────────────────────────

def test_build_narrative_blocks_returns_9():
    from api.narratives import build_narrative_blocks
    blocks = build_narrative_blocks(_base_ghost(), _base_parsed())
    assert len(blocks) == 9


def test_build_narrative_blocks_correct_ids():
    from api.narratives import build_narrative_blocks
    blocks = build_narrative_blocks(_base_ghost(), _base_parsed())
    ids = [b["id"] for b in blocks]
    assert ids[0] == "algorithmic_identity"
    assert ids[1] == "attention_signature"
    assert ids[2] == "dayparting"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/danweiman/TikTokAnalyzer && pytest tests/test_narratives.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'api.narratives'`

- [ ] **Step 3: Implement `api/narratives.py` with blocks 1–3**

```python
# api/narratives.py
"""
Deterministic Narrative Block System.

Generates 9 structured blocks from ghost_profile + parsed export.
Each block: {id, title, icon, prose, accent, stats, chart}.
"""
from __future__ import annotations

from collections import Counter


# ---------------------------------------------------------------------------
# Block 1 — Algorithmic Identity
# ---------------------------------------------------------------------------

def _build_algorithmic_identity_block(ghost_profile: dict, parsed: dict) -> dict:
    bn = ghost_profile.get("behavioral_nodes", {})
    followed_pct = float(bn.get("social_graph_followed_pct", 0))
    algo_pct = float(bn.get("social_graph_algorithmic_pct", 0))
    vibe = ghost_profile.get("creator_entities", {}).get("vibe_cluster", [])
    top_creator = vibe[0].get("handle", "Unknown") if vibe else "Unknown"

    if followed_pct > 60:
        prose = (
            f"Your feed is primarily driven by creators you've chosen to follow — {followed_pct:.0f}% "
            f"of your sustained attention goes to followed accounts, putting you among the most "
            f"intentional viewers on the platform. Your top creator, {top_creator}, has earned a "
            f"disproportionate share of your time. TikTok's algorithm confirms your taste rather "
            f"than shaping it."
        )
    elif followed_pct < 30:
        prose = (
            f"TikTok's algorithm dominates your attention. Only {followed_pct:.0f}% of your sustained "
            f"viewing goes to accounts you've explicitly followed — the rest is pure machine curation. "
            f"Your most-watched creator, {top_creator}, was likely surfaced algorithmically. "
            f"You are largely a product of the recommendation engine."
        )
    else:
        prose = (
            f"You split your attention between followed accounts ({followed_pct:.0f}%) and "
            f"algorithmic discovery ({algo_pct:.0f}%). {top_creator} leads your sustained viewing. "
            f"This balance suggests a measured relationship with the platform — curious but not "
            f"fully surrendered to the feed."
        )

    top3 = [(c.get("handle", "?"), c.get("linger_count", 0)) for c in vibe[:3]]
    stats = [
        {"label": "Followed %", "value": f"{followed_pct:.0f}%"},
        {"label": "Algorithmic %", "value": f"{algo_pct:.0f}%"},
    ]
    for i, (handle, _) in enumerate(top3, 1):
        stats.append({"label": f"#{i} Creator", "value": handle})

    # Donut: top 5 creators by linger count + Other
    total_linger = sum(c.get("linger_count", 0) for c in vibe)
    top5 = vibe[:5]
    top5_linger = sum(c.get("linger_count", 0) for c in top5)
    chart_data = [
        {"name": c["handle"], "value": c.get("linger_count", 0)}
        for c in top5 if c.get("linger_count", 0) > 0
    ]
    if total_linger > top5_linger and total_linger > 0:
        chart_data.append({"name": "Other", "value": total_linger - top5_linger})

    return {
        "id": "algorithmic_identity",
        "title": "ALGORITHMIC IDENTITY",
        "icon": "🎭",
        "prose": prose,
        "accent": "#4db8ff",
        "stats": stats,
        "chart": {"type": "donut", "data": chart_data} if chart_data else None,
    }


# ---------------------------------------------------------------------------
# Block 2 — Attention Signature
# ---------------------------------------------------------------------------

def _build_attention_signature_block(ghost_profile: dict, parsed: dict) -> dict:
    bn = ghost_profile.get("behavioral_nodes", {})
    sw = ghost_profile.get("stopwatch_metrics", {})
    skip_rate = float(bn.get("skip_rate_percentage", 0))
    linger_rate = float(bn.get("linger_rate_percentage", 0))
    total = int(sw.get("total_conscious_videos", 0))
    deep_dives = int(sw.get("deep_dives", 0))
    deep_dive_pct = round((deep_dives / max(total, 1)) * 100, 1)

    if linger_rate > 20:
        prose = (
            f"You are a deep watcher. {linger_rate:.0f}% of your views end in extended viewing — "
            f"far above typical patterns. TikTok's engagement model treats this as a strong positive "
            f"signal: creators you linger on are amplified in others' feeds. Your attention is a "
            f"resource the algorithm harvests aggressively."
        )
    elif skip_rate > 50:
        prose = (
            f"You are a ruthless curator. You skip {skip_rate:.0f}% of content quickly, training "
            f"the algorithm through rejection as much as acceptance. The videos that do hold your "
            f"attention — {linger_rate:.0f}% of views — send disproportionately strong signals. "
            f"Scarcity makes your engagement more valuable to the model."
        )
    else:
        prose = (
            f"Your viewing pattern is balanced — {skip_rate:.0f}% skipped, {linger_rate:.0f}% "
            f"lingered. You engage moderately across a range of content rather than sending strong "
            f"directional signals. The algorithm has a stable, moderate picture of your preferences."
        )

    stats = [
        {"label": "Linger Rate", "value": f"{linger_rate:.1f}%"},
        {"label": "Skip Rate", "value": f"{skip_rate:.1f}%"},
        {"label": "Deep Dive Rate", "value": f"{deep_dive_pct:.1f}%"},
        {"label": "Total Videos", "value": str(total)},
    ]

    chart_data = [
        {"metric": "Linger", "value": round(linger_rate, 1)},
        {"metric": "Skip", "value": round(skip_rate, 1)},
        {"metric": "Deep Dive", "value": deep_dive_pct},
    ]

    return {
        "id": "attention_signature",
        "title": "ATTENTION SIGNATURE",
        "icon": "👁️",
        "prose": prose,
        "accent": "#ff8c42",
        "stats": stats,
        "chart": {"type": "bar", "data": chart_data},
    }


# ---------------------------------------------------------------------------
# Block 3 — Daily Rhythm
# ---------------------------------------------------------------------------

def _fmt_hour(h: int) -> str:
    if h == 0:
        return "12 AM"
    if h < 12:
        return f"{h} AM"
    if h == 12:
        return "12 PM"
    return f"{h - 12} PM"


def _build_daily_rhythm_block(ghost_profile: dict, parsed: dict) -> dict:
    sw = ghost_profile.get("stopwatch_metrics", {})
    bn = ghost_profile.get("behavioral_nodes", {})
    heatmap: dict = sw.get("hourly_heatmap", {})
    night_pct = float(bn.get("night_shift_ratio", 0))
    peak_hour_raw = bn.get("peak_hour", "0")

    try:
        peak_h = int(peak_hour_raw) if peak_hour_raw else 0
    except (ValueError, TypeError):
        peak_h = 0

    peak_label = _fmt_hour(peak_h)

    if 5 <= peak_h < 12:
        window = "morning"
    elif 12 <= peak_h < 17:
        window = "afternoon"
    elif 17 <= peak_h < 22:
        window = "evening"
    else:
        window = "late night"

    if night_pct > 30:
        prose = (
            f"You are a night viewer — {night_pct:.0f}% of your TikTok activity occurs between "
            f"11 PM and 4 AM. Your peak engagement hour is {peak_label}. Late-night usage is "
            f"associated with passive consumption and higher ad susceptibility. TikTok's ad "
            f"targeting systems actively exploit this window."
        )
    elif window == "morning":
        prose = (
            f"You're a morning viewer — your peak engagement hour is {peak_label}. Morning usage "
            f"tends to be quick and habitual, content as a daily ritual rather than a late-night "
            f"escape. Only {night_pct:.0f}% of your activity occurs in the late-night window."
        )
    else:
        prose = (
            f"Your peak viewing hour is {peak_label}, placing you in the {window} cohort. "
            f"{night_pct:.0f}% of your activity occurs in the late-night window (11 PM–4 AM). "
            f"Your usage pattern follows a typical circadian rhythm — consistent with intentional "
            f"rather than compulsive consumption."
        )

    chart_data = [
        {"hour": str(h), "count": int(heatmap.get(str(h), 0))}
        for h in range(24)
    ]

    active_hours = len([v for v in heatmap.values() if int(v) > 0])
    stats = [
        {"label": "Peak Hour", "value": peak_label},
        {"label": "Night Viewing", "value": f"{night_pct:.0f}%"},
        {"label": "Active Hours", "value": str(active_hours)},
    ]

    return {
        "id": "dayparting",
        "title": "DAILY RHYTHM",
        "icon": "🕐",
        "prose": prose,
        "accent": "#a8ff78",
        "stats": stats,
        "chart": {"type": "bar", "data": chart_data},
    }


# ---------------------------------------------------------------------------
# Placeholder stubs — filled in Tasks 3 and 4
# ---------------------------------------------------------------------------

def _build_social_graph_block(ghost_profile: dict, parsed: dict) -> dict:
    raise NotImplementedError


def _build_share_behavior_block(ghost_profile: dict, parsed: dict) -> dict:
    raise NotImplementedError


def _build_comment_voice_block(ghost_profile: dict, parsed: dict) -> dict:
    raise NotImplementedError


def _build_transparency_gap_block(ghost_profile: dict, parsed: dict) -> dict:
    raise NotImplementedError


def _build_location_trace_block(ghost_profile: dict, parsed: dict) -> dict:
    raise NotImplementedError


def _build_closing_synthesis_block(ghost_profile: dict, parsed: dict) -> dict:
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_narrative_blocks(ghost_profile: dict, parsed: dict) -> list[dict]:
    """
    Generate ordered list of 9 narrative blocks.
    Each block that raises is silently skipped to prevent one bad block
    from crashing the whole response.
    """
    builders = [
        _build_algorithmic_identity_block,
        _build_attention_signature_block,
        _build_daily_rhythm_block,
        _build_social_graph_block,
        _build_share_behavior_block,
        _build_comment_voice_block,
        _build_transparency_gap_block,
        _build_location_trace_block,
        _build_closing_synthesis_block,
    ]
    blocks = []
    for builder in builders:
        try:
            blocks.append(builder(ghost_profile, parsed))
        except Exception:
            pass
    return blocks
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/danweiman/TikTokAnalyzer && pytest tests/test_narratives.py -v -k "identity or signature or rhythm or build_narrative"
```

Expected: 14 tests pass. The `build_narrative_blocks` tests will show only 3 blocks (stubs raise NotImplementedError and are silently skipped). That's expected — the final count will be 9 after Task 4.

- [ ] **Step 5: Commit**

```bash
git add api/narratives.py tests/test_narratives.py
git commit -m "feat: add narrative blocks 1-3 (identity, attention, rhythm)"
```

---

## Task 3: Narrative Blocks 4–6 (Social Graph, Share Behavior, Comment Voice)

**Files:**
- Modify: `api/narratives.py` (replace 3 stubs)
- Modify: `tests/test_narratives.py` (add tests for blocks 4–6)

- [ ] **Step 1: Add tests for blocks 4–6** (append to `tests/test_narratives.py`)

```python
# Append to tests/test_narratives.py

# ── Block 4: Social Graph ─────────────────────────────────────────────────────

def test_social_graph_schema():
    from api.narratives import _build_social_graph_block
    block = _build_social_graph_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "social_graph")
    assert block["chart"] is not None
    assert block["chart"]["type"] == "bar"


def test_social_graph_high_followed():
    from api.narratives import _build_social_graph_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["social_graph_followed_pct"] = 80.0
    block = _build_social_graph_block(ghost, _base_parsed())
    assert "follow" in block["prose"].lower()


def test_social_graph_low_followed():
    from api.narratives import _build_social_graph_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["social_graph_followed_pct"] = 10.0
    block = _build_social_graph_block(ghost, _base_parsed())
    assert "algorithm" in block["prose"].lower()


# ── Block 5: Share Behavior ───────────────────────────────────────────────────

def test_share_behavior_schema():
    from api.narratives import _build_share_behavior_block
    block = _build_share_behavior_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "share_behavior")


def test_share_behavior_no_shares():
    from api.narratives import _build_share_behavior_block
    ghost = _base_ghost()
    ghost["share_behavior"]["total_shares"] = 0
    ghost["share_behavior"]["share_methods"] = {}
    block = _build_share_behavior_block(ghost, _base_parsed())
    assert block["chart"] is None
    assert "silent" in block["prose"].lower() or "no content" in block["prose"].lower() or "no share" in block["prose"].lower() or "no comm" in block["prose"].lower()


def test_share_behavior_private_curator():
    from api.narratives import _build_share_behavior_block
    ghost = _base_ghost()
    ghost["share_behavior"]["share_behavior_type"] = "Private Curator"
    block = _build_share_behavior_block(ghost, _base_parsed())
    assert "private" in block["prose"].lower() or "curator" in block["prose"].lower()


# ── Block 6: Comment Voice ────────────────────────────────────────────────────

def test_comment_voice_schema():
    from api.narratives import _build_comment_voice_block
    block = _build_comment_voice_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "comment_voice")
    assert block["chart"] is None


def test_comment_voice_no_comments():
    from api.narratives import _build_comment_voice_block
    ghost = _base_ghost()
    ghost["comment_voice"]["total_comments"] = 0
    block = _build_comment_voice_block(ghost, _base_parsed())
    assert "silent" in block["prose"].lower() or "no comment" in block["prose"].lower() or "lurk" in block["prose"].lower()


def test_comment_voice_analytical():
    from api.narratives import _build_comment_voice_block
    ghost = _base_ghost()
    ghost["comment_voice"]["engagement_style_label"] = "Analytical Commenter"
    ghost["comment_voice"]["avg_length_chars"] = 180.0
    block = _build_comment_voice_block(ghost, _base_parsed())
    assert "analytical" in block["prose"].lower()
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd /Users/danweiman/TikTokAnalyzer && pytest tests/test_narratives.py -v -k "social_graph or share_behavior or comment_voice"
```

Expected: All 9 new tests fail with `NotImplementedError`.

- [ ] **Step 3: Replace stubs for blocks 4–6 in `api/narratives.py`**

Replace the three `raise NotImplementedError` stubs with:

```python
# ---------------------------------------------------------------------------
# Block 4 — Social Graph
# ---------------------------------------------------------------------------

def _build_social_graph_block(ghost_profile: dict, parsed: dict) -> dict:
    bn = ghost_profile.get("behavioral_nodes", {})
    followed_pct = float(bn.get("social_graph_followed_pct", 0))
    algo_pct = float(bn.get("social_graph_algorithmic_pct", 0))
    decl = ghost_profile.get("declared_signals", {})
    following_count = int(decl.get("following_count", 0))
    vibe = ghost_profile.get("creator_entities", {}).get("vibe_cluster", [])
    top_creator = vibe[0].get("handle", "—") if vibe else "—"

    if followed_pct > 50:
        prose = (
            f"You follow {following_count} accounts, and {followed_pct:.0f}% of your sustained "
            f"viewing goes to them. Your social graph is functioning as intended — you follow "
            f"creators you actually watch. This is increasingly rare on TikTok, where the FYP "
            f"often displaces intentional subscriptions entirely."
        )
    elif followed_pct < 20:
        prose = (
            f"You follow {following_count} accounts, but only {followed_pct:.0f}% of your sustained "
            f"viewing goes to them. The algorithm has almost entirely displaced your social graph. "
            f"In effect, your follower list is decorative — the machine decides what you see. "
            f"This is TikTok's design working as intended."
        )
    else:
        prose = (
            f"You follow {following_count} accounts, with {followed_pct:.0f}% of your viewing "
            f"going to followed creators and {algo_pct:.0f}% to algorithmically-surfaced content. "
            f"Your top watched creator is {top_creator}. The FYP is steadily colonizing your "
            f"timeline, but your social graph still has influence."
        )

    stats = [
        {"label": "Following", "value": str(following_count)},
        {"label": "Watched (Followed)", "value": f"{followed_pct:.0f}%"},
        {"label": "Watched (Algorithmic)", "value": f"{algo_pct:.0f}%"},
        {"label": "Top Watched", "value": top_creator},
    ]

    chart_data = [
        {"name": "Followed", "value": round(followed_pct, 1)},
        {"name": "Algorithmic", "value": round(algo_pct, 1)},
    ]

    return {
        "id": "social_graph",
        "title": "SOCIAL GRAPH",
        "icon": "🕸️",
        "prose": prose,
        "accent": "#ff4db8",
        "stats": stats,
        "chart": {"type": "bar", "data": chart_data},
    }


# ---------------------------------------------------------------------------
# Block 5 — Share Behavior
# ---------------------------------------------------------------------------

def _build_share_behavior_block(ghost_profile: dict, parsed: dict) -> dict:
    sb = ghost_profile.get("share_behavior", {})
    total_shares = int(sb.get("total_shares", 0))
    behavior_type = sb.get("share_behavior_type", "Mixed Sharer")
    primary_method = (sb.get("primary_share_method") or "none").title()
    share_methods: dict = sb.get("share_methods", {})
    total_likes = len(parsed.get("likes", []))
    share_to_like = round(total_shares / max(total_likes, 1), 3)

    if total_shares == 0:
        prose = (
            "You have shared no content from TikTok — or your export does not include share data. "
            "This puts you in the silent majority: viewers who consume without redistributing. "
            "You leave no traceable content trail outside the platform."
        )
    elif behavior_type == "Private Curator":
        prose = (
            f"You are a Private Curator. The majority of your {total_shares} shares go through "
            f"direct message or private channels, primarily via {primary_method}. You share content "
            f"intentionally with specific people rather than broadcasting broadly. Your shares are "
            f"high-signal recommendations, not reflexive reposting."
        )
    elif behavior_type == "Public Broadcaster":
        prose = (
            f"You are a Public Broadcaster — {total_shares} shares, primarily via {primary_method}. "
            f"You redistribute content publicly, extending TikTok's reach beyond the platform. "
            f"Your share-to-like ratio of {share_to_like:.3f} suggests curation is a primary "
            f"mode of engagement."
        )
    else:
        prose = (
            f"Your sharing behavior is mixed — {total_shares} shares across multiple channels, "
            f"with {primary_method} as the primary method. You balance private curation with "
            f"public sharing, acting as a connector between TikTok and the broader social web."
        )

    stats = [
        {"label": "Total Shares", "value": str(total_shares)},
        {"label": "Type", "value": behavior_type},
        {"label": "Primary Method", "value": primary_method},
        {"label": "Share/Like Ratio", "value": f"{share_to_like:.3f}"},
    ]

    chart_data = [
        {"name": k.title(), "value": v}
        for k, v in share_methods.items() if v > 0
    ]

    return {
        "id": "share_behavior",
        "title": "SHARE BEHAVIOR",
        "icon": "🔗",
        "prose": prose,
        "accent": "#ffd700",
        "stats": stats,
        "chart": {"type": "donut", "data": chart_data} if chart_data else None,
    }


# ---------------------------------------------------------------------------
# Block 6 — Comment Voice
# ---------------------------------------------------------------------------

def _build_comment_voice_block(ghost_profile: dict, parsed: dict) -> dict:
    cv = ghost_profile.get("comment_voice", {})
    total = int(cv.get("total_comments", 0))
    avg_chars = float(cv.get("avg_length_chars", 0))
    long_pct = float(cv.get("long_comment_pct", 0))
    emoji_density = float(cv.get("emoji_density", 0))
    style_label = cv.get("engagement_style_label", "Lurker")

    if total == 0:
        prose = (
            "No comments found in your export. You are a silent viewer — consuming without "
            "leaving textual traces in the public record. TikTok registers your presence through "
            "behavioral signals (watch time, skips, lingers), not your words."
        )
    elif style_label == "Analytical Commenter":
        prose = (
            f"You are an Analytical Commenter. Your {total} comments average {avg_chars:.0f} "
            f"characters — longer than typical reactions — with low emoji density ({emoji_density:.1%}). "
            f"You engage substantively. {long_pct:.0f}% of your comments exceed 150 characters, "
            f"leaving a readable and interpretable textual record."
        )
    elif style_label == "Reactive Commenter":
        prose = (
            f"You are a Reactive Commenter — quick, frequent responses averaging {avg_chars:.0f} "
            f"characters. Your {total} comments are short-form reactions. Emoji density: "
            f"{emoji_density:.1%}. You're highly engaged but leave minimal interpretable signal "
            f"in your comment text."
        )
    elif style_label == "Lurker":
        prose = (
            f"You comment rarely relative to your viewing volume. Your {total} total comments "
            f"average {avg_chars:.0f} characters. Lurkers account for the majority of TikTok's "
            f"audience — most consumption happens silently, engagement expressed through watch "
            f"time and sharing rather than text."
        )
    else:
        prose = (
            f"You are a {style_label}. {total} total comments averaging {avg_chars:.0f} characters. "
            f"{long_pct:.0f}% exceed 150 characters. Emoji density: {emoji_density:.1%}. "
            f"Your comment behavior reflects deliberate, selective engagement."
        )

    stats = [
        {"label": "Total Comments", "value": str(total)},
        {"label": "Avg Length", "value": f"{avg_chars:.0f} chars"},
        {"label": "Long Comments", "value": f"{long_pct:.0f}%"},
        {"label": "Style", "value": style_label},
    ]

    return {
        "id": "comment_voice",
        "title": "COMMENT VOICE",
        "icon": "💬",
        "prose": prose,
        "accent": "#c8a2c8",
        "stats": stats,
        "chart": None,
    }
```

- [ ] **Step 4: Run all narrative tests**

```bash
cd /Users/danweiman/TikTokAnalyzer && pytest tests/test_narratives.py -v
```

Expected: All tests that don't test blocks 7–9 pass. Tests for blocks 7–9 still fail (stubs).

- [ ] **Step 5: Commit**

```bash
git add api/narratives.py tests/test_narratives.py
git commit -m "feat: add narrative blocks 4-6 (social graph, share behavior, comment voice)"
```

---

## Task 4: Narrative Blocks 7–9 (Transparency Gap, Location Trace, Closing Synthesis)

**Files:**
- Modify: `api/narratives.py` (replace 3 remaining stubs)
- Modify: `tests/test_narratives.py` (add tests for blocks 7–9 + final count check)

- [ ] **Step 1: Add tests for blocks 7–9** (append to `tests/test_narratives.py`)

```python
# Append to tests/test_narratives.py

# ── Block 7: Transparency Gap ─────────────────────────────────────────────────

def test_transparency_gap_schema():
    from api.narratives import _build_transparency_gap_block
    block = _build_transparency_gap_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "transparency_gap")
    assert block["chart"] is not None
    assert block["chart"]["type"] == "bar"


def test_transparency_gap_empty_official():
    from api.narratives import _build_transparency_gap_block
    ghost = _base_ghost()
    ghost["transparency_gap"]["official_ad_interest_count"] = 0
    ghost["transparency_gap"]["behavioral_interest_count"] = 15
    block = _build_transparency_gap_block(ghost, _base_parsed())
    assert "empty" in block["prose"].lower() or "opt-out" in block["prose"].lower() or "no declared" in block["prose"].lower() or "privacy" in block["prose"].lower()


def test_transparency_gap_bar_has_expected_categories():
    from api.narratives import _build_transparency_gap_block
    block = _build_transparency_gap_block(_base_ghost(), _base_parsed())
    names = [d["category"] for d in block["chart"]["data"]]
    assert "Ad Interests" in names
    assert "Logins" in names


# ── Block 8: Location Trace ───────────────────────────────────────────────────

def test_location_trace_schema():
    from api.narratives import _build_location_trace_block
    block = _build_location_trace_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "location_trace")
    assert block["chart"] is None


def test_location_trace_home_city_in_stats():
    from api.narratives import _build_location_trace_block
    block = _build_location_trace_block(_base_ghost(), _base_parsed())
    labels = [s["label"] for s in block["stats"]]
    assert "Home City" in labels
    values = {s["label"]: s["value"] for s in block["stats"]}
    assert values["Home City"] == "Paris"


def test_location_trace_no_logins():
    from api.narratives import _build_location_trace_block
    ghost = _base_ghost()
    ghost["digital_footprint"]["recent_logins"] = []
    block = _build_location_trace_block(ghost, _base_parsed())
    # Should not crash; home city should be Unknown
    values = {s["label"]: s["value"] for s in block["stats"]}
    assert values.get("Home City") == "Unknown"


# ── Block 9: Closing Synthesis ────────────────────────────────────────────────

def test_closing_synthesis_schema():
    from api.narratives import _build_closing_synthesis_block
    block = _build_closing_synthesis_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "closing_synthesis")
    assert block["chart"] is None
    assert block["stats"] == []


def test_closing_synthesis_prose_references_engagement():
    from api.narratives import _build_closing_synthesis_block
    block = _build_closing_synthesis_block(_base_ghost(), _base_parsed())
    prose_lower = block["prose"].lower()
    # Should mention something about engagement or algorithm
    assert any(word in prose_lower for word in ["algorithm", "engagement", "linger", "watch", "behavior"])


# ── Final count check ─────────────────────────────────────────────────────────

def test_build_narrative_blocks_returns_9_after_all_implemented():
    from api.narratives import build_narrative_blocks
    blocks = build_narrative_blocks(_base_ghost(), _base_parsed())
    assert len(blocks) == 9, f"Expected 9 blocks, got {len(blocks)}: {[b['id'] for b in blocks]}"
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd /Users/danweiman/TikTokAnalyzer && pytest tests/test_narratives.py -v -k "transparency or location or closing or returns_9_after"
```

Expected: All fail with `NotImplementedError`.

- [ ] **Step 3: Replace the 3 remaining stubs in `api/narratives.py`**

Replace `_build_transparency_gap_block`, `_build_location_trace_block`, and `_build_closing_synthesis_block`:

```python
# ---------------------------------------------------------------------------
# Block 7 — Transparency Gap
# ---------------------------------------------------------------------------

def _build_transparency_gap_block(ghost_profile: dict, parsed: dict) -> dict:
    tg = ghost_profile.get("transparency_gap", {})
    official_count = int(tg.get("official_ad_interest_count", 0))
    behavioral_count = int(tg.get("behavioral_interest_count", 0))
    interpretation = tg.get("gap_interpretation", "")
    footprint = ghost_profile.get("digital_footprint", {})
    login_count = int(footprint.get("login_count", 0))
    unique_ips = int(footprint.get("unique_ips", 0))
    unique_devices = footprint.get("unique_devices", [])
    device_count = len(unique_devices) if isinstance(unique_devices, list) else int(unique_devices)
    searches = int(ghost_profile.get("search_rhythm", {}).get("total_searches", 0))
    likes = len(parsed.get("likes", []))
    comments = len(parsed.get("comments", []))
    shares = len(parsed.get("shares", []))

    if official_count == 0 and behavioral_count > 5:
        prose = (
            f"Your ad interest profile is empty — TikTok's official record claims no declared "
            f"interests, yet behavioral analysis shows {behavioral_count} inferred interest clusters. "
            f"This suggests a privacy opt-out, region restriction, or data suppression in the export. "
            f"The algorithm sees far more than what it reports to you."
        )
    elif official_count < behavioral_count * 0.5 and behavioral_count > 0:
        prose = (
            f"TikTok's official export shows {official_count} declared ad interest categories — "
            f"but behavioral signals reveal {behavioral_count} active interest clusters. "
            f"{interpretation} What TikTok discloses is a fraction of what it knows."
        )
    else:
        prose = (
            f"Your export contains {official_count} declared ad interest categories, "
            f"roughly matching the {behavioral_count} behavioral clusters. "
            f"Across {login_count} logins, {unique_ips} unique IPs, and {device_count} devices, "
            f"TikTok has assembled a cross-surface profile. {interpretation}"
        )

    stats = [
        {"label": "Declared Interests", "value": str(official_count)},
        {"label": "Behavioral Clusters", "value": str(behavioral_count)},
        {"label": "Login Events", "value": str(login_count)},
        {"label": "Unique IPs", "value": str(unique_ips)},
        {"label": "Unique Devices", "value": str(device_count)},
    ]

    chart_data = [
        {"category": "Ad Interests", "count": official_count},
        {"category": "Behaviors", "count": behavioral_count},
        {"category": "Searches", "count": searches},
        {"category": "Likes", "count": likes},
        {"category": "Comments", "count": comments},
        {"category": "Shares", "count": shares},
        {"category": "Logins", "count": login_count},
    ]

    return {
        "id": "transparency_gap",
        "title": "TRANSPARENCY GAP",
        "icon": "🔍",
        "prose": prose,
        "accent": "#ff4466",
        "stats": stats,
        "chart": {"type": "bar", "data": chart_data},
    }


# ---------------------------------------------------------------------------
# Block 8 — Location Trace
# ---------------------------------------------------------------------------

def _build_location_trace_block(ghost_profile: dict, parsed: dict) -> dict:
    footprint = ghost_profile.get("digital_footprint", {})
    logins: list[dict] = footprint.get("recent_logins", [])

    city_counter: Counter = Counter()
    country_counter: Counter = Counter()
    for login in logins:
        city = login.get("city", "") or ""
        country = login.get("country_name", "") or ""
        if city and city != "Unknown":
            city_counter[city] += 1
        if country and country != "Unknown":
            country_counter[country] += 1

    home_city = city_counter.most_common(1)[0][0] if city_counter else "Unknown"
    country_count = len(country_counter)
    city_count = len(city_counter)
    top_country = list(country_counter.keys())[0] if country_counter else "one country"

    sorted_logins = sorted(logins, key=lambda l: l.get("date", ""))
    first_login = sorted_logins[0].get("date", "Unknown")[:10] if sorted_logins else "Unknown"

    if country_count > 3:
        prose = (
            f"TikTok has tracked you across {country_count} countries and {city_count} cities. "
            f"Your login history spans significant geographic range — {home_city} appears most "
            f"frequently. Cross-border usage means your data may be subject to multiple regulatory "
            f"jurisdictions simultaneously."
        )
    elif city_count > 5:
        prose = (
            f"Your TikTok activity has been logged from {city_count} distinct cities, primarily "
            f"in {top_country}. Home base: {home_city}. First recorded login: {first_login}. "
            f"Each login IP is a geolocation data point TikTok retains indefinitely."
        )
    else:
        prose = (
            f"Your login history is geographically concentrated — primarily {home_city}. "
            f"First recorded login: {first_login}. TikTok has logged {len(logins)} login events "
            f"with associated IPs. Even a single IP can reveal your home ISP, city, and "
            f"approximate neighborhood."
        )

    stats = [
        {"label": "Home City", "value": home_city},
        {"label": "Countries Seen", "value": str(country_count)},
        {"label": "Cities Seen", "value": str(city_count)},
        {"label": "First Login", "value": first_login},
        {"label": "Login Events", "value": str(len(logins))},
    ]

    return {
        "id": "location_trace",
        "title": "WHERE TIKTOK FOUND YOU",
        "icon": "📍",
        "prose": prose,
        "accent": "#00e5ff",
        "stats": stats,
        "chart": None,
    }


# ---------------------------------------------------------------------------
# Block 9 — Closing Synthesis
# ---------------------------------------------------------------------------

def _build_closing_synthesis_block(ghost_profile: dict, parsed: dict) -> dict:
    bn = ghost_profile.get("behavioral_nodes", {})
    followed_pct = float(bn.get("social_graph_followed_pct", 0))
    linger_rate = float(bn.get("linger_rate_percentage", 0))
    tg = ghost_profile.get("transparency_gap", {})
    official = int(tg.get("official_ad_interest_count", 0))
    behavioral = int(tg.get("behavioral_interest_count", 0))
    cv = ghost_profile.get("comment_voice", {})
    style = cv.get("engagement_style_label", "Lurker")

    if linger_rate > 20 and followed_pct > 50:
        engagement = "a loyal, deep watcher whose attention is genuinely intentional"
    elif linger_rate > 20 and followed_pct < 30:
        engagement = "a deep but algorithmically-captured viewer — you watch closely, but the machine picks what"
    elif linger_rate < 10 and followed_pct < 30:
        engagement = "a passive scroller whose engagement is broad and shallow"
    else:
        engagement = "a balanced viewer with moderate engagement depth"

    gap_ratio = official / max(behavioral, 1)
    if gap_ratio < 0.5:
        exposure = "significant — the official export substantially under-represents TikTok's model of you"
    else:
        exposure = "moderate — declared interests roughly match behavioral signals"

    textual_trace = "a readable textual trace" if style != "Lurker" else "almost no public record"

    prose = (
        f"Across your usage history, you emerge as {engagement}. "
        f"The algorithm characterizes you through behavior rather than stated preferences: "
        f"every linger, skip, and late-night session updates a model you never consented to build. "
        f"Your transparency gap is {exposure}. "
        f"As a {style.lower()}, your comment behavior leaves {textual_trace}. "
        f"This dossier is a partial reconstruction — TikTok's actual model is orders of magnitude more granular."
    )

    return {
        "id": "closing_synthesis",
        "title": "CLOSING SYNTHESIS",
        "icon": "🧠",
        "prose": prose,
        "accent": "#e0e0e0",
        "stats": [],
        "chart": None,
    }
```

- [ ] **Step 4: Run all narrative tests**

```bash
cd /Users/danweiman/TikTokAnalyzer && pytest tests/test_narratives.py -v
```

Expected: All tests pass. `test_build_narrative_blocks_returns_9_after_all_implemented` should now show 9 blocks.

- [ ] **Step 5: Commit**

```bash
git add api/narratives.py tests/test_narratives.py
git commit -m "feat: add narrative blocks 7-9 (transparency gap, location trace, synthesis)"
```

---

## Task 5: Wire into `api/main.py` + Integration Test

**Files:**
- Modify: `api/main.py:103-135` (the `/api/analyze` route)
- Modify: `tests/test_api.py` (add narrative_blocks assertion)

- [ ] **Step 1: Add integration test** (append to `tests/test_api.py`)

```python
# Append to tests/test_api.py
from unittest.mock import patch, AsyncMock

def test_analyze_returns_narrative_blocks():
    """narrative_blocks should be present with 9 items after wiring."""
    fake_export = {
        "Activity": {
            "Video Browsing History": {
                "VideoList": [
                    {"Date": "2023-10-01 10:00:00", "VideoLink": "https://www.tiktok.com/@user1/video/12345"},
                    {"Date": "2023-10-01 10:00:03", "VideoLink": "https://www.tiktok.com/@user2/video/67890"},
                ]
            }
        }
    }
    # Mock enrich_logins_with_geo to avoid real HTTP calls
    with patch("api.main.enrich_logins_with_geo", new_callable=AsyncMock) as mock_enrich:
        mock_enrich.return_value = []  # no logins to enrich in this fixture
        response = client.post(
            "/api/analyze",
            files={"file": ("user_data_tiktok.json", json.dumps(fake_export).encode("utf-8"))}
        )
    assert response.status_code == 200
    data = response.json()
    assert "narrative_blocks" in data
    assert isinstance(data["narrative_blocks"], list)
    assert len(data["narrative_blocks"]) == 9
    # Check first block schema
    b = data["narrative_blocks"][0]
    assert b["id"] == "algorithmic_identity"
    assert "prose" in b
    assert "stats" in b
    assert "accent" in b
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/danweiman/TikTokAnalyzer && pytest tests/test_api.py::test_analyze_returns_narrative_blocks -v
```

Expected: FAIL — `"narrative_blocks" not in data`

- [ ] **Step 3: Modify `api/main.py` — add imports and update the `/api/analyze` route**

At the top of `api/main.py`, add these two imports after the existing imports:

```python
from api.narratives import build_narrative_blocks
from utils.ip_geo import enrich_logins_with_geo
```

Replace the `/api/analyze` route body (the section from `return build_ghost_profile(...)` at line 135) with:

```python
    ghost_profile = build_ghost_profile(parsed, exclude_hours=exclude_hours)

    # Enrich recent_logins with geolocation data (async, cached, fallback-safe)
    raw_logins: list[dict] = ghost_profile.get("digital_footprint", {}).get("recent_logins", [])
    if raw_logins:
        enriched_logins = await enrich_logins_with_geo(raw_logins)
        ghost_profile["digital_footprint"]["recent_logins"] = enriched_logins

    narrative_blocks = build_narrative_blocks(ghost_profile, parsed)

    return {**ghost_profile, "narrative_blocks": narrative_blocks}
```

The full updated route becomes:

```python
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
            exclude_hours = tuple(range(sleep_start, 24)) + tuple(range(0, sleep_end + 1))
    else:
        exclude_hours = ()

    ghost_profile = build_ghost_profile(parsed, exclude_hours=exclude_hours)

    # Enrich recent_logins with geolocation (async, cached, fallback-safe)
    raw_logins: list[dict] = ghost_profile.get("digital_footprint", {}).get("recent_logins", [])
    if raw_logins:
        enriched_logins = await enrich_logins_with_geo(raw_logins)
        ghost_profile["digital_footprint"]["recent_logins"] = enriched_logins

    narrative_blocks = build_narrative_blocks(ghost_profile, parsed)

    return {**ghost_profile, "narrative_blocks": narrative_blocks}
```

- [ ] **Step 4: Run all backend tests**

```bash
cd /Users/danweiman/TikTokAnalyzer && pytest tests/ -v
```

Expected: All existing tests pass, plus the new `test_analyze_returns_narrative_blocks` passes.

- [ ] **Step 5: Commit**

```bash
git add api/main.py tests/test_api.py
git commit -m "feat: wire narrative_blocks into /api/analyze response"
```

---

## Task 6: TypeScript Types

**Files:**
- Create: `algorithmic-mirror/app/types/narrative.ts`

- [ ] **Step 1: Create the types file**

```typescript
// algorithmic-mirror/app/types/narrative.ts

export interface NarrativeStat {
  label: string;
  value: string;
}

export interface NarrativeChart {
  type: "bar" | "line" | "donut";
  data: Record<string, unknown>[];
}

export interface NarrativeBlock {
  id: string;
  title: string;
  icon: string;
  prose: string;
  accent: string;
  stats: NarrativeStat[];
  chart?: NarrativeChart | null;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/danweiman/TikTokAnalyzer/algorithmic-mirror && npx tsc --noEmit 2>&1 | head -20
```

Expected: No errors (or only pre-existing errors unrelated to the new file).

- [ ] **Step 3: Commit**

```bash
git add algorithmic-mirror/app/types/narrative.ts
git commit -m "feat: add NarrativeBlock TypeScript types"
```

---

## Task 7: Install Recharts + BlockCard Component + Tests

**Files:**
- Modify: `algorithmic-mirror/package.json` (add recharts)
- Create: `algorithmic-mirror/app/components/BlockCard.tsx`
- Create: `algorithmic-mirror/__tests__/BlockCard.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// algorithmic-mirror/__tests__/BlockCard.test.tsx
import React from 'react';
import { render, screen } from '@testing-library/react';
import { BlockCard } from '../app/components/BlockCard';
import type { NarrativeBlock } from '../app/types/narrative';

// Recharts uses ResizeObserver and SVG dimensions unavailable in jsdom — mock it
jest.mock('recharts', () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  PieChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="pie-chart">{children}</div>
  ),
  Pie: () => null,
  Cell: () => null,
}));

const mockBarBlock: NarrativeBlock = {
  id: "test_block",
  title: "TEST BLOCK",
  icon: "🧪",
  prose: "This is the test prose paragraph.",
  accent: "#4db8ff",
  stats: [
    { label: "Metric A", value: "42%" },
    { label: "Metric B", value: "100" },
  ],
  chart: {
    type: "bar",
    data: [{ metric: "X", value: 10 }, { metric: "Y", value: 20 }],
  },
};

const mockDonutBlock: NarrativeBlock = {
  ...mockBarBlock,
  id: "donut_block",
  chart: { type: "donut", data: [{ name: "A", value: 30 }, { name: "B", value: 70 }] },
};

const mockNoChartBlock: NarrativeBlock = {
  ...mockBarBlock,
  id: "no_chart_block",
  chart: null,
};

test('renders icon and title', () => {
  render(<BlockCard block={mockBarBlock} />);
  expect(screen.getByText('🧪')).toBeInTheDocument();
  expect(screen.getByText('TEST BLOCK')).toBeInTheDocument();
});

test('renders prose', () => {
  render(<BlockCard block={mockBarBlock} />);
  expect(screen.getByText('This is the test prose paragraph.')).toBeInTheDocument();
});

test('renders stats labels and values', () => {
  render(<BlockCard block={mockBarBlock} />);
  expect(screen.getByText('Metric A')).toBeInTheDocument();
  expect(screen.getByText('42%')).toBeInTheDocument();
  expect(screen.getByText('Metric B')).toBeInTheDocument();
  expect(screen.getByText('100')).toBeInTheDocument();
});

test('renders bar chart for bar type', () => {
  render(<BlockCard block={mockBarBlock} />);
  expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  expect(screen.queryByTestId('pie-chart')).not.toBeInTheDocument();
});

test('renders pie chart for donut type', () => {
  render(<BlockCard block={mockDonutBlock} />);
  expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
  expect(screen.queryByTestId('bar-chart')).not.toBeInTheDocument();
});

test('renders no chart when chart is null', () => {
  render(<BlockCard block={mockNoChartBlock} />);
  expect(screen.queryByTestId('bar-chart')).not.toBeInTheDocument();
  expect(screen.queryByTestId('pie-chart')).not.toBeInTheDocument();
});

test('renders no stats section when stats is empty', () => {
  const noStatsBlock: NarrativeBlock = { ...mockBarBlock, stats: [], chart: null };
  render(<BlockCard block={noStatsBlock} />);
  // Prose still visible
  expect(screen.getByText('This is the test prose paragraph.')).toBeInTheDocument();
  // No stat labels
  expect(screen.queryByText('Metric A')).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/danweiman/TikTokAnalyzer/algorithmic-mirror && npm test -- --testPathPattern="BlockCard" --no-coverage 2>&1 | tail -20
```

Expected: `Cannot find module '../app/components/BlockCard'`

- [ ] **Step 3: Install recharts**

```bash
cd /Users/danweiman/TikTokAnalyzer/algorithmic-mirror && npm install recharts@^2.12.0
```

Expected: `added N packages` with no errors.

- [ ] **Step 4: Create `algorithmic-mirror/app/components/BlockCard.tsx`**

```tsx
// algorithmic-mirror/app/components/BlockCard.tsx
"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import type { NarrativeBlock } from "../types/narrative";

const CHART_PALETTE = [
  "#4db8ff",
  "#ff8c42",
  "#a8ff78",
  "#ff4db8",
  "#ffd700",
  "#c8a2c8",
  "#ff4466",
  "#00e5ff",
];

function BlockBarChart({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return null;
  const keys = Object.keys(data[0]);
  const xKey = keys[0] ?? "name";
  const yKey = keys[1] ?? "value";
  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
        <XAxis
          dataKey={xKey}
          tick={{ fill: "#888", fontSize: 10, fontFamily: "ui-monospace, monospace" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis hide />
        <Tooltip
          contentStyle={{
            background: "#111",
            border: "1px solid #333",
            color: "#eee",
            fontSize: 11,
            fontFamily: "ui-monospace, monospace",
          }}
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
        />
        <Bar dataKey={yKey} fill="#4db8ff" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function BlockDonutChart({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return null;
  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={45}
          outerRadius={75}
          paddingAngle={2}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={CHART_PALETTE[i % CHART_PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "#111",
            border: "1px solid #333",
            color: "#eee",
            fontSize: 11,
            fontFamily: "ui-monospace, monospace",
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

interface BlockCardProps {
  block: NarrativeBlock;
}

export function BlockCard({ block }: BlockCardProps) {
  const chart = useMemo(() => {
    if (!block.chart || !block.chart.data.length) return null;
    if (block.chart.type === "bar") return <BlockBarChart data={block.chart.data} />;
    if (block.chart.type === "donut") return <BlockDonutChart data={block.chart.data} />;
    return null;
  }, [block.chart]);

  return (
    <div
      style={{
        background: "#111",
        border: "1px solid #1e1e1e",
        borderLeft: `4px solid ${block.accent}`,
        padding: "20px 24px",
        fontFamily: "ui-monospace, Menlo, Monaco, 'Cascadia Mono', monospace",
      }}
    >
      {/* Icon + Title */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 14,
        }}
      >
        <span style={{ fontSize: 18, lineHeight: 1 }}>{block.icon}</span>
        <span
          style={{
            fontSize: 10,
            letterSpacing: "0.25em",
            color: block.accent,
            fontWeight: 700,
            textTransform: "uppercase",
          }}
        >
          {block.title}
        </span>
      </div>

      {/* Prose */}
      <p
        style={{
          fontSize: 13,
          lineHeight: 1.8,
          color: "#bbb",
          marginBottom: 16,
          maxWidth: 640,
        }}
      >
        {block.prose}
      </p>

      {/* Stats */}
      {block.stats.length > 0 && (
        <dl
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
            gap: "8px 12px",
            marginBottom: chart ? 20 : 0,
          }}
        >
          {block.stats.map((stat) => (
            <div
              key={stat.label}
              style={{ background: "#1a1a1a", padding: "8px 12px" }}
            >
              <dt
                style={{
                  fontSize: 9,
                  letterSpacing: "0.15em",
                  color: "#555",
                  textTransform: "uppercase",
                }}
              >
                {stat.label}
              </dt>
              <dd
                style={{
                  fontSize: 14,
                  color: "#eee",
                  marginTop: 3,
                  fontWeight: 600,
                }}
              >
                {stat.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {/* Chart */}
      {chart}
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/danweiman/TikTokAnalyzer/algorithmic-mirror && npm test -- --testPathPattern="BlockCard" --no-coverage 2>&1 | tail -20
```

Expected: 7 tests pass.

- [ ] **Step 6: Commit**

```bash
git add algorithmic-mirror/app/components/BlockCard.tsx algorithmic-mirror/__tests__/BlockCard.test.tsx algorithmic-mirror/package.json algorithmic-mirror/package-lock.json
git commit -m "feat: add BlockCard component with Recharts bar and donut support"
```

---

## Task 8: NarrativeReportView Component + Tests

**Files:**
- Create: `algorithmic-mirror/app/components/NarrativeReportView.tsx`
- Create: `algorithmic-mirror/__tests__/NarrativeReportView.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// algorithmic-mirror/__tests__/NarrativeReportView.test.tsx
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { NarrativeReportView } from '../app/components/NarrativeReportView';
import type { NarrativeBlock } from '../app/types/narrative';

// Mock recharts (same as BlockCard tests)
jest.mock('recharts', () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  PieChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="pie-chart">{children}</div>
  ),
  Pie: () => null,
  Cell: () => null,
}));

const makeBlock = (id: string, title: string): NarrativeBlock => ({
  id,
  title,
  icon: "🔹",
  prose: `Prose for ${title}.`,
  accent: "#4db8ff",
  stats: [],
  chart: null,
});

const twoBlocks: NarrativeBlock[] = [
  makeBlock("b1", "FIRST BLOCK"),
  makeBlock("b2", "SECOND BLOCK"),
];

test('renders DOSSIER header', () => {
  render(<NarrativeReportView narrativeBlocks={twoBlocks} onBack={jest.fn()} />);
  expect(screen.getByText('DOSSIER')).toBeInTheDocument();
});

test('renders all blocks', () => {
  render(<NarrativeReportView narrativeBlocks={twoBlocks} onBack={jest.fn()} />);
  expect(screen.getByText('FIRST BLOCK')).toBeInTheDocument();
  expect(screen.getByText('SECOND BLOCK')).toBeInTheDocument();
});

test('renders prose for each block', () => {
  render(<NarrativeReportView narrativeBlocks={twoBlocks} onBack={jest.fn()} />);
  expect(screen.getByText('Prose for FIRST BLOCK.')).toBeInTheDocument();
  expect(screen.getByText('Prose for SECOND BLOCK.')).toBeInTheDocument();
});

test('Back button calls onBack', () => {
  const onBack = jest.fn();
  render(<NarrativeReportView narrativeBlocks={twoBlocks} onBack={onBack} />);
  fireEvent.click(screen.getByRole('button', { name: /back/i }));
  expect(onBack).toHaveBeenCalledTimes(1);
});

test('renders empty state gracefully with no blocks', () => {
  render(<NarrativeReportView narrativeBlocks={[]} onBack={jest.fn()} />);
  expect(screen.getByText('DOSSIER')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/danweiman/TikTokAnalyzer/algorithmic-mirror && npm test -- --testPathPattern="NarrativeReportView" --no-coverage 2>&1 | tail -10
```

Expected: `Cannot find module '../app/components/NarrativeReportView'`

- [ ] **Step 3: Create `algorithmic-mirror/app/components/NarrativeReportView.tsx`**

```tsx
// algorithmic-mirror/app/components/NarrativeReportView.tsx
"use client";

import { BlockCard } from "./BlockCard";
import type { NarrativeBlock } from "../types/narrative";

interface Props {
  narrativeBlocks: NarrativeBlock[];
  onBack: () => void;
}

export function NarrativeReportView({ narrativeBlocks, onBack }: Props) {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0a0a0a",
        color: "#eee",
        fontFamily: "ui-monospace, Menlo, Monaco, monospace",
      }}
    >
      {/* Sticky header */}
      <div
        style={{
          position: "sticky",
          top: 0,
          zIndex: 10,
          background: "#0a0a0a",
          borderBottom: "1px solid #1a1a1a",
          padding: "16px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span
          style={{
            fontSize: 11,
            letterSpacing: "0.38em",
            color: "#4db8ff",
            textTransform: "uppercase",
            fontWeight: 700,
          }}
        >
          DOSSIER
        </span>
        <button
          onClick={onBack}
          aria-label="Back"
          style={{
            fontFamily: "ui-monospace, Menlo, Monaco, monospace",
            fontSize: 10,
            letterSpacing: "0.2em",
            color: "#888",
            background: "transparent",
            border: "1px solid #333",
            padding: "6px 16px",
            cursor: "pointer",
            textTransform: "uppercase",
          }}
        >
          ← Back
        </button>
      </div>

      {/* Block list */}
      <div
        style={{
          maxWidth: 720,
          margin: "0 auto",
          padding: "32px 24px 80px",
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        {narrativeBlocks.map((block) => (
          <BlockCard key={block.id} block={block} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/danweiman/TikTokAnalyzer/algorithmic-mirror && npm test -- --testPathPattern="NarrativeReportView" --no-coverage 2>&1 | tail -15
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/NarrativeReportView.tsx algorithmic-mirror/__tests__/NarrativeReportView.test.tsx
git commit -m "feat: add NarrativeReportView dossier component"
```

---

## Task 9: Wire "report" View in page.tsx + TheGlassHouse DOSSIER Button

**Files:**
- Modify: `algorithmic-mirror/app/page.tsx`
- Modify: `algorithmic-mirror/app/components/TheGlassHouse.tsx`

**Context for implementer:** `page.tsx` currently has `type View = "upload" | "narrative" | "hud"`. The `analyze()` function fetches from `/api/analyze` and casts the result as `GhostProfile`. The result now also contains `narrative_blocks` (array). `TheGlassHouse` is rendered at line 62–71 with props `profile`, `onReset`, `onViewRawForensics`, `sourceFile`.

- [ ] **Step 1: Update `page.tsx`**

Make these changes to `algorithmic-mirror/app/page.tsx`:

**1a. Add the import** at the top (after existing imports):
```tsx
import { NarrativeReportView } from "./components/NarrativeReportView";
import type { NarrativeBlock } from "./types/narrative";
```

**1b. Update the `View` type** (line 11):
```tsx
type View = "upload" | "narrative" | "hud" | "report";
```

**1c. Add `narrativeBlocks` state** (after the `uploadedFile` state declaration, currently around line 19):
```tsx
const [narrativeBlocks, setNarrativeBlocks] = useState<NarrativeBlock[]>([]);
```

**1d. Update `analyze()`** — replace `const data: GhostProfile = await res.json();` (line 33) through `setView("narrative");` with:
```tsx
      const raw = await res.json();
      setProfile(raw as GhostProfile);
      setNarrativeBlocks((raw as { narrative_blocks?: NarrativeBlock[] }).narrative_blocks ?? []);
      setView("narrative");
```

**1e. Update `handleReset()`** — add `setNarrativeBlocks([]);` inside the function body after `setUploadedFile(null);`:
```tsx
  const handleReset = () => {
    setProfile(null);
    setView("upload");
    setError(null);
    setUploadedFile(null);
    setNarrativeBlocks([]);
  };
```

**1f. Add the `"report"` view branch** — insert this block BEFORE the `if (profile && view === "narrative")` block (currently around line 62):
```tsx
  if (profile && view === "report") {
    return (
      <NarrativeReportView
        narrativeBlocks={narrativeBlocks}
        onBack={() => setView("narrative")}
      />
    );
  }
```

**1g. Pass `onOpenReport` to TheGlassHouse** — in the `view === "narrative"` branch (currently line 64), update the `<TheGlassHouse>` element to add the prop:
```tsx
      <TheGlassHouse
        profile={profile}
        onReset={handleReset}
        onViewRawForensics={() => setView("hud")}
        sourceFile={uploadedFile ?? undefined}
        onOpenReport={() => setView("report")}
      />
```

- [ ] **Step 2: Update `TheGlassHouse.tsx`**

**2a. Add `onOpenReport` to the Props interface** (currently at line 294–299):
```tsx
interface Props {
  profile: GhostProfile;
  onReset: () => void;
  onViewRawForensics: () => void;
  sourceFile?: File;
  onOpenReport?: () => void;
}
```

**2b. Destructure `onOpenReport`** in the function signature (line 301):
```tsx
export function TheGlassHouse({ profile, onReset, onViewRawForensics, sourceFile, onOpenReport }: Props) {
```

**2c. Add the "DOSSIER →" button** in the header (after the existing `<DownloadExportButton>` block, before the closing `</header>` tag at line 427). The current header ends with:
```tsx
            {sourceFile && (
              <DownloadExportButton
                file={sourceFile}
                apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
              />
            )}
          </header>
```

Replace with:
```tsx
            {sourceFile && (
              <DownloadExportButton
                file={sourceFile}
                apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
              />
            )}
            {onOpenReport && (
              <button
                onClick={onOpenReport}
                style={{
                  fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                  fontSize: 10,
                  letterSpacing: "0.28em",
                  textTransform: "uppercase",
                  color: "#1a1610",
                  background: "transparent",
                  border: "1px solid rgba(26,22,16,0.4)",
                  padding: "6px 14px",
                  cursor: "pointer",
                }}
              >
                DOSSIER →
              </button>
            )}
          </header>
```

- [ ] **Step 3: Verify the TypeScript compiles with no new errors**

```bash
cd /Users/danweiman/TikTokAnalyzer/algorithmic-mirror && npx tsc --noEmit 2>&1 | head -30
```

Expected: No new errors (there may be pre-existing errors from before this work; those are not your responsibility).

- [ ] **Step 4: Run the full frontend test suite**

```bash
cd /Users/danweiman/TikTokAnalyzer/algorithmic-mirror && npm test -- --no-coverage 2>&1 | tail -20
```

Expected: All existing tests still pass; no regressions. The new BlockCard and NarrativeReportView tests pass.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/page.tsx algorithmic-mirror/app/components/TheGlassHouse.tsx
git commit -m "feat: add DOSSIER view with narrative blocks to frontend"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ `utils/ip_geo.py` — Task 1
- ✅ `api/narratives.py` with 9 blocks — Tasks 2, 3, 4
- ✅ Block schema: `{id, title, icon, prose, accent, stats, chart}` — Tasks 2–4
- ✅ Wire into `/api/analyze` as `narrative_blocks` — Task 5
- ✅ IP geo enrichment in async route handler — Task 5
- ✅ TypeScript types — Task 6
- ✅ `BlockCard.tsx` with bar and donut charts — Task 7
- ✅ `NarrativeReportView.tsx` — Task 8
- ✅ `"report"` view in `page.tsx` — Task 9
- ✅ `onOpenReport` prop + "DOSSIER →" button in TheGlassHouse — Task 9
- ✅ Recharts dependency — Task 7
- ✅ `handleReset` clears `narrativeBlocks` — Task 9
- ✅ Tests for all new modules — each task

**No placeholders:** All code blocks are complete implementations.

**Type consistency:** `NarrativeBlock` defined in Task 6, imported in Tasks 7, 8, 9. Block ids defined in Task 2 match what Task 5's integration test checks.
