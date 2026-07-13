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

from collections import Counter, defaultdict
import re

from parsers.tiktok import _parse_date
from utils import oembed
from utils.creators import resolve_vibe_cluster

# ---------------------------------------------------------------------------
# Engagement signal weights & DM method set
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
    """Parse TikTok URL to extract creator username."""
    if not url:
        return None
    match = re.search(r'@([a-zA-Z0-9._-]+)/', url)
    if match:
        return f"@{match.group(1)}"
    return None


_URL_NOISE = {"www", "com", "tiktok", "http", "https", "video", "tag", "discover"}

def _keywords_from_url(url: str) -> list[str]:
    """Extract keyword hints from a URL."""
    if not url:
        return []
    creator = _extract_creator_from_url(url)
    if creator:
        return [creator.lstrip("@").replace("_", " ").replace(".", " ")]
    parts = re.split(r'[/:?&=\-_.]', url)
    return [p.lower() for p in parts if len(p) >= 4 and p.lower() not in _URL_NOISE and not p.isdigit()]


def _handle_from_link(link: str, link_handle_map: dict[str, str] | None = None) -> str | None:
    """Creator @handle for a watch link: URL regex first, then the resolved video_id→handle map."""
    creator = _extract_creator_from_url(link)
    if creator:
        return creator
    if link_handle_map:
        vid = oembed.extract_video_id(link)
        h = link_handle_map.get(vid) if vid else None
        if h:
            return h if h.startswith("@") else f"@{h}"
    return None


def _count_creators(link_set: set[str], limit: int = 15, count_key: str = "count", link_to_title: dict[str, str] = None, link_handle_map: dict[str, str] | None = None) -> list[dict]:
    """Extract creators and count frequencies, falling back to Video ID if handles are missing.

    When `link_handle_map` (video_id → handle, from the durable creator map) is
    supplied, links with no @handle in the URL are resolved through it, so counts
    aggregate by *real creator* instead of by one-off video id.
    """
    handle_freq: dict[str, int] = {}
    vid_freq: dict[str, int] = {}
    creator_titles: dict[str, list[str]] = defaultdict(list)
    link_to_vid: dict[str, str] = {}

    for link in link_set:
        vid = oembed.extract_video_id(link)
        creator = _handle_from_link(link, link_handle_map)

        if vid:
            link_to_vid[link] = vid
            if creator:
                handle_freq[creator] = handle_freq.get(creator, 0) + 1
                if link_to_title and link in link_to_title:
                    creator_titles[creator].append(link_to_title[link])
            else:
                vid_freq[vid] = vid_freq.get(vid, 0) + 1
                if link_to_title and link in link_to_title:
                    creator_titles[f"vid:{vid}"].append(link_to_title[link])

    if handle_freq:
        sorted_items = sorted(handle_freq.items(), key=lambda x: x[1], reverse=True)[:limit]
        results = []
        for handle, count in sorted_items:
            results.append({
                "handle": handle,
                count_key: count,
                "sample_titles": list(set(creator_titles[handle]))[:5]
            })
        return results
    else:
        # Fallback: Top videos by ID
        sorted_items = sorted(vid_freq.items(), key=lambda x: x[1], reverse=True)[:limit]
        results = []
        for vid, count in sorted_items:
            results.append({
                "handle": "Unknown",
                "video_id": vid,
                count_key: count,
                "sample_titles": list(set(creator_titles[f"vid:{vid}"]))[:5]
            })
        return results


def _echo_chamber_index(linger_links, link_handle_map: dict[str, str] | None = None) -> dict:
    """Concentration of *resolved* lingered videos on the top-5 creators.

    Measured across the full linger set via the resolved video_id→handle map,
    so it reflects real creators rather than the truncated top-20 ledger. Returns
    0 when nothing is resolved yet — honest at low coverage, unlike the prior
    top5/top20 ratio which returned a fixed ~25% artifact from 20 singletons.
    `basis`/`distinct_creators` let callers caveat a thin sample.
    """
    freq: dict[str, int] = {}
    for link in linger_links:
        h = _handle_from_link(link, link_handle_map)
        if h:
            freq[h] = freq.get(h, 0) + 1
    total = sum(freq.values())
    top5 = sum(sorted(freq.values(), reverse=True)[:5])
    return {
        "pct": round((top5 / total) * 100, 1) if total > 0 else 0.0,
        "basis": total,
        "distinct_creators": len(freq),
    }


# ---------------------------------------------------------------------------
# Task 1: True Stopwatch & AFK Firewall
# ---------------------------------------------------------------------------

def _run_stopwatch(browsing_history: list[dict], exclude_hours: tuple[int, ...] = ()) -> dict:
    """Parse consecutive video timestamps to compute time-delta behavioral metrics."""
    entries: list[dict] = []
    for item in browsing_history:
        dt = _parse_date(item.get("date", ""))
        if dt:
            entries.append({"dt": dt, "link": item.get("link", "")})

    entries.sort(key=lambda x: x["dt"])

    SLEEP_THRESHOLD_S = 1200
    clock_anomalies = 0
    sleep_scrubbed = 0
    graveyard_count = 0
    sandbox_count = 0
    linger_count = 0
    deep_dive_count = 0
    night_count = 0
    night_lingers = 0

    consecutive_skips = 0
    max_consecutive_skips = 0
    current_session_duration = 0
    max_session_duration = 0

    graveyard_links: set[str] = set()
    sandbox_links: set[str] = set()
    linger_links: set[str] = set()
    deep_dive_links: set[str] = set()
    hourly: defaultdict[int, int] = defaultdict(int)
    weekly: defaultdict[int, defaultdict[int, int]] = defaultdict(lambda: defaultdict(int))
    monthly_data = defaultdict(lambda: {"skip": 0, "total": 0})

    linger_events: list[dict] = []
    graveyard_events: list[dict] = []
    sandbox_events: list[dict] = []
    night_linger_events: list[dict] = []
    deep_dive_events: list[dict] = []

    for i in range(len(entries) - 1):
        cur = entries[i]
        nxt = entries[i + 1]
        delta = (nxt["dt"] - cur["dt"]).total_seconds()

        if delta < 0:
            clock_anomalies += 1
            continue

        if delta >= SLEEP_THRESHOLD_S:
            sleep_scrubbed += 1
            current_session_duration = 0
            continue

        if delta > 300:
            current_session_duration = 0
        else:
            current_session_duration += delta
            max_session_duration = max(max_session_duration, current_session_duration)

        hour = cur["dt"].hour
        if exclude_hours and hour in exclude_hours:
            continue

        dow = cur["dt"].weekday()
        hourly[hour] += 1
        weekly[dow][hour] += 1
        
        month_key = cur["dt"].strftime("%Y-%m")
        monthly_data[month_key]["total"] += 1

        if 23 <= hour or hour < 4:
            night_count += 1

        link = cur["link"]
        vid = oembed.extract_video_id(link) if link else None
        time_spent = min(delta, 270.0)
        monthly_data[month_key].setdefault("time_sum", 0.0)
        monthly_data[month_key]["time_sum"] += time_spent if delta >= 3 else 0.0
        
        if delta < 3:
            graveyard_count += 1
            consecutive_skips += 1
            max_consecutive_skips = max(max_consecutive_skips, consecutive_skips)
            monthly_data[month_key]["skip"] += 1
            if link: graveyard_links.add(link)
            if vid: graveyard_events.append({"video_id": vid, "link": link, "time_spent": time_spent, "hour": hour})
        elif delta <= 15:
            consecutive_skips = 0
            sandbox_count += 1
            if link: sandbox_links.add(link)
            if vid: sandbox_events.append({"video_id": vid, "link": link, "time_spent": time_spent, "hour": hour})
        elif delta <= 180:
            consecutive_skips = 0
            linger_count += 1
            if 23 <= hour or hour < 4: night_lingers += 1
            if link: linger_links.add(link)
            if vid:
                ev = {"video_id": vid, "link": link, "time_spent": time_spent, "hour": hour, "_month": month_key}
                linger_events.append(ev)
                if 23 <= hour or hour < 4: night_linger_events.append(ev)
        else:
            consecutive_skips = 0
            deep_dive_count += 1
            if 23 <= hour or hour < 4: night_lingers += 1
            if link:
                deep_dive_links.add(link)
                linger_links.add(link)
            if vid:
                ev = {"video_id": vid, "link": link, "time_spent": time_spent, "hour": hour, "_month": month_key}
                deep_dive_events.append(ev)
                linger_events.append(ev)
                if 23 <= hour or hour < 4: night_linger_events.append(ev)

    total_conscious = graveyard_count + sandbox_count + linger_count + deep_dive_count

    weekly_heatmap: dict[int, dict[int, int]] = {
        dow: {h: weekly[dow].get(h, 0) for h in range(24)}
        for dow in range(7)
    }
    
    monthly_skip_rates = {}
    for mk in sorted(monthly_data.keys()):
        m = monthly_data[mk]
        monthly_skip_rates[mk] = round(m["skip"] / m["total"] * 100, 1) if m["total"] > 0 else 0.0

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
        "max_consecutive_skips": max_consecutive_skips,
        "max_session_duration": max_session_duration,
        "_graveyard_links": graveyard_links,
        "_sandbox_links": sandbox_links,
        "_linger_links": linger_links,
        "_deep_dive_links": deep_dive_links,
        "hourly_heatmap": {str(h): hourly.get(h, 0) for h in range(24)},
        "weekly_heatmap": weekly_heatmap,
        "monthly_skip_rates": monthly_skip_rates,
        "linger_events": linger_events,
        "graveyard_events": graveyard_events,
        "sandbox_events": sandbox_events,
        "night_linger_events": night_linger_events,
        "deep_dive_events": deep_dive_events,
        "data_start_month": entries[0]["dt"].strftime("%B %Y") if entries else None,
    }


def _parse_date_to_month(ev: dict) -> str | None:
    return ev.get("_month")


def _infer_sleep_window(hourly_heatmap: dict) -> str:
    """Find the 4-hour consecutive dead zone — most likely the sleep window."""
    hours = [hourly_heatmap.get(str(h), hourly_heatmap.get(h, 0)) for h in range(24)]
    if not any(hours):
        return "Unknown"
    doubled = hours * 2
    WINDOW = 4
    best_start, best_sum = 0, float("inf")
    for s in range(24):
        w = sum(doubled[s : s + WINDOW])
        if w < best_sum:
            best_sum, best_start = w, s
    def _h(h: int) -> str:
        h = h % 24
        if h == 0: return "12 AM"
        if h < 12: return f"{h} AM"
        if h == 12: return "12 PM"
        return f"{h - 12} PM"
    return f"{_h(best_start)} – {_h(best_start + WINDOW)}"


def _algorithm_drift(monthly_skip_rates: dict) -> dict:
    """Compare first-half vs second-half skip rates to detect filter-bubble tightening."""
    months = sorted(monthly_skip_rates.keys())
    if len(months) < 4:
        return {"detectable": False, "direction": None, "delta_pct": None}
    mid = len(months) // 2
    early = [monthly_skip_rates[m] for m in months[:mid]]
    recent = [monthly_skip_rates[m] for m in months[mid:]]
    avg_early = sum(early) / len(early)
    avg_recent = sum(recent) / len(recent)
    delta = round(avg_recent - avg_early, 1)  # negative = fewer skips lately = tighter loop
    if delta < -4:
        direction = "tightening"
    elif delta > 4:
        direction = "loosening"
    else:
        direction = "stable"
    return {
        "detectable": True,
        "direction": direction,
        "delta_pct": delta,
        "early_avg": round(avg_early, 1),
        "recent_avg": round(avg_recent, 1),
    }


def _monthly_creator_trends(linger_events: list[dict], link_handle_map: dict[str, str] | None = None) -> dict:
    """Top-5 lingered creators per month (resolved handle → count)."""
    monthly_creators: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for ev in linger_events:
        handle = _handle_from_link(ev["link"], link_handle_map)
        if handle:
            mk = _parse_date_to_month(ev)
            if mk:
                monthly_creators[mk][handle] += 1
    return {
        mk: [{"handle": h, "count": c} for h, c in sorted(handles.items(), key=lambda x: -x[1])[:5]]
        for mk, handles in sorted(monthly_creators.items())
    }


def _monthly_topic_trends(searches_raw: list[dict], comments: list[dict]) -> dict:
    """Top-8 topics per month: whole search terms (weight 3) + comment words."""
    monthly_topics: dict[str, Counter] = defaultdict(Counter)
    for s in searches_raw:
        term = (s.get("term") or "").lower().strip()
        dt = _parse_date(s.get("date", ""))
        if term and dt and term not in _FOOTPRINT_STOP and len(term) > 2:
            mk = dt.strftime("%Y-%m")
            monthly_topics[mk][term] += 3  # searches weighted higher

    for c in comments:
        text = (c.get("comment") or "").lower()
        dt = _parse_date(c.get("date", ""))
        if text and dt:
            mk = dt.strftime("%Y-%m")
            for word in re.findall(r"[a-z]{3,}", text):
                if word not in _FOOTPRINT_STOP:
                    monthly_topics[mk][word] += 1

    return {
        mk: [{"term": t, "count": c} for t, c in counter.most_common(8)]
        for mk, counter in sorted(monthly_topics.items())
    }


def _sandbox_retests(sandbox_events: list[dict], link_handle_map: dict[str, str] | None = None) -> list[dict]:
    """Creators the algorithm re-served in the sandbox tier ≥2 times."""
    sandbox_creator_counts: Counter = Counter()
    for ev in sandbox_events:
        h = _handle_from_link(ev.get("link", ""), link_handle_map)
        if h:
            sandbox_creator_counts[h] += 1
    return [
        {"handle": h, "times_served": c}
        for h, c in sandbox_creator_counts.most_common(8)
        if c >= 2
    ]


def _skip_anomalies(monthly_skip_rates: dict) -> list[dict]:
    """Months whose skip rate deviates ≥3 points from the leave-one-out baseline."""
    skip_months = sorted(monthly_skip_rates.keys())
    anomalies: list[dict] = []
    if len(skip_months) >= 3:
        baseline_months = skip_months[:-1]
        baseline_avg = sum(monthly_skip_rates[m] for m in baseline_months) / len(baseline_months)
        for mk in skip_months:
            delta = monthly_skip_rates[mk] - baseline_avg
            if abs(delta) >= 3.0:
                anomalies.append({
                    "month": mk,
                    "skip_rate": monthly_skip_rates[mk],
                    "baseline_avg": round(baseline_avg, 1),
                    "delta": round(delta, 1),
                    "direction": "spike" if delta > 0 else "dip",
                })
    return anomalies


def _compute_peak_hour(hourly_heatmap: dict) -> str:
    if not hourly_heatmap or all(v == 0 for v in hourly_heatmap.values()):
        return "Unknown"
    peak_str = max(hourly_heatmap, key=lambda h: hourly_heatmap.get(h, 0))
    hour = int(peak_str)
    if hour == 0: return "12:00 AM"
    if hour < 12: return f"{hour:02d}:00 AM"
    if hour == 12: return "12:00 PM"
    return f"{(hour - 12):02d}:00 PM"


# ---------------------------------------------------------------------------
# Task 2: Engagement-Weighted Text Footprint
# ---------------------------------------------------------------------------

def _mine_text_footprint(parsed: dict) -> dict:
    """Build an engagement-weighted interest corpus."""
    corpus_items: list[tuple[str, str]] = []
    raw_comment_texts: list[str] = []

    for item in parsed.get("comments", []):
        text = item.get("comment", "")
        if text:
            corpus_items.extend([(text, "comment")] * _SIGNAL_WEIGHTS["comment"])
            raw_comment_texts.append(text)

    for item in parsed.get("searches", []):
        text = item.get("term", "")
        if text:
            corpus_items.extend([(text, "search")] * _SIGNAL_WEIGHTS["search"])

    for item in parsed.get("following", []):
        username = item.get("username", "")
        if username:
            words = re.split(r"[._@]", username.lower())
            text = " ".join(w for w in words if len(w) > 2)
            if text:
                corpus_items.extend([(text, "follow")] * _SIGNAL_WEIGHTS["follow"])

    for item in parsed.get("shares", []):
        method = (item.get("method") or "").lower()
        link = item.get("link", "")
        keywords = _keywords_from_url(link)
        if keywords:
            source = "share_dm" if method in _DM_METHODS else "share_public"
            for kw in keywords:
                corpus_items.extend([(kw, source)] * _SIGNAL_WEIGHTS[source])

    for item in parsed.get("favorites", []):
        link = item.get("link", "")
        for kw in _keywords_from_url(link):
            corpus_items.extend([(kw, "favorite")] * _SIGNAL_WEIGHTS["favorite"])

    for item in parsed.get("likes", []):
        link = item.get("link", "")
        for kw in _keywords_from_url(link):
            corpus_items.extend([(kw, "like")] * _SIGNAL_WEIGHTS["like"])

    if not corpus_items:
        return {"interest_clusters": [], "top_phrases": []}

    term_counts: Counter = Counter()
    term_sources: dict[str, Counter] = defaultdict(Counter)

    for text, source in corpus_items:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        for word in words:
            if word not in _FOOTPRINT_STOP:
                term_counts[word] += 1
                term_sources[word][source] += 1

    interest_clusters = [
        {"term": term, "count": count, "dominant_source": term_sources[term].most_common(1)[0][0]}
        for term, count in term_counts.most_common(20)
    ]

    phrase_counts: Counter = Counter()
    for text in raw_comment_texts:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        for i in range(len(words) - 1):
            if words[i] not in _FOOTPRINT_STOP and words[i + 1] not in _FOOTPRINT_STOP:
                phrase_counts[f"{words[i]} {words[i + 1]}"] += 1

    return {"interest_clusters": interest_clusters, "top_phrases": [{"phrase": p, "count": c} for p, c in phrase_counts.most_common(10)]}


# ---------------------------------------------------------------------------
# Task 3: Comment Voice Analysis
# ---------------------------------------------------------------------------

_ENTITY_KEYWORDS: dict[str, list[str]] = {
    "sports_teams": ["lakers", "warriors", "celtics", "bulls", "knicks", "nets", "heat", "patriots", "cowboys", "chiefs", "packers", "49ers", "yankees", "dodgers", "cubs", "nba", "nfl", "mlb", "nhl"],
    "tv_shows": ["stranger things", "the office", "breaking bad", "game of thrones", "friends", "seinfeld", "succession", "ozark", "sopranos", "wire"],
    "musicians": ["taylor swift", "drake", "beyonce", "kendrick", "billie eilish", "eminem", "rihanna", "travis scott", "bad bunny", "sza"],
    "political_figures": ["trump", "biden", "obama", "aoc", "bernie", "pelosi", "desantis", "harris", "musk"],
    "films": ["avengers", "oppenheimer", "barbie", "inception", "interstellar", "joker", "parasite", "dune", "titanic", "matrix"],
}

_EMOJI_RE = re.compile("[\U00002600-\U000026FF\U00002700-\U000027BF\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F9FF\U0001FA00-\U0001FA9F]+", flags=re.UNICODE)

def analyze_comment_voice(comments: list[dict], active_video_count: int, dm_share_count: int = 0) -> dict:
    """Characterise HOW the user engages via comments."""
    texts = [c.get("comment", "") for c in comments if c.get("comment")]
    total = len(texts)

    if total == 0:
        return {"total_comments": 0, "avg_length_chars": 0.0, "long_comments_count": 0, "long_comment_pct": 0.0, "top_20_longest": [], "references_detected": {}, "emoji_density": 0.0, "engagement_style_label": "Lurker"}

    lengths = [len(t) for t in texts]
    avg_length = sum(lengths) / total
    long_comments = [t for t in texts if len(t) > 150]
    top_20 = sorted(texts, key=len, reverse=True)[:20]

    total_chars = sum(lengths)
    emoji_chars = sum(len("".join(_EMOJI_RE.findall(t))) for t in texts)
    emoji_density = emoji_chars / total_chars if total_chars > 0 else 0.0

    all_text = " ".join(texts).lower()
    references: dict[str, list[str]] = {}
    for category, keywords in _ENTITY_KEYWORDS.items():
        found = [kw for kw in keywords if kw in all_text]
        if found: references[category] = found

    comment_rate = total / active_video_count if active_video_count > 0 else 0.0
    if comment_rate < 0.005: label = "Lurker"
    elif avg_length > 100 and emoji_density < 0.05: label = "Analytical Commenter"
    elif avg_length < 40 and comment_rate > 0.05: label = "Reactive Commenter"
    elif total < 20 and dm_share_count > total * 3: label = "Curator"
    else: label = "Community Participant"

    return {"total_comments": total, "avg_length_chars": round(avg_length, 1), "long_comments_count": len(long_comments), "long_comment_pct": round(len(long_comments) / total * 100, 1), "top_20_longest": top_20, "references_detected": references, "emoji_density": round(emoji_density, 4), "engagement_style_label": label}


# ---------------------------------------------------------------------------
# Task 5: Share Behavior Analysis
# ---------------------------------------------------------------------------

def _analyze_share_behavior(shares: list[dict]) -> dict:
    """Classify share behaviour."""
    if not shares:
        return {"total_shares": 0, "share_methods": {}, "primary_share_method": None, "share_behavior_type": "Mixed Sharer", "dm_share_count": 0}

    method_counts: Counter = Counter()
    dm_count = 0
    public_count = 0

    for item in shares:
        method = (item.get("method") or "unknown").lower()
        method_counts[method] += 1
        if method in _DM_METHODS: dm_count += 1
        else: public_count += 1

    total = len(shares)
    primary = method_counts.most_common(1)[0][0]
    dm_pct = dm_count / total
    public_pct = public_count / total

    if dm_pct >= 0.70: behavior_type = "Private Curator"
    elif public_pct > 0.50: behavior_type = "Public Broadcaster"
    else: behavior_type = "Mixed Sharer"

    return {"total_shares": total, "share_methods": dict(method_counts), "primary_share_method": primary, "share_behavior_type": behavior_type, "dm_share_count": dm_count}


# ---------------------------------------------------------------------------
# Task 6: Transparency Gap Calculation
# ---------------------------------------------------------------------------

def calculate_transparency_gap(parsed: dict, profile: dict) -> dict:
    """Compare official vs behavioral interests."""
    official = parsed.get("ad_interests", [])
    behavioral = profile.get("interest_clusters", [])
    official_count = len(official)
    behavioral_count = len(behavioral)

    if official_count == 0 and behavioral_count > 5:
        interpretation = "Ad interests empty — likely privacy opt-out — but behavioral profile shows strong inferred interests."
    elif official_count > 0 and official_count < behavioral_count * 0.5:
        interpretation = f"Significant gap: TikTok's declared interests underrepresent actual behavioral profile by approx {round((1 - official_count / behavioral_count) * 100)}%."
    else:
        interpretation = "Official interests roughly match behavioral profile."

    return {"official_ad_interest_count": official_count, "behavioral_interest_count": behavioral_count, "gap_interpretation": interpretation}


def _detect_atomic_traits(sw: dict, total_conscious: int, parsed: dict, linger_rate_pct: float, night_shift_pct: float, vibe_cluster: list[dict]) -> dict:
    """Detect boolean atomic traits based on behavioral data."""
    traits = {}
    traits["trapped"] = (sw["max_session_duration"] > 3600) or (linger_rate_pct > 30)
    traits["ruthless"] = sw["max_consecutive_skips"] >= 10
    traits["nocturnal"] = night_shift_pct > 35
    traits["curator"] = (len(parsed.get("shares", [])) / max(len(parsed.get("likes", [])), 1)) > 0.5
    actions_count = len(parsed.get("likes", [])) + len(parsed.get("shares", [])) + len(parsed.get("comments", []))
    traits["ghost"] = (actions_count / max(total_conscious, 1)) < 0.01
    total_linger_count = sum(c.get("linger_count", 0) for c in vibe_cluster)
    tech_linger_count = sum(c.get("linger_count", 0) for c in vibe_cluster if c.get("genre") == "tech")
    traits["optimizer"] = (tech_linger_count / max(total_linger_count, 1)) > 0.2
    return traits


def _synthesize_sub_archetypes(traits: dict, behavioral_nodes: dict) -> list[dict]:
    """Cluster traits into 2-4 sub-archetypes."""
    sub_archetypes = []
    if traits.get("curator") and behavioral_nodes.get("social_graph_followed_pct", 0) > 60:
        sub_archetypes.append({"name": "The Intentional Curator", "confidence": 0.9})
    if traits.get("nocturnal") and behavioral_nodes.get("linger_rate_percentage", 0) > 25:
        sub_archetypes.append({"name": "The Nocturnal Seeker", "confidence": 0.85})
    if traits.get("trapped") and behavioral_nodes.get("social_graph_algorithmic_pct", 0) > 75:
        sub_archetypes.append({"name": "The Algorithmic Captured", "confidence": 0.95})
    if traits.get("ghost") and behavioral_nodes.get("linger_rate_percentage", 0) < 10:
        sub_archetypes.append({"name": "The Passive Observer", "confidence": 0.8})
    return sub_archetypes


def _detect_cognitive_dissonance(traits: dict, sw: dict, behavioral_nodes: dict, parsed: dict, vibe_cluster: list[dict]) -> dict:
    """Identify contradictory behavioral identities."""
    night_total = sw["night_count"]
    night_trapped = night_total > 0 and (sw["night_lingers"] / night_total) > 0.3
    if traits.get("ruthless") and night_trapped:
        return {"detected": True, "label": "Circadian Drift", "note": "Your daytime curation is ruthless, but you lose control to the algorithm after midnight."}
    if len(parsed.get("following", [])) > 100 and behavioral_nodes.get("social_graph_algorithmic_pct", 0) > 90:
        return {"detected": True, "label": "Social Paradox", "note": "You follow a village of creators but let the algorithm choose 90% of what you actually see."}
    total_linger_count = sum(c.get("linger_count", 0) for c in vibe_cluster)
    tech_linger_pct = sum(c.get("linger_count", 0) for c in vibe_cluster if c.get("genre") == "tech") / max(total_linger_count, 1)
    if tech_linger_pct > 0.2 and traits.get("ghost"):
         return {"detected": True, "label": "Silent Expert", "note": "You consume high-fidelity knowledge at scale while leaving zero digital trace."}
    return {"detected": False, "label": None, "note": None}


def _determine_primary_archetype(behavioral_nodes: dict, parsed: dict, sw: dict, vibe_cluster: list[dict]) -> dict:
    """Synthesize high-level metrics into a deterministic primary archetype."""
    traits = _detect_atomic_traits(sw, sw["total_conscious_videos"], parsed, behavioral_nodes.get("linger_rate_percentage", 0), behavioral_nodes.get("night_shift_ratio", 0), vibe_cluster)
    sub_archetypes = _synthesize_sub_archetypes(traits, behavioral_nodes)
    dissonance = _detect_cognitive_dissonance(traits, sw, behavioral_nodes, parsed, vibe_cluster)
    primary_name = sub_archetypes[0]["name"] if sub_archetypes else "The Balanced Viewer"
    return {"name": primary_name, "sub_archetypes": sub_archetypes, "dissonance": dissonance, "atomic_traits": traits}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_ghost_profile(parsed: dict, exclude_hours: tuple[int, ...] = (), link_handle_map: dict[str, str] | None = None) -> dict:
    """Derive the strictly behavioral Ghost Profile payload.

    `link_handle_map` (video_id → handle, from utils.creator_map) lets every
    handle-dependent field — vibe_cluster, graveyard, echo-chamber, social-graph
    split, archetype — re-derive from real creators once oEmbed has resolved them.
    """
    active_history = parsed.get("watch_history_active", [])
    sw = _run_stopwatch(active_history, exclude_hours=exclude_hours)
    
    # Pre-map links to titles for richer creator context
    link_to_title = {item.get("link", ""): item.get("title", "") for item in active_history if item.get("link")}

    footprint = _mine_text_footprint(parsed)
    share_behavior = _analyze_share_behavior(parsed.get("shares", []))
    comment_voice = analyze_comment_voice(parsed.get("comments", []), active_video_count=sw["total_conscious_videos"], dm_share_count=share_behavior["dm_share_count"])
    transparency_gap = calculate_transparency_gap(parsed, {"interest_clusters": footprint["interest_clusters"]})

    total_conscious = sw["total_conscious_videos"]
    sustained_and_dives = sw["deep_lingers"] + sw["deep_dives"]
    linger_rate_pct = (sustained_and_dives / max(total_conscious, 1)) * 100
    night_shift_pct = (sw["night_count"] / max(total_conscious, 1)) * 100
    night_linger_pct = (sw["night_lingers"] / max(sustained_and_dives, 1)) * 100

    vibe_cluster = resolve_vibe_cluster(_count_creators(sw["_linger_links"], limit=20, count_key="linger_count", link_to_title=link_to_title, link_handle_map=link_handle_map))
    graveyard = resolve_vibe_cluster(_count_creators(sw["_graveyard_links"], limit=20, count_key="skip_count", link_to_title=link_to_title, link_handle_map=link_handle_map))

    following_usernames = {u.get("username", "").lower().lstrip("@") for u in parsed.get("following", [])}
    for c in vibe_cluster + graveyard:
        c["is_followed"] = c.get("handle", "").lower().lstrip("@") in following_usernames

    followed_videos = algorithmic_videos = 0
    for link in (set(sw["_graveyard_links"]) | set(sw["_sandbox_links"]) | set(sw["_linger_links"])):
        creator = _handle_from_link(link, link_handle_map)
        if creator:
            if creator.lstrip("@").lower() in following_usernames: followed_videos += 1
            else: algorithmic_videos += 1
    
    total_creators_found = followed_videos + algorithmic_videos
    followed_pct = round((followed_videos / total_creators_found) * 100, 1) if total_creators_found > 0 else 0.0
    algorithmic_pct = round((algorithmic_videos / total_creators_found) * 100, 1) if total_creators_found > 0 else 0.0

    behavioral_nodes = {
        "peak_hour": _compute_peak_hour(sw["hourly_heatmap"]),
        "inferred_sleep_window": _infer_sleep_window(sw["hourly_heatmap"]),
        "skip_rate_percentage": round((sw["graveyard_skips"] / max(total_conscious, 1)) * 100, 1),
        "linger_rate_percentage": round(linger_rate_pct, 1),
        "night_shift_ratio": round(night_shift_pct, 1),
        "night_linger_pct": round(night_linger_pct, 1),
        "night_lingers_count": sw["night_lingers"],
        "social_graph_algorithmic_pct": algorithmic_pct,
        "social_graph_followed_pct": followed_pct,
    }
    algorithm_drift = _algorithm_drift(sw.get("monthly_skip_rates", {}))

    primary_archetype = _determine_primary_archetype(behavioral_nodes, parsed, sw, vibe_cluster)

    searches_raw = parsed.get("searches", [])
    search_hour_hist = defaultdict(int)
    search_timeline = []
    for s in searches_raw:
        term, ds = s.get("term", ""), s.get("date", "")
        dt = _parse_date(ds)
        if dt:
            search_hour_hist[dt.hour] += 1
            search_timeline.append({"term": term, "date": ds, "hour": dt.hour, "dow": dt.weekday()})
    search_timeline.sort(key=lambda x: x["date"], reverse=True)

    declared_surface = set((s.get("term") or "").lower().strip() for s in searches_raw[:200]) | \
                       set((ad or "").lower().strip() for ad in parsed.get("ad_interests", [])) | \
                       set((si or "").lower().strip() for si in parsed.get("settings_interests", []))

    explicit_total = len(parsed.get("likes", [])) + len(parsed.get("comments", []))
    implicit_total = sustained_and_dives
    
    echo = _echo_chamber_index(sw["_linger_links"], link_handle_map)

    # ── Temporal / monthly features ──────────────────────────────────────────
    monthly_creator_trends = _monthly_creator_trends(sw["linger_events"], link_handle_map)
    monthly_topic_trends = _monthly_topic_trends(searches_raw, parsed.get("comments", []))
    sandbox_retests = _sandbox_retests(sw["sandbox_events"], link_handle_map)
    anomalies = _skip_anomalies(sw.get("monthly_skip_rates", {}))

    # ── Data cliff (start of watch history) ──────────────────────────────────
    data_start = sw.get("data_start_month")

    hourly_sorted = sorted(sw["hourly_heatmap"].items(), key=lambda x: x[1], reverse=True)
    top_hours = sorted([int(h) for h, v in hourly_sorted[:3] if v > 0])
    
    def _fmt_h(h: int) -> str:
        if h == 0: return "12 AM"
        if h < 12: return f"{h} AM"
        if h == 12: return "12 PM"
        return f"{h - 12} PM"

    # Ensure all sets are converted to lists for JSON serializability
    sw["_graveyard_links"] = list(sw["_graveyard_links"])
    sw["_sandbox_links"] = list(sw["_sandbox_links"])
    sw["_linger_links"] = list(sw["_linger_links"])
    sw["_deep_dive_links"] = list(sw["_deep_dive_links"])

    return {
        "status": "success",
        "interest_clusters": footprint["interest_clusters"],
        "interest_phrases": footprint["top_phrases"],
        "stopwatch_metrics": sw,
        "behavioral_nodes": behavioral_nodes,
        "primary_archetype": primary_archetype,
        "creator_entities": {"vibe_cluster": vibe_cluster, "graveyard": graveyard},
        "academic_insights": {
            "explicit_vs_implicit_ratio": round(explicit_total / implicit_total, 3) if implicit_total > 0 else 0.0,
            "explicit_actions_count": explicit_total,
            "implicit_linger_count": implicit_total,
            "echo_chamber_index_pct": echo["pct"],
            "echo_chamber_basis": echo["basis"],
            "echo_chamber_distinct_creators": echo["distinct_creators"],
            "top_creator_handles": [c.get("handle") for c in vibe_cluster[:5]],
        },
        "night_shift": {"percentage": round(night_shift_pct, 1), "count": sw["night_count"], "window": "23:00 – 04:00"},
        "digital_footprint": {
            "login_count": len(parsed.get("login_history", [])),
            "unique_ips": parsed.get("login_history_stats", {}).get("unique_ips", 0),
            "unique_devices": parsed.get("login_history_stats", {}).get("unique_devices", []),
            "recent_logins": sorted([{"date": l.get("date", ""), "ip": l.get("ip", ""), "device": l.get("device_model", ""), "system": l.get("device_system", ""), "network": l.get("network_type", ""), "carrier": l.get("carrier", "")} for l in parsed.get("login_history", []) if l.get("date")], key=lambda x: x["date"], reverse=True)[:25],
        },
        "search_rhythm": {"total_searches": len(search_timeline), "hourly_histogram": {str(h): search_hour_hist.get(h, 0) for h in range(24)}, "recent_searches": search_timeline[:30]},
        "discrepancy_gap": {"declared_surface_sample": sorted(list(declared_surface))[:40], "inferred_creator_handles": [c.get("handle") for c in vibe_cluster[:10]], "declared_count": len(declared_surface), "inferred_count": len(set(c.get("handle", "") for c in vibe_cluster))},
        "enrichment_targets": {
            "lingered": sorted(sw["linger_events"], key=lambda e: e["time_spent"], reverse=True)[:40],
            "graveyard": sw["graveyard_events"][:40],
            "sandbox": sw["sandbox_events"][:40],
            "night_lingered": sorted(sw["night_linger_events"], key=lambda e: e["time_spent"], reverse=True)[:30],
            "deep_dives": sorted(sw["deep_dive_events"], key=lambda e: e["time_spent"], reverse=True)[:20],
            "following_usernames": list(following_usernames),
        },
        "declared_signals": {
            "settings_interests": parsed.get("settings_interests", []),
            "ad_interests": parsed.get("ad_interests", []),
            "recent_searches": [s.get("term", "") for s in searches_raw[:30] if s.get("term")],
            "following_count": len(parsed.get("following", [])),
            "follower_count": len(parsed.get("followers", [])),
        },
        "ad_profile": {
            "advertiser_categories": parsed.get("ad_interests", []),
            "vulnerability_window": " / ".join(_fmt_h(h) for h in top_hours) if top_hours else "Unknown",
            "peak_ad_hour": behavioral_nodes["peak_hour"],
            "night_targeting": round(night_shift_pct, 1),
            "off_platform_tracked": len(parsed.get("off_tiktok_activity", [])) > 0,
            "off_platform_events": len(parsed.get("off_tiktok_activity", [])),
            "shop_order_count": len(parsed.get("shop_orders", [])),
            "shop_products": [p for order in parsed.get("shop_orders", []) for p in order.get("products", [])][:20],
            "product_browsing_count": len(parsed.get("product_browsing", [])),
            "browsed_products": [b["product"] for b in parsed.get("product_browsing", []) if b.get("product")][:25],
        },
        "comment_voice": comment_voice,
        "share_behavior": share_behavior,
        "transparency_gap": transparency_gap,
        "algorithm_drift": algorithm_drift,
        "monthly_creator_trends": monthly_creator_trends,
        "monthly_topic_trends": monthly_topic_trends,
        "sandbox_retests": sandbox_retests,
        "skip_anomalies": anomalies,
        "data_cliff": {"start_month": data_start, "window_days": 180},
    }
