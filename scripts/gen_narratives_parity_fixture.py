"""
Golden parity fixture for the WP-1.1 narratives port (api/narratives.py).

Covers build_narrative_blocks (the 9 deterministic block builders). The LLM path
(generate_narrative_blocks_llm) is out of scope (network). Hand-built ghost_profile
inputs hit every prose branch; one integration case runs the real orchestrator.

Parity traps: f-string formats :.0f / :.1f / :.3f use round-half-to-even; str.title().

Run from repo root:  PYTHONHASHSEED=0 python3 scripts/gen_narratives_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.narratives import build_narrative_blocks  # noqa: E402
from api.ghost_profile import build_ghost_profile  # noqa: E402


def vibe(*pairs):
    return [{"handle": h, "linger_count": c, "is_followed": f, "genre": g}
            for h, c, f, g in pairs]


def gp_high():
    return {
        "behavioral_nodes": {"social_graph_followed_pct": 70.0, "social_graph_algorithmic_pct": 30.0,
                             "skip_rate_percentage": 15.0, "linger_rate_percentage": 25.0,
                             "night_shift_ratio": 40.0, "peak_hour": "11 PM"},
        "stopwatch_metrics": {"total_conscious_videos": 200, "deep_dives": 30, "total_raw_videos": 250,
                              "hourly_heatmap": {str(h): (20 if h == 23 else 3) for h in range(24)}},
        "creator_entities": {"vibe_cluster": vibe(("@a", 40, True, "tech"), ("@b", 20, False, "sports"), ("@c", 10, False, "food"))},
        "declared_signals": {"following_count": 120},
        "share_behavior": {"total_shares": 12, "share_behavior_type": "Private Curator",
                           "primary_share_method": "whatsapp", "share_methods": {"whatsapp": 9, "copy_link": 3}},
        "comment_voice": {"total_comments": 8, "avg_length_chars": 142.5, "engagement_style_label": "Analytical Commenter"},
        "transparency_gap": {"official_ad_interest_count": 0, "behavioral_interest_count": 8, "gap_interpretation": "gap text"},
        "digital_footprint": {"login_count": 3, "unique_ips": 2,
                              "recent_logins": [{"city": "Denver"}, {"city": "Denver"}, {"city": "Aspen"}]},
        "primary_archetype": {"name": "The Intentional Curator"},
    }


def gp_low():
    return {
        "behavioral_nodes": {"social_graph_followed_pct": 10.0, "social_graph_algorithmic_pct": 90.0,
                             "skip_rate_percentage": 60.0, "linger_rate_percentage": 5.0,
                             "night_shift_ratio": 10.0, "peak_hour": "3 PM"},
        "stopwatch_metrics": {"total_conscious_videos": 500, "deep_dives": 5, "total_raw_videos": 600,
                              "hourly_heatmap": {str(h): (10 if h == 15 else 1) for h in range(24)}},
        "creator_entities": {"vibe_cluster": vibe(("@x", 5, False, "news"))},
        "declared_signals": {"following_count": 300},
        "share_behavior": {"total_shares": 0, "share_behavior_type": "Mixed Sharer",
                           "primary_share_method": None, "share_methods": {}},
        "comment_voice": {"total_comments": 0, "avg_length_chars": 0.0, "engagement_style_label": "Lurker"},
        "transparency_gap": {"official_ad_interest_count": 3, "behavioral_interest_count": 10, "gap_interpretation": "Significant gap detected."},
        "digital_footprint": {"login_count": 0, "unique_ips": 0, "recent_logins": []},
        "primary_archetype": {"name": "The Algorithmic Captured"},
    }


def gp_mid():
    return {
        "behavioral_nodes": {"social_graph_followed_pct": 45.0, "social_graph_algorithmic_pct": 55.0,
                             "skip_rate_percentage": 30.0, "linger_rate_percentage": 10.0,
                             "night_shift_ratio": 20.0, "peak_hour": "12 PM"},
        "stopwatch_metrics": {"total_conscious_videos": 100, "deep_dives": 8, "total_raw_videos": 120,
                              "hourly_heatmap": {str(h): (5 if h == 12 else 2) for h in range(24)}},
        "creator_entities": {"vibe_cluster": vibe(("@m", 6, True, "music"), ("@n", 4, False, "unknown"))},
        "declared_signals": {"following_count": 50},
        "share_behavior": {"total_shares": 20, "share_behavior_type": "Public Broadcaster",
                           "primary_share_method": "copy_link", "share_methods": {"copy_link": 15, "dm": 5}},
        "comment_voice": {"total_comments": 3, "avg_length_chars": 25.0, "engagement_style_label": "Reactive Commenter"},
        "transparency_gap": {"official_ad_interest_count": 2, "behavioral_interest_count": 3, "gap_interpretation": "Roughly matches."},
        "digital_footprint": {"login_count": 2, "unique_ips": 1, "recent_logins": [{"city": "Unknown"}, {}]},
        "primary_archetype": {"name": "The Balanced Viewer"},
    }


def cases():
    from scripts.gen_orchestrator_parity_fixture import rich_parsed  # reuse the rich export
    rich_gp = build_ghost_profile(rich_parsed())
    return [
        ("high_followed", gp_high(), {"likes": [{}] * 4}),
        ("low_followed", gp_low(), {"likes": []}),
        ("mid", gp_mid(), {"likes": [{}] * 10}),
        ("empty", {}, {}),
        ("integration_from_orchestrator", rich_gp, rich_parsed()),
    ]


def main():
    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 narratives port. Regenerate with "
                    "PYTHONHASHSEED=0 python3 scripts/gen_narratives_parity_fixture.py",
        "cases": [
            {"name": n, "input": {"ghost_profile": gp, "parsed": p},
             "expected": build_narrative_blocks(gp, p)}
            for n, gp, p in cases()
        ],
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "narratives_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(payload['cases'])} cases → {out_path}")


if __name__ == "__main__":
    main()
