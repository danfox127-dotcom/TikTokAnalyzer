"""
Golden parity fixture for the WP-1.1 comment-voice + share-behavior port.

Covers api.ghost_profile.analyze_comment_voice and _analyze_share_behavior.

Parity notes baked into the scenarios:
  - Python len() counts CODE POINTS; JS .length counts UTF-16 units. Any comment
    with an astral emoji diverges on avg length, the >150 long-comment boundary,
    and the top-20 sort. The "codepoint_boundary" case pins this (149 ascii + 1
    emoji = len 150 in Python, NOT > 150).
  - _EMOJI_RE matches RUNS (+) over broad ranges; emoji_chars = total emoji code
    points across all texts.
  - references preserve _ENTITY_KEYWORDS category + keyword order.
  - label + behavior-type if/elif ORDER is load-bearing.

Run from repo root:  python3 scripts/gen_engagement_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.ghost_profile import analyze_comment_voice, _analyze_share_behavior  # noqa: E402


def _c(text):
    return {"comment": text}


def comment_cases():
    return [
        ("empty", [], 100, 0),
        ("lurker_low_rate", [_c("nice")], 1000, 0),
        ("analytical", [
            _c("This is a genuinely thoughtful long-form comment that goes well beyond a hundred characters to explain the nuance in detail."),
            _c("Another carefully written paragraph with substance and no emoji at all, again comfortably over the one hundred character mark here."),
        ], 200, 0),
        ("reactive_short_highrate", [_c("lol")] * 10, 100, 0),
        ("curator_dm_heavy", [_c("a decent medium comment here ok")] * 5, 100, 20),
        ("references_and_emoji", [
            _c("the lakers are unstoppable this season 🔥🔥"),
            _c("taylor swift and drake dropped ☀ love it"),
            _c("trump vs biden again, and the office reruns"),
        ], 300, 0),
        ("codepoint_boundary", [_c("x" * 149 + "🔥")], 500, 0),  # len 150 (not >150) in Python
    ]


def share_cases():
    return [
        ("empty", []),
        ("private_curator", [
            {"method": "whatsapp"}, {"method": "whatsapp"}, {"method": "dm"}, {"method": "copy_link"},
        ]),
        ("public_broadcaster", [
            {"method": "copy_link"}, {"method": "copy_link"}, {"method": "copy_link"}, {"method": "whatsapp"},
        ]),
        ("mixed", [
            {"method": "whatsapp"}, {"method": "whatsapp"}, {"method": "copy_link"}, {"method": "copy_link"},
        ]),
        ("method_missing_defaults_unknown", [{}, {"method": None}, {"method": "COPY_LINK"}]),
    ]


def main():
    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 comment/share port. Regenerate "
                    "only on an intentional Python change: "
                    "python3 scripts/gen_engagement_parity_fixture.py",
        "comment_voice_cases": [
            {"name": n, "input": {"comments": cs, "active_video_count": avc, "dm_share_count": dsc},
             "expected": analyze_comment_voice(cs, avc, dsc)}
            for n, cs, avc, dsc in comment_cases()
        ],
        "share_behavior_cases": [
            {"name": n, "input": {"shares": s}, "expected": _analyze_share_behavior(s)}
            for n, s in share_cases()
        ],
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "engagement_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    n = len(payload["comment_voice_cases"]) + len(payload["share_behavior_cases"])
    print(f"wrote {n} cases → {out_path}")


if __name__ == "__main__":
    main()
