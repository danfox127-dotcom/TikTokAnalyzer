from utils.oembed_serialization import (
    normalize_oembed_result,
    serialize_oembed_result,
    deserialize_oembed_result,
)


def test_normalize_ok():
    raw = {
        "video_id": "123",
        "status": "ok",
        "title": "Fun Video",
        "author": "creator_handle",
        "author_name": "Creator",
        "thumbnail_url": "http://example.com/1.jpg",
    }
    norm = normalize_oembed_result(raw)
    assert norm["video_id"] == "123"
    assert norm["status"] == "ok"
    assert isinstance(norm["data"], dict)
    assert norm["data"]["title"] == "Fun Video"
    assert norm["data"]["author"] == "creator_handle"
    assert norm["data"]["author_name"] == "Creator"
    assert norm["data"]["thumbnail"] == "http://example.com/1.jpg"
    assert norm["error"] is None
    assert isinstance(norm["fetched_at"], float)
    assert norm["fetched_at"] > 0


def test_normalize_failed():
    raw = {"id": "456", "status": "failed", "error": "Network issue"}
    norm = normalize_oembed_result(raw)
    assert norm["video_id"] == "456"
    assert norm["status"] == "failed"
    assert norm["error"] == "Network issue"
    # data fields exist (defaults to empty strings)
    assert norm["data"]["title"] == ""
    assert isinstance(norm["data"]["author"], str)
    assert isinstance(norm["fetched_at"], float)


def test_serialize_deserialize_roundtrip():
    raw = {"video_id": "789", "title": "Roundtrip", "author": "A", "thumbnail": "thumb.png"}
    norm = normalize_oembed_result(raw)
    s = serialize_oembed_result(norm)
    loaded = deserialize_oembed_result(s)
    # Key fields should be preserved
    assert loaded["video_id"] == norm["video_id"]
    assert loaded["status"] == norm["status"]
    assert loaded["data"] == norm["data"]
    assert loaded["error"] == norm["error"]
    # Allow tiny float differences due to JSON formatting
    assert abs(float(loaded["fetched_at"]) - float(norm["fetched_at"])) < 1e-6
