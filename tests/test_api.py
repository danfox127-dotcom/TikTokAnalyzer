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

from unittest.mock import AsyncMock

def test_analyze_returns_narrative_blocks():
    """narrative_blocks should be present with 9 items after wiring."""
    fake_export = {
        "Activity": {
            "Video Browsing History": {
                "VideoList": [
                    {"Date": "2023-10-01 10:00:00", "VideoLink": "https://www.tiktok.com/@user1/video/12345"},
                    {"Date": "2023-10-01 10:00:03", "VideoLink": "https://www.tiktok.com/@user2/video/67890"},
                ]
            }
        }
    }
    # Mock enrich_logins_with_geo to avoid real HTTP calls
    with patch("api.main.enrich_logins_with_geo", new_callable=AsyncMock) as mock_enrich:
        mock_enrich.return_value = []  # no logins to enrich in this fixture
        response = client.post(
            "/api/analyze",
            files={"file": ("user_data_tiktok.json", json.dumps(fake_export).encode("utf-8"))}
        )
    assert response.status_code == 200
    data = response.json()
    assert "narrative_blocks" in data
    assert isinstance(data["narrative_blocks"], list)
    assert len(data["narrative_blocks"]) == 9
    # Check first block schema
    b = data["narrative_blocks"][0]
    assert b["id"] == "algorithmic_identity"
    assert "prose" in b
    assert "stats" in b
    assert "accent" in b

@patch("api.main.anthropic.AsyncAnthropic")
def test_analyze_llm_claude(mock_anthropic):
    """Verify Claude streaming response."""
    # Mock the streaming context manager and the text_stream
    class MockStream:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        @property
        def text_stream(self):
            async def gen():
                yield "Hello"
                yield " world"
            return gen()

    mock_client = mock_anthropic.return_value
    mock_client.messages.stream.return_value = MockStream()

    fake_export = {
        "Activity": {
            "Video Browsing History": {"VideoList": []}
        }
    }
    
    response = client.post(
        "/api/analyze/llm?provider=claude&api_key=test-key",
        files={"file": ("user_data_tiktok.json", json.dumps(fake_export).encode("utf-8"))}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    
    # Read chunks from stream
    chunks = [chunk for chunk in response.iter_lines()]
    assert "data: Hello" in chunks
    assert "data:  world" in chunks
    assert "data: [DONE]" in chunks

@patch("api.main.genai.GenerativeModel")
def test_analyze_llm_gemini(mock_gemini_model):
    """Verify Gemini streaming response."""
    # Mock the chunk objects
    class MockChunk:
        def __init__(self, text): self.text = text

    async def mock_gen():
        yield MockChunk("Gemini")
        yield MockChunk(" response")

    async def mock_call(*args, **kwargs):
        return mock_gen()

    mock_model = mock_gemini_model.return_value
    mock_model.generate_content_async.side_effect = mock_call

    fake_export = {
        "Activity": {
            "Video Browsing History": {"VideoList": []}
        }
    }
    
    response = client.post(
        "/api/analyze/llm?provider=gemini-pro&api_key=test-key",
        files={"file": ("user_data_tiktok.json", json.dumps(fake_export).encode("utf-8"))}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    
    chunks = [chunk for chunk in response.iter_lines()]
    assert "data: Gemini" in chunks
    assert "data:  response" in chunks
    assert "data: [DONE]" in chunks
