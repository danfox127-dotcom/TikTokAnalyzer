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
    assert "jazz" in terms, f"expected 'jazz' in clusters, got {terms}"
    assert "classical" in terms, f"expected 'classical' in clusters, got {terms}"
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


def test_dm_share_weighted_higher_than_public_share():
    """DM share (weight 8) should outrank an equivalent public share (weight 4).
    Tokenizer splits on underscores, so @finance_guru → 'finance' + 'guru'."""
    parsed = _minimal_parsed(
        shares=[
            {"link": "https://www.tiktok.com/@finance_guru/video/1", "method": "dm"},
            {"link": "https://www.tiktok.com/@cooking_show/video/2", "method": "copy_link"},
        ]
    )
    result = _mine_text_footprint(parsed)
    terms = {c["term"]: c for c in result["interest_clusters"]}
    # 'finance' comes from DM share (weight 8); 'cooking' from public share (weight 4)
    assert "finance" in terms, f"expected 'finance' in {list(terms.keys())}"
    assert "cooking" in terms, f"expected 'cooking' in {list(terms.keys())}"
    assert terms["finance"]["count"] > terms["cooking"]["count"]
    assert terms["finance"]["dominant_source"] == "share_dm"
    assert terms["cooking"]["dominant_source"] == "share_public"


def test_short_url_contributes_keywords_if_segments_present():
    """A URL with meaningful path segments (not just a short code) should contribute."""
    parsed = _minimal_parsed(
        favorites=[{"link": "https://www.tiktok.com/tag/skateboarding", "date": "2024-01-01"}]
    )
    result = _mine_text_footprint(parsed)
    terms = [c["term"] for c in result["interest_clusters"]]
    assert "skateboarding" in terms


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
