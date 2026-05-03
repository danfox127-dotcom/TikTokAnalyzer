import pytest
from ghost_profile import _detect_atomic_traits, _synthesize_sub_archetypes, _detect_cognitive_dissonance

@pytest.fixture
def base_sw():
    return {
        "max_session_duration": 1000,
        "max_consecutive_skips": 2,
        "night_count": 10,
        "night_lingers": 1,
        "total_conscious_videos": 100
    }

@pytest.fixture
def base_bn():
    return {
        "social_graph_followed_pct": 50,
        "social_graph_algorithmic_pct": 50,
        "linger_rate_percentage": 15,
        "night_shift_ratio": 10
    }

@pytest.fixture
def base_parsed():
    return {
        "shares": [{} for _ in range(5)],
        "likes": [{} for _ in range(20)],
        "comments": [{} for _ in range(5)],
        "following": [{} for _ in range(50)]
    }

@pytest.fixture
def base_vibe():
    return [
        {"handle": "@user1", "linger_count": 10, "genre": "humor"},
        {"handle": "@user2", "linger_count": 5, "genre": "unknown"}
    ]

def test_detect_atomic_traits_trapped(base_sw, base_parsed, base_vibe):
    # Test trapped via session duration
    sw = base_sw.copy()
    sw["max_session_duration"] = 4000 # > 3600
    traits = _detect_atomic_traits(sw, 100, base_parsed, 15, 10, base_vibe)
    assert traits["trapped"] is True

    # Test trapped via linger rate
    sw = base_sw.copy()
    traits = _detect_atomic_traits(sw, 100, base_parsed, 35, 10, base_vibe) # > 30%
    assert traits["trapped"] is True

def test_detect_atomic_traits_ruthless(base_sw, base_parsed, base_vibe):
    sw = base_sw.copy()
    sw["max_consecutive_skips"] = 10
    traits = _detect_atomic_traits(sw, 100, base_parsed, 15, 10, base_vibe)
    assert traits["ruthless"] is True

def test_detect_atomic_traits_ghost(base_sw, base_parsed, base_vibe):
    # actions = 5 shares + 20 likes + 5 comments = 30
    # 30 / 100 = 0.3 (30%) -> not a ghost
    traits = _detect_atomic_traits(base_sw, 100, base_parsed, 15, 10, base_vibe)
    assert traits["ghost"] is False

    # actions = 0
    parsed = {"shares": [], "likes": [], "comments": []}
    traits = _detect_atomic_traits(base_sw, 100, parsed, 15, 10, base_vibe)
    assert traits["ghost"] is True

def test_synthesize_sub_archetypes_intentional_curator(base_bn):
    traits = {"curator": True}
    bn = base_bn.copy()
    bn["social_graph_followed_pct"] = 70 # > 60
    subs = _synthesize_sub_archetypes(traits, bn)
    assert any(s["name"] == "The Intentional Curator" for s in subs)

def test_detect_cognitive_dissonance_circadian_drift(base_sw, base_bn, base_parsed, base_vibe):
    traits = {"ruthless": True}
    sw = base_sw.copy()
    sw["night_count"] = 10
    sw["night_lingers"] = 4 # 40% > 30% -> night_trapped
    diss = _detect_cognitive_dissonance(traits, sw, base_bn, base_parsed, base_vibe)
    assert diss["detected"] is True
    assert diss["label"] == "Circadian Drift"

def test_detect_cognitive_dissonance_social_paradox(base_sw, base_bn, base_parsed, base_vibe):
    traits = {}
    bn = base_bn.copy()
    bn["social_graph_algorithmic_pct"] = 95 # > 90
    parsed = base_parsed.copy()
    parsed["following"] = [{} for _ in range(150)] # > 100
    diss = _detect_cognitive_dissonance(traits, base_sw, bn, parsed, base_vibe)
    assert diss["detected"] is True
    assert diss["label"] == "Social Paradox"
