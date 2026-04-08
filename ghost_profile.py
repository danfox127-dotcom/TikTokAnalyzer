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
# Niche Taxonomy
# Each entry: keywords matched against the full text corpus (lowercased).
# Keys: keywords, cluster, vibe_boost, vulnerability, income, political
# ---------------------------------------------------------------------------

NICHE_MAP: list[dict] = [
    # ── Mental Health & Neurodivergence ────────────────────────────────────
    {
        "keywords": ["adhd", "attention deficit", "hyperfocus", "executive function", "neurodivergent"],
        "cluster": "ADHD / Neurodivergence",
        "vibe_boost": {"doomscrolling": 12, "escapism": 8},
        "vulnerability": "HIGH: ADHD Dopamine Loop Susceptibility",
    },
    {
        "keywords": ["anxiety", "anxious", "panic attack", "overthinking", "social anxiety", "nervous"],
        "cluster": "Anxiety & Stress",
        "vibe_boost": {"doomscrolling": 10, "escapism": 12},
        "vulnerability": "HIGH: Anxiety Response Pattern Detected",
    },
    {
        "keywords": ["depression", "depressed", "hopeless", "empty inside", "numb", "sad all"],
        "cluster": "Depression / Low Mood",
        "vibe_boost": {"doomscrolling": 15, "escapism": 10},
        "vulnerability": "CRITICAL: Depression Signals — High Compulsion Risk",
    },
    {
        "keywords": ["trauma", "ptsd", "abuse", "toxic relationship", "healing journey", "narcissist"],
        "cluster": "Trauma & Recovery",
        "vibe_boost": {"doomscrolling": 8, "escapism": 15},
        "vulnerability": "HIGH: Trauma Processing State",
    },
    {
        "keywords": ["insomnia", "cant sleep", "can't sleep", "sleep deprivation", "3am thoughts", "4am"],
        "cluster": "Sleep Disruption",
        "vibe_boost": {"doomscrolling": 18, "escapism": 5},
        "vulnerability": "CRITICAL: Sleep-Deprived / Maximum Compulsion Window",
    },
    {
        "keywords": ["burnout", "exhausted", "burnt out", "drained", "no motivation", "can't do anything"],
        "cluster": "Burnout / Exhaustion",
        "vibe_boost": {"doomscrolling": 14, "escapism": 10},
        "vulnerability": "HIGH: Burnout State — Passive Content Binge Pattern",
    },
    # ── Finance ────────────────────────────────────────────────────────────
    {
        "keywords": ["budget meal", "cheap food", "food bank", "broke", "no money", "paycheck to paycheck", "cant afford"],
        "cluster": "Budget Survival",
        "vibe_boost": {"aspirational": 5, "doomscrolling": 8},
        "income": "Low: Financial Distress Detected",
        "vulnerability": "HIGH: Scarcity Mindset / Financial Stress",
    },
    {
        "keywords": ["debt", "student loan", "credit card debt", "payday loan", "collections", "owe money", "overdraft"],
        "cluster": "Debt & Financial Stress",
        "vibe_boost": {"doomscrolling": 12, "aspirational": 3},
        "income": "Low-Medium: Active Debt Burden",
        "vulnerability": "HIGH: Financial Anxiety",
    },
    {
        "keywords": ["crypto", "bitcoin", "ethereum", "nft", "web3", "defi", "altcoin", "doge", "shitcoin", "blockchain"],
        "cluster": "Crypto / Digital Assets",
        "vibe_boost": {"aspirational": 15, "outrage_mechanics": 5},
        "income": "Medium: High-Risk Speculative Investor",
    },
    {
        "keywords": ["investing", "stocks", "dividend", "index fund", "s&p", "sp500", "roth ira", "401k", "etf", "portfolio"],
        "cluster": "Traditional Investing",
        "vibe_boost": {"aspirational": 12},
        "income": "Medium-High: Investment-Active",
    },
    {
        "keywords": ["side hustle", "passive income", "dropshipping", "amazon fba", "make money online", "get rich", "financial freedom"],
        "cluster": "Hustle Culture",
        "vibe_boost": {"aspirational": 18, "doomscrolling": 5},
        "income": "Low-Medium: Income-Anxious Grind Mode",
    },
    # ── Politics ───────────────────────────────────────────────────────────
    {
        "keywords": ["trump", "maga", "make america great", "republican", "conservative", "fox news", "desantis", "tucker carlson", "ben shapiro"],
        "cluster": "Right-Wing Politics",
        "vibe_boost": {"outrage_mechanics": 20},
        "political": "Right / MAGA-Aligned",
    },
    {
        "keywords": ["biden", "democrat", "liberal", "progressive", "bernie", "aoc", "squad", "socialism", "blm", "black lives matter"],
        "cluster": "Left / Progressive Politics",
        "vibe_boost": {"outrage_mechanics": 18},
        "political": "Progressive / Left-Aligned",
    },
    {
        "keywords": ["conspiracy", "deep state", "nwo", "new world order", "they don't want you", "plandemic", "wake up sheeple", "agenda", "elite control"],
        "cluster": "Conspiracy / Alternative Narratives",
        "vibe_boost": {"outrage_mechanics": 22, "doomscrolling": 10},
        "political": "Anti-Establishment / Conspiratorial",
        "vulnerability": "HIGH: Paranoid Pattern — Radicalization Risk",
    },
    # ── Lifestyle & Body ───────────────────────────────────────────────────
    {
        "keywords": ["weight loss", "calorie deficit", "intermittent fasting", "gym", "workout", "lose weight", "fat loss", "cutting"],
        "cluster": "Fitness & Body Image",
        "vibe_boost": {"aspirational": 14, "doomscrolling": 4},
        "vulnerability": "MODERATE: Body Image Monitoring Behavior",
    },
    {
        "keywords": ["skincare", "skin care", "acne", "glow up", "beauty routine", "sephora", "makeup", "anti-aging"],
        "cluster": "Beauty & Aesthetics",
        "vibe_boost": {"aspirational": 10, "escapism": 8},
    },
    {
        "keywords": ["luxury", "designer", "gucci", "louis vuitton", "chanel", "expensive watch", "rich lifestyle", "penthouse", "yacht"],
        "cluster": "Luxury Aspiration",
        "vibe_boost": {"aspirational": 20},
        "income": "Aspirational Middle Class (Luxury-Aspirant)",
    },
    {
        "keywords": ["van life", "digital nomad", "backpacking", "travel the world", "quit my job", "expat", "relocate abroad"],
        "cluster": "Escape / Travel Fantasy",
        "vibe_boost": {"escapism": 18, "aspirational": 8},
        "vulnerability": "MODERATE: Escape Fantasy — High Dissatisfaction Signal",
    },
    # ── Entertainment ──────────────────────────────────────────────────────
    {
        "keywords": ["anime", "manga", "webtoon", "isekai", "jujutsu", "one piece", "naruto", "demon slayer", "attack on titan"],
        "cluster": "Anime & Manga",
        "vibe_boost": {"escapism": 18},
    },
    {
        "keywords": ["gaming", "minecraft", "roblox", "fortnite", "valorant", "streamer", "twitch", "fps", "rpg", "speedrun"],
        "cluster": "Gaming",
        "vibe_boost": {"escapism": 16},
    },
    {
        "keywords": ["kpop", "k-pop", "bts", "blackpink", "stray kids", "enhypen", "kpop idol", "stan"],
        "cluster": "K-Pop / Korean Pop Culture",
        "vibe_boost": {"escapism": 14, "nostalgic": 5},
    },
    {
        "keywords": ["asmr", "oddly satisfying", "sleep sounds", "rain sounds", "white noise"],
        "cluster": "ASMR / Sensory Comfort",
        "vibe_boost": {"escapism": 12, "doomscrolling": 5},
        "vulnerability": "MODERATE: Sensory Soothing — Overstimulation Recovery",
    },
    # ── Relationships ──────────────────────────────────────────────────────
    {
        "keywords": ["breakup", "heartbreak", "divorce", "he left me", "she left me", "toxic ex", "gaslighting", "love bombing"],
        "cluster": "Relationship Pain",
        "vibe_boost": {"doomscrolling": 10, "escapism": 8},
        "vulnerability": "HIGH: Relationship Distress Signal",
    },
    {
        "keywords": ["situationship", "talking stage", "dating apps", "tinder", "rizz", "red flag", "attachment style"],
        "cluster": "Modern Dating Culture",
        "vibe_boost": {"escapism": 8, "doomscrolling": 5},
    },
    # ── Nostalgia ──────────────────────────────────────────────────────────
    {
        "keywords": ["90s", "80s", "y2k", "2000s", "retro", "childhood", "throwback", "old school", "vintage cartoons", "simpsons", "spongebob"],
        "cluster": "Nostalgia & Retro Culture",
        "vibe_boost": {"nostalgic": 22},
    },
    # ── Spirituality ───────────────────────────────────────────────────────
    {
        "keywords": ["astrology", "zodiac", "manifestation", "law of attraction", "crystals", "tarot", "spiritual awakening", "twin flame"],
        "cluster": "Spirituality & Manifestation",
        "vibe_boost": {"escapism": 12, "aspirational": 8},
        "vulnerability": "MODERATE: Magical Thinking / Destiny Narrative",
    },
    # ── Food ───────────────────────────────────────────────────────────────
    {
        "keywords": ["mukbang", "food review", "meal prep", "recipe", "cooking hack", "gordon ramsay", "baking"],
        "cluster": "Food & Cooking",
        "vibe_boost": {"escapism": 8},
    },
    # ── Productivity / Self-Improvement ────────────────────────────────────
    {
        "keywords": ["productivity", "morning routine", "discipline", "stoicism", "self improvement", "reading list", "wake up 5am"],
        "cluster": "Self-Optimization / Hustle Identity",
        "vibe_boost": {"aspirational": 16, "doomscrolling": 6},
        "vulnerability": "MODERATE: Performance Anxiety / Impostor Pattern",
    },
]

# Severity ranking used when multiple vulnerability signals fire
_VULN_SEVERITY = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MODERATE": 2,
    "LOW": 1,
}


def _severity(label: str) -> int:
    for prefix, score in _VULN_SEVERITY.items():
        if label.startswith(prefix):
            return score
    return 0


# ---------------------------------------------------------------------------
# Text footprint extraction
# ---------------------------------------------------------------------------

def _mine_text_footprint(parsed: dict) -> list[str]:
    """
    Collect every piece of user-generated text from the parsed export:
    search terms, comment bodies, hashtag names, bio, favorite collection names.
    Returns a flat list of lowercased strings.
    """
    corpus: list[str] = []

    # Search history (most signal-rich)
    for item in parsed.get("searches", []):
        term = item.get("term", "")
        if term:
            corpus.append(term.lower())

    # Comments the user wrote
    for item in parsed.get("comments", []):
        text = item.get("comment", "")
        if text:
            corpus.append(text.lower())

    # Favorite collection names (reveal interests user cared enough to save)
    for name in parsed.get("favorite_collections", []):
        corpus.append(name.lower())

    # Bio
    bio = parsed.get("profile", {}).get("bio", "")
    if bio:
        corpus.append(bio.lower())

    # Ad interest strings and settings interests
    for item in parsed.get("ad_interests", []):
        corpus.append(str(item).lower())
    for item in parsed.get("settings_interests", []):
        corpus.append(str(item).lower())

    return corpus


# ---------------------------------------------------------------------------
# Niche classification
# ---------------------------------------------------------------------------

def _classify_niches(corpus: list[str]) -> tuple[list[str], dict, dict]:
    """
    Run the full text corpus against NICHE_MAP.

    Returns:
        clusters     – list of matched cluster display names (deduplicated, ordered by hit count)
        vibe_boosts  – cumulative {vibe_key: int} to add to behavioral scores
        overrides    – {vulnerability: str | None, income: str | None, political: str | None}
    """
    full_text = " ".join(corpus)

    cluster_hits: dict[str, int] = {}           # cluster → hit count
    vibe_accumulator: dict[str, int] = {}

    best_vulnerability: str | None = None
    income_signals: list[str] = []
    political_signals: list[str] = []

    for entry in NICHE_MAP:
        matched = sum(1 for kw in entry["keywords"] if kw in full_text)
        if matched == 0:
            continue

        cluster = entry["cluster"]
        cluster_hits[cluster] = cluster_hits.get(cluster, 0) + matched

        # Accumulate vibe boosts (scaled: more keyword hits → stronger boost)
        for vibe, delta in entry.get("vibe_boost", {}).items():
            boost = min(delta * matched, delta * 2)   # cap at 2× base
            vibe_accumulator[vibe] = vibe_accumulator.get(vibe, 0) + boost

        # Keep the highest-severity vulnerability signal
        vuln = entry.get("vulnerability")
        if vuln:
            if best_vulnerability is None or _severity(vuln) > _severity(best_vulnerability):
                best_vulnerability = vuln

        # Collect income and political signals (take the first/most-hit later)
        if entry.get("income"):
            income_signals.append(entry["income"])
        if entry.get("political"):
            political_signals.append(entry["political"])

    # Sort clusters by hit count descending
    sorted_clusters = sorted(cluster_hits, key=lambda c: cluster_hits[c], reverse=True)

    overrides = {
        "vulnerability": best_vulnerability,
        "income": income_signals[0] if income_signals else None,
        "political": _resolve_political(political_signals),
    }

    return sorted_clusters, vibe_accumulator, overrides


def _resolve_political(signals: list[str]) -> str | None:
    """If both left and right signals fired, return Fragmented."""
    if not signals:
        return None
    has_right = any("Right" in s or "MAGA" in s or "Conspir" in s for s in signals)
    has_left = any("Left" in s or "Progressive" in s for s in signals)
    if has_right and has_left:
        return "Politically Fragmented (Cross-Spectrum Engagement)"
    return signals[0]


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------

def _compute_peak_hour(hourly_heatmap: dict) -> str:
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
    return f"{(hour - 12):02d}:00 PM"


def _infer_age(birth_date: str, night_shift: float, skip_rate: float) -> str:
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
    # Behavioral fallback
    if night_shift > 35 and skip_rate > 60:
        return "18–24"
    if night_shift > 20 or skip_rate > 50:
        return "25–34"
    return "35–44"


def _infer_income(
    ad_interests: list[str],
    shop_orders: list,
    niche_override: str | None,
) -> str:
    """Income inference: niche text signals take precedence over ad category heuristics."""
    if niche_override:
        return niche_override

    # Legacy keyword fallback (ad interests only)
    _LUXURY = {"luxury", "premium", "designer", "wealth", "real estate", "investing", "crypto", "yacht"}
    _BUDGET = {"discount", "deal", "sale", "budget", "affordable", "debt", "loan", "payday"}

    low = " ".join(str(i).lower() for i in ad_interests)
    luxury_hits = sum(1 for kw in _LUXURY if kw in low)
    budget_hits = sum(1 for kw in _BUDGET if kw in low)
    order_count = len(shop_orders)

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
    linger_rate: float,
    niche_override: str | None,
) -> str:
    """Vulnerability: niche text signals override behavioral estimates."""
    if niche_override:
        return niche_override

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
    niche_override: str | None,
) -> str:
    """Political lean: niche text signals override ad interest heuristics."""
    if niche_override:
        return niche_override

    if outrage_score < 15 and blocked_count == 0:
        return "Apolitical"
    if outrage_score >= 60 or blocked_count >= 10:
        return "Highly Polarized"

    low = " ".join(str(i).lower() for i in all_interests)
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
    """
    ba = parsed.get("behavioral_analysis", {})
    profile = parsed.get("profile", {})
    ad_interests: list[str] = parsed.get("ad_interests", [])
    settings_interests: list[str] = parsed.get("settings_interests", [])
    all_interests = ad_interests + settings_interests
    blocked_count = len(parsed.get("blocked_users", []))
    favorites_count = len(parsed.get("favorites", []))
    shop_orders = parsed.get("shop_orders", [])

    # ── Behavioral primitives ─────────────────────────────────────────────
    skip_rate: float = ba.get("skip_rate", 0.0)
    linger_rate: float = ba.get("linger_rate", 0.0)
    night_shift: float = ba.get("night_shift_ratio", 0.0)
    total_videos: int = ba.get("total_videos", 0)
    skip_count: int = ba.get("skip_count", 0)
    casual_count: int = ba.get("casual_count", 0)
    linger_count: int = ba.get("linger_count", 0)
    hourly_heatmap: dict = ba.get("hourly_heatmap", {})

    # ── Text mining ───────────────────────────────────────────────────────
    corpus = _mine_text_footprint(parsed)
    interest_clusters, vibe_boosts, overrides = _classify_niches(corpus)

    search_terms = [s.get("term", "") for s in parsed.get("searches", []) if s.get("term")]

    # ── Vibe Vectors (behavioral baseline + niche text boosts) ────────────

    volume_factor = min(total_videos / 2000 * 20, 20)

    # Base scores from behavior
    doomscrolling_base = int(skip_rate * 0.5 + night_shift * 0.4 + volume_factor)
    escapism_base = int(linger_rate * 0.5 + min(favorites_count / 10, 15))
    aspirational_base = 0
    nostalgic_base = 0
    outrage_base = min(blocked_count * 3, 30)

    # Apply niche boosts
    doomscrolling = min(100, doomscrolling_base + vibe_boosts.get("doomscrolling", 0))
    escapism      = min(100, escapism_base      + vibe_boosts.get("escapism", 0))
    aspirational  = min(100, aspirational_base  + vibe_boosts.get("aspirational", 0))
    nostalgic     = min(100, nostalgic_base     + vibe_boosts.get("nostalgic", 0))
    outrage_mechanics = min(100, outrage_base   + vibe_boosts.get("outrage_mechanics", 0))

    # ── Target Lock Inferences ────────────────────────────────────────────

    estimated_age = _infer_age(profile.get("birth_date", ""), night_shift, skip_rate)
    inferred_income = _infer_income(ad_interests, shop_orders, overrides["income"])
    vulnerability_state = _infer_vulnerability(
        doomscrolling, night_shift, skip_rate, linger_rate, overrides["vulnerability"]
    )
    political_lean = _infer_political_lean(
        outrage_mechanics, all_interests, blocked_count, overrides["political"]
    )

    # ── Raw Metrics ───────────────────────────────────────────────────────

    watch_seconds = skip_count * 1.5 + casual_count * 9 + linger_count * 30
    total_watch_time_minutes = int(watch_seconds / 60)

    # ── Behavioral Nodes ──────────────────────────────────────────────────

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
        "interest_clusters": interest_clusters,
    }
