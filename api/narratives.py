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
            "audience — most consumption happens silently, engagement expressed through watch "
            "time and sharing rather than text."
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
