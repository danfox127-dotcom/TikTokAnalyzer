from utils import topic_engine


def test_cache_key_is_stable_and_order_independent():
    a = [{"video_id": "1", "weight": 2.0}, {"video_id": "2", "weight": 1.0}]
    b = [{"video_id": "2", "weight": 1.0}, {"video_id": "1", "weight": 2.0}]
    assert topic_engine.cache_key(a, "topics-v1") == topic_engine.cache_key(b, "topics-v1")
    # weight change → different key
    c = [{"video_id": "1", "weight": 9.0}, {"video_id": "2", "weight": 1.0}]
    assert topic_engine.cache_key(a, "topics-v1") != topic_engine.cache_key(c, "topics-v1")
    # prompt version is part of the key
    assert topic_engine.cache_key(a, "topics-v1") != topic_engine.cache_key(a, "topics-v2")


def test_taxonomy_names_loads_716_category_names():
    names = topic_engine.taxonomy_names()
    assert len(names) == 716
    assert "Education" in names


def test_validate_drops_hallucinated_ids_and_normalizes():
    raw = [
        {"name": "Gym", "video_ids": ["1", "999"], "taxonomy_hint": "Fitness"},  # 999 not in input
        {"name": "", "video_ids": ["2"]},                                        # empty name dropped
        {"name": "Cooking", "video_ids": ["2"]},                                 # no taxonomy_hint → null
    ]
    out = topic_engine.validate_clusters(raw, {"1", "2"})
    assert [c["name"] for c in out] == ["Gym", "Cooking"]
    assert out[0]["video_ids"] == ["1"]          # 999 dropped (traceability)
    assert out[0]["taxonomy_hint"] == "Fitness"
    assert out[0]["confidence"] == 0.7
    assert out[0]["evidence_kind"] == "video"
    assert out[1]["taxonomy_hint"] is None


def test_validate_rejects_non_list():
    import pytest
    with pytest.raises(ValueError):
        topic_engine.validate_clusters({"not": "a list"}, {"1"})
