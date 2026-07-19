import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    from utils import topic_engine
    async def fake_cluster_topics(videos, api_key, provider, prompt_version=topic_engine.PROMPT_VERSION):
        return {"source": "llm", "clusters": [{"name": "Fitness", "video_ids": ["1"],
                "taxonomy_hint": "Fitness & Workout", "confidence": 0.7, "evidence_kind": "video"}],
                "prompt_version": prompt_version, "cached": False,
                "usage": {"input_tokens": 10, "output_tokens": 20}}
    monkeypatch.setattr(topic_engine, "cluster_topics", fake_cluster_topics)
    from api.main import app
    return TestClient(app)


def test_topics_endpoint_returns_clusters(client):
    resp = client.post("/api/topics?provider=claude",
                       json={"videos": [{"video_id": "1", "weight": 3.0}]},
                       headers={"X-API-Key": "sk-test"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "llm"
    assert body["clusters"][0]["name"] == "Fitness"


def test_topics_endpoint_surfaces_llm_error_as_502(monkeypatch):
    from utils import topic_engine
    async def boom(videos, api_key, provider, prompt_version=topic_engine.PROMPT_VERSION):
        raise ValueError("bad key")
    monkeypatch.setattr(topic_engine, "cluster_topics", boom)
    from api.main import app
    resp = TestClient(app).post("/api/topics?provider=claude",
                                json={"videos": [{"video_id": "1", "weight": 1.0}]},
                                headers={"X-API-Key": "x"})
    assert resp.status_code == 502
