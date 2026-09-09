"""utils.calibration — the fallback contract.

The loader must never raise and never block analysis, so every degenerate file
shape has to land on the shipped thresholds rather than an exception.
"""
import json

import pytest

from utils import calibration as cal


def _write(tmp_path, payload):
    p = tmp_path / "stopwatch_calibration.json"
    p.write_text(json.dumps(payload) if not isinstance(payload, str) else payload)
    return str(p)


def _valid(**overrides):
    body = {
        "schema_version": 1,
        "generated_utc": "2026-09-08T00:00:00+00:00",
        "weighting": "by_view",
        "corpus": {"videos": 4501800000, "source": {"name": "tiktok-videos-4b", "caveats": ["sample, not census"]}},
        "proposed_thresholds": {
            "graveyard": {"gap_s": 5},
            "sandbox": {"gap_s": 21},
            "linger": {"gap_s": 95},
            "deep_dive": {"gap_s": 240},
        },
    }
    body.update(overrides)
    return body


def test_missing_file_yields_the_shipped_thresholds(tmp_path):
    path = str(tmp_path / "absent.json")
    assert cal.thresholds(path) == cal.FALLBACK_THRESHOLDS
    assert cal.is_calibrated(path) is False


def test_a_valid_calibration_overrides_every_bucket(tmp_path):
    path = _write(tmp_path, _valid())
    assert cal.thresholds(path) == {"graveyard": 5, "sandbox": 21, "linger": 95, "deep_dive": 240}
    assert cal.is_calibrated(path) is True


def test_malformed_json_falls_back_instead_of_raising(tmp_path):
    assert cal.thresholds(_write(tmp_path, "{not json")) == cal.FALLBACK_THRESHOLDS


def test_unknown_schema_version_is_refused(tmp_path):
    path = _write(tmp_path, _valid(schema_version=99))
    assert cal.thresholds(path) == cal.FALLBACK_THRESHOLDS


def test_a_partial_calibration_degrades_one_bucket_at_a_time(tmp_path):
    path = _write(tmp_path, _valid(proposed_thresholds={"sandbox": {"gap_s": 21}}))
    assert cal.thresholds(path) == {**cal.FALLBACK_THRESHOLDS, "sandbox": 21}


def test_an_unreachable_target_keeps_its_shipped_value(tmp_path):
    # derive_thresholds serialises an unreachable target as gap_s: null
    path = _write(tmp_path, _valid(proposed_thresholds={
        "graveyard": {"gap_s": 5}, "deep_dive": {"gap_s": None, "unreachable": True},
    }))
    t = cal.thresholds(path)
    assert t["graveyard"] == 5
    assert t["deep_dive"] == cal.FALLBACK_THRESHOLDS["deep_dive"]


@pytest.mark.parametrize("bad", [0, -4, "12", True, None])
def test_non_positive_or_wrong_typed_gaps_are_ignored(tmp_path, bad):
    path = _write(tmp_path, _valid(proposed_thresholds={"sandbox": {"gap_s": bad}}))
    assert cal.thresholds(path)["sandbox"] == cal.FALLBACK_THRESHOLDS["sandbox"]


def test_out_of_order_thresholds_are_refused_wholesale(tmp_path):
    # linger below sandbox would make the sandbox band unreachable
    path = _write(tmp_path, _valid(proposed_thresholds={
        "graveyard": {"gap_s": 5}, "sandbox": {"gap_s": 90},
        "linger": {"gap_s": 20}, "deep_dive": {"gap_s": 240},
    }))
    assert cal.thresholds(path) == cal.FALLBACK_THRESHOLDS


def test_duplicate_thresholds_are_refused(tmp_path):
    path = _write(tmp_path, _valid(proposed_thresholds={
        "graveyard": {"gap_s": 15}, "sandbox": {"gap_s": 15},
        "linger": {"gap_s": 95}, "deep_dive": {"gap_s": 240},
    }))
    assert cal.thresholds(path) == cal.FALLBACK_THRESHOLDS


def test_unknown_buckets_are_ignored(tmp_path):
    path = _write(tmp_path, _valid(proposed_thresholds={
        **_valid()["proposed_thresholds"], "teleport": {"gap_s": 7},
    }))
    assert set(cal.thresholds(path)) == set(cal.FALLBACK_THRESHOLDS)


def test_provenance_carries_the_corpus_caveats(tmp_path):
    p = cal.provenance(_write(tmp_path, _valid()))
    assert p["calibrated"] is True
    assert p["corpus_name"] == "tiktok-videos-4b"
    assert p["weighting"] == "by_view"
    assert "sample, not census" in p["caveats"]


def test_provenance_is_honest_when_uncalibrated(tmp_path):
    p = cal.provenance(str(tmp_path / "absent.json"))
    assert p["calibrated"] is False
    assert p["thresholds"] == cal.FALLBACK_THRESHOLDS
    assert "Hand-picked" in p["basis"]
