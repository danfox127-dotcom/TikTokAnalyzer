import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "online", "service": "algorithmic-forensics-api"}

def test_analyze_empty_file():
    # Upload an empty file to /api/analyze
    response = client.post(
        "/api/analyze",
        files={"file": ("empty.json", b"")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_analyze_valid_file():
    # Upload a fake valid tiktok export payload
    fake_export = {
        "Activity": {
            "Video Browsing History": {
                "VideoList": [
                    {"Date": "2023-10-01 10:00:00", "VideoLink": "https://www.tiktok.com/@user1/video/12345"}
                ]
            }
        }
    }
    response = client.post(
        "/api/analyze",
        files={"file": ("user_data_tiktok.json", json.dumps(fake_export).encode("utf-8"))}
    )
    assert response.status_code == 200
    data = response.json()
    assert "enrichment_targets" in data
    assert "lingered" in data["enrichment_targets"]

@patch("api.main.oembed.fetch_many")
def test_enrich_endpoint(mock_fetch_many):
    # Mock the return value of fetch_many.
    # Note: Because fetch_many is an async function, we need to mock it returning a coroutine or use AsyncMock properly.
    # Since we use patch directly, let's just make it return what we want.
    async def mock_fetch(*args, **kwargs):
        return [
            {
                "video_id": "12345",
                "status": "ok",
                "data": {
                    "title": "A fun video #party",
                    "author": "user1",
                    "author_name": "User One",
                    "thumbnail": "http://example.com/thumb.jpg"
                },
                "error": None
            }
        ]
    mock_fetch_many.side_effect = mock_fetch

    payload = {
        "lingered": [{"video_id": "12345", "Date": "2023-10-01 10:00:00"}],
        "graveyard": [],
        "sandbox": [],
        "night_lingered": [],
        "following_usernames": ["user1"]
    }
    
    response = client.post("/api/enrich", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # Check that the video data was enriched
    assert len(data["videos"]["lingered"]) == 1
    video = data["videos"]["lingered"][0]
    assert video["title"] == "A fun video #party"
    assert video["author"] == "user1"
    
    # Check video_results
    assert "video_results" in data
    assert data["video_results"]["12345"]["status"] == "ok"
    
    # Check themes and top_creators
    assert "themes" in data
    assert "top_creators" in data
    assert "lingered" in data["top_creators"]
    assert len(data["top_creators"]["lingered"]) > 0
    assert data["top_creators"]["lingered"][0]["author"] == "user1"
    
    assert "cache_metrics" in data

def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    text = response.text
    assert "algorithmic_enrich_requests_total" in text
