# scripts/derive_thresholds.py
"""Turn a corpus duration distribution into stopwatch thresholds — and audit the
ones we currently ship.

Background
----------
api/ghost_profile.py buckets each watched video by the *gap* to the next history
entry, against four hand-picked cutoffs:

    delta <   3s  -> graveyard (skip)
    delta <=  15s -> sandbox
    delta <= 180s -> linger
    delta <= 300s -> deep_dive
    else          -> abandoned

Those are round numbers, not measurements. Given a corpus duration distribution
(from scripts/calibrate_from_corpus.py) we can say what each cutoff *means* as a
completion rate, and pick cutoffs that sit at stated completion percentiles
instead. Completion is what the platform's own ranker optimises for, so it is the
defensible unit to reason in.

The model
---------
Let D be the duration of a video drawn from the corpus, weighted by views (a
watch history is drawn from what the feed serves, not from what creators post).
For a gap of g seconds:

    completion(g)  = E[ min(g, D) / D ]   expected fraction of the video watched
    completed(g)   = P( D <= g )          share of videos watched fully at least once
    loops(g)       = E[ g / D ]           average passes through the video

completion(g) is monotonic in g, so each target inverts to a unique cutoff.

Run:
    python3 scripts/derive_thresholds.py                    # audit + propose
    python3 scripts/derive_thresholds.py --weight by_post   # compare weightings
    python3 scripts/derive_thresholds.py --write            # emit the JSON
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_IN = os.path.join(ROOT, "data", "corpus_calibration.json")
DEFAULT_OUT = os.path.join(ROOT, "data", "stopwatch_calibration.json")

# The cutoffs api/ghost_profile.py ships today, for the audit column.
CURRENT = {"graveyard": 3, "sandbox": 15, "linger": 180, "deep_dive": 300}

# Where we propose to put each boundary, in completion terms. These are the
# judgement calls in this file; everything else is measurement.
#
#   graveyard  a glance. Under a quarter of the video seen.
#   sandbox    watched, but not through. Boundary at one full pass of the
#              median served video.
#   linger     through at least once, for most of the corpus.
#   deep_dive  longer than almost any single video, so the excess time is
#              re-watching rather than watching.
#
# Ordering is guaranteed, not hoped for. completed(g) <= completion(g) for every
# g (a video with D <= g adds 1 to both; one with D > g adds 0 to completed but
# g/D > 0 to completion), so the completion-0.25 cutoff never exceeds the
# completed-0.25 cutoff, and completed is monotonic, so 0.50 <= 0.90 <= 0.99
# yields a non-decreasing ladder on any corpus.
#
# An earlier draft anchored deep_dive on loops >= 3, which inverted the ladder on
# a short-video corpus: three passes of an 18s video is 54s, below the linger
# cutoff. Loops is kept as a reported diagnostic, not an anchor.
TARGETS = {
    "graveyard": {"metric": "completion", "value": 0.25,
                  "means": "under a quarter of the video seen"},
    "sandbox":   {"metric": "completed",  "value": 0.50,
                  "means": "half the corpus watched through at least once"},
    "linger":    {"metric": "completed",  "value": 0.90,
                  "means": "nine in ten videos watched through at least once"},
    "deep_dive": {"metric": "completed",  "value": 0.99,
                  "means": "longer than 99% of videos run, so the rest is re-watching"},
}

# The engine's buckets are ordered bands; a ladder that is not strictly
# increasing would leave a bucket that can never fire.
LADDER = ["graveyard", "sandbox", "linger", "deep_dive"]

# Upper bound for the inverse scan. Past ghost_profile's SLEEP_THRESHOLD_S (1200s)
# a gap is treated as AFK, so a derived cutoff above it would never fire.
SCAN_MAX_S = 1200


def load_pmf(cal: dict, weight: str) -> dict[int, float]:
    """Duration probability mass function from the committed histogram."""
    hist = cal["durations"][weight]
    total = sum(hist.values())
    if not total:
        raise SystemExit(f"duration histogram '{weight}' is empty")
    return {int(d): n / total for d, n in hist.items() if int(d) > 0}


def completion(pmf: dict[int, float], g: float) -> float:
    """E[min(g,D)/D] — expected fraction of the video watched."""
    return sum(p * min(g, d) / d for d, p in pmf.items())


def completed(pmf: dict[int, float], g: float) -> float:
    """P(D <= g) — share of videos fully watched at least once."""
    return sum(p for d, p in pmf.items() if d <= g)


def loops(pmf: dict[int, float], g: float) -> float:
    """E[g/D] — average passes through the video."""
    return sum(p * g / d for d, p in pmf.items())


_METRICS = {"completion": completion, "completed": completed, "loops": loops}


def percentile(pmf: dict[int, float], q: float) -> int:
    """Smallest duration d with P(D <= d) >= q."""
    acc = 0.0
    for d in sorted(pmf):
        acc += pmf[d]
        if acc >= q:
            return d
    return max(pmf)


def invert(pmf: dict[int, float], metric: str, target: float) -> int | None:
    """Smallest whole-second gap g where metric(g) >= target.

    All three metrics are non-decreasing in g, so a linear scan finds the unique
    boundary. Returns None if the target is unreachable inside SCAN_MAX_S.
    """
    fn = _METRICS[metric]
    for g in range(1, SCAN_MAX_S + 1):
        if fn(pmf, g) >= target:
            return g
    return None


def describe(pmf: dict[int, float], g: float) -> dict:
    """All three metrics at one gap — the audit row for a cutoff."""
    return {
        "gap_s": g,
        "completion": round(completion(pmf, g), 4),
        "completed_share": round(completed(pmf, g), 4),
        "loops": round(loops(pmf, g), 3),
    }


def derive(cal: dict, weight: str) -> dict:
    pmf = load_pmf(cal, weight)

    proposed, audit = {}, {}
    for bucket, spec in TARGETS.items():
        g = invert(pmf, spec["metric"], spec["value"])
        proposed[bucket] = {
            "gap_s": g,
            "target_metric": spec["metric"],
            "target_value": spec["value"],
            "means": spec["means"],
            "unreachable": g is None,
            **({} if g is None else {"at_cutoff": describe(pmf, g)}),
        }
        audit[bucket] = {"current_gap_s": CURRENT[bucket], **describe(pmf, CURRENT[bucket])}

    gaps = [proposed[b]["gap_s"] for b in LADDER]
    concrete = [g for g in gaps if g is not None]
    ladder_valid = concrete == sorted(concrete) and len(set(concrete)) == len(concrete)

    return {
        "schema_version": 1,
        "generated_utc": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
        "weighting": weight,
        # utils.calibration refuses a non-increasing ladder; say so here too, so a
        # bad run is visible at derivation rather than silently ignored at load.
        "ladder_valid": ladder_valid,
        "corpus": {
            "source": cal.get("source", {}),
            "generated_utc": cal.get("generated_utc"),
            "videos": cal.get("totals", {}).get("videos"),
            "total_views": cal.get("totals", {}).get("total_views"),
        },
        "duration_percentiles_s": {
            f"p{int(q * 100)}": percentile(pmf, q)
            for q in (0.10, 0.25, 0.50, 0.75, 0.90, 0.99)
        },
        "ad_baseline": {
            "share_of_posts": cal.get("totals", {}).get("ad_share_of_posts"),
            "share_of_views": cal.get("totals", {}).get("ad_share_of_views"),
        },
        "current_thresholds_audit": audit,
        "proposed_thresholds": proposed,
    }


def report(d: dict) -> str:
    """Human-readable summary — the thing worth pasting into a spec."""
    L = []
    src = d["corpus"].get("source", {}).get("name") or d["corpus"].get("source", {}).get("glob", "?")
    videos = d["corpus"].get("videos")
    L.append(f"corpus     {src}")
    L.append(f"           {videos:,} videos, weighting = {d['weighting']}" if videos else
             f"           weighting = {d['weighting']}")
    pct = d["duration_percentiles_s"]
    L.append("duration   " + "  ".join(f"{k}={v}s" for k, v in pct.items()))
    ad = d["ad_baseline"]
    if ad.get("share_of_views") is not None:
        L.append(f"ads        {ad['share_of_views'] * 100:.2f}% of views, "
                 f"{(ad.get('share_of_posts') or 0) * 100:.2f}% of posts")
    L.append("")
    L.append("what today's cutoffs actually mean")
    L.append(f"  {'bucket':<11}{'gap':>7}{'completion':>13}{'watched thru':>14}{'loops':>8}")
    for b, a in d["current_thresholds_audit"].items():
        L.append(f"  {b:<11}{str(a['current_gap_s']) + 's':>7}"
                 f"{a['completion'] * 100:>12.1f}%{a['completed_share'] * 100:>13.1f}%"
                 f"{a['loops']:>8.2f}")
    L.append("")
    L.append("proposed cutoffs, anchored on completion")
    L.append(f"  {'bucket':<11}{'now':>6}{'->':>4}{'new':>6}   anchor")
    for b, p in d["proposed_thresholds"].items():
        new = "n/a" if p["gap_s"] is None else f"{p['gap_s']}s"
        L.append(f"  {b:<11}{str(CURRENT[b]) + 's':>6}{'->':>4}{new:>6}   {p['means']}")
    if not d.get("ladder_valid", True):
        L.append("")
        L.append("  WARNING: the proposed cutoffs are not strictly increasing, so at")
        L.append("  least one bucket could never fire. utils.calibration will refuse")
        L.append("  this file and keep the shipped thresholds.")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-i", "--input", default=DEFAULT_IN, help=f"calibration JSON (default: {DEFAULT_IN})")
    ap.add_argument("-o", "--out", default=DEFAULT_OUT, help=f"output JSON (default: {DEFAULT_OUT})")
    ap.add_argument("--weight", choices=("by_view", "by_post"), default="by_view",
                    help="by_view models what a feed serves (default); by_post what creators upload")
    ap.add_argument("--write", action="store_true", help="write the JSON as well as printing the report")
    args = ap.parse_args(argv)

    if not os.path.exists(args.input):
        raise SystemExit(
            f"{args.input} not found — run scripts/calibrate_from_corpus.py first."
        )
    with open(args.input) as f:
        cal = json.load(f)

    derived = derive(cal, args.weight)
    print(report(derived))

    if args.write:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(derived, f, indent=2)
            f.write("\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
