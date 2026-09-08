"""Corpus calibration + threshold derivation.

The derivation maths is tested against a hand-computable distribution; the DuckDB
pass is tested end-to-end against a synthetic parquet corpus with a known answer,
so neither test needs the real 289 GB dataset.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import derive_thresholds as dt  # noqa: E402

pa = pytest.importorskip("pyarrow", reason="calibration extras not installed")
pq = pytest.importorskip("pyarrow.parquet", reason="calibration extras not installed")
pytest.importorskip("duckdb", reason="calibration extras not installed")

import calibrate_from_corpus as cc  # noqa: E402


# --------------------------------------------------------------------------
# derivation maths — a two-point distribution with arithmetic we can do by hand
# --------------------------------------------------------------------------

# Half the corpus is 10s long, half is 30s.
PMF = {10: 0.5, 30: 0.5}


def test_completion_is_a_weighted_mean_of_fractions():
    # at 10s: the 10s videos are complete (1.0), the 30s ones are a third seen
    assert dt.completion(PMF, 10) == pytest.approx(0.5 * 1.0 + 0.5 * (10 / 30))
    # past the longest video everything is complete
    assert dt.completion(PMF, 30) == pytest.approx(1.0)
    assert dt.completion(PMF, 100) == pytest.approx(1.0)


def test_completion_is_monotonic_so_inversion_is_unique():
    vals = [dt.completion(PMF, g) for g in range(1, 60)]
    assert vals == sorted(vals)


def test_completed_share_is_a_step_function_at_each_duration():
    assert dt.completed(PMF, 9) == pytest.approx(0.0)
    assert dt.completed(PMF, 10) == pytest.approx(0.5)
    assert dt.completed(PMF, 29) == pytest.approx(0.5)
    assert dt.completed(PMF, 30) == pytest.approx(1.0)


def test_loops_counts_passes_through_and_exceeds_one():
    # 60s spent: six passes of a 10s video, two of a 30s
    assert dt.loops(PMF, 60) == pytest.approx(0.5 * 6 + 0.5 * 2)


def test_invert_finds_the_first_second_meeting_the_target():
    g = dt.invert(PMF, "completed", 0.5)
    assert g == 10
    assert dt.completed(PMF, g) >= 0.5
    assert dt.completed(PMF, g - 1) < 0.5


def test_invert_returns_none_when_the_target_cannot_be_reached():
    # no finite gap makes completion exceed 1.0
    assert dt.invert(PMF, "completion", 1.5) is None


def test_percentile_reads_off_the_cdf():
    assert dt.percentile(PMF, 0.25) == 10
    assert dt.percentile(PMF, 0.5) == 10
    assert dt.percentile(PMF, 0.75) == 30


def test_derive_audits_current_thresholds_and_proposes_new_ones():
    cal = {
        "durations": {"by_view": {str(d): int(p * 1000) for d, p in PMF.items()}},
        "totals": {"videos": 1000, "ad_share_of_posts": 0.01, "ad_share_of_views": 0.02},
    }
    out = dt.derive(cal, "by_view")

    # every shipped cutoff is audited, at the value ghost_profile actually uses
    assert set(out["current_thresholds_audit"]) == set(dt.CURRENT)
    assert out["current_thresholds_audit"]["graveyard"]["current_gap_s"] == 3
    # a 3s gap on this corpus is a glance, not a watch
    assert out["current_thresholds_audit"]["graveyard"]["completion"] < 0.25

    assert set(out["proposed_thresholds"]) == set(dt.CURRENT)
    assert out["proposed_thresholds"]["sandbox"]["gap_s"] == 10
    assert out["ad_baseline"]["share_of_views"] == 0.02
    # report renders without blowing up on this shape
    assert "proposed cutoffs" in dt.report(out)


def test_derive_rejects_an_empty_histogram():
    with pytest.raises(SystemExit):
        dt.derive({"durations": {"by_view": {}}, "totals": {}}, "by_view")


# --------------------------------------------------------------------------
# DuckDB pass — synthetic corpus, known answer
# --------------------------------------------------------------------------

@pytest.fixture
def corpus(tmp_path):
    """Six rows: four videos, two photo posts, one ad, two hashtagged captions."""
    rows = {
        "content_id": [1, 2, 3, 4, 5, 6],
        "create_time": pa.array(
            ["2025-01-01T00:00:00+00:00", "2025-02-01T00:00:00+00:00",
             "2025-03-01T00:00:00+00:00", "2025-04-01T00:00:00+00:00",
             "2025-05-01T00:00:00+00:00", "2025-06-01T00:00:00+00:00"],
            type=pa.string(),
        ).cast(pa.timestamp("ms", tz="UTC")),
        "desc": ["a #Cats b", "no tags here", "#cats #dogs", "", "#cats", "photo"],
        "duration": [10, 10, 30, 30, 7, 7],
        "is_video": [1, 1, 1, 1, 0, 0],
        "music_id": [100, 100, 200, 300, 400, 500],
        "views": [100, 100, 100, 100, 999, 999],
        "likes": [1, 2, 3, 4, 5, 6],
        "comments": [0, 0, 0, 0, 0, 0],
        "shares": [0, 0, 0, 0, 0, 0],
        "saves": [0, 0, 0, 0, 0, 0],
        "country": ["US"] * 6,
        "language": ["en"] * 6,
        "is_ad": [1, 0, 0, 0, 0, 0],
    }
    path = tmp_path / "videos-00.parquet"
    pq.write_table(pa.table(rows), path)
    return str(path)


def test_totals_split_video_and_photo_posts(corpus):
    con = cc._connect()
    totals = cc.collect_totals(con, corpus)
    assert totals["videos"] == 6
    assert totals["video_posts"] == 4
    assert totals["photo_posts"] == 2
    assert totals["total_views"] == 100 * 4 + 999 * 2
    # one ad in six posts, and its 100 views out of 2398
    assert totals["ad_share_of_posts"] == pytest.approx(1 / 6, abs=1e-6)
    assert totals["ad_share_of_views"] == pytest.approx(100 / 2398, abs=1e-6)


def test_duration_histogram_excludes_photo_posts(corpus):
    con = cc._connect()
    hist = cc.collect_duration_histogram(con, corpus)
    # the 7s photo posts carry the most views but are not watch durations
    assert hist["by_post"] == {10: 2, 30: 2}
    assert hist["by_view"] == {10: 200, 30: 200}
    assert 7 not in hist["by_post"]


def test_duration_histogram_collapses_the_long_tail(tmp_path):
    path = tmp_path / "long.parquet"
    pq.write_table(pa.table({
        "duration": [5, cc.MAX_DURATION_S + 500],
        "is_video": [1, 1],
        "views": [1, 1],
    }), path)
    hist = cc.collect_duration_histogram(cc._connect(), str(path))
    assert set(hist["by_post"]) == {5, cc.MAX_DURATION_S}


def test_hashtags_are_lowercased_counted_and_view_weighted(corpus):
    con = cc._connect()
    tags = cc.collect_hashtags(con, corpus)
    assert tags["captions_with_hashtags"] == 3
    by_tag = {t["tag"]: t for t in tags["top"]}
    # "#Cats" and "#cats" are the same tag
    assert by_tag["cats"]["captions"] == 3
    assert by_tag["dogs"]["captions"] == 1
    # cats appears on rows with 100 + 100 + 999 views
    assert by_tag["cats"]["views"] == 1199
    # no caption text escapes into the artefact
    assert "no tags here" not in json.dumps(tags)


def test_end_to_end_calibrate_then_derive(corpus, tmp_path):
    cal_path = tmp_path / "corpus_calibration.json"
    assert cc.main([corpus, "-o", str(cal_path), "--source", "synthetic"]) == 0

    cal = json.loads(cal_path.read_text())
    assert cal["schema_version"] == 1
    assert cal["source"]["name"] == "synthetic"
    assert cal["source"]["caveats"], "provenance caveats must ship with the numbers"

    derived = dt.derive(cal, "by_view")
    # same 50/50 10s-and-30s shape as the maths fixture above
    assert derived["duration_percentiles_s"]["p50"] == 10
    assert derived["proposed_thresholds"]["sandbox"]["gap_s"] == 10
    assert derived["corpus"]["videos"] == 6


def test_skip_hashtags_omits_the_caption_pass(corpus, tmp_path):
    out = tmp_path / "cal.json"
    assert cc.main([corpus, "-o", str(out), "--skip-hashtags"]) == 0
    assert "hashtags" not in json.loads(out.read_text())


def test_totals_record_the_caption_base_for_hashtag_priors(corpus):
    # Captions are often blank in this corpus, so the hashtag base is much
    # smaller than the row count — the output has to say so.
    totals = cc.collect_totals(cc._connect(), corpus)
    assert totals["captions_nonempty"] == 5  # row 4's "" is present but empty
    assert totals["caption_nonempty_share"] == pytest.approx(5 / 6, abs=1e-6)


def test_locale_mix_is_reported_for_the_bias_check(corpus):
    locale = cc.collect_locale(cc._connect(), corpus)
    assert locale["language"] == [{"code": "en", "posts": 6, "views": 2398}]
    assert locale["country"][0]["code"] == "US"


@pytest.fixture
def mixed_corpus(tmp_path):
    """Two locales with different duration profiles, so a filter changes the answer."""
    path = tmp_path / "mixed.parquet"
    pq.write_table(pa.table({
        "content_id": [1, 2, 3, 4],
        "create_time": pa.array(["2025-01-01T00:00:00+00:00"] * 4,
                                type=pa.string()).cast(pa.timestamp("ms", tz="UTC")),
        "desc": ["#a", "#b", "#c", "#d"],
        "duration": [10, 10, 120, 120],
        "is_video": [1, 1, 1, 1],
        "views": [1, 1, 1, 1],
        "country": ["US", "US", "MM", "MM"],
        "language": ["en", "en", "un", "un"],
        "is_ad": [0, 0, 0, 0],
    }), path)
    return str(path)


def test_language_filter_narrows_the_distribution(mixed_corpus):
    con = cc._connect()
    where, params = cc._filter_clause(["en"], [])
    hist = cc.collect_duration_histogram(con, mixed_corpus, where, params)
    assert hist["by_post"] == {10: 2}, "un-labelled 120s rows should be excluded"

    unfiltered = cc.collect_duration_histogram(con, mixed_corpus)
    assert unfiltered["by_post"] == {10: 2, 120: 2}


def test_country_filter_applies_to_captions_too(mixed_corpus):
    con = cc._connect()
    where, params = cc._filter_clause([], ["MM"])
    tags = cc.collect_hashtags(con, mixed_corpus, where, params)
    assert {t["tag"] for t in tags["top"]} == {"c", "d"}


def test_filter_values_are_bound_not_interpolated():
    # a hostile locale code must land in params, leaving the SQL text inert
    where, params = cc._filter_clause(["en'; DROP TABLE x; --"], [])
    assert where == "language IN (?)"
    assert params == ["en'; DROP TABLE x; --"]


def test_empty_filter_is_a_no_op():
    assert cc._filter_clause([], []) == ("TRUE", [])


def test_filtered_run_records_the_filter_and_the_full_locale_mix(mixed_corpus, tmp_path):
    out = tmp_path / "cal.json"
    assert cc.main([mixed_corpus, "-o", str(out), "--language", "en"]) == 0
    cal = json.loads(out.read_text())

    assert cal["filter"]["language"] == ["en"]
    assert cal["durations"]["by_post"] == {"10": 2}
    # the locale mix stays unfiltered, so the run still shows what it sampled from
    codes = {e["code"] for e in cal["locale_mix"]["language"]}
    assert codes == {"en", "un"}


def test_a_filter_matching_nothing_fails_loudly(mixed_corpus, tmp_path):
    with pytest.raises(SystemExit):
        cc.main([mixed_corpus, "-o", str(tmp_path / "x.json"), "--language", "zz"])


# --------------------------------------------------------------------------
# the ladder must hold on any corpus, not just the ones we happened to try
# --------------------------------------------------------------------------

def _cal_from_durations(durations):
    hist = {}
    for d in durations:
        hist[str(d)] = hist.get(str(d), 0) + 1
    return {"durations": {"by_view": hist}, "totals": {"videos": len(durations)}}


@pytest.mark.parametrize("seed", range(25))
def test_proposed_ladder_is_strictly_increasing_on_random_corpora(seed):
    import random
    rng = random.Random(seed)
    # shapes ranging from all-short to a heavy long tail
    durations = [max(1, int(rng.lognormvariate(rng.uniform(1.5, 4.0), rng.uniform(0.3, 1.4))))
                 for _ in range(4000)]
    out = dt.derive(_cal_from_durations(durations), "by_view")
    gaps = [out["proposed_thresholds"][b]["gap_s"] for b in dt.LADDER]
    concrete = [g for g in gaps if g is not None]
    assert concrete == sorted(concrete), f"ladder inverted: {dict(zip(dt.LADDER, gaps))}"
    assert out["ladder_valid"] is True


def test_completed_never_exceeds_completion():
    # the inequality the ordering guarantee rests on
    import random
    rng = random.Random(0)
    pmf = {}
    for _ in range(200):
        d = rng.randint(1, 400)
        pmf[d] = pmf.get(d, 0) + 1
    total = sum(pmf.values())
    pmf = {d: n / total for d, n in pmf.items()}
    for g in range(1, 500, 7):
        assert dt.completed(pmf, g) <= dt.completion(pmf, g) + 1e-12


def test_a_short_video_corpus_no_longer_inverts_deep_dive():
    # the regression that the loops-based anchor produced: an all-18s corpus
    # put "three passes" (54s) below the 90%-completed cutoff
    out = dt.derive(_cal_from_durations([18] * 100 + [20] * 100), "by_view")
    gaps = [out["proposed_thresholds"][b]["gap_s"] for b in dt.LADDER]
    assert gaps == sorted(gaps)


def test_report_warns_when_the_ladder_is_invalid():
    out = dt.derive(_cal_from_durations([10] * 100), "by_view")
    out["ladder_valid"] = False
    assert "WARNING" in dt.report(out)


def test_view_and_post_weighting_can_disagree(tmp_path):
    """A corpus where short videos get the views must calibrate differently."""
    path = tmp_path / "skew.parquet"
    pq.write_table(pa.table({
        # most posts are long, but the short ones take almost all the impressions
        "duration": [10] * 30 + [200] * 70,
        "is_video": [1] * 100,
        "views": [1000] * 30 + [1] * 70,
    }), path)
    hist = cc.collect_duration_histogram(cc._connect(), str(path))
    cal = {"durations": hist, "totals": {"videos": 100}}

    by_view = dt.derive(cal, "by_view")["duration_percentiles_s"]["p50"]
    by_post = dt.derive(cal, "by_post")["duration_percentiles_s"]["p50"]
    assert by_view == 10, "view weighting should follow what the feed serves"
    assert by_post == 200, "post weighting follows what creators upload"
