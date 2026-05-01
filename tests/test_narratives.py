# tests/test_narratives.py
"""Unit tests for narrative block builders."""
import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _base_ghost() -> dict:
    """Minimal ghost_profile dict covering all blocks."""
    return {
        "behavioral_nodes": {
            "peak_hour": "14",
            "skip_rate_percentage": 30.0,
            "linger_rate_percentage": 15.0,
            "night_shift_ratio": 10.0,
            "night_linger_pct": 8.0,
            "social_graph_followed_pct": 45.0,
            "social_graph_algorithmic_pct": 55.0,
        },
        "stopwatch_metrics": {
            "total_conscious_videos": 500,
            "deep_lingers": 50,
            "deep_dives": 25,
            "graveyard_skips": 150,
            "hourly_heatmap": {str(h): (5 if h == 14 else 1) for h in range(24)},
        },
        "creator_entities": {
            "vibe_cluster": [
                {"handle": "@creator1", "linger_count": 30},
                {"handle": "@creator2", "linger_count": 20},
                {"handle": "@creator3", "linger_count": 10},
            ],
            "graveyard": [],
        },
        "comment_voice": {
            "total_comments": 42,
            "avg_length_chars": 85.0,
            "long_comments_count": 4,
            "long_comment_pct": 9.5,
            "emoji_density": 0.02,
            "engagement_style_label": "Community Participant",
        },
        "share_behavior": {
            "total_shares": 15,
            "share_methods": {"chat": 10, "instagram": 5},
            "share_behavior_type": "Private Curator",
            "primary_share_method": "chat",
            "dm_share_count": 10,
        },
        "transparency_gap": {
            "official_ad_interest_count": 8,
            "behavioral_interest_count": 12,
            "gap_interpretation": "Official interests roughly match behavioral profile.",
        },
        "digital_footprint": {
            "login_count": 25,
            "unique_ips": 3,
            "unique_devices": ["iPhone 14", "MacBook Pro"],
            "recent_logins": [
                {"date": "2024-03-01", "ip": "1.2.3.4", "city": "Paris", "country_name": "France"},
                {"date": "2024-02-01", "ip": "1.2.3.4", "city": "Paris", "country_name": "France"},
            ],
        },
        "declared_signals": {
            "following_count": 120,
            "ad_interests": ["Technology", "Sports"],
            "recent_searches": ["python", "cooking"],
        },
        "search_rhythm": {"total_searches": 200},
        "academic_insights": {"echo_chamber_index_pct": 55.0},
    }


def _base_parsed() -> dict:
    return {
        "likes": [{}] * 80,
        "comments": [{}] * 42,
        "shares": [{}] * 15,
        "following": [{}] * 120,
    }


# ── Block schema helper ───────────────────────────────────────────────────────

def _assert_block_schema(block: dict, expected_id: str):
    assert block["id"] == expected_id
    assert isinstance(block["title"], str) and block["title"]
    assert isinstance(block["icon"], str) and block["icon"]
    assert isinstance(block["prose"], str) and len(block["prose"]) > 20
    assert isinstance(block["accent"], str) and block["accent"].startswith("#")
    assert isinstance(block["stats"], list)
    # chart is either None or has type + data
    if block["chart"] is not None:
        assert block["chart"]["type"] in ("bar", "donut", "line")
        assert isinstance(block["chart"]["data"], list)


# ── Block 1: Algorithmic Identity ─────────────────────────────────────────────

def test_algorithmic_identity_schema():
    from api.narratives import _build_algorithmic_identity_block
    block = _build_algorithmic_identity_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "algorithmic_identity")


def test_algorithmic_identity_high_followed():
    from api.narratives import _build_algorithmic_identity_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["social_graph_followed_pct"] = 75.0
    ghost["behavioral_nodes"]["social_graph_algorithmic_pct"] = 25.0
    block = _build_algorithmic_identity_block(ghost, _base_parsed())
    assert "follow" in block["prose"].lower() or "intentional" in block["prose"].lower()


def test_algorithmic_identity_low_followed():
    from api.narratives import _build_algorithmic_identity_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["social_graph_followed_pct"] = 10.0
    ghost["behavioral_nodes"]["social_graph_algorithmic_pct"] = 90.0
    block = _build_algorithmic_identity_block(ghost, _base_parsed())
    assert "algorithm" in block["prose"].lower()


def test_algorithmic_identity_no_vibe_cluster():
    from api.narratives import _build_algorithmic_identity_block
    ghost = _base_ghost()
    ghost["creator_entities"]["vibe_cluster"] = []
    block = _build_algorithmic_identity_block(ghost, _base_parsed())
    assert block["chart"] is None or block["chart"]["data"] == []


# ── Block 2: Attention Signature ──────────────────────────────────────────────

def test_attention_signature_schema():
    from api.narratives import _build_attention_signature_block
    block = _build_attention_signature_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "attention_signature")
    assert block["chart"] is not None
    assert block["chart"]["type"] == "bar"


def test_attention_signature_high_linger():
    from api.narratives import _build_attention_signature_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["linger_rate_percentage"] = 35.0
    block = _build_attention_signature_block(ghost, _base_parsed())
    assert "deep" in block["prose"].lower() or "extended" in block["prose"].lower()


def test_attention_signature_high_skip():
    from api.narratives import _build_attention_signature_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["skip_rate_percentage"] = 65.0
    ghost["behavioral_nodes"]["linger_rate_percentage"] = 5.0
    block = _build_attention_signature_block(ghost, _base_parsed())
    assert "skip" in block["prose"].lower() or "curator" in block["prose"].lower()


# ── Block 3: Daily Rhythm ──────────────────────────────────────────────────────

def test_daily_rhythm_schema():
    from api.narratives import _build_daily_rhythm_block
    block = _build_daily_rhythm_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "dayparting")
    assert block["chart"] is not None
    assert block["chart"]["type"] == "bar"
    assert len(block["chart"]["data"]) == 24


def test_daily_rhythm_night_owl():
    from api.narratives import _build_daily_rhythm_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["night_shift_ratio"] = 40.0
    block = _build_daily_rhythm_block(ghost, _base_parsed())
    assert "night" in block["prose"].lower()


def test_daily_rhythm_peak_hour_in_stats():
    from api.narratives import _build_daily_rhythm_block
    block = _build_daily_rhythm_block(_base_ghost(), _base_parsed())
    labels = [s["label"] for s in block["stats"]]
    assert "Peak Hour" in labels


# ── build_narrative_blocks smoke test ────────────────────────────────────────

def test_build_narrative_blocks_returns_9():
    from api.narratives import build_narrative_blocks
    blocks = build_narrative_blocks(_base_ghost(), _base_parsed())
    assert len(blocks) == 9


def test_build_narrative_blocks_correct_ids():
    from api.narratives import build_narrative_blocks
    blocks = build_narrative_blocks(_base_ghost(), _base_parsed())
    ids = [b["id"] for b in blocks]
    assert ids[0] == "algorithmic_identity"
    assert ids[1] == "attention_signature"
    assert ids[2] == "dayparting"

# ── Block 4: Social Graph ─────────────────────────────────────────────────────

def test_social_graph_schema():
    from api.narratives import _build_social_graph_block
    block = _build_social_graph_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "social_graph")
    assert block["chart"] is not None
    assert block["chart"]["type"] == "bar"


def test_social_graph_high_followed():
    from api.narratives import _build_social_graph_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["social_graph_followed_pct"] = 80.0
    block = _build_social_graph_block(ghost, _base_parsed())
    assert "follow" in block["prose"].lower()


def test_social_graph_low_followed():
    from api.narratives import _build_social_graph_block
    ghost = _base_ghost()
    ghost["behavioral_nodes"]["social_graph_followed_pct"] = 10.0
    block = _build_social_graph_block(ghost, _base_parsed())
    assert "algorithm" in block["prose"].lower()


# ── Block 5: Share Behavior ───────────────────────────────────────────────────

def test_share_behavior_schema():
    from api.narratives import _build_share_behavior_block
    block = _build_share_behavior_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "share_behavior")


def test_share_behavior_no_shares():
    from api.narratives import _build_share_behavior_block
    ghost = _base_ghost()
    ghost["share_behavior"]["total_shares"] = 0
    ghost["share_behavior"]["share_methods"] = {}
    block = _build_share_behavior_block(ghost, _base_parsed())
    assert block["chart"] is None
    assert "silent" in block["prose"].lower() or "no content" in block["prose"].lower() or "no share" in block["prose"].lower() or "no comm" in block["prose"].lower()


def test_share_behavior_private_curator():
    from api.narratives import _build_share_behavior_block
    ghost = _base_ghost()
    ghost["share_behavior"]["share_behavior_type"] = "Private Curator"
    block = _build_share_behavior_block(ghost, _base_parsed())
    assert "private" in block["prose"].lower() or "curator" in block["prose"].lower()


# ── Block 6: Comment Voice ────────────────────────────────────────────────────

def test_comment_voice_schema():
    from api.narratives import _build_comment_voice_block
    block = _build_comment_voice_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "comment_voice")
    assert block["chart"] is None


def test_comment_voice_no_comments():
    from api.narratives import _build_comment_voice_block
    ghost = _base_ghost()
    ghost["comment_voice"]["total_comments"] = 0
    block = _build_comment_voice_block(ghost, _base_parsed())
    assert "silent" in block["prose"].lower() or "no comment" in block["prose"].lower() or "lurk" in block["prose"].lower()


def test_comment_voice_analytical():
    from api.narratives import _build_comment_voice_block
    ghost = _base_ghost()
    ghost["comment_voice"]["engagement_style_label"] = "Analytical Commenter"
    ghost["comment_voice"]["avg_length_chars"] = 180.0
    block = _build_comment_voice_block(ghost, _base_parsed())
    assert "analytical" in block["prose"].lower()

# ── Block 7: Transparency Gap ─────────────────────────────────────────────────

def test_transparency_gap_schema():
    from api.narratives import _build_transparency_gap_block
    block = _build_transparency_gap_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "transparency_gap")
    assert block["chart"] is not None
    assert block["chart"]["type"] == "bar"


def test_transparency_gap_empty_official():
    from api.narratives import _build_transparency_gap_block
    ghost = _base_ghost()
    ghost["transparency_gap"]["official_ad_interest_count"] = 0
    ghost["transparency_gap"]["behavioral_interest_count"] = 15
    block = _build_transparency_gap_block(ghost, _base_parsed())
    assert "empty" in block["prose"].lower() or "opt-out" in block["prose"].lower() or "no declared" in block["prose"].lower() or "privacy" in block["prose"].lower()


def test_transparency_gap_bar_has_expected_categories():
    from api.narratives import _build_transparency_gap_block
    block = _build_transparency_gap_block(_base_ghost(), _base_parsed())
    names = [d["category"] for d in block["chart"]["data"]]
    assert "Ad Interests" in names
    assert "Logins" in names


# ── Block 8: Location Trace ───────────────────────────────────────────────────

def test_location_trace_schema():
    from api.narratives import _build_location_trace_block
    block = _build_location_trace_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "location_trace")
    assert block["chart"] is None


def test_location_trace_home_city_in_stats():
    from api.narratives import _build_location_trace_block
    block = _build_location_trace_block(_base_ghost(), _base_parsed())
    labels = [s["label"] for s in block["stats"]]
    assert "Home City" in labels
    values = {s["label"]: s["value"] for s in block["stats"]}
    assert values["Home City"] == "Paris"


def test_location_trace_no_logins():
    from api.narratives import _build_location_trace_block
    ghost = _base_ghost()
    ghost["digital_footprint"]["recent_logins"] = []
    block = _build_location_trace_block(ghost, _base_parsed())
    # Should not crash; home city should be Unknown
    values = {s["label"]: s["value"] for s in block["stats"]}
    assert values.get("Home City") == "Unknown"


# ── Block 9: Closing Synthesis ────────────────────────────────────────────────

def test_closing_synthesis_schema():
    from api.narratives import _build_closing_synthesis_block
    block = _build_closing_synthesis_block(_base_ghost(), _base_parsed())
    _assert_block_schema(block, "closing_synthesis")
    assert block["chart"] is None
    assert block["stats"] == []


def test_closing_synthesis_prose_references_engagement():
    from api.narratives import _build_closing_synthesis_block
    block = _build_closing_synthesis_block(_base_ghost(), _base_parsed())
    prose_lower = block["prose"].lower()
    # Should mention something about engagement or algorithm
    assert any(word in prose_lower for word in ["algorithm", "engagement", "linger", "watch", "behavior"])


# ── Final count check ─────────────────────────────────────────────────────────

def test_build_narrative_blocks_returns_9_after_all_implemented():
    from api.narratives import build_narrative_blocks
    blocks = build_narrative_blocks(_base_ghost(), _base_parsed())
    assert len(blocks) == 9, f"Expected 9 blocks, got {len(blocks)}: {[b['id'] for b in blocks]}"
