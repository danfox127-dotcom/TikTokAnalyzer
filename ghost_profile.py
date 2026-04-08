"""
Ghost Profile Scoring Engine
Converts a parsed TikTok export dict (from parsers.tiktok) into the
algorithmic forensics payload the Next.js frontend expects.

Public API
----------
    build_ghost_profile(parsed: dict) -> dict
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Keyword sets used for interest-based inference
# ---------------------------------------------------------------------------

_ASPIRATIONAL_KEYWORDS = {
    "fitness", "health", "beauty", "fashion", "luxury", "travel",
    "real estate", "entrepreneur", "investing", "investment", "lifestyle",
    "wellness", "yoga", "diet", "weight loss", "career", "success",
    "motivation", "self improvement", "personal development",
}

_NOSTALGIC_KEYWORDS = {
    "retro", "vintage", "nostalgia", "classic", "throwback", "90s",
    "80s", "70s", "old school", "memories", "childhood", "y2k",
    "golden age", "millennials", "gen x",
}

_OUTRAGE_KEYWORDS = {
    "politics", "news", "current events", "social issues", "conservative",
    "liberal", "progressive", "activism", "protest", "social justice",
    "election", "voting", "government", "immigration", "gun", "abortion",
    "climate", "controversy", "scandal", "debate",
}

_ESCAPISM_KEYWORDS = {
    "gaming", "anime", "fantasy", "fiction", "movies", "tv shows",
    "streaming", "memes", "comedy", "entertainment", "celebrity",
    "k-pop", "music", "art", "crafts", "diy", "cooking", "asmr",
}

_LUXURY_AD_KEYWORDS = {
    "luxury", "premium", "high-end", "designer", "wealth", "real estate",
    "investing", "investment", "stocks", "crypto", "yacht", "travel",
}

_BUDGET_AD_KEYWORDS = {
    "discount", "deal", "sale", "coupon", "budget", "affordable",
    "personal finance", "debt", "loan", "payday", "pawn",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _keyword_score(items: list[str], keyword_set: set[str]) -> int:
    """Count how many items (lowercased) contain at least one keyword."""
    hits = 0
    for item in items:
        low = item.lower()
        if any(kw in low for kw in keyword_set):
            hits += 1
    return hits


def _compute_peak_hour(hourly_heatmap: dict) -> str:
    """
    Given the hourly_heatmap dict (keys are string hour ints "0"–"23"),
    return the peak hour formatted as e.g. "02:00 AM".
    """
    if not hourly_heatmap or all(v == 0 for v in hourly_heatmap.values()):
        return "Unknown"
    peak_str = max(hourly_heatmap, key=lambda h: hourly_heatmap.get(h, 0))
    hour = int(peak_str)
    if hour == 0:
        return "12:00 AM"
    if hour < 12:
        return f"{hour:02d}:00 AM"
    if hour == 12:
        return "12:00 PM"
    return f"{hour - 12:02d}:00 PM"


def _infer_age(birth_date: str, night_shift: float, skip_rate: float) -> str:
    """Return an age-bracket string, falling back to behavioral heuristics."""
    if birth_date:
        try:
            from datetime import date
            parts = birth_date.replace("/", "-").split("-")
            year = int(parts[0]) if len(parts[0]) == 4 else int(parts[-1])
            age = date.today().year - year
            if age < 18:
                return "Under 18"
            if age <= 24:
                return "18–24"
            if age <= 34:
                return "25–34"
            if age <= 44:
                return "35–44"
            if age <= 54:
                return "45–54"
            return "55+"
        except (ValueError, IndexError):
            pass
    # Behavioral fallback: heavy night usage + fast scrolling → younger skew
    if night_shift > 35 and skip_rate > 60:
        return "18–24"
    if night_shift > 20 or skip_rate > 50:
        return "25–34"
    return "35–44"


def _infer_income(luxury_hits: int, budget_hits: int, order_count: int) -> str:
    if luxury_hits >= 3:
        return "Medium-High"
    if luxury_hits >= 1 and budget_hits == 0:
        return "Medium"
    if budget_hits >= 2 or (order_count > 5 and luxury_hits == 0):
        return "Low"
    if order_count > 10:
        return "Medium"
    return "Medium-Low"


def _infer_vulnerability(
    doomscrolling: int,
    night_shift: float,
    skip_rate: float,
    linger_rate: float,  # noqa: ARG001  (reserved for future use)
) -> str:
    """Composite stress / compulsion signal."""
    stress_score = doomscrolling * 0.5 + night_shift * 0.3 + skip_rate * 0.2
    if stress_score >= 55:
        return "CRITICAL: High Stress / Fatigue"
    if stress_score >= 35:
        return "HIGH: Elevated Compulsive Patterns"
    if stress_score >= 20:
        return "MODERATE: Occasional Escape Behavior"
    return "LOW: Controlled Usage"


def _infer_political_lean(
    outrage_score: int,
    all_interests: list[str],
    blocked_count: int,
) -> str:
    if outrage_score < 15 and blocked_count == 0:
        return "Apolitical"
    if outrage_score >= 60 or blocked_count >= 10:
        return "Highly Polarized"

    low = " ".join(all_interests).lower()
    conservative_signals = sum(
        1 for kw in ["conservative", "republican", "right", "maga", "trump", "fox"]
        if kw in low
    )
    progressive_signals = sum(
        1 for kw in ["progressive", "democrat", "liberal", "left", "socialist", "blm"]
        if kw in low
    )
    if conservative_signals > progressive_signals:
        return "Right-Leaning"
    if progressive_signals > conservative_signals:
        return "Left-Leaning"
    if outrage_score >= 30:
        return "Polarized (Undetermined)"
    return "Moderate"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_ghost_profile(parsed: dict) -> dict:
    """
    Derive the Ghost Profile payload from a parsed TikTok export.

    Args:
        parsed: The dict returned by parsers.tiktok.parse_tiktok_export[_from_bytes].

    Returns:
        Full Ghost Profile dict ready to serialize as JSON.
        All vibe_vector scores are ints in [0, 100].
    """
    ba = parsed.get("behavioral_analysis", {})
    profile = parsed.get("profile", {})
    ad_interests: list[str] = parsed.get("ad_interests", [])
    settings_interests: list[str] = parsed.get("settings_interests", [])
    all_interests = ad_interests + settings_interests
    search_terms = [s.get("term", "") for s in parsed.get("searches", []) if s.get("term")]
    blocked_count = len(parsed.get("blocked_users", []))
    favorites_count = len(parsed.get("favorites", []))
    shop_orders = parsed.get("shop_orders", [])

    # Behavioral primitives from the parser
    skip_rate: float = ba.get("skip_rate", 0.0)
    linger_rate: float = ba.get("linger_rate", 0.0)
    night_shift: float = ba.get("night_shift_ratio", 0.0)
    total_videos: int = ba.get("total_videos", 0)
    skip_count: int = ba.get("skip_count", 0)
    casual_count: int = ba.get("casual_count", 0)
    linger_count: int = ba.get("linger_count", 0)
    hourly_heatmap: dict = ba.get("hourly_heatmap", {})

    # ── Vibe Vectors ──────────────────────────────────────────────────────

    # Doomscrolling: rapid scrolling + night usage + raw volume
    volume_factor = min(total_videos / 2000 * 20, 20)          # up to 20 pts
    doomscrolling = int(min(100, skip_rate * 0.5 + night_shift * 0.4 + volume_factor))

    # Escapism: lingering on entertainment + saved/favorited content
    escapism_interest_score = min(_keyword_score(all_interests, _ESCAPISM_KEYWORDS) * 5, 40)
    escapism = int(min(100, linger_rate * 0.5 + escapism_interest_score + min(favorites_count / 10, 15)))

    # Aspirational: ad-targeting interests matching aspirational themes
    aspirational_hits = _keyword_score(all_interests, _ASPIRATIONAL_KEYWORDS)
    aspirational_search_hits = _keyword_score(search_terms, _ASPIRATIONAL_KEYWORDS)
    aspirational = int(min(100, aspirational_hits * 8 + aspirational_search_hits * 4))

    # Nostalgic: search terms and interest keywords with nostalgic signals
    nostalgic_search_hits = _keyword_score(search_terms, _NOSTALGIC_KEYWORDS)
    nostalgic_interest_hits = _keyword_score(all_interests, _NOSTALGIC_KEYWORDS)
    nostalgic = int(min(100, nostalgic_search_hits * 12 + nostalgic_interest_hits * 6))

    # Outrage mechanics: political interests + block behaviour + political searches
    outrage_interest_hits = _keyword_score(all_interests, _OUTRAGE_KEYWORDS)
    outrage_search_hits = _keyword_score(search_terms, _OUTRAGE_KEYWORDS)
    block_factor = min(blocked_count * 3, 30)
    outrage_mechanics = int(min(100, outrage_interest_hits * 6 + outrage_search_hits * 4 + block_factor))

    # ── Target Lock Inferences ────────────────────────────────────────────

    estimated_age = _infer_age(profile.get("birth_date", ""), night_shift, skip_rate)

    luxury_hits = _keyword_score(ad_interests, _LUXURY_AD_KEYWORDS)
    budget_hits = _keyword_score(ad_interests, _BUDGET_AD_KEYWORDS)
    inferred_income = _infer_income(luxury_hits, budget_hits, len(shop_orders))

    vulnerability_state = _infer_vulnerability(doomscrolling, night_shift, skip_rate, linger_rate)
    political_lean = _infer_political_lean(outrage_mechanics, all_interests, blocked_count)

    # ── Raw Metrics ───────────────────────────────────────────────────────

    # Estimate watch time: skip≈1.5 s, casual≈9 s, linger≈30 s
    watch_seconds = skip_count * 1.5 + casual_count * 9 + linger_count * 30
    total_watch_time_minutes = int(watch_seconds / 60)

    # ── Behavioral Nodes ─────────────────────────────────────────────────

    peak_activity_hour = _compute_peak_hour(hourly_heatmap)

    return {
        "status": "success",
        "vibe_vectors": {
            "doomscrolling": doomscrolling,
            "escapism": escapism,
            "aspirational": aspirational,
            "nostalgic": nostalgic,
            "outrage_mechanics": outrage_mechanics,
        },
        "target_lock_inferences": {
            "estimated_age": estimated_age,
            "inferred_income": inferred_income,
            "vulnerability_state": vulnerability_state,
            "political_lean": political_lean,
        },
        "raw_metrics": {
            "total_videos": total_videos,
            "total_watch_time_minutes": total_watch_time_minutes,
        },
        "behavioral_nodes": {
            "peak_activity_hour": peak_activity_hour,
            "skip_rate_percentage": round(skip_rate, 1),
            "linger_rate_percentage": round(linger_rate, 1),
            "night_shift_ratio": round(night_shift, 1),
        },
    }
