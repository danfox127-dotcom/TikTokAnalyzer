import asyncio
import pytest
from utils import topic_engine


@pytest.fixture
def _mocks(monkeypatch):
    # oEmbed: id -> title
    async def fake_fetch_many(video_ids, concurrency=8):
        titles = {"1": "gym leg day", "2": "pasta recipe"}
        return [{"video_id": v, "status": "ok", "data": {"title": titles.get(v, "")}} for v in video_ids]
    monkeypatch.setattr(topic_engine.oembed, "fetch_many", fake_fetch_many)

    calls = {"n": 0}
    async def fake_call_llm(prompt, api_key, provider):
        calls["n"] += 1
        raw = '[{"name":"Fitness","video_ids":["1"],"taxonomy_hint":"Fitness & Workout"},' \
              '{"name":"Cooking","video_ids":["2"],"taxonomy_hint":"Food & Drink"}]'
        return raw, {"input_tokens": 10, "output_tokens": 20}
    monkeypatch.setattr(topic_engine, "_call_llm", fake_call_llm)
    # force in-memory cache
    monkeypatch.setattr(topic_engine.creator_map, "_redis", None)
    topic_engine.creator_map._local.clear()
    return calls


def test_cluster_topics_returns_validated_result(_mocks):
    videos = [{"video_id": "1", "weight": 3.0}, {"video_id": "2", "weight": 1.0}]
    res = asyncio.run(topic_engine.cluster_topics(videos, "sk-test", "claude"))
    assert res["source"] == "llm" and res["cached"] is False
    assert {c["name"] for c in res["clusters"]} == {"Fitness", "Cooking"}
    assert res["usage"] == {"input_tokens": 10, "output_tokens": 20}


def test_cluster_topics_cache_hit_skips_llm(_mocks):
    videos = [{"video_id": "1", "weight": 3.0}, {"video_id": "2", "weight": 1.0}]
    asyncio.run(topic_engine.cluster_topics(videos, "sk-test", "claude"))
    res2 = asyncio.run(topic_engine.cluster_topics(videos, "sk-test", "claude"))
    assert res2["cached"] is True
    assert _mocks["n"] == 1  # LLM called once, second run served from cache


def test_cluster_topics_retries_once_then_raises(monkeypatch):
    async def fake_fetch_many(video_ids, concurrency=8):
        return [{"video_id": v, "status": "ok", "data": {"title": "x"}} for v in video_ids]
    monkeypatch.setattr(topic_engine.oembed, "fetch_many", fake_fetch_many)
    monkeypatch.setattr(topic_engine.creator_map, "_redis", None)
    topic_engine.creator_map._local.clear()
    n = {"n": 0}
    async def bad_llm(prompt, api_key, provider):
        n["n"] += 1
        return "not json", {"input_tokens": 1, "output_tokens": 1}
    monkeypatch.setattr(topic_engine, "_call_llm", bad_llm)
    with pytest.raises(ValueError):
        asyncio.run(topic_engine.cluster_topics([{"video_id": "1", "weight": 1.0}], "k", "claude"))
    assert n["n"] == 2  # one retry


def test_cluster_topics_empty_titles_returns_empty(monkeypatch):
    async def no_titles(video_ids, concurrency=8):
        return [{"video_id": v, "status": "failed", "data": {"title": ""}} for v in video_ids]
    monkeypatch.setattr(topic_engine.oembed, "fetch_many", no_titles)
    monkeypatch.setattr(topic_engine.creator_map, "_redis", None)
    topic_engine.creator_map._local.clear()
    res = asyncio.run(topic_engine.cluster_topics([{"video_id": "1", "weight": 1.0}], "k", "claude"))
    assert res["clusters"] == [] and res["source"] == "llm"


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


def test_build_prompt_carries_real_video_ids():
    # Regression for WP-2.1 final review finding: the prompt used to drop the
    # video_id entirely, so the LLM could never echo back a real id and
    # validate_clusters would always filter video_ids down to [].
    prompt = topic_engine._build_prompt([("111", "gym leg day", 3.0), ("222", "pasta", 1.0)])
    assert "111" in prompt
    assert "222" in prompt
    assert "gym leg day" in prompt
    assert "pasta" in prompt


def test_cluster_topics_round_trips_real_large_ids(monkeypatch):
    # Uses realistic large numeric TikTok ids (not the toy "1"/"2" ids used
    # elsewhere) to prove video_ids survive prompt -> LLM -> validate_clusters
    # without being masked by a mock that fabricates matching ids.
    real_ids = ["7311111111111111111", "7322222222222222222"]

    async def fake_fetch_many(video_ids, concurrency=8):
        titles = {real_ids[0]: "gym leg day", real_ids[1]: "pasta recipe"}
        return [{"video_id": v, "status": "ok", "data": {"title": titles.get(v, "")}} for v in video_ids]
    monkeypatch.setattr(topic_engine.oembed, "fetch_many", fake_fetch_many)
    monkeypatch.setattr(topic_engine.creator_map, "_redis", None)
    topic_engine.creator_map._local.clear()

    captured_prompt = {}

    async def fake_call_llm(prompt, api_key, provider):
        captured_prompt["text"] = prompt
        # Simulate a real LLM echoing back the ids it actually saw in the prompt.
        assert real_ids[0] in prompt and real_ids[1] in prompt
        raw = (
            '[{"name":"Fitness","video_ids":["%s"],"taxonomy_hint":"Fitness & Workout"}]'
            % real_ids[0]
        )
        return raw, {"input_tokens": 10, "output_tokens": 20}
    monkeypatch.setattr(topic_engine, "_call_llm", fake_call_llm)

    videos = [{"video_id": real_ids[0], "weight": 3.0}, {"video_id": real_ids[1], "weight": 1.0}]
    res = asyncio.run(topic_engine.cluster_topics(videos, "sk-test", "claude"))
    assert res["clusters"][0]["video_ids"] == [real_ids[0]]
    assert res["clusters"][0]["video_ids"] != []
