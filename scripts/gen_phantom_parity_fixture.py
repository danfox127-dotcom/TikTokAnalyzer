"""
Golden parity fixture for the WP-1.3 phantom-session detector.

Runs the frozen Python oracle (`api.ghost_profile._detect_phantom_sessions`) over
hand-built histories and dumps {input, expected} to
`algorithmic-mirror/engine/__fixtures__/phantom_parity.json`.

engagement is stored as date strings; both the generator and the TS port parse
them to timestamps, so the "zero engagement in window" gate stays parity-exact.

Run from repo root:  python3 scripts/gen_phantom_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.ghost_profile import _detect_phantom_sessions, _parse_date  # noqa: E402

VID = "https://www.tiktok.com/@creator/video/"


def _hist(deltas, base, links=None):
    entries, cur = [], base
    for i, d in enumerate(deltas):
        entries.append({"date": cur.strftime("%Y-%m-%d %H:%M:%S"),
                        "link": (links[i] if links else VID + str(i))})
        cur = cur + timedelta(seconds=d)
    entries.append({"date": cur.strftime("%Y-%m-%d %H:%M:%S"), "link": ""})
    return entries


def scenarios():
    night = datetime(2024, 3, 11, 1, 0, 0)   # 01:00 night
    day = datetime(2024, 3, 11, 14, 0, 0)
    cases = []

    # Synthetic asleep-autoplay: 10 night lingers @60s, no engagement → phantom.
    cases.append(("synthetic_asleep", _hist([60.0] * 10, night), []))

    # Engagement inside the window disqualifies.
    cases.append(("engaged_disqualifies", _hist([60.0] * 10, night),
                  [(night + timedelta(seconds=300)).strftime("%Y-%m-%d %H:%M:%S")]))

    # Engagement AFTER the window doesn't disqualify.
    cases.append(("engaged_outside_window", _hist([60.0] * 10, night),
                  [(night + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")]))

    # Too short (8 qualifying videos).
    cases.append(("too_short", _hist([60.0] * 8, night), []))

    # Daytime run → not night.
    cases.append(("daytime", _hist([60.0] * 10, day), []))

    # Cadence out of range (200s > 180 ceiling).
    cases.append(("cadence_too_slow", _hist([200.0] * 10, night), []))

    # Boundary cadence 30s and 180s both qualify.
    cases.append(("cadence_boundaries", _hist([30.0, 180.0] * 6, night), []))

    # Two phantom nights → phantom_nights == 2. A two-day gap separates them.
    two = _hist([60.0] * 10, night) + _hist([60.0] * 10, night + timedelta(days=2))
    cases.append(("two_nights", two, []))

    cases.append(("empty", [], []))
    return cases


def main():
    payload = {
        "_comment": "Golden parity fixture for WP-1.3 _detect_phantom_sessions. "
                    "Regenerate only on an intentional Python change: "
                    "python3 scripts/gen_phantom_parity_fixture.py",
        "cases": [],
    }
    for name, history, engagement in scenarios():
        eng_dts = [_parse_date(e) for e in engagement]
        out = _detect_phantom_sessions(history, [d for d in eng_dts if d])
        out = {k: v for k, v in out.items() if k != "_phantom_links"}  # links are a set
        payload["cases"].append({
            "name": name,
            "input": {"history": history, "engagement": engagement},
            "expected": out,
        })

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "phantom_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(payload['cases'])} cases → {out_path}")


if __name__ == "__main__":
    main()
