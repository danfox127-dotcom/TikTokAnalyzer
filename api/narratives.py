# api/narratives.py
"""
Deterministic Narrative Block System.

Generates 9 structured blocks from ghost_profile + parsed export.
Each block: {id, title, icon, prose, accent, stats, chart, provenance}.
"""
from __future__ import annotations

import json
from collections import Counter
import anthropic
import google.generativeai as genai

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

    total_linger = sum(c.get("linger_count", 0) for c in vibe)
    top5 = vibe[:5]
    top5_linger = sum(c.get("linger_count", 0) for c in top5)
    chart_data = [
        {"name": c.get("handle", "Unknown"), "value": c.get("linger_count", 0)}
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
        "provenance": "Derived from watch time deltas (linger count) on identified creator handles vs discovery feed.",
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
        "provenance": f"Calculated from video interaction events (skip/linger ratios) across {total} conscious views.",
    }


# ---------------------------------------------------------------------------
# Block 3 — Daily Rhythm
# ---------------------------------------------------------------------------

def _fmt_hour(h: int) -> str:
    if h == 0: return "12 AM"
    if h < 12: return f"{h} AM"
    if h == 12: return "12 PM"
    return f"{h - 12} PM"


def _build_daily_rhythm_block(ghost_profile: dict, parsed: dict) -> dict:
    sw = ghost_profile.get("stopwatch_metrics", {})
    bn = ghost_profile.get("behavioral_nodes", {})
    heatmap: dict = sw.get("hourly_heatmap", {})
    total_events = int(sw.get("total_raw_videos", 0))
    night_pct = float(bn.get("night_shift_ratio", 0))
    peak_label = bn.get("peak_hour", "Unknown")

    if night_pct > 30:
        prose = (
            f"You are a night viewer — {night_pct:.0f}% of your TikTok activity occurs between "
            f"11 PM and 4 AM. Your peak engagement hour is {peak_label}. Late-night usage is "
            f"associated with passive consumption and higher ad susceptibility. TikTok's ad "
            f"targeting systems actively exploit this window."
        )
    else:
        prose = (
            f"Your peak viewing hour is {peak_label}. {night_pct:.0f}% of your activity occurs in "
            f"the late-night window (11 PM–4 AM). Your usage pattern follows a typical circadian "
            f"rhythm — consistent with intentional rather than compulsive consumption."
        )

    chart_data = [{"hour": str(h), "count": int(heatmap.get(str(h), 0))} for h in range(24)]
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
        "provenance": f"Aggregated from hourly engagement frequency across {total_events} video events.",
    }


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
            f"In effect, your follower list is decorative — the machine decides what you see."
        )
    else:
        prose = (
            f"You follow {following_count} accounts, with {followed_pct:.0f}% of your viewing "
            f"going to followed creators and {algo_pct:.0f}% to algorithmically-surfaced content. "
            f"Your top watched creator is {top_creator}. The social graph still has some influence."
        )

    stats = [
        {"label": "Following", "value": str(following_count)},
        {"label": "Watched (Followed)", "value": f"{followed_pct:.0f}%"},
        {"label": "Watched (Algorithmic)", "value": f"{algo_pct:.0f}%"},
        {"label": "Top Watched", "value": top_creator},
    ]

    nodes = []
    for c in vibe[:12]:
        nodes.append({
            "name": c.get("handle", "Unknown"),
            "size": c.get("linger_count", 0),
            "is_followed": c.get("is_followed", False),
            "genre": c.get("genre", "unknown"),
        })

    return {
        "id": "social_graph",
        "title": "SOCIAL GRAPH",
        "icon": "🕸️",
        "prose": prose,
        "accent": "#ff4db8",
        "stats": stats,
        "chart": {"type": "creator_graph", "data": nodes},
        "provenance": "Determined by comparing engagement metrics on followed accounts vs algorithmically-surfaced creators.",
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
        prose = "You have shared no content from TikTok. You leave no traceable content trail outside the platform."
    elif behavior_type == "Private Curator":
        prose = (
            f"You are a Private Curator. The majority of your {total_shares} shares go through "
            f"direct message, primarily via {primary_method}. Your shares are high-signal "
            f"recommendations, not reflexive reposting."
        )
    else:
        prose = (
            f"Your sharing behavior is {behavior_type.lower()} — {total_shares} shares, "
            f"with {primary_method} as the primary method. You extend TikTok's reach beyond the platform."
        )

    stats = [
        {"label": "Total Shares", "value": str(total_shares)},
        {"label": "Type", "value": behavior_type},
        {"label": "Primary Method", "value": primary_method},
        {"label": "Share/Like Ratio", "value": f"{share_to_like:.3f}"},
    ]

    chart_data = [{"name": k.title(), "value": v} for k, v in share_methods.items() if v > 0]

    return {
        "id": "share_behavior",
        "title": "SHARE BEHAVIOR",
        "icon": "🔗",
        "prose": prose,
        "accent": "#ffd700",
        "stats": stats,
        "chart": {"type": "donut", "data": chart_data} if chart_data else None,
        "provenance": "Extracted from share method metadata and correlated with like volume.",
    }


# ---------------------------------------------------------------------------
# Block 6 — Comment Voice
# ---------------------------------------------------------------------------

def _build_comment_voice_block(ghost_profile: dict, parsed: dict) -> dict:
    cv = ghost_profile.get("comment_voice", {})
    total = int(cv.get("total_comments", 0))
    avg_chars = float(cv.get("avg_length_chars", 0))
    style_label = cv.get("engagement_style_label", "Lurker")

    if total == 0:
        prose = "No comments found. You are a silent viewer, engaging through watch time rather than text."
    else:
        prose = (
            f"You are a {style_label}. Your {total} comments average {avg_chars:.0f} characters. "
            f"Your textual footprint reflects a {style_label.lower()} mode of engagement."
        )

    stats = [
        {"label": "Total Comments", "value": str(total)},
        {"label": "Avg Length", "value": f"{avg_chars:.0f} chars"},
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
        "provenance": "Analyzed from comment length and frequency relative to viewing volume.",
    }


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

    if official_count == 0 and behavioral_count > 5:
        prose = (
            f"Your ad interest profile is empty, yet behavioral analysis shows {behavioral_count} "
            f"inferred interest clusters. The algorithm sees far more than what it reports."
        )
    else:
        prose = (
            f"TikTok discloses {official_count} declared interests — but behavioral signals "
            f"reveal {behavioral_count} clusters. {interpretation}"
        )

    stats = [
        {"label": "Declared Interests", "value": str(official_count)},
        {"label": "Behavioral Clusters", "value": str(behavioral_count)},
        {"label": "Login Events", "value": str(login_count)},
        {"label": "Unique IPs", "value": str(unique_ips)},
    ]

    chart_data = [
        {"category": "Ad Interests", "count": official_count},
        {"category": "Behaviors", "count": behavioral_count},
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
        "provenance": "Forensic gap between 'Settings Interests' and behavioral categories inferred from video metadata.",
    }


# ---------------------------------------------------------------------------
# Block 8 — Location Trace
# ---------------------------------------------------------------------------

def _build_location_trace_block(ghost_profile: dict, parsed: dict) -> dict:
    footprint = ghost_profile.get("digital_footprint", {})
    logins: list[dict] = footprint.get("recent_logins", [])

    city_counter: Counter = Counter()
    for login in logins:
        city = login.get("city", "") or ""
        if city and city != "Unknown": city_counter[city] += 1

    home_city = city_counter.most_common(1)[0][0] if city_counter else "Unknown"
    city_count = len(city_counter)

    prose = (
        f"Your login history covers {city_count} cities, with {home_city} as your home base. "
        f"Even a single IP can reveal your ISP and approximate neighborhood."
    )

    stats = [
        {"label": "Home City", "value": home_city},
        {"label": "Cities Seen", "value": str(city_count)},
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
        "provenance": f"Geolocated from IP addresses recorded in {len(logins)} distinct login events.",
    }


# ---------------------------------------------------------------------------
# Block 9 — Closing Synthesis
# ---------------------------------------------------------------------------

def _build_closing_synthesis_block(ghost_profile: dict, parsed: dict) -> dict:
    bn = ghost_profile.get("behavioral_nodes", {})
    archetype = ghost_profile.get("primary_archetype", {}).get("name", "The Balanced Viewer")
    
    prose = (
        f"Across your usage history, you emerge as {archetype}. "
        f"The algorithm characterizes you through behavior rather than stated preferences. "
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
        "provenance": "Cross-dimensional behavioral synthesis mapped from all forensic blocks.",
    }


# ---------------------------------------------------------------------------
# LLM Generation
# ---------------------------------------------------------------------------

async def generate_narrative_blocks_llm(
    ghost_profile: dict, 
    api_key: str, 
    provider: str = "claude"
) -> list[dict]:
    """
    Generate 9 Dossier blocks using an LLM with a strict execution prompt.
    """
    compact_profile = {
        "archetype": ghost_profile.get("primary_archetype", {}),
        "metrics": ghost_profile.get("behavioral_nodes", {}),
        "interests": ghost_profile.get("interest_clusters", [])[:15],
        "creators": ghost_profile.get("creator_entities", {}).get("vibe_cluster", [])[:10],
        "night_shift": ghost_profile.get("night_shift", {}),
        "transparency": ghost_profile.get("transparency_gap", {})
    }

    prompt = f"""
You are a social media forensic analyst. Generate a 9-block "Dossier" for a user based on their TikTok behavioral data.
The data shows how the algorithm sees them, not their stated preferences.

DATA:
{json.dumps(compact_profile, indent=2)}

TASK:
Generate exactly 9 narrative blocks. Each block MUST follow this JSON schema:
{{
  "id": "algorithmic_identity | attention_signature | dayparting | social_graph | share_behavior | comment_voice | transparency_gap | location_trace | closing_synthesis",
  "title": "UPPERCASE TITLE",
  "icon": "emoji",
  "prose": "2-3 sentences of direct, slightly noir, insightful analysis",
  "accent": "hex color",
  "stats": [{{ "label": "string", "value": "string" }}],
  "chart": {{ "type": "donut|bar|creator_graph", "data": [...] }} | null,
  "provenance": "1 sentence explaining the data origin"
}}

STRICT RULES:
1. Return ONLY a valid JSON array of 9 objects.
2. Tone: "Dark Deco" — forensic, noir, objective.
3. Be specific: Reference the numbers in the prose.
4. Address the user as "you".

RESPONSE:
"""

    try:
        if provider == "claude":
            client = anthropic.AsyncAnthropic(api_key=api_key)
            response = await client.messages.create(
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                model="claude-sonnet-4-5",
            )
            raw_text = response.content[0].text
        elif provider.startswith("gemini"):
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-3-pro")
            response = await model.generate_content_async(prompt)
            raw_text = response.text
        else:
            return []

        start = raw_text.find("[")
        end = raw_text.rfind("]") + 1
        if start != -1 and end > start:
            return json.loads(raw_text[start:end])
        return []
    except Exception as e:
        print(f"LLM Narrative Error: {e}")
        return []

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_narrative_blocks(ghost_profile: dict, parsed: dict) -> list[dict]:
    """Generate ordered list of 9 narrative blocks (deterministic fallback)."""
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
        except Exception as e:
            print(f"Block Builder Error: {e}")
    return blocks
