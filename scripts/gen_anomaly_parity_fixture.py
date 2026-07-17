"""
Golden parity fixture for the WP-1.3 adaptive-anomaly flag.

Runs the frozen Python oracle (`api.ghost_profile._adaptive_anomaly`) over
hand-built histories and dumps {input, expected} to
`algorithmic-mirror/engine/__fixtures__/anomaly_parity.json`.

The only parity-fragile piece is the nearest-rank p99 index; scenarios pick n so
`(99n+99)//100 - 1` lands on an unambiguous, distinct delta.

Run from repo root:  python3 scripts/gen_anomaly_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.ghost_profile import _adaptive_anomaly  # noqa: E402

BASE = datetime(2024, 3, 11, 1, 0, 0)


def _hist(deltas):
    entries, cur = [], BASE
    for d in deltas:
        entries.append({"date": cur.strftime("%Y-%m-%d %H:%M:%S"), "link": "x"})
        cur = cur + timedelta(seconds=d)
    entries.append({"date": cur.strftime("%Y-%m-%d %H:%M:%S"), "link": ""})
    return entries


def scenarios():
    return [
        # Floor branch: n=100, p99=60 (<1200) → threshold floors to 1200; the one
        # 2000s gap is flagged. count=1.
        ("floor_branch", _hist([60.0] * 99 + [2000.0])),
        # Adaptive branch: n=200, p99=2500 (>1200) → personal bar rises; only the
        # two gaps beyond 2500 are flagged. count=2, threshold=2500.
        ("adaptive_branch", _hist([60.0] * 195 + [1500.0, 2000.0, 2500.0, 3000.0, 3500.0])),
        # Clock anomalies (negative deltas) are excluded from the sample.
        ("with_clock_anomaly", [
            {"date": "2024-03-11 01:00:00", "link": "a"},
            {"date": "2024-03-11 01:00:30", "link": "b"},
            {"date": "2024-03-11 01:00:10", "link": "c"},  # earlier → negative delta
            {"date": "2024-03-11 02:00:00", "link": "d"},  # a 3590s gap after sort
            {"date": "2024-03-11 02:00:30", "link": ""},
        ]),
        ("single_video", _hist([60.0])),
        ("empty", []),
    ]


def main():
    payload = {
        "_comment": "Golden parity fixture for WP-1.3 _adaptive_anomaly. "
                    "Regenerate only on an intentional Python change: "
                    "python3 scripts/gen_anomaly_parity_fixture.py",
        "cases": [
            {"name": n, "input": {"history": h}, "expected": _adaptive_anomaly(h)}
            for n, h in scenarios()
        ],
    }
    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "anomaly_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(payload['cases'])} cases → {out_path}")


if __name__ == "__main__":
    main()
