"""
Ghost Profile Scoring Engine — v3 "Pure Stopwatch & Entity Resolution"
Converts a parsed TikTok export dict (from parsers.tiktok) into the
algorithmic forensics payload the Next.js frontend expects.

Architecture
------------
1. True Stopwatch — parse timestamp deltas, scrub AFK anomalies, bucket conscious views.
2. Cross-Platform Entity Resolution — extract creators from URLs, count skips vs lingers.

Public API
----------
    build_ghost_profile(parsed: dict) -> dict
"""
from __future__ import annotations

from collections import defaultdict
import re

from parsers.tiktok import _parse_date
import oembed

# ---------------------------------------------------------------------------
# Engagement signal weights & DM method set (shared by Tasks 2 and 4)
# ---------------------------------------------------------------------------

_DM_METHODS = {
    "chat_head", "dm", "message", "whatsapp", "instagram",
    "line", "kakaotalk", "telegram",
}

_SIGNAL_WEIGHTS = {
    "comment":      10,
    "favorite":      7,
    "share_dm":      8,
    "share_public":  4,
    "follow":        6,
    "search":        5,
    "like":          3,
}

_FOOTPRINT_STOP = {
    "the", "and", "to", "of", "a", "in", "is", "for", "on", "you", "that",
    "this", "it", "with", "as", "at", "are", "be", "your", "my", "from",
    "so", "but", "not", "have", "we", "all", "can", "by", "if", "or",
    "an", "do", "what", "just", "about", "like", "how", "out", "up",
    "when", "was", "will", "they", "me", "get", "no", "one", "there",
    "its", "also", "more", "than", "then", "now", "has", "had", "him",
    "her", "she", "he", "who", "which", "been", "would", "could", "should",
}

# ---------------------------------------------------------------------------
# Cross-Platform Entity Resolution
# ---------------------------------------------------------------------------

def _extract_creator_from_url(url: str) -> str | None:
    """
    Parse TikTok URL to extract creator username.
    Handles: https://www.tiktok.com/@username/video/... → @username
    Also supports: https://vm.tiktok.com/...
    """
    if not url:
        return None

    match = re.search(r'@([a-zA-Z0-9._-]+)/', url)
    if match:
        return f"@{match.group(1)}"

    return None


_URL_NOISE = {"www", "com", "tiktok", "http", "https", "video", "tag", "discover"}


def _keywords_from_url(url: str) -> list[str]:
    """Extract keyword hints from a URL as space-separated strings safe for tokenization.

    Returns creator handle (underscores replaced with spaces) if present, otherwise
    falls back to non-noise path segments.
    """
    if not url:
        return []
    creator = _extract_creator_from_url(url)
    if creator:
        # Replace underscores so "finance_guru" tokenizes to "finance guru"
        return [creator.lstrip("@").replace("_", " ").replace(".", " ")]
    # Fallback: split on common URL delimiters and return non-noise segments of length ≥ 4
    parts = re.split(r'[/:?&=\-_.]', url)
    return [p.lower() for p in parts if len(p) >= 4 and p.lower() not in _URL_NOISE and not p.isdigit()]


def _count_creators(link_set: set[str], limit: int = 15, count_key: str = "count") -> list[dict]:
    """
    Given a set of TikTok URLs, extract creators and count frequencies.
    Return top N creators sorted by frequency descending.
    """
    creator_freq: dict[str, int] = {}

    for link in link_set:
        creator = _extract_creator_from_url(link)
        if creator:
            creator_freq[creator] = creator_freq.get(creator, 0) + 1

    sorted_creators = sorted(
        creator_freq.items(),
        key=lambda x: x[1],
        reverse=True
    )[:limit]

    return [
        {"handle": creator, count_key: count}
        for creator, count in sorted_creators
    ]


# ---------------------------------------------------------------------------
# Task 1: True Stopwatch & AFK Firewall
# ---------------------------------------------------------------------------

def _run_stopwatch(browsing_history: list[dict], exclude_hours: tuple[int, ...] = ()) -> dict:
    """
    Parse consecutive video timestamps to compute time-delta behavioral metrics.
    """
    entries: list[dict] = []
    for item in browsing_history:
        dt = _parse_date(item.get("date", ""))
        if dt:
            entries.append({"dt": dt, "link": item.get("link", "")})

    entries.sort(key=lambda x: x["dt"])

    # Thresholds
    # 1200s = 20 minutes: phone left open while sleeping / accidental exposure.
    # These are discarded entirely — they skew deep_dive counts and inflate lingers.
    # 0s to <0: clock anomaly (impossible). Also discarded.
    SLEEP_THRESHOLD_S = 1200

    clock_anomalies = 0   # delta < 0 (impossible timestamp)
    sleep_scrubbed = 0    # delta >= 1200 (left open / fell asleep)
    graveyard_count = 0
    sandbox_count = 0
    linger_count = 0
    deep_dive_count = 0
    night_count = 0
    night_lingers = 0

    graveyard_links: set[str] = set()
    sandbox_links: set[str] = set()
    linger_links: set[str] = set()
    deep_dive_links: set[str] = set()
    hourly: defaultdict[int, int] = defaultdict(int)
    # weekly_heatmap: dow (0=Mon) → hour → count
    weekly: defaultdict[int, defaultdict[int, int]] = defaultdict(lambda: defaultdict(int))

    linger_events: list[dict] = []
    graveyard_events: list[dict] = []
    sandbox_events: list[dict] = []
    night_linger_events: list[dict] = []
    deep_dive_events: list[dict] = []

    for i in range(len(entries) - 1):
        cur = entries[i]
        nxt = entries[i + 1]
        delta = (nxt["dt"] - cur["dt"]).total_seconds()

        # ── Clock anomaly (true impossibility) ──────────────────────────
        if delta < 0:
            clock_anomalies += 1
            continue

        # ── Sleep / accidental exposure (20+ minutes) ───────────────────
        # Phone left on while sleeping, or TikTok open in background.
        # These are NOT valid behavioral signals — scrub entirely.
        if delta >= SLEEP_THRESHOLD_S:
            sleep_scrubbed += 1
            continue

        # 0s–1199s: bucket normally. delta > 300 = phone briefly put down
        # (session break) but the video still counts. Cap time_spent at 270s.

        hour = cur["dt"].hour

        # Optional sleep-hour filter (e.g. 1AM–4AM)
        if exclude_hours and hour in exclude_hours:
            continue

        dow = cur["dt"].weekday()  # 0=Monday, 6=Sunday
        hourly[hour] += 1
        weekly[dow][hour] += 1
        if 23 <= hour or hour < 4:
            night_count += 1

        link = cur["link"]
        vid = oembed.extract_video_id(link) if link else None
        time_spent = min(delta, 270.0)
        if delta < 3:
            graveyard_count += 1
            if link:
                graveyard_links.add(link)
            if vid:
                graveyard_events.append({"video_id": vid, "link": link, "time_spent": time_spent, "hour": hour})
        elif delta <= 15:
            sandbox_count += 1
            if link:
                sandbox_links.add(link)
            if vid:
                sandbox_events.append({"video_id": vid, "link": link, "time_spent": time_spent, "hour": hour})
        elif delta <= 180:
            # 15–180s: sustained attention (deep_lingers for back-compat)
            linger_count += 1
            if 23 <= hour or hour < 4:
                night_lingers += 1
            if link:
                linger_links.add(link)
            if vid:
                ev = {"video_id": vid, "link": link, "time_spent": time_spent, "hour": hour}
                linger_events.append(ev)
                if 23 <= hour or hour < 4:
                    night_linger_events.append(ev)
        else:
            # >180s: deep dive — full commitment
            deep_dive_count += 1
            if 23 <= hour or hour < 4:
                night_lingers += 1
            if link:
                deep_dive_links.add(link)
                linger_links.add(link)  # also counts toward sustained for entity resolution
            if vid:
                ev = {"video_id": vid, "link": link, "time_spent": time_spent, "hour": hour}
                deep_dive_events.append(ev)
                linger_events.append(ev)  # deep dives are also lingered for theme extraction
                if 23 <= hour or hour < 4:
                    night_linger_events.append(ev)

    total_conscious = graveyard_count + sandbox_count + linger_count + deep_dive_count

    # Build weekly_heatmap as a plain dict for JSON serialisation
    weekly_heatmap: dict[int, dict[int, int]] = {
        dow: {h: weekly[dow].get(h, 0) for h in range(24)}
        for dow in range(7)
    }

    return {
        "total_raw_videos": len(entries),
        "total_conscious_videos": total_conscious,
        "sleep_anomalies_scrubbed": clock_anomalies,
        "sleep_scrubbed": sleep_scrubbed,
        "graveyard_skips": graveyard_count,
        "sandbox_views": sandbox_count,
        "deep_lingers": linger_count,
        "deep_dives": deep_dive_count,
        "night_count": night_count,
        "night_lingers": night_lingers,
        "_graveyard_links": graveyard_links,
        "_sandbox_links": sandbox_links,
        "_linger_links": linger_links,
        "_deep_dive_links": deep_dive_links,
        "hourly_heatmap": {str(h): hourly.get(h, 0) for h in range(24)},
        "weekly_heatmap": weekly_heatmap,
        "linger_events": linger_events,
        "graveyard_events": graveyard_events,
        "sandbox_events": sandbox_events,
        "night_linger_events": night_linger_events,
        "deep_dive_events": deep_dive_events,
    }


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


# ---------------------------------------------------------------------------
# Task 2: Engagement-Weighted Text Footprint
# ---------------------------------------------------------------------------

def _mine_text_footprint(parsed: dict) -> dict:
    """
    Build an engagement-weighted text corpus from all signal sources and
    extract interest clusters with source attribution.
    """
    import re
    from collections import Counter, defaultdict

    corpus_items: list[tuple[str, str]] = []  # (text, source_type)

    # Comments — weight 10
    for item in parsed.get("comments", []):
        text = item.get("comment", "")
        if text:
            corpus_items.extend([(text, "comment")] * _SIGNAL_WEIGHTS["comment"])

    # Searches — weight 5
    for item in parsed.get("searches", []):
        text = item.get("term", "")
        if text:
            corpus_items.extend([(text, "search")] * _SIGNAL_WEIGHTS["search"])

    # Follows — weight 6 (split username on _ and . to get keywords)
    for item in parsed.get("following", []):
        username = item.get("username", "")
        if username:
            words = re.split(r"[._@]", username.lower())
            text = " ".join(w for w in words if len(w) > 2)
            if text:
                corpus_items.extend([(text, "follow")] * _SIGNAL_WEIGHTS["follow"])

    # Shares — weight 8 (DM) or 4 (public); extract keyword hints from URL
    for item in parsed.get("shares", []):
        method = (item.get("method") or "").lower()
        link = item.get("link", "")
        keywords = _keywords_from_url(link)
        if keywords:
            source = "share_dm" if method in _DM_METHODS else "share_public"
            for kw in keywords:
                corpus_items.extend([(kw, source)] * _SIGNAL_WEIGHTS[source])

    # Favorites — weight 7
    for item in parsed.get("favorites", []):
        link = item.get("link", "")
        for kw in _keywords_from_url(link):
            corpus_items.extend([(kw, "favorite")] * _SIGNAL_WEIGHTS["favorite"])

    # Likes — weight 3
    for item in parsed.get("likes", []):
        link = item.get("link", "")
        for kw in _keywords_from_url(link):
            corpus_items.extend([(kw, "like")] * _SIGNAL_WEIGHTS["like"])

    if not corpus_items:
        return {"interest_clusters": [], "top_phrases": []}

    # Tokenise and count with source attribution
    term_counts: Counter = Counter()
    term_sources: dict[str, Counter] = defaultdict(Counter)

    for text, source in corpus_items:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        for word in words:
            if word not in _FOOTPRINT_STOP:
                term_counts[word] += 1
                term_sources[word][source] += 1

    interest_clusters = [
        {
            "term": term,
            "count": count,
            "dominant_source": term_sources[term].most_common(1)[0][0],
        }
        for term, count in term_counts.most_common(20)
    ]

    # 2-gram phrases from comment text only (richest signal)
    phrase_counts: Counter = Counter()
    for text, source in corpus_items:
        if source == "comment":
            words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
            for i in range(len(words) - 1):
                if words[i] not in _FOOTPRINT_STOP and words[i + 1] not in _FOOTPRINT_STOP:
                    phrase_counts[f"{words[i]} {words[i + 1]}"] += 1

    top_phrases = [
        {"phrase": phrase, "count": count}
        for phrase, count in phrase_counts.most_common(10)
    ]

    return {"interest_clusters": interest_clusters, "top_phrases": top_phrases}


# ---------------------------------------------------------------------------
# Tasks 4–6 stubs (implemented in subsequent tasks)
# ---------------------------------------------------------------------------

def analyze_comment_voice(parsed: dict) -> dict:
    """Stub — implemented in Task 4."""
    return {}


def _analyze_share_behavior(parsed: dict) -> dict:
    """Stub — implemented in Task 5."""
    return {}


def calculate_transparency_gap(parsed: dict) -> dict:
    """Stub — implemented in Task 6."""
    return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_ghost_profile(parsed: dict, exclude_hours: tuple[int, ...] = ()) -> dict:
    """
    Derive the strictly behavioral Ghost Profile payload.

    exclude_hours: tuple of hour ints (0-23) to omit from stopwatch analysis.
                   e.g. (1, 2, 3) to filter out 1AM–4AM (likely sleep time).
    """
    # ── Task 1: True Stopwatch ────────────────────────────────────────────
    active_history = (
        parsed.get("watch_history_active")
        or parsed.get("browsing_history", [])
    )
    sw = _run_stopwatch(active_history, exclude_hours=exclude_hours)

    # ── Task 2: Engagement-Weighted Interest Scoring ───────────────────────
    footprint = _mine_text_footprint(parsed)
    interest_clusters = footprint["interest_clusters"]
    interest_phrases  = footprint["top_phrases"]

    total_conscious: int = sw["total_conscious_videos"]
    graveyard_skips: int = sw["graveyard_skips"]
    sandbox_views: int   = sw["sandbox_views"]
    deep_lingers: int    = sw["deep_lingers"]
    deep_dives_count: int = sw["deep_dives"]
    sleep_anomalies: int = sw["sleep_anomalies_scrubbed"]
    sleep_scrubbed: int  = sw["sleep_scrubbed"]
    night_count: int     = sw["night_count"]

    sustained_and_dives = deep_lingers + deep_dives_count
    graveyard_rate     = (graveyard_skips / max(total_conscious, 1)) * 100
    linger_rate_pct    = (sustained_and_dives / max(total_conscious, 1)) * 100
    night_shift_pct    = (night_count    / max(total_conscious, 1)) * 100
    night_linger_pct   = (sw["night_lingers"] / max(sustained_and_dives, 1)) * 100

    peak_activity_hour = _compute_peak_hour(sw["hourly_heatmap"])

    # ── Cross-Platform Entity Resolution ───────────────────────────────────
    vibe_cluster = _count_creators(sw["_linger_links"], limit=20, count_key="linger_count")
    graveyard = _count_creators(sw["_graveyard_links"], limit=20, count_key="skip_count")

    # ── Evidence samples (raw excerpts for the Notes panel) ──────────────
    searches_raw = parsed.get("searches", [])
    login_history = parsed.get("login_history", [])
    login_stats = parsed.get("login_history_stats", {})

    # Rhythm of curiosity: search timestamps bucketed by hour
    search_hour_hist: defaultdict[int, int] = defaultdict(int)
    search_timeline: list[dict] = []
    for s in searches_raw:
        term = s.get("term") or s.get("SearchTerm") or ""
        date_str = s.get("date") or s.get("Date") or ""
        if not term or not date_str:
            continue
        dt = _parse_date(date_str)
        if not dt:
            continue
        search_hour_hist[dt.hour] += 1
        search_timeline.append({
            "term": term,
            "date": date_str,
            "hour": dt.hour,
            "dow": dt.weekday(),
        })
    search_timeline.sort(key=lambda x: x["date"], reverse=True)

    # Discrepancy gap: what user declared vs. what machine inferred
    declared_surface = set()
    for s in searches_raw[:200]:
        term = (s.get("term") or "").lower().strip()
        if term:
            declared_surface.add(term)
    for ad in parsed.get("ad_interests", []):
        declared_surface.add((ad or "").lower().strip())
    for si in parsed.get("settings_interests", []):
        declared_surface.add((si or "").lower().strip())

    inferred_handles = [c.get("handle") for c in vibe_cluster[:10]]

    # ── Academic Insights (ByteDance Monolith framing) ────────────────────
    # Explicit vs Implicit: the "folk theory" (likes/comments) vs the true
    # behavioral driver (passive retention on deep content).
    explicit_total = len(parsed.get("likes", [])) + len(parsed.get("comments", []))
    implicit_total = deep_lingers + deep_dives_count
    if implicit_total > 0:
        explicit_vs_implicit_ratio = round(explicit_total / implicit_total, 3)
    else:
        explicit_vs_implicit_ratio = 0.0

    # Echo Chamber Index: top-5 creator concentration of sustained attention.
    total_linger_links = sum(c.get("linger_count", 0) for c in vibe_cluster)
    top5_linger = sum(c.get("linger_count", 0) for c in vibe_cluster[:5])
    if total_linger_links > 0:
        echo_chamber_index_pct = round((top5_linger / total_linger_links) * 100, 1)
    else:
        echo_chamber_index_pct = 0.0

    # ── Social Graph Death ────────────────────────────────────────────────
    following_usernames = {u.get("username", "").lower().lstrip("@") for u in parsed.get("following", [])}
    followed_videos = 0
    algorithmic_videos = 0
    all_conscious_links = sw["_graveyard_links"] | sw["_sandbox_links"] | sw["_linger_links"]
    for link in all_conscious_links:
        creator = _extract_creator_from_url(link)
        if creator:
            clean_creator = creator.lstrip("@").lower()
            if clean_creator in following_usernames:
                followed_videos += 1
            else:
                algorithmic_videos += 1
    
    total_creators_found = followed_videos + algorithmic_videos
    if total_creators_found > 0:
        followed_pct = round((followed_videos / total_creators_found) * 100, 1)
        algorithmic_pct = round((algorithmic_videos / total_creators_found) * 100, 1)
    else:
        followed_pct = 0.0
        algorithmic_pct = 0.0

    # ── Ad Targeting Profile ──────────────────────────────────────────────
    # Top 3 activity hours = ad vulnerability windows (highest engagement density)
    hourly_sorted = sorted(sw["hourly_heatmap"].items(), key=lambda x: x[1], reverse=True)
    top_hours = [int(h) for h, v in hourly_sorted[:3] if v > 0]

    def _fmt_hour(h: int) -> str:
        if h == 0:   return "12 AM"
        if h < 12:   return f"{h} AM"
        if h == 12:  return "12 PM"
        return f"{h - 12} PM"

    vulnerability_window = " / ".join(_fmt_hour(h) for h in sorted(top_hours)) if top_hours else "Unknown"
    off_tiktok = parsed.get("off_tiktok_activity", [])
    shop_orders = parsed.get("shop_orders", [])

    return {
        "status": "success",
        "interest_clusters": interest_clusters,
        "interest_phrases": interest_phrases,
        "stopwatch_metrics": {
            "total_conscious_videos": total_conscious,
            "sleep_anomalies_scrubbed": sleep_anomalies,
            "sleep_scrubbed": sleep_scrubbed,
            "graveyard_skips": graveyard_skips,
            "sandbox_views": sandbox_views,
            "deep_lingers": deep_lingers,
            "deep_dives": deep_dives_count,
            "total_videos": sw["total_raw_videos"],
            "hourly_heatmap": sw["hourly_heatmap"],
            "weekly_heatmap": sw["weekly_heatmap"],
            "monthly_skip_rates": parsed.get("behavioral_analysis", {}).get("monthly_skip_rates", {}),
        },
        "behavioral_nodes": {
            "peak_hour": peak_activity_hour,
            "skip_rate_percentage": round(graveyard_rate, 1),
            "linger_rate_percentage": round(linger_rate_pct, 1),
            "night_shift_ratio": round(night_shift_pct, 1),
            "night_linger_pct": round(night_linger_pct, 1),
            "night_lingers_count": sw["night_lingers"],
            "social_graph_algorithmic_pct": algorithmic_pct,
            "social_graph_followed_pct": followed_pct,
        },
        "creator_entities": {
            "vibe_cluster": vibe_cluster,
            "graveyard": graveyard,
        },
        "academic_insights": {
            "explicit_vs_implicit_ratio": explicit_vs_implicit_ratio,
            "explicit_actions_count": explicit_total,
            "implicit_linger_count": implicit_total,
            "echo_chamber_index_pct": echo_chamber_index_pct,
            "top_creator_handles": [c.get("handle") for c in vibe_cluster[:5]],
        },
        "night_shift": {
            "percentage": round(night_shift_pct, 1),
            "count": night_count,
            "window": "23:00 – 04:00",
        },
        "digital_footprint": {
            "login_count": len(login_history),
            "unique_ips": login_stats.get("unique_ips", 0),
            "unique_devices": login_stats.get("unique_devices", []),
            "ip_locations": login_stats.get("ip_locations", []),
            "recent_logins": sorted(
                [
                    {
                        "date": l.get("date", ""),
                        "ip": l.get("ip", ""),
                        "device": l.get("device_model", ""),
                        "system": l.get("device_system", ""),
                        "network": l.get("network_type", ""),
                        "carrier": l.get("carrier", ""),
                    }
                    for l in login_history if l.get("date")
                ],
                key=lambda x: x["date"],
                reverse=True,
            )[:25],
        },
        "search_rhythm": {
            "total_searches": len(search_timeline),
            "hourly_histogram": {str(h): search_hour_hist.get(h, 0) for h in range(24)},
            "recent_searches": search_timeline[:30],
        },
        "discrepancy_gap": {
            "declared_surface_sample": sorted(list(declared_surface))[:40],
            "inferred_creator_handles": inferred_handles,
            "declared_count": len(declared_surface),
            "inferred_count": len(set(c.get("handle", "") for c in vibe_cluster)),
        },
        "_evidence": {
            "prologue": {
                "total_raw_videos": sw["total_raw_videos"],
                "total_conscious": total_conscious,
                "search_count": len(search_timeline),
                "top_creators": [c.get("handle") for c in vibe_cluster[:5]],
                "top_ad_interests": parsed.get("ad_interests", [])[:8],
            },
            "feedback_loop": {
                "top_lingers_raw": sorted(sw["linger_events"], key=lambda e: e["time_spent"], reverse=True)[:12],
                "echo_chamber_top5": vibe_cluster[:5],
                "night_lingers_raw": sorted(sw["night_linger_events"], key=lambda e: e["time_spent"], reverse=True)[:10],
            },
            "discrepancy": {
                "declared_searches_raw": [s for s in searches_raw[:30] if s.get("term")],
                "declared_ad_interests": parsed.get("ad_interests", [])[:25],
                "declared_settings_interests": parsed.get("settings_interests", [])[:25],
                "inferred_vibe_cluster_raw": vibe_cluster[:15],
                "inferred_graveyard_raw": graveyard[:15],
            },
            "digital_footprint": {
                "login_history_raw": [
                    {
                        "date": l.get("date", ""),
                        "ip": l.get("ip", ""),
                        "device": l.get("device_model", ""),
                        "system": l.get("device_system", ""),
                        "carrier": l.get("carrier", ""),
                    }
                    for l in login_history[:40] if l.get("date")
                ],
                "shop_orders_count": len(shop_orders),
                "off_tiktok_events": len(off_tiktok),
            },
            "psychographic": {
                "ad_interests_raw": parsed.get("ad_interests", []),
                "settings_interests_raw": parsed.get("settings_interests", []),
                "top_deep_dives": sorted(sw["deep_dive_events"], key=lambda e: e["time_spent"], reverse=True)[:8],
            },
            "search_rhythm": {
                "searches_sample": search_timeline[:25],
                "peak_search_hour": max(search_hour_hist.items(), key=lambda x: x[1])[0] if search_hour_hist else None,
            },
        },
        "enrichment_targets": {
            "lingered": sorted(sw["linger_events"], key=lambda e: e["time_spent"], reverse=True)[:40],
            "graveyard": sw["graveyard_events"][:40],
            "sandbox": sw["sandbox_events"][:40],
            "night_lingered": sorted(sw["night_linger_events"], key=lambda e: e["time_spent"], reverse=True)[:30],
            "deep_dives": sorted(sw["deep_dive_events"], key=lambda e: e["time_spent"], reverse=True)[:20],
            "following_usernames": list(following_usernames),
        },
        "deep_dives": {
            "count": deep_dives_count,
            "videos": sorted(sw["deep_dive_events"], key=lambda e: e["time_spent"], reverse=True)[:20],
        },
        "declared_signals": {
            "settings_interests": parsed.get("settings_interests", []),
            "ad_interests": parsed.get("ad_interests", []),
            "recent_searches": [s.get("term", "") for s in parsed.get("searches", [])[:30] if s.get("term")],
            "following_count": len(parsed.get("following", [])),
            "follower_count": len(parsed.get("followers", [])),
        },
        "ad_profile": {
            "advertiser_categories": parsed.get("ad_interests", []),
            "vulnerability_window": vulnerability_window,
            "peak_ad_hour": peak_activity_hour,
            "night_targeting": round(night_shift_pct, 1),  # % of activity in 11PM–4AM window
            "off_platform_tracked": len(off_tiktok) > 0,
            "off_platform_events": len(off_tiktok),
            "shop_order_count": len(shop_orders),
            "shop_products": [
                p
                for order in shop_orders
                for p in order.get("products", [])
            ][:20],
        },
    }
