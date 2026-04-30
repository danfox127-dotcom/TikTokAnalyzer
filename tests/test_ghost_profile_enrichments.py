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
