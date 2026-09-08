# scripts/calibrate_from_corpus.py
"""Offline corpus calibration — reduce a large TikTok video corpus to a few hundred
numbers we can commit and ship.

This never runs in the app and never touches user data. It is an author-side pass
over a public research corpus (e.g. kuben-developer/tiktok-videos-4b on HuggingFace,
27 zstd parquet files, ~289 GB) that emits data/corpus_calibration.json.

What it measures, and why:

  duration histogram   Our stopwatch (api/ghost_profile.py) buckets a watch into
                       skip/sandbox/linger from the *gap* between consecutive
                       history timestamps, with no idea how long the video was.
                       A duration distribution converts any gap into a completion
                       rate, which is the signal the platform itself optimises for.

  view weighting       A watch history is drawn from what the feed *serves*, not
                       from what creators *post*. Weighting each duration by its
                       view count approximates the distribution a viewer actually
                       encounters. Both weightings are emitted so the difference
                       stays auditable; the derivation pass uses view-weighted.

  ad rate              Population baseline for "what share of a feed is sponsored",
                       which the Transparency Gap narrative currently cannot source.

  hashtag priors       Caption hashtag frequencies, for topic inference that today
                       depends on rate-limited per-video oEmbed titles.

Only aggregates leave this script. No content_id, no caption text, no row-level
data is written to the output, so the committed artefact is not personal data.

Run:
    pip install -r requirements-calibration.txt

    # a single 10 GB file is enough for a first pass (~167M videos)
    python3 scripts/calibrate_from_corpus.py 'videos-00.parquet'

    # or the whole corpus
    python3 scripts/calibrate_from_corpus.py 'videos-*.parquet'

    # or straight off HuggingFace without downloading
    python3 scripts/calibrate_from_corpus.py \
        'hf://datasets/kuben-developer/tiktok-videos-4b/videos-*.parquet'
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "data", "corpus_calibration.json")

# Durations at or above this are lumped into a single tail bucket. TikTok allows
# far longer posts, but the stopwatch's own ceiling is 300s (see ghost_profile's
# `abandoned` bucket), so per-second resolution past 10 minutes buys nothing.
MAX_DURATION_S = 600

# Hashtags rarer than this share of captions are dropped — a long tail of
# single-use tags would dominate the file size and generalise to nothing.
HASHTAG_MIN_SHARE = 1e-6
HASHTAG_TOP_N = 2000


def _filter_clause(languages: list[str], countries: list[str]) -> tuple[str, list]:
    """Build an optional locale filter as SQL text + bound parameters.

    Values are always bound, never interpolated into the statement, so a locale
    code from the command line cannot alter the query.
    """
    clauses, params = [], []
    if languages:
        clauses.append("language IN (" + ",".join("?" * len(languages)) + ")")
        params.extend(languages)
    if countries:
        clauses.append("country IN (" + ",".join("?" * len(countries)) + ")")
        params.extend(countries)
    return (" AND ".join(clauses) if clauses else "TRUE"), params


def _connect():
    try:
        import duckdb
    except ImportError:
        sys.exit(
            "duckdb is not installed.\n"
            "  pip install -r requirements-calibration.txt"
        )
    con = duckdb.connect()
    # hf:// and s3:// globs need the httpfs extension; harmless if already present.
    try:
        con.execute("INSTALL httpfs; LOAD httpfs;")
    except Exception:
        pass  # local paths work without it
    return con


def _scalar(con, sql: str, params: list):
    return con.execute(sql, params).fetchone()


def collect_totals(con, glob: str, where: str = "TRUE", wparams: list | None = None) -> dict:
    """Corpus-wide counts. One pass, no grouping."""
    row = _scalar(con, f"""
        SELECT
            count(*)                                        AS videos,
            sum(is_video)                                   AS video_posts,
            sum(views)                                      AS total_views,
            sum(is_ad)                                      AS ad_posts,
            sum(CASE WHEN is_ad = 1 THEN views ELSE 0 END)  AS ad_views,
            count("desc")                                   AS captions_present,
            sum(CASE WHEN "desc" IS NOT NULL AND length(trim("desc")) > 0
                     THEN 1 ELSE 0 END)                     AS captions_nonempty,
            -- cast in SQL: handing a tz-aware timestamp back to Python makes
            -- DuckDB require pytz, which this script otherwise does not need
            CAST(min(create_time) AS VARCHAR)               AS first_post,
            CAST(max(create_time) AS VARCHAR)               AS last_post
        FROM read_parquet(?)
        WHERE {where}
    """, [glob, *(wparams or [])])
    (videos, video_posts, total_views, ad_posts, ad_views,
     captions_present, captions_nonempty, first_post, last_post) = row
    return {
        "videos": int(videos or 0),
        "video_posts": int(video_posts or 0),
        "photo_posts": int((videos or 0) - (video_posts or 0)),
        "total_views": int(total_views or 0),
        # Two different questions: what share of posts are ads, vs what share of
        # *impressions* are ads. The second is what a viewer experiences.
        "ad_share_of_posts": _ratio(ad_posts, videos),
        "ad_share_of_views": _ratio(ad_views, total_views),
        # Captions are frequently blank in this corpus, so hashtag priors rest on
        # a much smaller base than the row count suggests. Record the base.
        "captions_present": int(captions_present or 0),
        "captions_nonempty": int(captions_nonempty or 0),
        "caption_nonempty_share": _ratio(captions_nonempty, videos),
        "create_time_min": _iso(first_post),
        "create_time_max": _iso(last_post),
    }


def collect_duration_histogram(con, glob: str, where: str = "TRUE", wparams: list | None = None) -> dict:
    """Per-second duration counts, unweighted and view-weighted.

    Photo posts (is_video = 0) are excluded: their `duration` is not a watch
    length and would pull the distribution toward zero.
    """
    rows = con.execute(f"""
        SELECT
            least(duration, ?)  AS d,
            count(*)            AS n,
            sum(views)          AS v
        FROM read_parquet(?)
        WHERE is_video = 1 AND duration > 0 AND {where}
        GROUP BY 1
        ORDER BY 1
    """, [MAX_DURATION_S, glob, *(wparams or [])]).fetchall()

    by_post, by_view = {}, {}
    for d, n, v in rows:
        by_post[int(d)] = int(n or 0)
        by_view[int(d)] = int(v or 0)
    return {
        "max_duration_s": MAX_DURATION_S,
        "note": (
            f"Per-second counts for is_video=1 posts. Durations >= {MAX_DURATION_S}s "
            f"are collapsed into the {MAX_DURATION_S} bucket."
        ),
        "by_post": by_post,
        "by_view": by_view,
    }


def collect_locale(con, glob: str, top_n: int = 25) -> dict:
    """Top languages and countries, by posts and by views.

    This is the bias check. The corpus is a sample of global TikTok, and its
    language mix need not resemble the mix any given user's feed serves. If the
    corpus is overwhelmingly a locale your users are not in, the duration
    distribution it yields may not describe their feed — compare these shares
    against your audience before trusting an uncalibrated global run, or re-run
    with --language to calibrate against a matching slice.

    TikTok's own `language` labels are inferred and often "un" (unknown); they
    are recorded here as-is, not treated as ground truth.
    """
    def _top(col):
        rows = con.execute(f"""
            SELECT {col} AS k, count(*) AS n, sum(views) AS v
            FROM read_parquet(?)
            WHERE {col} IS NOT NULL
            GROUP BY 1 ORDER BY n DESC LIMIT ?
        """, [glob, top_n]).fetchall()
        return [{"code": k, "posts": int(n or 0), "views": int(v or 0)} for k, n, v in rows]

    return {"language": _top("language"), "country": _top("country")}


def collect_hashtags(con, glob: str, where: str = "TRUE", wparams: list | None = None) -> dict:
    """Hashtag frequency from captions, unweighted and view-weighted.

    regexp_extract_all pulls every #tag from `desc`; unnest explodes them so each
    tag is counted once per caption it appears in. Only the tag token is kept —
    no caption text reaches the output.
    """
    # "desc" is quoted throughout: it is a SQL reserved word (ORDER BY ... DESC)
    # and an unquoted reference is a parser error, not a column. The regex braces
    # are doubled because this is an f-string — \p{{L}} reaches DuckDB as \p{L}.
    rows = con.execute(f"""
        WITH tagged AS (
            SELECT
                lower(unnest(regexp_extract_all("desc", '#[\\p{{L}}\\p{{N}}_]+'))) AS tag,
                views
            FROM read_parquet(?)
            WHERE "desc" IS NOT NULL AND "desc" LIKE '%#%' AND {where}
        )
        SELECT tag, count(*) AS n, sum(views) AS v
        FROM tagged
        GROUP BY 1
        ORDER BY n DESC
        LIMIT ?
    """, [glob, *(wparams or []), HASHTAG_TOP_N]).fetchall()

    captions = _scalar(con, f"""
        SELECT count(*) FROM read_parquet(?)
        WHERE "desc" IS NOT NULL AND "desc" LIKE '%#%' AND {where}
    """, [glob, *(wparams or [])])[0] or 0

    out = []
    for tag, n, v in rows:
        share = _ratio(n, captions)
        if share is not None and share < HASHTAG_MIN_SHARE:
            continue
        out.append({
            "tag": tag.lstrip("#"),
            "captions": int(n or 0),
            "caption_share": share,
            "views": int(v or 0),
        })
    return {"captions_with_hashtags": int(captions), "top": out}


def _ratio(num, den) -> float | None:
    if not den:
        return None
    return round(float(num or 0) / float(den), 8)


def _iso(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    return str(v)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("glob", help="parquet path or glob (local, hf:// or s3://)")
    ap.add_argument("-o", "--out", default=DEFAULT_OUT, help=f"output JSON (default: {DEFAULT_OUT})")
    ap.add_argument("--source", default="", help="corpus name recorded in the output provenance")
    ap.add_argument("--skip-hashtags", action="store_true",
                    help="skip the caption pass (much slower than the numeric ones)")
    ap.add_argument("--language", action="append", default=[], metavar="CODE",
                    help="restrict to these TikTok language labels (repeatable), "
                         "e.g. --language en. Use when the global corpus mix does "
                         "not resemble your audience")
    ap.add_argument("--country", action="append", default=[], metavar="CC",
                    help="restrict to these two-letter country codes (repeatable)")
    args = ap.parse_args(argv)

    where, wparams = _filter_clause(args.language, args.country)
    con = _connect()

    print(f"[1/4] totals over {args.glob} ...", flush=True)
    totals = collect_totals(con, args.glob, where, wparams)
    if not totals["videos"]:
        raise SystemExit("no rows matched — check the glob and any --language/--country filter")

    print("[2/4] duration histogram ...", flush=True)
    durations = collect_duration_histogram(con, args.glob, where, wparams)

    print("[3/4] locale mix ...", flush=True)
    locale = collect_locale(con, args.glob)

    hashtags = None
    if not args.skip_hashtags:
        print("[4/4] hashtag frequencies ...", flush=True)
        hashtags = collect_hashtags(con, args.glob, where, wparams)
    else:
        print("[4/4] hashtags skipped", flush=True)

    payload = {
        "schema_version": 1,
        "generated_utc": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
        "source": {
            "glob": args.glob,
            "name": args.source,
            "caveats": [
                "Coverage is a sample, not a census; the corpus is a subset of TikTok.",
                "The corpus is hash-partitioned on creator ID, so coverage is "
                "all-or-nothing per creator rather than uniformly random.",
                "Engagement counts are a single snapshot, not a time series; older "
                "posts have had longer to accumulate views.",
            ],
        },
        "filter": {"language": args.language, "country": args.country},
        "totals": totals,
        "durations": durations,
        # Always the unfiltered mix, so a filtered run still records what slice
        # of the corpus it took.
        "locale_mix": locale,
    }
    if hashtags is not None:
        payload["hashtags"] = hashtags

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=False)
        f.write("\n")

    print(f"wrote {args.out}: {totals['videos']:,} videos, "
          f"{len(durations['by_post'])} duration buckets"
          + (f", {len(hashtags['top'])} hashtags" if hashtags else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
