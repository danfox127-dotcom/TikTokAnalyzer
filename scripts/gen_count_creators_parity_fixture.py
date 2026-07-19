"""
Golden parity fixture for the WP-1.1 creator-counting port.

Covers api.ghost_profile._count_creators plus utils.creators.{get_creator_meta,
resolve_vibe_cluster}.

_count_creators is non-deterministic in two ways that the scenarios neutralize:
  - it iterates a set (order varies) → we use DISTINCT counts so result ordering
    is fixed by count, independent of iteration order;
  - sample_titles = list(set(titles))[:5] has arbitrary order/selection → we keep
    <=5 UNIQUE titles per creator (so [:5] drops nothing) and SORT sample_titles
    in the expected output; the TS test sorts too and compares order-insensitively.

Run from repo root:  python3 scripts/gen_count_creators_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.ghost_profile import _count_creators  # noqa: E402
from utils.creators import get_creator_meta, resolve_vibe_cluster  # noqa: E402

TT = "https://www.tiktok.com/@"
NOH = "https://www.tiktok.com/video/"  # no @handle segment


def _norm(results):
    """Sort each result's sample_titles so the committed fixture is stable and the
    order-insensitive comparison is explicit."""
    out = []
    for r in results:
        r = dict(r)
        r["sample_titles"] = sorted(r["sample_titles"])
        out.append(r)
    return out


def count_scenarios():
    # (name, links, limit, count_key, link_to_title, link_handle_map)
    return [
        ("handle_based_distinct", [
            f"{TT}a/video/1", f"{TT}a/video/2", f"{TT}a/video/3",
            f"{TT}b/video/4", f"{TT}b/video/5",
            f"{TT}c/video/6",
        ], 15, "linger_count", {
            f"{TT}a/video/1": "cooking one", f"{TT}a/video/2": "cooking two",
            f"{TT}b/video/4": "gaming one",
        }, None),
        ("vid_fallback_all_unresolved", [
            f"{NOH}10", f"{NOH}10", f"{NOH}20",
        ], 15, "count", {f"{NOH}10": "mystery clip"}, None),
        ("handle_first_drops_unresolved_vids", [
            f"{TT}a/video/1", f"{TT}a/video/2",
            f"{NOH}99",  # unresolved vid → dropped because a handle exists
        ], 15, "count", None, None),
        ("map_resolution", [
            f"{NOH}500", f"{NOH}500", f"{NOH}600",
        ], 15, "count", None, {"500": "resolvedcreator", "600": "@another"}),
        ("limit_truncates", [
            f"{TT}a/video/1", f"{TT}a/video/2", f"{TT}a/video/3", f"{TT}a/video/4",  # 4
            f"{TT}b/video/5", f"{TT}b/video/6", f"{TT}b/video/7",                     # 3
            f"{TT}c/video/8", f"{TT}c/video/9",                                       # 2
            f"{TT}d/video/10",                                                        # 1
        ], 2, "count", None, None),
        ("no_vid_links_skipped", [
            "https://www.tiktok.com/@a/photo/1",  # no /video/ → skipped
            f"{TT}b/video/2", f"{TT}b/video/3",
        ], 15, "count", None, None),
        ("titles_dedup", [
            f"{TT}a/video/1", f"{TT}a/video/2", f"{TT}a/video/3",
        ], 15, "count", {
            f"{TT}a/video/1": "same", f"{TT}a/video/2": "same", f"{TT}a/video/3": "diff",
        }, None),
        ("empty", [], 15, "count", None, None),
    ]


def meta_scenarios():
    return ["@ChelseaFC", "khaby.lame", "NBA", "brooklyn.beckham", "unknownhandle", ""]


def vibe_scenarios():
    return [
        ("known_and_unknown", [
            {"handle": "@chelseafc", "count": 5},
            {"handle": "@nobody", "count": 2},
        ]),
        ("case_and_at_prefix", [
            {"handle": "@Khaby.Lame", "count": 3},
        ]),
        ("empty", []),
    ]


def main():
    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 creator-counting port. "
                    "Regenerate only on an intentional Python change: "
                    "python3 scripts/gen_count_creators_parity_fixture.py",
        "count_cases": [
            {"name": n, "input": {"links": lk, "limit": lim, "count_key": ck,
                                  "link_to_title": ltt, "link_handle_map": lhm},
             "expected": _norm(_count_creators(lk, limit=lim, count_key=ck,
                                               link_to_title=ltt, link_handle_map=lhm))}
            for n, lk, lim, ck, ltt, lhm in count_scenarios()
        ],
        "meta_cases": [
            {"name": h or "empty", "input": {"handle": h}, "expected": get_creator_meta(h)}
            for h in meta_scenarios()
        ],
        "vibe_cases": [
            {"name": n, "input": {"vibe_cluster": vc}, "expected": resolve_vibe_cluster(vc)}
            for n, vc in vibe_scenarios()
        ],
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "count_creators_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    n = sum(len(v) for k, v in payload.items() if k != "_comment")
    print(f"wrote {n} cases → {out_path}")


if __name__ == "__main__":
    main()
