# WP-2.5 · Niche-Drift Metric — Design

**Status:** approved design, pre-implementation
**Date:** 2026-07-27
**Depends on:** `stopwatch_metrics.linger_events` (carry `_month` + `link`), `handleFromLink` + the `linkHandleMap` (creator resolution), WP-1.4 (`TemporalSeries`)
**Unblocks:** WP-3.4 (polished Timeline panel)
**Refs:** implementation-plan WP-2.5; research-integration §3

## 1. Purpose

Chart how a user's feed **narrows over time** — the "niche drift" the CHI 2026 study
documented (TikTok trading mass appeal for personal precision). The original spec
measured this via per-video **like counts**; that is not buildable (see §2), so this
design measures the *same phenomenon* through signals we own: **per-month distinct
creators** and **top-5 creator concentration**, each with a fitted trend.

## 2. The blocker that reshaped this WP (verified 2026-07-27)

The original AC ("monthly mean/median like-count of watched videos, where oEmbed
supplies counts") is **not achievable**:
- TikTok's oEmbed (`utils/oembed.py`, our only enrichment) returns **only**
  `title / author / author_name / thumbnail` — **no engagement counts**.
- No `like_count` / `play_count` / `view_count` exists anywhere in the export, parser,
  or profile.
- The user's export contains *their* likes, not the *global* like-count of each
  watched video.

Research §3's premise ("oEmbed enrichment can return engagement counts") is factually
wrong about TikTok's public oEmbed. Building the like-count curve would require
inventing numbers — against the project's honesty ground rule. **Decision: redefine
drift onto creator concentration, a signal we actually own.**

## 3. Decisions (settled during brainstorming, 2026-07-27)

1. **Redefine, don't fake.** Measure feed-narrowing via per-month **distinct creators**
   + **top-5 concentration %**, both computable from `linger_events` + creator
   resolution. Not global like-counts.
2. **Two signals, one series.** A single `TemporalSeries` whose point value carries
   both signals (shared buckets → two lines on one x-axis). Topic-diversity as a third
   signal is out of scope (keeps this [S]).
3. **Architecture: pure engine layer in the pipeline** (like `persona.ts`).
   `buildNicheDrift(profile, linkHandleMap)` reuses the same `handleFromLink`
   resolution path as `monthlyCreatorTrends`; `buildGhostProfile` untouched. It rides
   in the second-pass `out` (after `/api/resolve` supplies `linkHandleMap`), so it sees
   resolved creators — no dependency on the page-level `creator_resolution` field.
4. **Coverage gate = resolved-creator coverage.** The honest analog of the original
   "<40% have counts": exclude (`insufficient_evidence`) when **< 40% of linger events
   resolve to a creator handle**. Computed internally from the events + `linkHandleMap`.
5. **Sparse month → quarter widening.** A month with **< 10 resolved videos** is too
   thin; if any month is sparse, re-bucket the **whole** series by quarter (uniform
   granularity, mirroring the WP-1.4 month↔week rule).

## 4. Data flow

```
runEngine(raw) → runEngineFromParsed(parsed, { linkHandleMap })
        │   stopwatch_metrics.linger_events: each { link, _month, time_spent, … }
        ▼
buildNicheDrift(profile, linkHandleMap)   ← NEW pure fn (engine/nicheDrift.ts)
        │   per bucket: distinct resolved creators + top-5 concentration %
        │   internal resolved-coverage gate; least-squares slope per signal
        ▼
EngineResult.niche_drift → payload.niche_drift
        ▼
<NicheDriftChart result={profile.niche_drift} />   ← Timeline tab; polished = WP-3.4
```

## 5. Per-bucket math

Group `linger_events` by `_month` (or `YYYY-Q#` after widening). Resolve each event's
`link` via `handleFromLink(link, linkHandleMap)`; keep only events that resolve to a
non-empty handle. Per bucket:
- `distinct_creators` = count of distinct resolved handles.
- `top5_concentration_pct` = (events on the bucket's top-5 handles by count) ÷
  (bucket's total resolved events) × 100, `pyRound(…, 1)`.
- Internally track `resolved_videos` / `total_videos` per bucket for the widening test.

**Resolved-coverage gate:** `resolved_coverage_pct` = (total resolved linger events) ÷
(total linger events) × 100. If **< 40%**, return `insufficient_evidence` with
`requirements: { needed: "≥40% of watched videos resolved to a creator", had: "<pct>%" }`.

**Sparse → quarter:** if any month bucket has `resolved_videos < 10`, recompute every
bucket keyed by quarter (`${year}-Q${quarter}`) and set `granularity: "quarter"`; else
`granularity: "month"`. Widen **at most once** — a still-sparse quarter is accepted as-is
(no cascade to years); the trend/`insufficient_trend` logic in §6 covers the thin case.

## 6. Trend fit

A deterministic **least-squares linear slope** over ordered buckets (x = index 0..n−1,
y = the signal), computed once per signal:
- `slope` = Σ((xᵢ−x̄)(yᵢ−ȳ)) / Σ((xᵢ−x̄)²), `pyRound(…, 3)`.
- `direction`: for distinct-creators, `slope < −ε → "narrowing"`, `slope > ε →
  "widening"`, else `"flat"`; for concentration, `slope > ε → "narrowing"`, `slope <
  −ε → "widening"`, else `"flat"` (rising concentration = narrowing). `ε = 0.01`.
- **< 3 buckets** → cannot fit: `slope: null`, `direction: "insufficient_trend"` (the
  series still emits its points).

## 7. Payload shape

```ts
interface NicheDriftPoint {
  period: string;                 // "2026-01" or "2026-Q1"
  distinct_creators: number;
  top5_concentration_pct: number;
}
interface DriftTrend { slope: number | null; direction: string; }
interface NicheDriftResult {
  status: "ok" | "insufficient_evidence" | "error";
  series: TemporalSeries<NicheDriftPoint>;       // granularity "month" | "quarter"
  distinct_creators_trend: DriftTrend;
  top5_concentration_trend: DriftTrend;
  resolved_coverage_pct: number;                 // the gate value, surfaced for transparency
  requirements?: { needed: string; had: string };
  method: string;                                // formulas + 40% gate + slope method
}
```

`TemporalSeries<NicheDriftPoint>` = `{ granularity, points: { period, value: NicheDriftPoint }[] }`.
`buildNicheDrift` does not touch `claims.ts`.

## 8. Error handling / degradation

- < 40% resolved → `insufficient_evidence` (the honest default when creators aren't
  resolved).
- < 3 buckets → series emits, trend is `insufficient_trend` (not an error).
- Malformed `profile` / no `linger_events` → `status: "error"`, no crash.
- Empty resolved set (0 events resolve) → `insufficient_evidence` (coverage 0%).

## 9. UI

Minimal `app/components/NicheDriftChart.tsx`: a recharts `LineChart` with two lines
(distinct creators + top-5 concentration %) over the month/quarter x-axis, plus a
one-line narrative headline from the trend — e.g. *"Your feed narrowed from {first} to
{last} creators"* when narrowing, a neutral "held steady" when flat. Three states
(ok / insufficient_evidence / error); warm-paper palette; lucide + recharts only; no
animation. Wired into the **Timeline tab** (temporal-evolution content). Polished
version → WP-3.4.

## 10. Testing (maps every AC)

### Engine (TS, no network, fixtures)
- `nicheDrift.test.ts`:
  - **(AC)** per-month `distinct_creators` + `top5_concentration_pct` on synthetic
    linger fixtures (handles resolved via a supplied `linkHandleMap`).
  - narrowing fixture (distinct creators fall m/m) → `direction: "narrowing"`, negative
    slope; widening fixture → the reverse; flat → `"flat"`.
  - **(AC)** quarter widening: a sub-10-resolved month re-buckets the whole series to
    `granularity: "quarter"`.
  - < 3 buckets → `slope: null`, `direction: "insufficient_trend"`, series still emits.
  - **(AC)** coverage gate: < 40% resolved → `insufficient_evidence` + `requirements`;
    ≥ 40% → ok.
  - malformed profile → `error`; determinism (same input → identical result).

### Component (TS, jsdom, recharts mocked)
- `NicheDriftChart.test.tsx`: renders all three states; ok shows the narrative headline
  + both series.

## 11. Out of scope (YAGNI / later WPs)

- Real global like-counts (the blocked original — needs a count source we don't have).
- Topic-diversity as a third signal (kept [S]).
- Touching `buildGhostProfile` / `claims.ts` / golden fixtures.
- The polished Timeline panel → WP-3.4.
- Any Python / backend change (pure client TS, like the rest of Phase 2's insight layer).

## 12. Open risks

- **Creator resolution is the dependency.** With a thin `linkHandleMap` (few resolved
  handles), the 40% gate fires and the metric honestly shows insufficient rather than a
  misleading curve. This ties WP-2.5's usefulness to the resolution pipeline's coverage.
- **Concentration vs distinct-count can diverge.** A user can watch more distinct
  creators yet concentrate more time on a top-5 — the two lines can move oppositely.
  That is real signal, not a bug; the UI shows both without forcing a single verdict.
- **Short histories** (< 3 buckets, or all-sparse) yield a series without a trend — the
  narrative headline degrades to a neutral statement rather than over-claiming a slope.
