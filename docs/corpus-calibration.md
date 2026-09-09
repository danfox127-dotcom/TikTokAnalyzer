# Corpus calibration — grounding the stopwatch in measured video durations

## The problem this solves

`api/ghost_profile.py` decides what a watched video *meant* from one number: the
gap between consecutive entries in the user's watch history. It compares that gap
against four cutoffs:

| bucket | gap | reading |
|---|---|---|
| graveyard | < 3s | skipped |
| sandbox | ≤ 15s | glanced |
| linger | ≤ 180s | engaged |
| deep_dive | ≤ 300s | absorbed |
| abandoned | ≤ 1200s | walked away |

Those cutoffs are absolute, and the engine has no idea how long the video was.
That produces two systematic errors:

- **A 5s gap on a 4s video** is a complete watch, possibly a loop. Scored as a
  near-skip.
- **A 20s gap on a 3-minute video** is bailing at 11%. Scored as engaged linger.

The fix is to express the cutoffs in **completion rate** — the fraction of the
video actually watched — which is the quantity the platform's own ranker
optimises for, and therefore the defensible unit to reason in.

## The approach: measure once, ship constants

We do **not** join user watch history against an external corpus at analyse time.
That would mean shipping tens of gigabytes, or sending video IDs to a server,
which would break the local-only guarantee the product rests on.

Instead the corpus is reduced **once, offline, on a maintainer's machine** to a
few hundred aggregate numbers that are committed to the repo. No row-level data,
no captions, no IDs are retained — so the committed artefact is aggregate
statistics, not personal data.

```
public corpus (~289 GB)
        │  scripts/calibrate_from_corpus.py     (DuckDB, one pass)
        ▼
data/corpus_calibration.json                    duration histogram, ad rate,
        │                                       hashtag priors, locale mix
        │  scripts/derive_thresholds.py         (pure maths, no corpus)
        ▼
data/stopwatch_calibration.json                 audited + proposed cutoffs
        │
        ▼  utils/calibration.py                 loads it, or falls back silently
```

## Running it

```bash
pip install -r requirements-calibration.txt

# One 10 GB file (~167M videos) is plenty for a first pass
python3 scripts/calibrate_from_corpus.py 'videos-00.parquet' --source 'tiktok-videos-4b'

# See what today's cutoffs mean, and what the corpus proposes instead
python3 scripts/derive_thresholds.py

# Commit the derived thresholds
python3 scripts/derive_thresholds.py --write
```

Both scripts accept local paths, globs, `hf://` and `s3://` URIs.

## How the derivation works

Let `D` be the duration of a video drawn from the corpus. For a gap of `g` seconds:

- `completion(g) = E[min(g, D) / D]` — expected fraction of the video watched
- `completed(g) = P(D ≤ g)` — share of videos watched through at least once
- `loops(g) = E[g / D]` — average passes through

Each cutoff is placed by inverting one of these against a stated target. The
targets are the only judgement calls in the pipeline; everything else is
measurement.

**Durations are weighted by view count by default.** A watch history is drawn
from what the feed *serves*, not from what creators *upload*, and the two
distributions differ substantially. Both weightings are emitted so the choice
stays auditable — compare with `--weight by_post`.

**The ladder is guaranteed to be ordered.** Since `completed(g) ≤ completion(g)`
for every `g`, and `completed` is monotonic, the targets (completion 0.25, then
completed 0.50 / 0.90 / 0.99) yield a non-decreasing ladder on any corpus. An
earlier draft anchored `deep_dive` on `loops ≥ 3`, which inverted the ladder on a
short-video corpus — three passes of an 18s video is 54s, below the linger
cutoff. `loops` is still reported as a diagnostic, but it is not an anchor.

## Reading the report

```
duration   p10=9s  p25=12s  p50=18s  p75=40s  p90=84s  p99=170s
ads        3.98% of views, 3.52% of posts

what today's cutoffs actually mean
  bucket         gap   completion  watched thru   loops
  graveyard       3s        17.5%          0.0%    0.17
  sandbox        15s        67.7%         44.3%    0.88
```

Read that as: our 3-second "skip" cutoff means the user saw about 17% of the
video — a defensible definition of a skip. Our 15-second "glance" cutoff means
they saw about 68% and watched 44% of videos all the way through, which is a
*lot* more engagement than the word "sandbox" implies.

*(Numbers above are from a synthetic demo corpus, not real data.)*

## Coverage caveats — read before trusting any of it

The public corpus this was built for is **a sample, not a census**, and the
sampling is not benign:

- It is hash-partitioned **on creator ID**, so coverage is all-or-nothing per
  creator, not a uniform random slice.
- It is a ~3-week collection window against an unstated fraction of TikTok.
- `country` and `language` are TikTok's own inferred labels and are frequently
  `un` (unknown). They are recorded as-is, never treated as ground truth.
- Engagement counts are a single snapshot, so older posts have had longer to
  accumulate views.
- Many captions are empty, so hashtag priors rest on a much smaller base than the
  row count suggests — `totals.caption_nonempty_share` records that base.

Every run therefore emits `locale_mix` (unfiltered, even on a filtered run) as a
**bias check**: compare the corpus's language and country mix against your actual
audience. If they diverge badly, recalibrate against a matching slice:

```bash
python3 scripts/calibrate_from_corpus.py 'videos-*.parquet' --language en --country US
```

These caveats travel with the numbers. `utils.calibration.provenance()` returns
them alongside the thresholds, so any narrative block built on calibrated cutoffs
can state where they came from — as the project's determinism convention requires.

## What this deliberately does not do

- **It does not identify creators.** The corpus carries no author ID, username or
  profile data, by design. Creator resolution still goes through
  `utils/creator_map.py` and oEmbed.
- **It does not change any live behaviour.** Nothing in the analyse path imports
  `utils/calibration.py` yet. With no calibration file committed, `thresholds()`
  returns exactly the values `ghost_profile.py` hard-codes today, so adopting the
  module is a no-op until someone commits a calibration and wires it in.
- **It does not redistribute corpus data.** Only aggregates are committed.
