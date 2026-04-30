import json
import pytest
from exporters.llm_export import generate_llm_export


def _base_ghost() -> dict:
    return {
        "interest_clusters": [{"term": "sports", "count": 5, "dominant_source": "search"}],
        "comment_voice": {"engagement_style_label": "Lurker", "top_20_longest": []},
        "share_behavior": {"share_behavior_type": "Mixed Sharer", "total_shares": 0},
        "transparency_gap": {"gap_interpretation": "roughly match"},
        "behavioral_nodes": {"skip_rate_percentage": 20.0},
        "digital_footprint": {
            "ip_locations": ["1.2.3.4"],
            "recent_logins": [{"ip": "1.2.3.4", "date": "2024-01-01"}],
            "unique_devices": ["iPhone"],
        },
        "stopwatch_metrics": {"total_conscious_videos": 1000},
    }


def _base_parsed() -> dict:
    return {
        "browsing_history": [{"link": "https://www.tiktok.com/@user/video/1", "date": "2024-01-01"}],
        "watch_history_full": [{"link": "https://www.tiktok.com/@user/video/1", "date": "2024-01-01"}],
        "watch_history_active": [],
        "login_history": [{"ip": "1.2.3.4", "date": "2024-01-01", "device_model": "iPhone"}],
        "behavioral_analysis": {
            "skip_rate": 20.0,
            "linger_rate": 15.0,
            "passive_videos_removed": 50,
            "session_count": 10,
        },
        "ad_interests": ["sports"],
    }


def test_ip_addresses_excluded():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    result_str = json.dumps(result)
    assert "1.2.3.4" not in result_str


def test_watch_history_urls_excluded():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    result_str = json.dumps(result)
    assert "tiktok.com" not in result_str


def test_login_history_excluded():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    result_str = json.dumps(result)
    assert "login_history" not in result_str


def test_meta_block_present():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    assert "_meta" in result
    assert "instructions_for_llm" in result["_meta"]
    assert "suggested_opening" in result["_meta"]
    assert "followup_prompts" in result["_meta"]
    assert "generated_at" in result["_meta"]
    assert "privacy_note" in result["_meta"]
    assert "tool_version" in result["_meta"]


def test_behavioral_summary_included():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    assert "behavioral_summary" in result
    assert "skip_rate" in result["behavioral_summary"]


def test_interest_clusters_included():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    assert "profile" in result
    assert "interest_clusters" in result["profile"]


def test_followup_prompts_is_list():
    result = generate_llm_export(_base_parsed(), _base_ghost())
    assert isinstance(result["_meta"]["followup_prompts"], list)
    assert len(result["_meta"]["followup_prompts"]) >= 3


def test_evidence_block_excluded():
    """_evidence contains raw video URLs — must not appear in export."""
    ghost = _base_ghost()
    ghost["_evidence"] = {
        "feedback_loop": {
            "top_lingers_raw": [{"link": "https://www.tiktok.com/@user/video/99", "time_spent": 120}]
        }
    }
    result = generate_llm_export(_base_parsed(), ghost)
    assert "_evidence" not in result.get("profile", {})
    assert "tiktok.com" not in json.dumps(result)
