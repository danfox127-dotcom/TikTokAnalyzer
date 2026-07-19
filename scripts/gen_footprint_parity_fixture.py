"""
Golden parity fixture for the WP-1.1 text-footprint port.

Covers api.ghost_profile._mine_text_footprint (+ _keywords_from_url), which
builds the engagement-weighted interest corpus (interest_clusters, top_phrases).

Parity notes baked into the scenarios:
  - the corpus repeats each (text, source) tuple SIGNAL_WEIGHTS[source] times, so
    counts are weighted and source/term tie-order follows corpus insertion order
    (comments -> searches -> following -> shares -> favorites -> likes).
  - tokenizing uses re r"\\b[a-zA-Z]{3,}\\b" where Python's \\b is UNICODE-aware;
    the "unicode_boundary" case pins the behavior next to accented letters.
  - dominant_source and most_common ties break by first-insertion order.

Run from repo root:  python3 scripts/gen_footprint_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.ghost_profile import _mine_text_footprint, _keywords_from_url  # noqa: E402

TT = "https://www.tiktok.com/"


def footprint_scenarios():
    return [
        ("comments_only", {
            "comments": [
                {"comment": "amazing sourdough baking tips baking"},
                {"comment": "baking bread every weekend"},
            ],
        }),
        ("searches_weighted", {
            "searches": [{"term": "crypto investing guide"}, {"term": "crypto news"}],
        }),
        ("following_username_split", {
            "following": [
                {"username": "chelsea_fc.official"},
                {"username": "nba"},           # all parts <=2 after split? "nba" len3 kept
            ],
        }),
        ("shares_dm_vs_public", {
            "shares": [
                {"method": "whatsapp", "link": TT + "@cookingchannel/video/1"},   # dm
                {"method": "copy_link", "link": TT + "tag/gaming-setup/video/2"}, # public
            ],
        }),
        ("favorites_and_likes", {
            "favorites": [{"link": TT + "@fitnessguru/video/9"}],
            "likes": [{"link": TT + "tag/home-decor/video/3"}],
        }),
        ("mixed_dominant_source_and_truncation", {
            "comments": [{"comment": "gaming gaming gaming setup"}],   # comment weight 10
            "likes": [{"link": TT + "tag/gaming/video/1"}],           # like weight 3
            "searches": [{"term": "recipe ideas dinner"}],
        }),
        ("unicode_boundary", {
            # "café" is not [a-zA-Z]{3,} bounded (é is a unicode word char), so
            # Python extracts nothing from it; "ramen" survives.
            "comments": [{"comment": "café ramen ramen tutorial"}],
        }),
        ("empty", {}),
    ]


def keywords_url_scenarios():
    return [
        TT + "@chelsea_fc.official/video/123",   # creator -> "chelsea fc official"
        TT + "tag/cooking-recipes/food",         # path parts filtered
        TT + "video/1234567",                    # only digits/noise -> []
        "",                                       # empty -> []
        TT + "discover/HomeDecor",               # "homedecor" kept (len>=4, not noise)
    ]


def main():
    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 text-footprint port. "
                    "Regenerate only on an intentional Python change: "
                    "python3 scripts/gen_footprint_parity_fixture.py",
        "footprint_cases": [
            {"name": n, "input": {"parsed": p}, "expected": _mine_text_footprint(p)}
            for n, p in footprint_scenarios()
        ],
        "keywords_url_cases": [
            {"name": u or "empty", "input": {"url": u}, "expected": _keywords_from_url(u)}
            for u in keywords_url_scenarios()
        ],
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "footprint_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    n = len(payload["footprint_cases"]) + len(payload["keywords_url_cases"])
    print(f"wrote {n} cases → {out_path}")


if __name__ == "__main__":
    main()
