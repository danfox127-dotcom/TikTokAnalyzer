# SYS.TEARDOWN Part 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the TikTok behavioral analysis pipeline with session-aware scrubbing, engagement-weighted interest scoring, comment voice analysis, share behavior analysis, transparency gap calculation, and a privacy-safe LLM export endpoint.

**Architecture:** Session detection lives in `parsers/tiktok.py` and produces `watch_history_active`; all downstream analysis in `ghost_profile.py` consumes it. New analysis functions (`_mine_text_footprint`, `analyze_comment_voice`, `_analyze_share_behavior`, `calculate_transparency_gap`) are added to `ghost_profile.py` and called from `build_ghost_profile()`. A new `exporters/llm_export.py` module generates the privacy-safe JSON; a new FastAPI endpoint in `api/main.py` serves it.

**Tech Stack:** Python 3.14, FastAPI, existing `parsers/tiktok.py` + `ghost_profile.py` patterns; pytest for tests; no new pip dependencies.

---

## File Map

| File | Change |
|---|---|
| `parsers/tiktok.py` | Add `_detect_sessions()`, `_compute_night_shift_ratio()`; update `_parse_tiktok_data()` |
| `ghost_profile.py` | Add module-level constants; add `_mine_text_footprint()`, `analyze_comment_voice()`, `_analyze_share_behavior()`, `calculate_transparency_gap()`; update `build_ghost_profile()` |
| `exporters/__init__.py` | New (empty) |
| `exporters/llm_export.py` | New — `generate_llm_export()` |
| `api/main.py` | Add `POST /api/export/llm` endpoint |
| `tests/test_session_scrubbing.py` | New — Task 1 tests |
| `tests/test_ghost_profile_enrichments.py` | New — Tasks 2–6 tests |
| `tests/test_llm_export.py` | New — Task 7 tests |

---

## Task 1: Session-Aware Watch History Scrubbing

**Files:**
- Modify: `parsers/tiktok.py`
- Test: `tests/test_session_scrubbing.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_session_scrubbing.py`:

```python
from datetime import datetime, timedelta
from parsers.tiktok import _detect_sessions


def _entry(dt: datetime, link: str = "https://www.tiktok.com/@user/video/123") -> dict:
    return {"date": dt.strftime("%Y-%m-%d %H:%M:%S"), "link": link}


BASE = datetime(2024, 1, 1, 12, 0, 0)


def test_autoplay_artifact_flagged_passive():
    """Videos within 2s of the previous video are passive (autoplay artifact)."""
    history = [
        _entry(BASE),
        _entry(BASE + timedelta(seconds=1)),   # autoplay — should be passive
        _entry(BASE + timedelta(seconds=30)),
    ]
    result = _detect_sessions(history, [], [], [])
    assert result["passive_videos_removed"] >= 1
    assert result["active_video_count"] <= 2


def test_zero_engagement_session_with_5_plus_videos_is_passive():
    """Sessions with 5+ videos and no engagement actions are passive."""
    history = [_entry(BASE + timedelta(minutes=i * 3)) for i in range(6)]
    result = _detect_sessions(history, [], [], [])
    assert result["passive_sessions_detected"] >= 1
    assert result["active_video_count"] < 6


def test_zero_engagement_session_with_fewer_than_5_videos_not_passive():
    """Sessions with < 5 videos are NOT flagged passive even without engagement."""
    history = [_entry(BASE + timedelta(minutes=i * 3)) for i in range(4)]
    result = _detect_sessions(history, [], [], [])
    assert result["passive_sessions_detected"] == 0


def test_engaged_session_stays_active():
    """A session that has a like within its time window keeps all its videos."""
    history = [_entry(BASE + timedelta(minutes=i * 3)) for i in range(6)]
    likes = [{"date": (BASE + timedelta(minutes=9)).strftime("%Y-%m-%d %H:%M:%S")}]
    result = _detect_sessions(history, likes, [], [])
    assert result["passive_sessions_detected"] == 0
    assert result["active_video_count"] == 6


def test_session_gap_splits_sessions():
    """A gap > 30 minutes between two videos starts a new session."""
    history = [
        _entry(BASE),
        _entry(BASE + timedelta(minutes=45)),
    ]
    result = _detect_sessions(history, [], [], [])
    assert result["session_count"] == 2


def test_output_keys_present():
    history = [_entry(BASE + timedelta(minutes=i)) for i in range(3)]
    result = _detect_sessions(history, [], [], [])
    for key in (
        "watch_history_full", "watch_history_active",
        "passive_videos_removed", "passive_sessions_detected",
        "active_video_count", "session_count", "avg_session_length_videos",
    ):
        assert key in result, f"Missing key: {key}"


def test_empty_history_returns_empty_active():
    result = _detect_sessions([], [], [], [])
    assert result["watch_history_active"] == []
    assert result["passive_videos_removed"] == 0
```

- [ ] **Step 2: Run to verify they all fail**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_session_scrubbing.py -v 2>&1 | head -40
```

Expected: ImportError or AttributeError — `_detect_sessions` not defined yet.

- [ ] **Step 3: Add `_compute_night_shift_ratio` helper to `parsers/tiktok.py`**

Insert after the `_parse_date` function (line ~24):

```python
def _compute_night_shift_ratio(history: list[dict]) -> float:
    """Night-shift ratio from raw history (23:00–04:00). Used on full history, not active."""
    night = total = 0
    for item in history:
        dt = _parse_date(item.get("date", ""))
        if dt:
            total += 1
            if 23 <= dt.hour or dt.hour < 4:
                night += 1
    return round(night / total * 100, 1) if total > 0 else 0.0
```

- [ ] **Step 4: Add `_detect_sessions` to `parsers/tiktok.py`**

Insert after `_compute_night_shift_ratio`:

```python
_SESSION_GAP_S = 1800   # 30 minutes → new session
_DM_METHODS = {
    "chat_head", "dm", "message", "whatsapp", "instagram",
    "line", "kakaotalk", "telegram",
}


def _detect_sessions(
    browsing_history: list[dict],
    likes: list[dict],
    comments: list[dict],
    shares: list[dict],
) -> dict:
    """
    Split browsing_history into sessions and flag passive videos.

    A video is passive if:
    - It follows the previous video by < 2 seconds (autoplay artifact), OR
    - It belongs to a session of 5+ videos with zero engagement actions.

    Returns watch_history_active (passive removed) and watch_history_full (original).
    """
    if not browsing_history:
        return {
            "watch_history_full": [],
            "watch_history_active": [],
            "passive_videos_removed": 0,
            "passive_sessions_detected": 0,
            "active_video_count": 0,
            "session_count": 0,
            "avg_session_length_videos": 0.0,
        }

    # Build engagement timestamp set (likes + comments + shares)
    engagement_times: list[datetime] = []
    for source in (likes, comments, shares):
        for item in source:
            dt = _parse_date(item.get("date", ""))
            if dt:
                engagement_times.append(dt)

    # Parse and index history; items without datetimes are kept as-is (active)
    parsed_entries: list[dict] = []
    unparseable: list[dict] = []
    for idx, item in enumerate(browsing_history):
        dt = _parse_date(item.get("date", ""))
        if dt:
            parsed_entries.append({"_dt": dt, "_orig": item, "_idx": idx})
        else:
            unparseable.append(item)

    parsed_entries.sort(key=lambda e: e["_dt"])

    # Split into sessions
    sessions: list[list[dict]] = []
    if parsed_entries:
        current: list[dict] = [parsed_entries[0]]
        for i in range(1, len(parsed_entries)):
            gap = (parsed_entries[i]["_dt"] - parsed_entries[i - 1]["_dt"]).total_seconds()
            if gap > _SESSION_GAP_S:
                sessions.append(current)
                current = [parsed_entries[i]]
            else:
                current.append(parsed_entries[i])
        sessions.append(current)

    # Determine which entries are passive
    passive_indices: set[int] = set()
    passive_sessions = 0

    for session in sessions:
        s_start = session[0]["_dt"]
        s_end = session[-1]["_dt"]

        # Zero-engagement session with 5+ videos → whole session is passive
        has_engagement = any(s_start <= et <= s_end for et in engagement_times)
        if not has_engagement and len(session) >= 5:
            passive_sessions += 1
            for entry in session:
                passive_indices.add(entry["_idx"])

        # Autoplay artifacts: video follows previous by < 2 seconds
        for i in range(1, len(session)):
            delta = (session[i]["_dt"] - session[i - 1]["_dt"]).total_seconds()
            if delta < 2:
                passive_indices.add(session[i]["_idx"])

    watch_history_full = [e["_orig"] for e in parsed_entries] + unparseable
    watch_history_active = [
        e["_orig"] for e in parsed_entries if e["_idx"] not in passive_indices
    ] + unparseable

    session_lengths = [len(s) for s in sessions]
    avg_len = round(sum(session_lengths) / len(session_lengths), 1) if sessions else 0.0

    return {
        "watch_history_full": watch_history_full,
        "watch_history_active": watch_history_active,
        "passive_videos_removed": len(passive_indices),
        "passive_sessions_detected": passive_sessions,
        "active_video_count": len(watch_history_active),
        "session_count": len(sessions),
        "avg_session_length_videos": avg_len,
    }
```

- [ ] **Step 5: Wire `_detect_sessions` into `_parse_tiktok_data`**

In `_parse_tiktok_data`, replace the two lines:
```python
    behavioral_analysis = _compute_behavioral_analysis(browsing_history)
```
with:
```python
    session_result = _detect_sessions(browsing_history, likes, comments, shares)
    watch_history_active = session_result["watch_history_active"]
    behavioral_analysis = _compute_behavioral_analysis(watch_history_active)
    # Night shift preserved from full history — time-of-day patterns remain meaningful
    # even when content is passive.
    behavioral_analysis["night_shift_ratio"] = _compute_night_shift_ratio(browsing_history)
    behavioral_analysis["night_shift_passive_adjusted"] = True
    behavioral_analysis.update({
        "passive_videos_removed": session_result["passive_videos_removed"],
        "passive_sessions_detected": session_result["passive_sessions_detected"],
        "active_video_count": session_result["active_video_count"],
        "session_count": session_result["session_count"],
        "avg_session_length_videos": session_result["avg_session_length_videos"],
    })
```

And update the return dict in `_parse_tiktok_data` to include the new keys after `"browsing_history": browsing_history,`:
```python
        "browsing_history": browsing_history,
        "watch_history_full": session_result["watch_history_full"],
        "watch_history_active": watch_history_active,
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_session_scrubbing.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 7: Smoke-test against the real export (if available)**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -c "
from parsers.tiktok import parse_tiktok_export
import glob, json
files = glob.glob('**/user_data_tiktok.json', recursive=True)
if files:
    r = parse_tiktok_export(files[0])
    ba = r['behavioral_analysis']
    print('total_videos:', r['behavioral_analysis'].get('total_videos'))
    print('active_video_count:', ba.get('active_video_count'))
    print('passive_removed:', ba.get('passive_videos_removed'))
    print('session_count:', ba.get('session_count'))
else:
    print('No export found — skipping smoke test')
"
```

Expected: `active_video_count` < `total_videos` and `passive_videos_removed` > 0 if the export has passive sessions.

- [ ] **Step 8: Commit**

```bash
git add parsers/tiktok.py tests/test_session_scrubbing.py
git commit -m "feat: add session-aware watch history scrubbing to tiktok parser"
```

---

## Task 2: Wire Ghost Profile to Use `watch_history_active`

**Files:**
- Modify: `ghost_profile.py`

- [ ] **Step 1: Update `build_ghost_profile` to consume `watch_history_active`**

In `ghost_profile.py`, find the line in `build_ghost_profile`:
```python
    sw = _run_stopwatch(parsed.get("browsing_history", []), exclude_hours=exclude_hours)
```

Replace with:
```python
    active_history = (
        parsed.get("watch_history_active")
        or parsed.get("browsing_history", [])
    )
    sw = _run_stopwatch(active_history, exclude_hours=exclude_hours)
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/ -v --ignore=tests/test_session_scrubbing.py 2>&1 | tail -20
```

Expected: all previously-passing tests still pass; no regressions.

- [ ] **Step 3: Commit**

```bash
git add ghost_profile.py
git commit -m "feat: ghost_profile stopwatch now consumes watch_history_active"
```

---

## Task 3: Engagement-Weighted Interest Scoring (`_mine_text_footprint`)

**Files:**
- Modify: `ghost_profile.py`
- Test: `tests/test_ghost_profile_enrichments.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ghost_profile_enrichments.py`:

```python
"""Tests for Tasks 3–6: _mine_text_footprint, analyze_comment_voice,
_analyze_share_behavior, calculate_transparency_gap."""

from ghost_profile import (
    _mine_text_footprint,
    analyze_comment_voice,
    _analyze_share_behavior,
    calculate_transparency_gap,
)


# ── _mine_text_footprint ──────────────────────────────────────────────────────

def _minimal_parsed(**overrides) -> dict:
    base = {
        "comments": [],
        "searches": [],
        "likes": [],
        "favorites": [],
        "shares": [],
        "following": [],
    }
    base.update(overrides)
    return base


def test_interest_clusters_returned():
    parsed = _minimal_parsed(
        searches=[{"term": "basketball", "date": "2024-01-01 00:00:00"}]
    )
    result = _mine_text_footprint(parsed)
    assert "interest_clusters" in result
    assert isinstance(result["interest_clusters"], list)


def test_comment_weighted_higher_than_equivalent_searches():
    """1 comment (weight 10) > 1 search (weight 5) for the same term."""
    parsed = _minimal_parsed(
        comments=[{"comment": "jazz music is great", "date": "2024-01-01 00:00:00"}],
        searches=[{"term": "classical music", "date": "2024-01-01 00:00:00"}],
    )
    result = _mine_text_footprint(parsed)
    terms = [c["term"] for c in result["interest_clusters"]]
    # "jazz" appears at weight 10; "classical" at weight 5 — jazz should rank higher
    if "jazz" in terms and "classical" in terms:
        assert terms.index("jazz") < terms.index("classical")


def test_dominant_source_is_comment_when_comment_drives_term():
    parsed = _minimal_parsed(
        comments=[{"comment": "skateboarding tricks", "date": "2024-01-01 00:00:00"}],
    )
    result = _mine_text_footprint(parsed)
    skate_cluster = next(
        (c for c in result["interest_clusters"] if c["term"] == "skateboarding"), None
    )
    assert skate_cluster is not None
    assert skate_cluster["dominant_source"] == "comment"


def test_empty_parsed_returns_empty_clusters():
    result = _mine_text_footprint(_minimal_parsed())
    assert result["interest_clusters"] == []


def test_top_phrases_present():
    parsed = _minimal_parsed(
        comments=[
            {"comment": "dark humor comedy is underrated", "date": "2024-01-01"}
            for _ in range(3)
        ]
    )
    result = _mine_text_footprint(parsed)
    assert "top_phrases" in result
    assert isinstance(result["top_phrases"], list)
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_ghost_profile_enrichments.py::test_interest_clusters_returned -v 2>&1 | head -20
```

Expected: ImportError — `_mine_text_footprint` not defined yet.

- [ ] **Step 3: Add module-level constants to `ghost_profile.py`**

At the top of `ghost_profile.py`, after the imports block, add:

```python
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
```

- [ ] **Step 4: Add `_mine_text_footprint` to `ghost_profile.py`**

Add the following function after the `_compute_peak_hour` function (before the Public API section):

```python
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

    # Shares — weight 8 (DM) or 4 (public); extract creator username from URL
    for item in parsed.get("shares", []):
        method = (item.get("method") or "").lower()
        link = item.get("link", "")
        creator = _extract_creator_from_url(link) if link else None
        if creator:
            source = "share_dm" if method in _DM_METHODS else "share_public"
            corpus_items.extend([(creator, source)] * _SIGNAL_WEIGHTS[source])

    # Favorites — weight 7
    for item in parsed.get("favorites", []):
        link = item.get("link", "")
        creator = _extract_creator_from_url(link) if link else None
        if creator:
            corpus_items.extend([(creator, "favorite")] * _SIGNAL_WEIGHTS["favorite"])

    # Likes — weight 3
    for item in parsed.get("likes", []):
        link = item.get("link", "")
        creator = _extract_creator_from_url(link) if link else None
        if creator:
            corpus_items.extend([(creator, "like")] * _SIGNAL_WEIGHTS["like"])

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
```

- [ ] **Step 5: Call `_mine_text_footprint` from `build_ghost_profile`**

In `build_ghost_profile`, after the stopwatch block (after `sw = _run_stopwatch(...)`), add:

```python
    # ── Task 2: Engagement-Weighted Interest Scoring ───────────────────────
    footprint = _mine_text_footprint(parsed)
    interest_clusters = footprint["interest_clusters"]
    interest_phrases  = footprint["top_phrases"]
```

Then in the return dict, add:
```python
        "interest_clusters": interest_clusters,
        "interest_phrases": interest_phrases,
```

- [ ] **Step 6: Run the footprint tests**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_ghost_profile_enrichments.py -k "footprint or cluster or source or phrase or empty_parsed" -v
```

Expected: all 5 footprint tests PASS.

- [ ] **Step 7: Commit**

```bash
git add ghost_profile.py tests/test_ghost_profile_enrichments.py
git commit -m "feat: engagement-weighted text footprint and interest clusters"
```

---

## Task 4: Comment Voice Analysis

**Files:**
- Modify: `ghost_profile.py`
- Test: `tests/test_ghost_profile_enrichments.py` (append)

- [ ] **Step 1: Add comment voice tests to `tests/test_ghost_profile_enrichments.py`**

Append to the file:

```python
# ── analyze_comment_voice ─────────────────────────────────────────────────────

def test_lurker_label_below_half_percent():
    """< 0.5% comment rate → Lurker."""
    comments = [{"comment": "lol", "date": "2024-01-01"}]
    result = analyze_comment_voice(comments, active_video_count=1000)
    assert result["engagement_style_label"] == "Lurker"


def test_analytical_label_long_avg_low_emoji():
    long_text = "This is a detailed analytical observation about the subject matter " * 3
    comments = [{"comment": long_text, "date": "2024-01-01"} for _ in range(30)]
    result = analyze_comment_voice(comments, active_video_count=500)
    assert result["engagement_style_label"] == "Analytical Commenter"


def test_reactive_label_short_frequent():
    comments = [{"comment": "lmao", "date": "2024-01-01"} for _ in range(60)]
    result = analyze_comment_voice(comments, active_video_count=500)
    assert result["engagement_style_label"] == "Reactive Commenter"


def test_top_20_longest_sorted_descending():
    comments = [{"comment": "x" * i, "date": "2024-01-01"} for i in range(1, 30)]
    result = analyze_comment_voice(comments, active_video_count=1000)
    assert len(result["top_20_longest"]) <= 20
    lengths = [len(c) for c in result["top_20_longest"]]
    assert lengths == sorted(lengths, reverse=True)


def test_long_comment_count():
    comments = [
        {"comment": "a" * 200, "date": "2024-01-01"},
        {"comment": "b" * 50,  "date": "2024-01-01"},
    ]
    result = analyze_comment_voice(comments, active_video_count=1000)
    assert result["long_comments_count"] == 1


def test_empty_comments_returns_lurker():
    result = analyze_comment_voice([], active_video_count=500)
    assert result["engagement_style_label"] == "Lurker"
    assert result["total_comments"] == 0


def test_references_detected_sports():
    comments = [{"comment": "go lakers let's go!", "date": "2024-01-01"}]
    result = analyze_comment_voice(comments, active_video_count=100)
    assert "sports_teams" in result["references_detected"]
    assert "lakers" in result["references_detected"]["sports_teams"]
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_ghost_profile_enrichments.py -k "lurker or analytical or reactive or top_20 or long_comment or empty_comments or references" -v 2>&1 | head -30
```

Expected: ImportError — `analyze_comment_voice` not defined yet.

- [ ] **Step 3: Add `analyze_comment_voice` to `ghost_profile.py`**

Add after `_mine_text_footprint`:

```python
# ---------------------------------------------------------------------------
# Task 3: Comment Voice Analysis
# ---------------------------------------------------------------------------

_ENTITY_KEYWORDS: dict[str, list[str]] = {
    "sports_teams": [
        "lakers", "warriors", "celtics", "bulls", "knicks", "nets", "heat",
        "patriots", "cowboys", "chiefs", "packers", "49ers", "yankees",
        "dodgers", "cubs", "nba", "nfl", "mlb", "nhl",
    ],
    "tv_shows": [
        "stranger things", "the office", "breaking bad", "game of thrones",
        "friends", "seinfeld", "succession", "ozark", "sopranos", "wire",
    ],
    "musicians": [
        "taylor swift", "drake", "beyonce", "kendrick", "billie eilish",
        "eminem", "rihanna", "travis scott", "bad bunny", "sza",
    ],
    "political_figures": [
        "trump", "biden", "obama", "aoc", "bernie", "pelosi", "desantis",
        "harris", "musk",
    ],
    "films": [
        "avengers", "oppenheimer", "barbie", "inception", "interstellar",
        "joker", "parasite", "dune", "titanic", "matrix",
    ],
}

_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F9FF"
    "\U00002700-\U000027BF"
    "\U0001FA00-\U0001FA9F"
    "]+",
    flags=re.UNICODE,
)


def analyze_comment_voice(
    comments: list[dict],
    active_video_count: int,
    dm_share_count: int = 0,
) -> dict:
    """
    Characterise HOW the user engages via comments — not just what topics appear.
    """
    texts = [c.get("comment", "") for c in comments if c.get("comment")]
    total = len(texts)

    if total == 0:
        return {
            "total_comments": 0,
            "avg_length_chars": 0.0,
            "long_comments_count": 0,
            "long_comment_pct": 0.0,
            "top_20_longest": [],
            "references_detected": {},
            "emoji_density": 0.0,
            "engagement_style_label": "Lurker",
        }

    lengths = [len(t) for t in texts]
    avg_length = sum(lengths) / total
    long_comments = [t for t in texts if len(t) > 150]
    top_20 = sorted(texts, key=len, reverse=True)[:20]

    # Emoji density: emoji character count / total character count
    total_chars = sum(lengths)
    emoji_chars = sum(len("".join(_EMOJI_RE.findall(t))) for t in texts)
    emoji_density = emoji_chars / total_chars if total_chars > 0 else 0.0

    # Named entity detection
    all_text = " ".join(texts).lower()
    references: dict[str, list[str]] = {}
    for category, keywords in _ENTITY_KEYWORDS.items():
        found = [kw for kw in keywords if kw in all_text]
        if found:
            references[category] = found

    # Engagement style label (priority order)
    comment_rate = total / active_video_count if active_video_count > 0 else 0.0

    if comment_rate < 0.005:
        label = "Lurker"
    elif avg_length > 100 and emoji_density < 0.05:
        label = "Analytical Commenter"
    elif avg_length < 40 and comment_rate > 0.05:
        label = "Reactive Commenter"
    elif total < 20 and dm_share_count > total * 3:
        label = "Curator"
    else:
        label = "Community Participant"

    return {
        "total_comments": total,
        "avg_length_chars": round(avg_length, 1),
        "long_comments_count": len(long_comments),
        "long_comment_pct": round(len(long_comments) / total * 100, 1),
        "top_20_longest": top_20,
        "references_detected": references,
        "emoji_density": round(emoji_density, 4),
        "engagement_style_label": label,
    }
```

Note: `re` is already imported at the top of `ghost_profile.py` (add `import re` if not present).

- [ ] **Step 4: Add `re` import if missing**

Check the imports at the top of `ghost_profile.py`. If `import re` is not present, add it after `from collections import defaultdict`.

- [ ] **Step 5: Call `analyze_comment_voice` from `build_ghost_profile`**

After the footprint block in `build_ghost_profile`, add:

```python
    # ── Task 3: Comment Voice ─────────────────────────────────────────────
    # share_behavior not computed yet — pass dm_share_count=0 as placeholder;
    # will be updated after Task 4.
    comment_voice = analyze_comment_voice(
        parsed.get("comments", []),
        active_video_count=sw["total_conscious_videos"],
        dm_share_count=0,
    )
```

Add to the return dict:
```python
        "comment_voice": comment_voice,
```

- [ ] **Step 6: Run comment voice tests**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_ghost_profile_enrichments.py -k "lurker or analytical or reactive or top_20 or long_comment or empty_comments or references" -v
```

Expected: all 7 comment voice tests PASS.

- [ ] **Step 7: Commit**

```bash
git add ghost_profile.py tests/test_ghost_profile_enrichments.py
git commit -m "feat: comment voice analysis with engagement style labels and entity detection"
```

---

## Task 5: Share Behavior Analysis

**Files:**
- Modify: `ghost_profile.py`
- Test: `tests/test_ghost_profile_enrichments.py` (append)

- [ ] **Step 1: Add share behavior tests to `tests/test_ghost_profile_enrichments.py`**

Append:

```python
# ── _analyze_share_behavior ───────────────────────────────────────────────────

def test_private_curator_over_70_pct_dm():
    shares = (
        [{"method": "chat_head", "date": "2024-01-01"}] * 8
        + [{"method": "copy", "date": "2024-01-01"}] * 2
    )
    result = _analyze_share_behavior(shares)
    assert result["share_behavior_type"] == "Private Curator"


def test_public_broadcaster_over_50_pct_public():
    shares = (
        [{"method": "copy", "date": "2024-01-01"}] * 6
        + [{"method": "chat_head", "date": "2024-01-01"}] * 4
    )
    result = _analyze_share_behavior(shares)
    assert result["share_behavior_type"] == "Public Broadcaster"


def test_mixed_sharer_no_dominant_method():
    shares = (
        [{"method": "chat_head", "date": "2024-01-01"}] * 5
        + [{"method": "copy", "date": "2024-01-01"}] * 5
    )
    result = _analyze_share_behavior(shares)
    assert result["share_behavior_type"] == "Mixed Sharer"


def test_share_methods_counted_correctly():
    shares = [
        {"method": "chat_head", "date": "2024-01-01"},
        {"method": "copy",      "date": "2024-01-01"},
        {"method": "chat_head", "date": "2024-01-01"},
    ]
    result = _analyze_share_behavior(shares)
    assert result["share_methods"]["chat_head"] == 2
    assert result["share_methods"]["copy"] == 1
    assert result["total_shares"] == 3


def test_empty_shares_returns_mixed_sharer():
    result = _analyze_share_behavior([])
    assert result["share_behavior_type"] == "Mixed Sharer"
    assert result["total_shares"] == 0
    assert result["dm_share_count"] == 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_ghost_profile_enrichments.py -k "curator or broadcaster or mixed or methods_counted or empty_shares" -v 2>&1 | head -20
```

Expected: ImportError — `_analyze_share_behavior` not defined.

- [ ] **Step 3: Add `_analyze_share_behavior` to `ghost_profile.py`**

Add after `analyze_comment_voice`:

```python
# ---------------------------------------------------------------------------
# Task 4: Share Behavior Analysis
# ---------------------------------------------------------------------------


def _analyze_share_behavior(shares: list[dict]) -> dict:
    """Classify share behaviour as Private Curator, Public Broadcaster, or Mixed Sharer."""
    from collections import Counter

    if not shares:
        return {
            "total_shares": 0,
            "share_methods": {},
            "primary_share_method": None,
            "share_behavior_type": "Mixed Sharer",
            "dm_share_count": 0,
        }

    method_counts: Counter = Counter()
    dm_count = 0
    public_count = 0

    for item in shares:
        method = (item.get("method") or "unknown").lower()
        method_counts[method] += 1
        if method in _DM_METHODS:
            dm_count += 1
        else:
            public_count += 1

    total = len(shares)
    primary = method_counts.most_common(1)[0][0]
    dm_pct = dm_count / total
    public_pct = public_count / total

    if dm_pct > 0.70:
        behavior_type = "Private Curator"
    elif public_pct > 0.50:
        behavior_type = "Public Broadcaster"
    else:
        behavior_type = "Mixed Sharer"

    return {
        "total_shares": total,
        "share_methods": dict(method_counts),
        "primary_share_method": primary,
        "share_behavior_type": behavior_type,
        "dm_share_count": dm_count,
    }
```

- [ ] **Step 4: Wire `_analyze_share_behavior` into `build_ghost_profile` and fix `comment_voice` DM count**

In `build_ghost_profile`, after the comment voice block, add:

```python
    # ── Task 4: Share Behavior ────────────────────────────────────────────
    share_behavior = _analyze_share_behavior(parsed.get("shares", []))

    # Back-fill dm_share_count now that we have it
    comment_voice = analyze_comment_voice(
        parsed.get("comments", []),
        active_video_count=sw["total_conscious_videos"],
        dm_share_count=share_behavior["dm_share_count"],
    )
```

(Remove the earlier placeholder call to `analyze_comment_voice` from Task 3 Step 5 — this replaces it.)

Add to return dict:
```python
        "share_behavior": share_behavior,
```

- [ ] **Step 5: Run share behavior tests**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_ghost_profile_enrichments.py -k "curator or broadcaster or mixed or methods_counted or empty_shares" -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add ghost_profile.py tests/test_ghost_profile_enrichments.py
git commit -m "feat: share behavior analysis with Private Curator/Public Broadcaster classification"
```

---

## Task 6: Transparency Gap Calculation

**Files:**
- Modify: `ghost_profile.py`
- Test: `tests/test_ghost_profile_enrichments.py` (append)

- [ ] **Step 1: Add transparency gap tests to `tests/test_ghost_profile_enrichments.py`**

Append:

```python
# ── calculate_transparency_gap ────────────────────────────────────────────────

def test_empty_official_large_behavioral_opt_out_message():
    parsed = {"ad_interests": []}
    profile = {"interest_clusters": [{"term": f"t{i}"} for i in range(10)]}
    result = calculate_transparency_gap(parsed, profile)
    interp = result["gap_interpretation"].lower()
    assert "opt-out" in interp or "privacy" in interp or "empty" in interp


def test_significant_gap_under_50_pct():
    parsed = {"ad_interests": ["sports", "news"]}
    profile = {"interest_clusters": [{"term": f"t{i}"} for i in range(10)]}
    result = calculate_transparency_gap(parsed, profile)
    assert result["official_ad_interest_count"] == 2
    assert result["behavioral_interest_count"] == 10
    interp = result["gap_interpretation"].lower()
    assert "gap" in interp or "underrepresent" in interp


def test_roughly_equal_counts():
    parsed = {"ad_interests": [f"interest{i}" for i in range(10)]}
    profile = {"interest_clusters": [{"term": f"t{i}"} for i in range(10)]}
    result = calculate_transparency_gap(parsed, profile)
    interp = result["gap_interpretation"].lower()
    assert "match" in interp or "roughly" in interp


def test_output_keys_present():
    result = calculate_transparency_gap({"ad_interests": []}, {"interest_clusters": []})
    assert "official_ad_interest_count" in result
    assert "behavioral_interest_count" in result
    assert "gap_interpretation" in result
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_ghost_profile_enrichments.py -k "opt_out or significant_gap or roughly_equal or output_keys" -v 2>&1 | head -20
```

Expected: ImportError — `calculate_transparency_gap` not defined.

- [ ] **Step 3: Add `calculate_transparency_gap` to `ghost_profile.py`**

Add after `_analyze_share_behavior`:

```python
# ---------------------------------------------------------------------------
# Task 5: Transparency Gap Calculation
# ---------------------------------------------------------------------------


def calculate_transparency_gap(parsed: dict, profile: dict) -> dict:
    """
    Compare TikTok's officially declared ad interests against the behaviorally
    inferred interest clusters, and derive a plain-language interpretation.
    """
    official = parsed.get("ad_interests", [])
    behavioral = profile.get("interest_clusters", [])

    official_count = len(official)
    behavioral_count = len(behavioral)

    if official_count == 0 and behavioral_count > 5:
        interpretation = (
            "Ad interests empty — likely privacy opt-out or region restriction — "
            "but behavioral profile shows strong inferred interests TikTok uses "
            "regardless of official categorization."
        )
    elif official_count > 0 and official_count < behavioral_count * 0.5:
        pct_diff = round((1 - official_count / behavioral_count) * 100)
        interpretation = (
            f"Significant gap: TikTok's declared interests underrepresent actual "
            f"behavioral profile by approximately {pct_diff}%."
        )
    else:
        interpretation = "Official interests roughly match behavioral profile."

    return {
        "official_ad_interest_count": official_count,
        "behavioral_interest_count": behavioral_count,
        "gap_interpretation": interpretation,
    }
```

- [ ] **Step 4: Wire `calculate_transparency_gap` into `build_ghost_profile`**

After the share_behavior block, add:

```python
    # ── Task 5: Transparency Gap ──────────────────────────────────────────
    transparency_gap = calculate_transparency_gap(
        parsed,
        {"interest_clusters": interest_clusters},
    )
```

Add to return dict:
```python
        "transparency_gap": transparency_gap,
```

- [ ] **Step 5: Run all enrichment tests**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_ghost_profile_enrichments.py -v
```

Expected: all tests PASS (footprint + comment voice + share behavior + transparency gap).

- [ ] **Step 6: Commit**

```bash
git add ghost_profile.py tests/test_ghost_profile_enrichments.py
git commit -m "feat: transparency gap calculation comparing declared vs behavioral interests"
```

---

## Task 7: LLM Export Endpoint

**Files:**
- Create: `exporters/__init__.py`
- Create: `exporters/llm_export.py`
- Modify: `api/main.py`
- Test: `tests/test_llm_export.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm_export.py`:

```python
import json
import pytest
from exporters.llm_export import generate_llm_export


def _base_ghost() -> dict:
    return {
        "interest_clusters": [{"term": "sports", "count": 5, "dominant_source": "search"}],
        "comment_voice": {"engagement_style_label": "Lurker", "top_20_longest": []},
        "share_behavior": {"share_behavior_type": "Mixed Sharer", "total_shares": 0},
        "transparency_gap": {"gap_interpretation": "roughly match"},
        "behavioral_nodes": {"skip_rate_percentage": 20.0},
        "digital_footprint": {
            "ip_locations": ["1.2.3.4"],
            "recent_logins": [{"ip": "1.2.3.4", "date": "2024-01-01"}],
            "unique_devices": ["iPhone"],
        },
        "stopwatch_metrics": {"total_conscious_videos": 1000},
    }


def _base_parsed() -> dict:
    return {
        "browsing_history": [{"link": "https://www.tiktok.com/@user/video/1", "date": "2024-01-01"}],
        "watch_history_full": [{"link": "https://www.tiktok.com/@user/video/1", "date": "2024-01-01"}],
        "watch_history_active": [],
        "login_history": [{"ip": "1.2.3.4", "date": "2024-01-01", "device_model": "iPhone"}],
        "behavioral_analysis": {
            "skip_rate": 20.0,
            "linger_rate": 15.0,
            "passive_videos_removed": 50,
            "session_count": 10,
        },
        "ad_interests": ["sports"],
    }


def test_ip_addresses_excluded():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    result_str = json.dumps(result)
    assert "1.2.3.4" not in result_str


def test_watch_history_urls_excluded():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    result_str = json.dumps(result)
    assert "tiktok.com" not in result_str


def test_login_history_excluded():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    result_str = json.dumps(result)
    assert "login_history" not in result_str


def test_meta_block_present():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    assert "_meta" in result
    assert "instructions_for_llm" in result["_meta"]
    assert "suggested_opening" in result["_meta"]
    assert "followup_prompts" in result["_meta"]
    assert "generated_at" in result["_meta"]
    assert "privacy_note" in result["_meta"]


def test_behavioral_summary_included():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    assert "behavioral_summary" in result
    assert "skip_rate" in result["behavioral_summary"]


def test_interest_clusters_included():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    assert "profile" in result
    assert "interest_clusters" in result["profile"]


def test_followup_prompts_is_list():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    assert isinstance(result["_meta"]["followup_prompts"], list)
    assert len(result["_meta"]["followup_prompts"]) >= 3
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_llm_export.py -v 2>&1 | head -20
```

Expected: ModuleNotFoundError — `exporters` package not found.

- [ ] **Step 3: Create `exporters/__init__.py`**

```bash
mkdir -p /Users/danweiman/TikTokAnalyzer/exporters
touch /Users/danweiman/TikTokAnalyzer/exporters/__init__.py
```

- [ ] **Step 4: Create `exporters/llm_export.py`**

```python
"""
LLM Export Generator — produces a privacy-safe JSON payload for upload to
Claude.ai or Gemini for narrative synthesis.

Excluded: watch history URLs, login history (IPs), raw link lists, DM content.
Included: all behavioral metrics, interest clusters, comment voice, share
          behavior, transparency gap, and LLM instructions.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone


_INSTRUCTIONS_FOR_LLM = (
    "You are analyzing a behavioral profile derived from a user's TikTok data "
    "export. This data represents inferences made by the SYS.TEARDOWN forensic "
    "analyzer — it shows what TikTok's algorithm likely knows about this person "
    "based on their usage patterns, not what they explicitly told the platform.\n\n"
    "Your job: narrate this profile back to the user in plain language. Cover:\n"
    "(1) What kind of user TikTok thinks they are\n"
    "(2) Which vibe vectors are being most actively exploited and how\n"
    "(3) What the transparency gap reveals about platform behavior\n"
    "(4) What their engagement style says about them vs. how the algorithm sees them\n"
    "(5) What content and ad categories they're likely being served as a result\n\n"
    "Be specific and direct. Reference the actual numbers. Do not be alarmist but "
    "do not soften what the data shows. The user has chosen to understand this — "
    "treat them as an intelligent adult working through something real.\n\n"
    "If comment samples are included, use them to characterise HOW the user "
    "engages — their voice, their analytical style, their cultural references — "
    "and note where this diverges from the algorithmic profile."
)

_PII_KEYS = frozenset({
    "ip", "email", "phone",
    "watch_history_full", "watch_history_active", "browsing_history",
    "login_history", "ip_locations", "recent_logins",
    "enrichment_targets",
})

_BEHAVIORAL_SUMMARY_EXCLUDE = frozenset({"top_linger_links", "top_skip_links"})


def _strip_pii(obj: object) -> object:
    """Recursively remove PII-bearing keys from dicts and lists."""
    if isinstance(obj, dict):
        return {k: _strip_pii(v) for k, v in obj.items() if k not in _PII_KEYS}
    if isinstance(obj, list):
        return [_strip_pii(item) for item in obj]
    return obj


def generate_llm_export(parsed: dict, ghost_profile: dict) -> dict:
    """
    Build a privacy-safe export dict suitable for pasting into an LLM chat.

    Args:
        parsed: Output of parse_tiktok_export_from_bytes / parse_tiktok_export.
        ghost_profile: Output of build_ghost_profile.

    Returns:
        Dict with _meta, behavioral_summary, and profile blocks.
        No watch URLs, IPs, or login records.
    """
    profile_clean = _strip_pii(copy.deepcopy(ghost_profile))

    behavioral_summary = {
        k: v
        for k, v in parsed.get("behavioral_analysis", {}).items()
        if k not in _BEHAVIORAL_SUMMARY_EXCLUDE
    }

    return {
        "_meta": {
            "privacy_note": (
                "No watch history URLs, IP addresses, login records, or personal "
                "identifiers are included in this export."
            ),
            "tool_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "instructions_for_llm": _INSTRUCTIONS_FOR_LLM,
            "suggested_opening": (
                "Here is my TikTok behavioral profile generated by SYS.TEARDOWN. "
                "Please narrate this back to me — what kind of user does TikTok "
                "think I am, which manipulation levers are being used on me, and "
                "what does the transparency gap reveal?"
            ),
            "followup_prompts": [
                "Which vibe vector is being most actively exploited and how?",
                "What does my comment voice reveal that the algorithm doesn't capture?",
                "What content am I likely being served that I'm not aware of?",
                "What does the transparency gap tell you about how TikTok treats my data?",
            ],
        },
        "behavioral_summary": behavioral_summary,
        "profile": profile_clean,
    }
```

- [ ] **Step 5: Run LLM export tests**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/test_llm_export.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Add `POST /api/export/llm` to `api/main.py`**

Add `Response` to the existing FastAPI imports line:
```python
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Response
```

Add the import near the top of `api/main.py` with the other local imports:
```python
from exporters.llm_export import generate_llm_export
```

Add the endpoint after the existing `/api/enrich` route:

```python
@app.post("/api/export/llm")
async def export_llm(file: UploadFile = File(...)):
    """
    Parse a TikTok export and return a privacy-safe LLM analysis JSON.
    Suitable for uploading directly to Claude.ai or Gemini.
    """
    import json
    from datetime import date as _date

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

    filename = f"tiktok_analysis_{_date.today().isoformat()}.json"
    content = json.dumps(payload, indent=2, ensure_ascii=False)

    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 7: Smoke-test the endpoint**

In a separate terminal, start the API:
```bash
cd /Users/danweiman/TikTokAnalyzer && uvicorn api.main:app --port 8005 --reload
```

In another terminal (or use curl if available):
```bash
# If a real export is available:
curl -s -X POST http://localhost:8005/api/export/llm \
  -F "file=@path/to/user_data_tiktok.json" \
  -o /tmp/export_test.json && \
  python -c "
import json
with open('/tmp/export_test.json') as f:
    d = json.load(f)
print('_meta keys:', list(d.get('_meta', {}).keys()))
print('ip in export:', '1.2' in json.dumps(d))
print('tiktok.com in export:', 'tiktok.com' in json.dumps(d))
print('interest_clusters count:', len(d.get('profile', {}).get('interest_clusters', [])))
"
```

Expected: `_meta` keys present, no IP addresses, no `tiktok.com` URLs in output.

- [ ] **Step 8: Run the full test suite**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests pass across all test files.

- [ ] **Step 9: Commit**

```bash
git add exporters/__init__.py exporters/llm_export.py api/main.py tests/test_llm_export.py
git commit -m "feat: LLM export endpoint — privacy-safe JSON for Claude.ai/Gemini upload"
```

---

## Final Verification

- [ ] **Run full suite one more time**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -m pytest tests/ -v
```

Expected: all tests pass with no warnings about missing fields or import errors.

- [ ] **Verify backward compatibility**

```bash
cd /Users/danweiman/TikTokAnalyzer && python -c "
from parsers.tiktok import parse_tiktok_export
import glob
files = glob.glob('**/user_data_tiktok.json', recursive=True)
if not files:
    print('No export found — skip')
else:
    from ghost_profile import build_ghost_profile
    parsed = parse_tiktok_export(files[0])
    gp = build_ghost_profile(parsed)
    # All pre-existing keys must still be present
    for key in ('status', 'stopwatch_metrics', 'behavioral_nodes', 'creator_entities',
                'academic_insights', 'night_shift', 'digital_footprint', 'search_rhythm',
                'discrepancy_gap', '_evidence', 'enrichment_targets', 'deep_dives',
                'declared_signals', 'ad_profile'):
        assert key in gp, f'MISSING KEY: {key}'
    # New keys must now be present
    for key in ('interest_clusters', 'comment_voice', 'share_behavior', 'transparency_gap'):
        assert key in gp, f'NEW KEY MISSING: {key}'
    print('All keys present. Backward compat: OK')
    print('interest_clusters:', gp['interest_clusters'][:3])
    print('comment_voice label:', gp['comment_voice']['engagement_style_label'])
    print('share_behavior type:', gp['share_behavior']['share_behavior_type'])
    print('transparency_gap:', gp['transparency_gap']['gap_interpretation'][:80])
"
```
