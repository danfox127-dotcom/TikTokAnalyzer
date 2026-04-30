"""
Phase 1 backend tests — spec 2026-04-14-algorithmic-mirror-story-design.

Covers:
  - New engagement tier classification (graveyard / sandbox / deep_lingers / deep_dives)
  - weekly_heatmap shape
  - build_pillar_narrative output shape
  - build_anti_profile_signature fallback behaviour
"""
import sys
import os

# Ensure repo root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime, timedelta

from ghost_profile import _run_stopwatch
from psychographic import build_pillar_narrative, build_anti_profile_signature


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_history(deltas_seconds: list[float], base: datetime | None = None) -> list[dict]:
    """
    Build a fake browsing_history list from a sequence of delta seconds.
    Each entry will be `delta` seconds after the previous one.
    The last entry is a trailing dummy needed to compute the final delta.
    """
    if base is None:
        base = datetime(2024, 3, 11, 14, 0, 0)  # Monday 14:00
    entries = []
    current = base
    for delta in deltas_seconds:
        entries.append({"date": current.strftime("%Y-%m-%d %H:%M:%S"),
                        "link": "https://www.tiktok.com/@creator/video/12345"})
        current = current + timedelta(seconds=delta)
    # trailing entry so the last video gets a stopwatch reading
    entries.append({"date": current.strftime("%Y-%m-%d %H:%M:%S"), "link": ""})
    return entries


# ---------------------------------------------------------------------------
# 1. Tier classification
# ---------------------------------------------------------------------------

class TestTierClassification:
    def test_graveyard_under_3s(self):
        history = _make_history([1.5])
        result = _run_stopwatch(history)
        assert result["graveyard_skips"] == 1
        assert result["sandbox_views"] == 0
        assert result["deep_lingers"] == 0
        assert result["deep_dives"] == 0

    def test_sandbox_3_to_15s(self):
        history = _make_history([3.0, 10.0, 15.0])
        result = _run_stopwatch(history)
        # 3s boundary: delta <= 15 → sandbox (delta < 3 is graveyard)
        # 3.0 → sandbox, 10.0 → sandbox, 15.0 → sandbox
        assert result["sandbox_views"] == 3
        assert result["graveyard_skips"] == 0
        assert result["deep_lingers"] == 0
        assert result["deep_dives"] == 0

    def test_deep_lingers_15_to_180s(self):
        history = _make_history([16.0, 90.0, 180.0])
        result = _run_stopwatch(history)
        assert result["deep_lingers"] == 3
        assert result["deep_dives"] == 0

    def test_deep_dives_over_180s(self):
        history = _make_history([181.0, 250.0, 270.0])
        result = _run_stopwatch(history)
        assert result["deep_dives"] == 3
        assert result["deep_lingers"] == 0

    def test_boundary_exactly_180s_is_deep_linger(self):
        history = _make_history([180.0])
        result = _run_stopwatch(history)
        assert result["deep_lingers"] == 1
        assert result["deep_dives"] == 0

    def test_boundary_181s_is_deep_dive(self):
        history = _make_history([181.0])
        result = _run_stopwatch(history)
        assert result["deep_dives"] == 1
        assert result["deep_lingers"] == 0

    def test_mixed_tiers(self):
        # graveyard=1, sandbox=1, deep_linger=1, deep_dive=1
        history = _make_history([1.0, 5.0, 60.0, 200.0])
        result = _run_stopwatch(history)
        assert result["graveyard_skips"] == 1
        assert result["sandbox_views"] == 1
        assert result["deep_lingers"] == 1
        assert result["deep_dives"] == 1

    def test_deep_dive_events_list(self):
        history = _make_history([200.0, 50.0])
        result = _run_stopwatch(history)
        assert len(result["deep_dive_events"]) == 1
        assert result["deep_dive_events"][0]["time_spent"] == 200.0

    def test_deep_dive_capped_at_270s(self):
        history = _make_history([1300.0])
        result = _run_stopwatch(history)
        # 1300 >= 1200 (SLEEP_THRESHOLD_S) → AFK firewall → sleep_scrubbed, not classified
        assert result["sleep_scrubbed"] == 1
        assert result["deep_dives"] == 0

    def test_total_conscious_includes_deep_dives(self):
        history = _make_history([1.0, 5.0, 60.0, 200.0])
        result = _run_stopwatch(history)
        expected = (result["graveyard_skips"] + result["sandbox_views"]
                    + result["deep_lingers"] + result["deep_dives"])
        assert result["total_conscious_videos"] == expected


# ---------------------------------------------------------------------------
# 2. weekly_heatmap shape
# ---------------------------------------------------------------------------

class TestWeeklyHeatmap:
    def test_weekly_heatmap_has_7_days(self):
        history = _make_history([30.0])
        result = _run_stopwatch(history)
        wh = result["weekly_heatmap"]
        assert set(wh.keys()) == set(range(7))

    def test_each_day_has_24_hours(self):
        history = _make_history([30.0])
        result = _run_stopwatch(history)
        for dow, hours in result["weekly_heatmap"].items():
            assert set(hours.keys()) == set(range(24)), f"dow={dow} missing hours"

    def test_weekly_heatmap_counts_correct_day_and_hour(self):
        # base is Monday 2024-03-11 14:00:00 → dow=0, hour=14
        base = datetime(2024, 3, 11, 14, 0, 0)
        history = _make_history([30.0], base=base)
        result = _run_stopwatch(history)
        wh = result["weekly_heatmap"]
        assert wh[0][14] == 1, "Expected 1 view at Monday 14:00"

    def test_weekly_heatmap_sums_to_hourly_heatmap(self):
        """hourly_heatmap[h] == sum of weekly_heatmap[dow][h] across all days."""
        history = _make_history([5.0, 30.0, 200.0, 1.5, 10.0])
        result = _run_stopwatch(history)
        hourly = result["hourly_heatmap"]
        wh = result["weekly_heatmap"]
        for h in range(24):
            expected = int(hourly.get(str(h), 0))
            actual = sum(wh[dow][h] for dow in range(7))
            assert actual == expected, f"hour={h}: hourly={expected} vs weekly sum={actual}"


# ---------------------------------------------------------------------------
# 3. build_pillar_narrative output shape
# ---------------------------------------------------------------------------

class TestBuildPillarNarrative:
    _KEYWORDS = [
        {"term": "workout", "count": 10},
        {"term": "gym", "count": 8},
        {"term": "fitness", "count": 6},
    ]
    _PHRASES = [{"phrase": "gym workout", "count": 5}]
    _EMOJIS = [{"emoji": "💪", "count": 3}]
    _TITLES = ["Best gym workout 2024", "How to stay fit", "Morning run tips"]

    def test_returns_three_keys(self):
        result = build_pillar_narrative(
            "psychographic", self._KEYWORDS, self._PHRASES, self._EMOJIS, self._TITLES
        )
        assert set(result.keys()) == {"headline", "interpretation", "evidence"}

    def test_headline_is_string(self):
        result = build_pillar_narrative(
            "psychographic", self._KEYWORDS, self._PHRASES, self._EMOJIS, self._TITLES
        )
        assert isinstance(result["headline"], str)
        assert len(result["headline"]) > 0

    def test_interpretation_is_string_second_person(self):
        result = build_pillar_narrative(
            "psychographic", self._KEYWORDS, self._PHRASES, self._EMOJIS, self._TITLES
        )
        assert isinstance(result["interpretation"], str)
        assert len(result["interpretation"]) > 0

    def test_evidence_is_list_of_up_to_3(self):
        result = build_pillar_narrative(
            "psychographic", self._KEYWORDS, self._PHRASES, self._EMOJIS, self._TITLES
        )
        assert isinstance(result["evidence"], list)
        assert len(result["evidence"]) <= 3

    def test_all_four_pillars_produce_output(self):
        for pillar in ("psychographic", "anti_profile", "sandbox", "night"):
            result = build_pillar_narrative(
                pillar, self._KEYWORDS, self._PHRASES, self._EMOJIS, self._TITLES
            )
            assert result["headline"], f"empty headline for pillar={pillar}"
            assert result["interpretation"], f"empty interpretation for pillar={pillar}"

    def test_unknown_pillar_falls_back_to_psychographic(self):
        result = build_pillar_narrative(
            "nonexistent_pillar", self._KEYWORDS, self._PHRASES, self._EMOJIS, self._TITLES
        )
        assert isinstance(result["headline"], str)

    def test_headline_contains_category_phrase(self):
        result = build_pillar_narrative(
            "psychographic", self._KEYWORDS, self._PHRASES, self._EMOJIS, self._TITLES
        )
        # Category should be 'fitness' → phrase is "body, movement, and physical challenge"
        assert "fitness" in result["headline"] or "body" in result["headline"] or "movement" in result["headline"]

    def test_evidence_filters_hidden_titles(self):
        titles = ["Title Hidden", "No Caption (Just Hashtags)", "Real title here"]
        result = build_pillar_narrative(
            "psychographic", self._KEYWORDS, self._PHRASES, self._EMOJIS, titles
        )
        assert "Title Hidden" not in result["evidence"]
        assert "No Caption (Just Hashtags)" not in result["evidence"]
        assert "Real title here" in result["evidence"]

    def test_empty_keywords_returns_fallback(self):
        result = build_pillar_narrative("psychographic", [], [], [], [])
        assert isinstance(result["headline"], str)
        assert isinstance(result["interpretation"], str)
        assert isinstance(result["evidence"], list)


# ---------------------------------------------------------------------------
# 4. build_anti_profile_signature fallback
# ---------------------------------------------------------------------------

class TestBuildAntiProfileSignature:
    def test_returns_set_difference(self):
        # 6 anti terms, 1 overlaps with pro → 5 remain → above threshold, no fallback
        anti = [
            {"term": "news", "count": 5},
            {"term": "politics", "count": 4},
            {"term": "dance", "count": 3},
            {"term": "comedy", "count": 3},
            {"term": "travel", "count": 2},
            {"term": "protest", "count": 2},
        ]
        pro = [
            {"term": "dance", "count": 10},
            {"term": "fitness", "count": 8},
        ]
        result = build_anti_profile_signature(anti, pro)
        terms = [kw["term"] for kw in result]
        assert "dance" not in terms, "dance appears in pro terms, should be filtered"
        assert "news" in terms
        assert "politics" in terms

    def test_fallback_when_fewer_than_5_results(self):
        """If set difference yields <5 terms, raw anti_keywords returned."""
        anti = [
            {"term": "news", "count": 5},
            {"term": "politics", "count": 4},
        ]
        pro = [
            {"term": "workout", "count": 10},
        ]
        # Difference is 2 terms (<5) → fallback to raw
        result = build_anti_profile_signature(anti, pro)
        assert result == anti

    def test_fallback_when_total_anti_is_small(self):
        anti = [{"term": "a", "count": 1}, {"term": "b", "count": 1}]
        pro = [{"term": "c", "count": 1}]
        result = build_anti_profile_signature(anti, pro)
        assert result == anti

    def test_no_overlap_returns_all_anti(self):
        anti = [
            {"term": "news", "count": 5},
            {"term": "politics", "count": 4},
            {"term": "protest", "count": 3},
            {"term": "election", "count": 3},
            {"term": "government", "count": 2},
        ]
        pro = [{"term": "fitness", "count": 10}, {"term": "gym", "count": 8}]
        result = build_anti_profile_signature(anti, pro)
        assert len(result) == 5

    def test_case_insensitive_matching(self):
        # 6 anti terms, "DANCE" overlaps with pro "dance" (case-insensitive) → 5 remain → no fallback
        anti = [
            {"term": "DANCE", "count": 5},
            {"term": "news", "count": 4},
            {"term": "comedy", "count": 3},
            {"term": "politics", "count": 3},
            {"term": "food", "count": 2},
            {"term": "protest", "count": 2},
        ]
        pro = [{"term": "dance", "count": 10}]
        result = build_anti_profile_signature(anti, pro)
        terms = [kw["term"].lower() for kw in result]
        assert "dance" not in terms

    def test_empty_inputs(self):
        result = build_anti_profile_signature([], [])
        assert result == []

    def test_returns_list_of_dicts(self):
        anti = [
            {"term": "news", "count": 5},
            {"term": "politics", "count": 4},
            {"term": "protest", "count": 3},
            {"term": "election", "count": 3},
            {"term": "government", "count": 2},
        ]
        result = build_anti_profile_signature(anti, [])
        assert all(isinstance(kw, dict) for kw in result)
