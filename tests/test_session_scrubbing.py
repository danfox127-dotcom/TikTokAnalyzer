from datetime import datetime, timedelta
from parsers.tiktok import _detect_sessions


def _entry(dt: datetime, link: str = "https://www.tiktok.com/@user/video/123") -> dict:
    return {"date": dt.strftime("%Y-%m-%d %H:%M:%S"), "link": link}


BASE = datetime(2024, 1, 1, 12, 0, 0)


def test_autoplay_artifact_flagged_passive():
    """Videos within 2s of the previous video are passive (autoplay artifact)."""
    history = [
        _entry(BASE),
        _entry(BASE + timedelta(seconds=1)),
        _entry(BASE + timedelta(seconds=30)),
    ]
    result = _detect_sessions(history, [], [], [])
    assert result["passive_videos_removed"] == 1
    assert result["active_video_count"] == 2


def test_zero_engagement_session_with_5_plus_videos_is_passive():
    """Sessions with 5+ videos and no engagement actions are passive."""
    history = [_entry(BASE + timedelta(minutes=i * 3)) for i in range(6)]
    result = _detect_sessions(history, [], [], [])
    assert result["passive_sessions_detected"] == 1
    assert result["active_video_count"] == 0


def test_zero_engagement_session_with_fewer_than_5_videos_not_passive():
    """Sessions with < 5 videos are NOT flagged passive even without engagement."""
    history = [_entry(BASE + timedelta(minutes=i * 3)) for i in range(4)]
    result = _detect_sessions(history, [], [], [])
    assert result["passive_sessions_detected"] == 0


def test_engaged_session_stays_active():
    """A session that has a like within its time window keeps all its videos."""
    history = [_entry(BASE + timedelta(minutes=i * 3)) for i in range(6)]
    likes = [{"date": (BASE + timedelta(minutes=9)).strftime("%Y-%m-%d %H:%M:%S")}]
    result = _detect_sessions(history, likes, [], [])
    assert result["passive_sessions_detected"] == 0
    assert result["active_video_count"] == 6


def test_session_gap_splits_sessions():
    """A gap > 30 minutes between two videos starts a new session."""
    history = [
        _entry(BASE),
        _entry(BASE + timedelta(minutes=45)),
    ]
    result = _detect_sessions(history, [], [], [])
    assert result["session_count"] == 2


def test_output_keys_present():
    history = [_entry(BASE + timedelta(minutes=i)) for i in range(3)]
    result = _detect_sessions(history, [], [], [])
    for key in (
        "watch_history_full", "watch_history_active",
        "passive_videos_removed", "passive_sessions_detected",
        "active_video_count", "session_count", "avg_session_length_videos",
    ):
        assert key in result, f"Missing key: {key}"


def test_empty_history_returns_empty_active():
    result = _detect_sessions([], [], [], [])
    assert result["watch_history_active"] == []
    assert result["passive_videos_removed"] == 0
