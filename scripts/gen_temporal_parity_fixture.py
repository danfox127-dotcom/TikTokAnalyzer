"""
Golden parity fixture for the WP-1.1 temporal-features port.

Covers the six standalone temporal functions (extracted, behavior-preserving,
from build_ghost_profile) in api.ghost_profile:
  - _algorithm_drift         (first-half vs second-half skip rate)
  - _infer_sleep_window      (min 4-hour wrap-around dead zone)
  - _monthly_creator_trends  (top-5 lingered creators per month)
  - _monthly_topic_trends    (searches weight 3 + comment words, top-8/month)
  - _sandbox_retests         (creators re-served in sandbox tier >=2)
  - _skip_anomalies          (months >=3pts from leave-one-out baseline)

Note: _monthly_topic_trends tokenizes comments with plain r"[a-z]{3,}" (NO word
boundary), unlike text-footprint's r"\\b[a-zA-Z]{3,}\\b" — so "café" -> "caf" here.

Run from repo root:  python3 scripts/gen_temporal_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.ghost_profile import (  # noqa: E402
    _algorithm_drift, _infer_sleep_window, _monthly_creator_trends,
    _monthly_topic_trends, _sandbox_retests, _skip_anomalies,
)

TT = "https://www.tiktok.com/@"


def _ev(handle, month, vid="1", tier_link=None):
    """A linger/sandbox event dict (fields the temporal fns read: link, _month)."""
    return {"video_id": vid, "link": tier_link or f"{TT}{handle}/video/{vid}",
            "time_spent": 60.0, "hour": 10, "_month": month}


def drift_cases():
    return [
        ("too_few_months", {"2024-01": 40.0, "2024-02": 30.0, "2024-03": 20.0}),
        ("tightening", {"2024-01": 40.0, "2024-02": 38.0, "2024-03": 20.0, "2024-04": 18.0}),
        ("loosening", {"2024-01": 18.0, "2024-02": 20.0, "2024-03": 38.0, "2024-04": 40.0}),
        ("stable", {"2024-01": 30.0, "2024-02": 31.0, "2024-03": 32.0, "2024-04": 33.0}),
        ("six_months", {f"2024-0{m}": float(10 * m) for m in range(1, 7)}),
    ]


def sleep_cases():
    dead = {str(h): (0 if 2 <= h <= 6 else 10) for h in range(24)}          # dead 2-6am
    wrap = {str(h): (0 if h in (23, 0, 1, 2) else 8) for h in range(24)}    # dead 23-02 (wrap)
    allzero = {str(h): 0 for h in range(24)}
    return [("dead_zone_morning", dead), ("wraparound", wrap), ("all_zero", allzero)]


def creator_trend_cases():
    hm = {"900": "resolvedcreator"}
    return [
        ("multi_month_top5", {
            "linger_events": [
                _ev("a", "2024-01"), _ev("a", "2024-01"), _ev("b", "2024-01"),
                _ev("c", "2024-02"), _ev("c", "2024-02"), _ev("c", "2024-02"), _ev("d", "2024-02"),
            ],
            "link_handle_map": None,
        }),
        ("map_resolution_and_unresolved", {
            "linger_events": [
                _ev(None, "2024-03", vid="900", tier_link=f"https://www.tiktok.com/video/900"),  # via map
                _ev(None, "2024-03", vid="404", tier_link=f"https://www.tiktok.com/video/404"),  # unresolved
                _ev("x", "2024-03"),
            ],
            "link_handle_map": hm,
        }),
        ("more_than_five_creators", {
            "linger_events": [_ev(h, "2024-04") for h in ["a", "b", "c", "d", "e", "f", "g"]],
            "link_handle_map": None,
        }),
        ("empty", {"linger_events": [], "link_handle_map": None}),
    ]


def topic_trend_cases():
    return [
        ("searches_and_comments", {
            "searches": [
                {"term": "sourdough starter", "date": "2024-01-10 09:00:00"},
                {"term": "sourdough starter", "date": "2024-01-12 09:00:00"},
                {"term": "hi", "date": "2024-01-12 09:00:00"},          # len<=2 -> skipped
                {"term": "crypto", "date": ""},                         # no date -> skipped
            ],
            "comments": [
                {"comment": "love baking baking bread", "date": "2024-01-15 09:00:00"},
                {"comment": "no date here", "date": ""},                # skipped
                {"comment": "café ramen", "date": "2024-02-01 09:00:00"},  # café -> "caf" (no boundary)
            ],
        }),
        ("empty", {"searches": [], "comments": []}),
    ]


def sandbox_cases():
    return [
        ("retests_threshold", {
            "sandbox_events": [
                _ev("a", "2024-01"), _ev("a", "2024-01"), _ev("a", "2024-01"),  # 3 -> included
                _ev("b", "2024-01"), _ev("b", "2024-01"),                        # 2 -> included
                _ev("c", "2024-01"),                                             # 1 -> excluded
            ],
            "link_handle_map": None,
        }),
        ("empty", {"sandbox_events": [], "link_handle_map": None}),
    ]


def anomaly_cases():
    return [
        ("too_few", {"2024-01": 40.0, "2024-02": 30.0}),
        ("spike_and_dip", {"2024-01": 10.0, "2024-02": 12.0, "2024-03": 50.0}),
        ("none_within_threshold", {"2024-01": 30.0, "2024-02": 31.0, "2024-03": 32.0}),
    ]


def main():
    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 temporal port. Regenerate "
                    "only on an intentional Python change: "
                    "python3 scripts/gen_temporal_parity_fixture.py",
        "algorithm_drift_cases": [
            {"name": n, "input": {"monthly_skip_rates": r}, "expected": _algorithm_drift(r)}
            for n, r in drift_cases()
        ],
        "sleep_window_cases": [
            {"name": n, "input": {"hourly_heatmap": h}, "expected": _infer_sleep_window(h)}
            for n, h in sleep_cases()
        ],
        "creator_trend_cases": [
            {"name": n, "input": i,
             "expected": _monthly_creator_trends(i["linger_events"], i["link_handle_map"])}
            for n, i in creator_trend_cases()
        ],
        "topic_trend_cases": [
            {"name": n, "input": i,
             "expected": _monthly_topic_trends(i["searches"], i["comments"])}
            for n, i in topic_trend_cases()
        ],
        "sandbox_retest_cases": [
            {"name": n, "input": i,
             "expected": _sandbox_retests(i["sandbox_events"], i["link_handle_map"])}
            for n, i in sandbox_cases()
        ],
        "skip_anomaly_cases": [
            {"name": n, "input": {"monthly_skip_rates": r}, "expected": _skip_anomalies(r)}
            for n, r in anomaly_cases()
        ],
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "temporal_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    n = sum(len(v) for k, v in payload.items() if k != "_comment")
    print(f"wrote {n} cases → {out_path}")


if __name__ == "__main__":
    main()
