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
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "echo_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    n = sum(len(payload[k]) for k in ("creator_url_cases", "handle_cases", "echo_cases"))
    print(f"wrote {n} cases → {out_path}")


if __name__ == "__main__":
    main()
