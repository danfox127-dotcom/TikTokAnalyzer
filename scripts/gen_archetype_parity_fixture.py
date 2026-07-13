"""
Golden parity fixture for the WP-1.1 archetype port.

Covers the persona cluster in api.ghost_profile:
  - _detect_atomic_traits       (6 boolean traits)
  - _synthesize_sub_archetypes  (append-ordered named archetypes)
  - _detect_cognitive_dissonance(first-match-wins contradiction)
  - _determine_primary_archetype(composes the three)

All pure boolean/arithmetic — parity is about exact thresholds, sub-archetype
APPEND order, and dissonance FIRST-MATCH order. Inputs are hand-built.

Run from repo root:  python3 scripts/gen_archetype_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.ghost_profile import (  # noqa: E402
    _detect_atomic_traits, _synthesize_sub_archetypes,
    _detect_cognitive_dissonance, _determine_primary_archetype,
)


def sw(max_session=0, max_skips=0, night_count=0, night_lingers=0, total_conscious=100):
    return {
        "max_session_duration": max_session,
        "max_consecutive_skips": max_skips,
        "night_count": night_count,
        "night_lingers": night_lingers,
        "total_conscious_videos": total_conscious,
    }


def parsed(shares=0, likes=0, comments=0, following=0):
    return {
        "shares": [{}] * shares, "likes": [{}] * likes,
        "comments": [{}] * comments, "following": [{}] * following,
    }


def vibe(*pairs):
    return [{"genre": g, "linger_count": c} for g, c in pairs]


def atomic_cases():
    return [
        ("all_false", sw(), 100, parsed(likes=100), 0.0, 0.0, vibe(("food", 10))),
        ("trapped_via_session", sw(max_session=3601), 100, parsed(likes=100), 0.0, 0.0, vibe(("food", 10))),
        ("trapped_via_linger", sw(), 100, parsed(likes=100), 30.1, 0.0, vibe(("food", 10))),
        ("ruthless", sw(max_skips=10), 100, parsed(likes=100), 0.0, 0.0, vibe(("food", 10))),
        ("nocturnal", sw(), 100, parsed(likes=100), 0.0, 35.1, vibe(("food", 10))),
        ("curator", sw(), 100, parsed(shares=6, likes=10), 0.0, 0.0, vibe(("food", 10))),
        ("ghost", sw(), 1000, parsed(likes=3, shares=2, comments=1), 0.0, 0.0, vibe(("food", 10))),
        ("optimizer", sw(), 100, parsed(likes=100), 0.0, 0.0, vibe(("tech", 3), ("food", 10))),
    ]


def sub_cases():
    return [
        ("intentional_curator", {"curator": True}, {"social_graph_followed_pct": 61}),
        ("nocturnal_seeker", {"nocturnal": True}, {"linger_rate_percentage": 26}),
        ("algorithmic_captured", {"trapped": True}, {"social_graph_algorithmic_pct": 76}),
        ("passive_observer", {"ghost": True}, {"linger_rate_percentage": 9}),
        ("multiple_append_order", {"curator": True, "nocturnal": True, "trapped": True},
         {"social_graph_followed_pct": 70, "linger_rate_percentage": 30, "social_graph_algorithmic_pct": 80}),
        ("none", {"curator": True}, {"social_graph_followed_pct": 50}),  # threshold not met
    ]


def dissonance_cases():
    return [
        ("circadian_drift", {"ruthless": True}, sw(night_count=10, night_lingers=4), {}, parsed(), vibe()),
        ("social_paradox", {}, sw(), {"social_graph_algorithmic_pct": 91}, parsed(following=101), vibe()),
        ("silent_expert", {"ghost": True}, sw(), {}, parsed(), vibe(("tech", 3), ("food", 5))),
        ("first_match_wins", {"ruthless": True, "ghost": True},
         sw(night_count=10, night_lingers=4), {"social_graph_algorithmic_pct": 91},
         parsed(following=101), vibe(("tech", 9), ("food", 1))),  # all 3 conditions true -> Circadian first
        ("none", {}, sw(), {}, parsed(), vibe()),
    ]


def primary_cases():
    return [
        ("balanced_default", {"linger_rate_percentage": 0, "night_shift_ratio": 0},
         parsed(likes=100), sw(), vibe(("food", 10))),
        ("nocturnal_seeker_primary",
         {"linger_rate_percentage": 26, "night_shift_ratio": 40,
          "social_graph_followed_pct": 10, "social_graph_algorithmic_pct": 50},
         parsed(likes=100), sw(night_count=10, night_lingers=5, total_conscious=100), vibe(("food", 10))),
    ]


def main():
    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 archetype port. Regenerate "
                    "only on an intentional Python change: "
                    "python3 scripts/gen_archetype_parity_fixture.py",
        "atomic_cases": [
            {"name": n, "input": {"sw": s, "total_conscious": tc, "parsed": p,
                                  "linger_rate_pct": lr, "night_shift_pct": ns, "vibe_cluster": v},
             "expected": _detect_atomic_traits(s, tc, p, lr, ns, v)}
            for n, s, tc, p, lr, ns, v in atomic_cases()
        ],
        "sub_cases": [
            {"name": n, "input": {"traits": t, "behavioral_nodes": bn},
             "expected": _synthesize_sub_archetypes(t, bn)}
            for n, t, bn in sub_cases()
        ],
        "dissonance_cases": [
            {"name": n, "input": {"traits": t, "sw": s, "behavioral_nodes": bn,
                                  "parsed": p, "vibe_cluster": v},
             "expected": _detect_cognitive_dissonance(t, s, bn, p, v)}
            for n, t, s, bn, p, v in dissonance_cases()
        ],
        "primary_cases": [
            {"name": n, "input": {"behavioral_nodes": bn, "parsed": p, "sw": s, "vibe_cluster": v},
             "expected": _determine_primary_archetype(bn, p, s, v)}
            for n, bn, p, s, v in primary_cases()
        ],
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "archetype_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    n = sum(len(v) for k, v in payload.items() if k != "_comment")
    print(f"wrote {n} cases → {out_path}")


if __name__ == "__main__":
    main()
