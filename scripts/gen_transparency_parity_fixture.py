"""
Golden parity fixture for the WP-1.1 transparency-gap port.
Covers api.ghost_profile.calculate_transparency_gap.

Parity note: the gap percent uses Python round() with no digits (round-half-to-
even → int). The "banker_rounding_half" case (official 3 / behavioral 8 → 62.5)
pins the even-rounding behavior.

Run from repo root:  python3 scripts/gen_transparency_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.ghost_profile import calculate_transparency_gap  # noqa: E402


def _clusters(n):
    return [{"term": f"t{i}", "count": 1} for i in range(n)]


def cases():
    return [
        ("empty_official_strong_behavioral", {"ad_interests": []}, {"interest_clusters": _clusters(8)}),
        ("significant_gap_70", {"ad_interests": ["a", "b", "c"]}, {"interest_clusters": _clusters(10)}),
        ("banker_rounding_half", {"ad_interests": ["a", "b", "c"]}, {"interest_clusters": _clusters(8)}),  # 62.5 -> 62
        ("roughly_match", {"ad_interests": ["a", "b", "c", "d", "e"]}, {"interest_clusters": _clusters(6)}),
        ("empty_official_weak_behavioral", {"ad_interests": []}, {"interest_clusters": _clusters(3)}),
        ("both_empty", {"ad_interests": []}, {"interest_clusters": []}),
        ("missing_keys", {}, {}),
    ]


def main():
    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 transparency-gap port. "
                    "Regenerate only on an intentional Python change: "
                    "python3 scripts/gen_transparency_parity_fixture.py",
        "cases": [
            {"name": n, "input": {"parsed": p, "profile": pr},
             "expected": calculate_transparency_gap(p, pr)}
            for n, p, pr in cases()
        ],
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "transparency_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(payload['cases'])} cases → {out_path}")


if __name__ == "__main__":
    main()
