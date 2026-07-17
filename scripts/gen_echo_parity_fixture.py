"""
Golden parity fixture for the WP-1.1 creator/echo-chamber port.

Covers the deterministic creator-resolution cluster from api.ghost_profile:
  - _extract_creator_from_url
  - _handle_from_link          (URL regex, then video_id -> handle map)
  - _echo_chamber_index        (top-5 concentration; sums counts, so it is
                                order-independent despite iterating a set)

_count_creators is intentionally NOT covered here: its output order depends on
Python set-iteration + list(set(...)) for sample_titles + tie-breaking, so it is
not reproducible across languages and needs its own order-insensitive slice.

Run from repo root:  python3 scripts/gen_echo_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.ghost_profile import (  # noqa: E402
    _extract_creator_from_url,
    _handle_from_link,
    _echo_chamber_index,
    _echo_chamber_split,
)

V = "https://www.tiktok.com/@"        # + "<handle>/video/<id>"
VID_ONLY = "https://www.tiktok.com/video/"  # no @handle segment


def creator_url_cases():
    return [
        ("handle_with_slash", V + "chelseafc/video/123"),
        ("handle_dots_underscores", V + "khaby.lame/video/9"),
        ("handle_hyphen", V + "reece-james/video/9"),
        ("no_trailing_slash", "https://www.tiktok.com/@masonmount"),  # regex needs '@name/'
        ("no_handle", VID_ONLY + "555"),
        ("empty", ""),
    ]


def handle_cases():
    hm = {"555": "newyorkcity", "777": "@timeoutnewyork"}
    return [
        ("url_handle_wins", V + "nba/video/1", hm),
        ("map_hit_bare_handle_gets_at", VID_ONLY + "555", hm),      # -> @newyorkcity
        ("map_hit_already_at", VID_ONLY + "777", hm),               # -> @timeoutnewyork
        ("map_miss", VID_ONLY + "999", hm),                         # -> None
        ("no_map_no_urlhandle", VID_ONLY + "555", None),            # -> None
        ("empty_link", "", hm),
    ]


def echo_cases():
    hm = {"101": "creatora", "102": "creatorb"}

    def links(*ids_or_urls):
        return list(ids_or_urls)

    return [
        # All URL-handled, concentrated on one creator -> pct 100
        ("single_creator", links(
            V + "a/video/1", V + "a/video/2", V + "a/video/3"), None),
        # Two creators 2:1 -> top5 sum == total -> 100 (only 2 distinct, both in top5)
        ("two_creators_top5_covers_all", links(
            V + "a/video/1", V + "a/video/2", V + "b/video/3"), None),
        # Six creators one each -> top5=5, total=6 -> 83.3
        ("six_creators_spread", links(
            V + "a/video/1", V + "b/video/2", V + "c/video/3",
            V + "d/video/4", V + "e/video/5", V + "f/video/6"), None),
        # Mix: some resolved via map, some via URL, some unresolved (dropped)
        ("map_and_url_mixed", links(
            V + "a/video/1", VID_ONLY + "101", VID_ONLY + "102",
            VID_ONLY + "999"), hm),  # 999 unresolved -> excluded
        # Ties in counts still fine because echo sums the top-5 values
        ("ties", links(
            V + "a/video/1", V + "b/video/2", V + "c/video/3",
            V + "a/video/4", V + "b/video/5", V + "c/video/6"), None),
        ("empty", links(), None),
    ]


def _ev(day, handle, time):
    # Resolution is by @handle in the URL, so the video id is irrelevant.
    return {"link": V + handle + "/video/1", "time_spent": float(time), "_day": day}


def echo_split_cases():
    """WP-1.7 daily_concentration / cluster_churn scenarios.

    Small cases are hand-verifiable (distinct times, no boundary ties between the
    5th and 6th cluster, so the top-5 SET is unambiguous). The benchmark case is
    engineered to reproduce the published ≈0.5 concentration / ≈0.8 churn so the
    formula is pinned to its intended meaning, not just to itself.
    """
    cases = []

    # 2 clusters, 1 day: top5 covers all -> conc 1.0; 1 active day -> churn 0.0;
    # bubble True (conc>0.6, churn<0.4). per_month mirrors overall.
    cases.append(("two_clusters_one_day", [
        _ev("2024-01-01", "a", 30), _ev("2024-01-01", "b", 10),
    ], None))

    # 6 clusters, 1 day: top5 = 20/21 of time.
    cases.append(("six_clusters_one_day", [
        _ev("2024-01-02", "a", 6), _ev("2024-01-02", "b", 5), _ev("2024-01-02", "c", 4),
        _ev("2024-01-02", "d", 3), _ev("2024-01-02", "e", 2), _ev("2024-01-02", "f", 1),
    ], None))

    # 2 days, top5 fully rotates -> churn 1.0; bubble False.
    cases.append(("two_days_full_churn", [
        _ev("2024-01-01", "a", 10), _ev("2024-01-01", "b", 9), _ev("2024-01-01", "c", 8),
        _ev("2024-01-01", "d", 7), _ev("2024-01-01", "e", 6), _ev("2024-01-01", "f", 5),
        _ev("2024-01-02", "g", 10), _ev("2024-01-02", "h", 9), _ev("2024-01-02", "i", 8),
        _ev("2024-01-02", "j", 7), _ev("2024-01-02", "k", 6), _ev("2024-01-02", "l", 5),
    ], None))

    # 2 days, identical top5 -> churn 0.0; conc 0.889; bubble True.
    cases.append(("two_days_no_churn", [
        _ev("2024-01-01", "a", 10), _ev("2024-01-01", "b", 9), _ev("2024-01-01", "c", 8),
        _ev("2024-01-01", "d", 7), _ev("2024-01-01", "e", 6), _ev("2024-01-01", "f", 5),
        _ev("2024-01-02", "a", 10), _ev("2024-01-02", "b", 9), _ev("2024-01-02", "c", 8),
        _ev("2024-01-02", "d", 7), _ev("2024-01-02", "e", 6), _ev("2024-01-02", "f", 5),
    ], None))

    # 2 days, 2 of top5 replaced -> churn 0.4 (exactly the bubble boundary, so NOT <0.4).
    cases.append(("two_days_partial_churn", [
        _ev("2024-01-01", "a", 10), _ev("2024-01-01", "b", 9), _ev("2024-01-01", "c", 8),
        _ev("2024-01-01", "d", 7), _ev("2024-01-01", "e", 6), _ev("2024-01-01", "f", 5),
        _ev("2024-01-02", "a", 10), _ev("2024-01-02", "b", 9), _ev("2024-01-02", "c", 8),
        _ev("2024-01-02", "x", 7), _ev("2024-01-02", "y", 6), _ev("2024-01-02", "f", 5),
    ], None))

    # Two months -> per_month has two keys, each computed independently.
    cases.append(("two_months", [
        _ev("2024-01-10", "a", 10), _ev("2024-01-10", "b", 5),
        _ev("2024-02-11", "c", 8), _ev("2024-02-11", "d", 8), _ev("2024-02-11", "e", 3),
    ], None))

    # Unresolved links (no @handle, no map) are dropped -> empty result.
    cases.append(("all_unresolved", [
        {"link": VID_ONLY + "999", "time_spent": 20.0, "_day": "2024-01-01"},
    ], None))

    # Empty.
    cases.append(("empty", [], None))

    # Benchmark-scale: 6 days, each with a top-5 (times 10/9/8/7/6 = 40) plus a
    # 40-creator tail (time 1 each = 40) -> daily conc = 40/80 = 0.5. The top-5
    # rotates by 4 each day (carrying exactly one), so each day replaces 4/5 ->
    # churn 0.8. Reproduces the published ≈0.5 / ≈0.79 benchmark.
    bench = []
    for d in range(6):
        day = f"2024-03-0{d + 1}"
        top = [f"t{d * 4 + k}" for k in range(5)]
        for handle, t in zip(top, (10, 9, 8, 7, 6)):
            bench.append(_ev(day, handle, t))
        for j in range(40):
            bench.append(_ev(day, f"tail{j}", 1))
    cases.append(("benchmark_scale", bench, None))

    return cases


def main():
    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 creator/echo port. "
                    "Generated from api.ghost_profile. Regenerate only on an "
                    "intentional Python change: python3 scripts/gen_echo_parity_fixture.py",
        "creator_url_cases": [
            {"name": n, "input": {"url": u}, "expected": _extract_creator_from_url(u)}
            for n, u in creator_url_cases()
        ],
        "handle_cases": [
            {"name": n, "input": {"link": lk, "link_handle_map": hm},
             "expected": _handle_from_link(lk, hm)}
            for n, lk, hm in handle_cases()
        ],
        "echo_cases": [
            {"name": n, "input": {"linger_links": lks, "link_handle_map": hm},
             "expected": _echo_chamber_index(lks, hm)}
            for n, lks, hm in echo_cases()
        ],
        "echo_split_cases": [
            {"name": n, "input": {"linger_events": evs, "link_handle_map": hm},
             "expected": _echo_chamber_split(evs, hm)}
            for n, evs, hm in echo_split_cases()
        ],
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "echo_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    n = sum(len(payload[k]) for k in ("creator_url_cases", "handle_cases", "echo_cases", "echo_split_cases"))
    print(f"wrote {n} cases → {out_path}")


if __name__ == "__main__":
    main()
