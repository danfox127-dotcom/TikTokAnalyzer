"""Read the committed stopwatch calibration, if there is one.

Produced by scripts/calibrate_from_corpus.py -> scripts/derive_thresholds.py.

Nothing in the live analyse path imports this yet — it is the seam for wiring
corpus-derived thresholds into api/ghost_profile.py, and it exists so that the
risky half of that wiring (what happens when the file is absent, stale or
malformed) is settled and tested first.

The contract is that this module never raises and never blocks analysis. With no
calibration file, `thresholds()` returns exactly the values ghost_profile ships
today, so adopting it is a no-op until a calibration is committed.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALIBRATION_PATH = os.environ.get(
    "STOPWATCH_CALIBRATION_PATH",
    os.path.join(ROOT, "data", "stopwatch_calibration.json"),
)

# The cutoffs api/ghost_profile.py hard-codes today. Duplicated deliberately: this
# module must answer with the shipped behaviour when there is nothing to load,
# without importing the engine it is meant to feed.
FALLBACK_THRESHOLDS = {"graveyard": 3, "sandbox": 15, "linger": 180, "deep_dive": 300}

SUPPORTED_SCHEMA = 1

_cache: Optional[dict] = None
_loaded = False


def load(path: str | None = None, *, refresh: bool = False) -> Optional[dict]:
    """Parse the calibration file, or return None if it is unusable.

    Result is memoised; pass refresh=True after regenerating the file in-process.
    """
    global _cache, _loaded
    if _loaded and not refresh and path is None:
        return _cache

    target = path or CALIBRATION_PATH
    parsed: Optional[dict] = None
    try:
        with open(target) as f:
            data = json.load(f)
        if data.get("schema_version") != SUPPORTED_SCHEMA:
            logger.warning(
                "calibration %s has schema_version %r, expected %r — ignoring",
                target, data.get("schema_version"), SUPPORTED_SCHEMA,
            )
        elif not isinstance(data.get("proposed_thresholds"), dict):
            logger.warning("calibration %s has no proposed_thresholds — ignoring", target)
        else:
            parsed = data
    except FileNotFoundError:
        logger.debug("no calibration at %s; using shipped thresholds", target)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("calibration %s unreadable (%s) — using shipped thresholds", target, e)

    if path is None:
        _cache, _loaded = parsed, True
    return parsed


def is_calibrated(path: str | None = None) -> bool:
    return thresholds(path) != FALLBACK_THRESHOLDS


def thresholds(path: str | None = None) -> dict[str, int]:
    """Bucket -> gap cutoff in seconds.

    Any bucket the calibration does not supply a usable value for keeps its
    shipped default, so a partial calibration degrades one bucket at a time
    rather than all of them.
    """
    data = load(path)
    out = dict(FALLBACK_THRESHOLDS)
    if not data:
        return out

    for bucket, spec in (data.get("proposed_thresholds") or {}).items():
        if bucket not in out or not isinstance(spec, dict):
            continue
        gap = spec.get("gap_s")
        # `unreachable` targets serialise as null; keep the shipped value there.
        if isinstance(gap, (int, float)) and not isinstance(gap, bool) and gap > 0:
            out[bucket] = int(gap)

    # The engine's buckets are ordered bands. A calibration that inverts them
    # would silently produce empty buckets, so refuse it wholesale.
    order = ["graveyard", "sandbox", "linger", "deep_dive"]
    values = [out[b] for b in order]
    if values != sorted(values) or len(set(values)) != len(values):
        logger.warning("calibrated thresholds are not strictly increasing (%s) — "
                       "falling back to shipped values", out)
        return dict(FALLBACK_THRESHOLDS)
    return out


def provenance(path: str | None = None) -> dict[str, Any]:
    """Where the numbers came from, for the `provenance` field on narrative blocks.

    Every insight in this project states which data produced it; a threshold
    derived from an external corpus has to carry that corpus's caveats with it.
    """
    data = load(path)
    if not data:
        return {
            "calibrated": False,
            "basis": "Hand-picked thresholds; no corpus calibration committed.",
            "thresholds": dict(FALLBACK_THRESHOLDS),
        }
    corpus = data.get("corpus") or {}
    source = corpus.get("source") or {}
    return {
        "calibrated": True,
        "basis": "Thresholds derived from the duration distribution of a public "
                 "TikTok corpus, weighted by view count.",
        "thresholds": thresholds(path),
        "weighting": data.get("weighting"),
        "corpus_name": source.get("name") or source.get("glob"),
        "corpus_videos": corpus.get("videos"),
        "generated_utc": data.get("generated_utc"),
        "caveats": source.get("caveats") or [],
    }
