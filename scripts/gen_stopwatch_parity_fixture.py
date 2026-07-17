"""
Generate the golden parity fixture for the WP-1.1 stopwatch port.

Runs the FROZEN Python oracle (`api.ghost_profile._run_stopwatch`) against a
battery of hand-built input histories and dumps {input, expected} pairs to
`algorithmic-mirror/engine/__fixtures__/stopwatch_parity.json`.

The TypeScript port asserts its own `runStopwatch` against this file. The
fixture is COMMITTED and regenerated only on purpose (an intentional Python
change shows up as a fixture git-diff you review), so parity catches drift
instead of silently tracking whatever Python does today.

Run from repo root:  python3 scripts/gen_stopwatch_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.ghost_profile import _run_stopwatch  # noqa: E402

VID = "https://www.tiktok.com/@creator/video/"
NOVID = "https://www.tiktok.com/@creator/photo/"  # no /video/<id> → video_id is None


def _entry(dt: datetime, link: str) -> dict:
    # strftime truncates to whole seconds — exactly what the TS port will read
    # back from the fixture, so sub-second deltas can't diverge across languages.
    return {"date": dt.strftime("%Y-%m-%d %H:%M:%S"), "link": link}


def _from_deltas(deltas, base, link=VID + "1", links=None):
    """Build a history where entry i+1 is `deltas[i]` seconds after entry i."""
    entries = []
    cur = base
    for i, d in enumerate(deltas):
        lk = links[i] if links else link
        entries.append(_entry(cur, lk))
        cur = cur + timedelta(seconds=d)
    entries.append(_entry(cur, ""))  # trailing so the last real video gets a reading
    return entries


def build_scenarios():
    mon14 = datetime(2024, 3, 11, 14, 0, 0)  # Monday 14:00 (weekday()==0)
    scenarios = []

    # 1. Tier boundaries — exact edges 3/15/180/300s
    scenarios.append(("tier_boundaries", _from_deltas(
        [1.0, 3.0, 15.0, 16.0, 180.0, 181.0, 300.0, 301.0], mon14), ()))

    # 2. Graveyard streak → max_consecutive_skips
    scenarios.append(("graveyard_streak", _from_deltas([1.0] * 12, mon14), ()))

    # 3. Session accumulation vs reset (>300s resets current session)
    scenarios.append(("session_reset", _from_deltas(
        [30.0, 30.0, 30.0, 400.0, 45.0, 45.0], mon14), ()))

    # 4. Sleep scrub (>=1200s) resets session and is excluded
    scenarios.append(("sleep_scrub", _from_deltas([60.0, 1500.0, 60.0], mon14), ()))

    # 5. Clock anomaly — a later row with an EARLIER timestamp (negative delta).
    #    Built explicitly since _from_deltas is monotonic. After the sort inside
    #    the stopwatch these re-order, so we craft raw unsorted rows.
    scenarios.append(("clock_anomaly", [
        _entry(mon14, VID + "a"),
        _entry(mon14 + timedelta(seconds=30), VID + "b"),
        _entry(mon14 + timedelta(seconds=10), VID + "c"),  # earlier than prev row
        _entry(mon14 + timedelta(seconds=90), VID + "d"),
        _entry(mon14 + timedelta(seconds=120), ""),
    ], ()))

    # 6. Night hours (23,0,1,2,3) → night_count / night_lingers
    night = datetime(2024, 3, 11, 23, 30, 0)
    scenarios.append(("night_window", _from_deltas([60.0, 200.0, 5.0, 60.0], night), ()))

    # 7. Multi-month → monthly_skip_rates, data_start_month, event _month
    jan = datetime(2024, 1, 5, 10, 0, 0)
    hist = _from_deltas([1.0, 1.0, 60.0], jan)[:-1]              # Jan: 2 skips + 1 linger
    hist += _from_deltas([60.0, 1.0, 200.0], datetime(2024, 3, 2, 9, 0, 0))  # Mar
    scenarios.append(("multi_month", hist, ()))

    # 8. Distinct + repeated links across tiers (link sets, event arrays)
    links = [VID + "1", VID + "1", VID + "2", NOVID + "3", VID + "2"]
    scenarios.append(("link_dedup_and_novid", _from_deltas(
        [1.0, 20.0, 200.0, 10.0, 60.0], mon14, links=links), ()))

    # 9. exclude_hours param drops the 14:00 hour entirely
    scenarios.append(("exclude_hours_14", _from_deltas([60.0, 60.0], mon14), (14,)))

    # 10. Weekday spread (Mon..Sun) for weekly_heatmap encoding. Distinct count
    #     per weekday (Mon=1 linger .. Sun=7) so a day-relabeling bug can't hide
    #     behind a symmetric all-days-equal histogram.
    wk = []
    for day_offset in range(7):
        d0 = datetime(2024, 3, 11, 12, 0, 0) + timedelta(days=day_offset)
        for k in range(day_offset + 2):  # day_offset+1 lingers (60s apart) that day
            wk.append(_entry(d0 + timedelta(seconds=60 * k), VID + f"d{day_offset}_{k}"))
    wk.append(_entry(datetime(2024, 3, 18, 12, 0, 0), ""))
    scenarios.append(("weekday_spread", wk, ()))

    # 11. Empty history
    scenarios.append(("empty", [], ()))

    # 12. WP-1.4 temporal: >=90 day span -> MONTH granularity, distinct per-month
    #     bucket mix (month i has 1 graveyard + (i+1) lingers). Cross-month jumps
    #     are >1200s => sleep_scrubbed, so they don't pollute period_data.
    ms = []
    for i, mo in enumerate([1, 2, 3, 4, 5]):
        base = datetime(2024, mo, 10, 12, 0, 0)
        ms += _from_deltas([1.0] + [60.0] * (i + 1), base)[:-1]
    ms.append(_entry(datetime(2024, 5, 20, 12, 0, 0), ""))  # span Jan10..May20 = 131d
    scenarios.append(("temporal_month_span", ms, ()))

    # 13. WP-1.4 temporal: <90 day span -> WEEK granularity, crossing the 2024->2025
    #     year boundary. Monday-anchored week keys mean 2025-01-01 (Wed) belongs to
    #     the week starting 2024-12-30 — the exact ISO week-year edge a naive port
    #     would miss. Each date: 2 lingers + 1 skip.
    yb = []
    for base in (datetime(2024, 12, 28, 12, 0, 0), datetime(2024, 12, 30, 12, 0, 0),
                 datetime(2025, 1, 1, 12, 0, 0), datetime(2025, 1, 6, 12, 0, 0)):
        yb += _from_deltas([60.0, 60.0, 1.0], base)[:-1]
    yb.append(_entry(datetime(2025, 1, 6, 13, 0, 0), ""))
    scenarios.append(("temporal_week_year_boundary", yb, ()))

    return scenarios


def _jsonable(out: dict) -> dict:
    """Sets aren't JSON-serializable and their order is meaningless — sort to lists."""
    result = {}
    for k, v in out.items():
        if isinstance(v, set):
            result[k] = sorted(v)
        else:
            result[k] = v
    return result


def main():
    cases = []
    for name, history, exclude in build_scenarios():
        out = _run_stopwatch(history, exclude_hours=exclude)
        cases.append({
            "name": name,
            "input": {"history": history, "exclude_hours": list(exclude)},
            "expected": _jsonable(out),
        })

    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 stopwatch port. "
                    "Generated from the frozen Python oracle (api.ghost_profile._run_stopwatch). "
                    "Regenerate ONLY on an intentional Python change: "
                    "python3 scripts/gen_stopwatch_parity_fixture.py",
        "oracle": "api.ghost_profile._run_stopwatch",
        "cases": cases,
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "stopwatch_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(cases)} cases → {out_path}")


if __name__ == "__main__":
    main()
