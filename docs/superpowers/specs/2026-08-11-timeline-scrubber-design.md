# WP-3.3 · Timeline Scrubber — Design

**Status:** approved design, pre-implementation
**Date:** 2026-08-11
**Depends on:** WP-3.1 (Dossier shell, `TimelineTab.tsx` extraction — shipped)
**Unblocks:** WP-3.4 (polished panel treatments)
**Refs:** implementation-plan WP-3.3; dependency graph `WP-1.5 → WP-3.2 → WP-3.1 → WP-3.3 → WP-3.4`

## 1. Purpose

Add a month-range scrub control to the Timeline tab so a user can narrow the
four time-based panels (Niche Drift, Algorithm Efficiency, Creator Dominance,
Topic Trends) to a sub-window of their history, without any network
round-trip or statistical recomputation.

## 2. Context discovered during brainstorming (2026-08-11)

The master plan's WP-3.3 line describes a "global" scrubber operating on the
engine's unified `TemporalSeries` field. Two things surfaced while scoping:

- The actual `temporal_series` field the engine computes (`stopwatch_buckets`,
  `night_shift_ratio`, `explicit_vs_implicit_ratio`) is **not surfaced to the
  frontend at all** — missing from the `GhostProfile` interface in
  `GhostProfileHUD.tsx`. Wiring it up is explicitly out of scope here (see §7).
- What `TimelineTab.tsx` (from WP-3.1) actually renders today is four
  differently-shaped month-keyed datasets: `niche_drift.series` (genuinely
  `TemporalSeries<NicheDriftPoint>`), `stopwatch_metrics.monthly_skip_rates` +
  `skip_anomalies`, `monthly_creator_trends`, and `monthly_topic_trends` (the
  latter three are ad-hoc `Record<month, ...>` / arrays keyed by a month
  string, not the formal `TemporalSeries` type).

## 3. Decisions (settled during brainstorming, 2026-08-11)

1. **Scoped to the Timeline tab only — not shell-level/cross-tab.** One
   `activeRange` state lives inside `TimelineTab.tsx`. No state is lifted to
   `DossierShell.tsx`; other tabs are untouched. "Panels" in the master plan's
   AC means the panels within this one tab.
2. **Scrubs existing datasets only — `temporal_series` stays orphaned.**
   Surfacing it is a separate, additive WP (new panels), not a scrubber
   concern.
3. **Niche-drift headline/trend badge stay anchored to full history.** The
   narrowing/widening trend and the "narrowed from X to Y" sentence are
   computed server-side via least-squares over the *entire* series; scrubbing
   only narrows which points the chart *plots* (`NicheDriftChart` gets a new
   optional `visibleRange` prop that filters `result.series.points` for the
   `data` array passed to recharts). Headline/badge text keeps reading the
   unfiltered `result`. This is the literal reading of "no recompute" and
   avoids a badge that claims a trend the visible slice doesn't support.
4. **Dual-handle range slider**, not two dropdowns. Two overlaid native
   `<input type="range">` thumbs sharing one visual track (no new dependency,
   standard technique), styled with the existing `dashboardPrimitives` tokens.
5. **The scrubber's axis is always months — niche-drift maps its selection
   onto quarters when widened.** `niche_drift.series` widens to quarter keys
   (e.g. `"2025-Q1"`) when monthly data is sparse (`granularity ===
   "quarter"`), while the other three panels always use plain month keys
   (`"2025-01"`). Rather than excluding niche-drift from the scrub when
   widened (inconsistent UX — one panel silently ignoring the control), the
   scrubber's own axis stays month-based (built from the union of the three
   always-monthly datasets), and `NicheDriftChart`'s `visibleRange` filter
   includes a quarter point whenever the quarter's month range *overlaps* the
   selected `[start, end]` months — see §5.

## 4. Architecture

```
algorithmic-mirror/app/components/
  MonthRangeScrubber.tsx   — new, controlled component
  NicheDriftChart.tsx      — gains optional `visibleRange?: [string, string]` prop
  tabs/
    TimelineTab.tsx        — gains `activeRange` state + scrubber + per-panel filtering
```

```ts
interface MonthRangeScrubberProps {
  months: string[];              // full sorted period-key axis, e.g. ["2025-01", ..., "2025-11"]
  value: [string, string];       // current [start, end] selection
  onChange: (range: [string, string]) => void;
}
```

`TimelineTab` computes `months` as the sorted union of period keys across all
four datasets. `activeRange` defaults to `[months[0], months[months.length - 1]]`
(full span) on mount. The lower thumb is clamped to never exceed the upper
(and vice versa), so the range can never invert.

## 5. Data flow / filtering behavior

Filtering is a pure, trivial array/object filter — no recomputation of
trends, slopes, or aggregates. This satisfies the "client-side only, no
recompute" AC and keeps updates well under the 100ms target.

- **Algorithm Efficiency Timeline**: `monthly_skip_rates` entries and
  `skip_anomalies` entries outside `activeRange` are dropped before
  rendering. The bar-height scale (`maxRate`) recomputes from the *visible*
  subset only (a display-scale recalculation, not a statistical one), so the
  chart rescales to fill the frame at any zoom window.
- **Creator Dominance by Month** / **Topic Trends by Month**: month cards
  outside `activeRange` are excluded from the `Object.entries(...).map(...)`
  render.
- **Niche Drift**: `NicheDriftChart` receives `visibleRange={activeRange}`
  (always expressed as `[startMonth, endMonth]`, e.g. `["2025-01",
  "2025-06"]`); internally it filters `result.series.points` for the recharts
  `data` array only. `headline(result)` and the trend badges keep reading the
  full, unfiltered `result`. When `result.series.granularity === "quarter"`,
  each point's quarter key (e.g. `"2025-Q1"`) is expanded back to its
  contained month range (`Q1` → `["01", "02", "03"]` of that year) and kept
  if that range *overlaps* `visibleRange` at all — a quarter is shown as soon
  as any part of it falls inside the scrubbed window, not only when fully
  contained. When `granularity === "month"`, the point's own key is compared
  directly against `visibleRange`.

If a panel's dataset is empty after filtering, the panel keeps rendering its
container with whatever "nothing here" affordance it already has today (each
panel already null-guards on empty datasets independent of this WP).

## 6. Motion

Each of the four panel bodies wraps its filtered list (bars, cards, anomaly
entries) in a `motion.div` with `layout` enabled inside an `AnimatePresence`,
using the transition `{ type: "spring", stiffness: 320, damping: 18 }` — the
same spring values already established as this codebase's general-purpose
motion curve in `FileDropzone.tsx`'s `SPRING_HOVER`, rather than inventing a
new one. (`DossierShell.tsx`'s own tab-switch `AnimatePresence` uses a plain
`{ duration: 0.2 }` fade, not a spring — not the right reference here.)
Entries added/removed by scrubbing animate in/out and reflow instead of
popping. Respects `prefers-reduced-motion` per this repo's standing
convention.

## 7. Out of scope (YAGNI / later WPs)

- Wiring up the orphaned `temporal_series` field (`stopwatch_buckets`,
  `night_shift_ratio`, `explicit_vs_implicit_ratio`) — a separate, additive
  WP.
- Any cross-tab / shell-level range sharing.
- Persisting the scrubbed range across navigation or in the URL — range
  resets to full-span on remount.
- Recomputing niche-drift trend statistics for arbitrary sub-windows.
- WP-3.4's polished panel treatments — this WP only adds the scrub mechanism
  to the panels as they exist today.

## 8. Error handling / degradation

- If the union of period keys has 0 or 1 entries, the scrubber doesn't
  render at all — panels fall back to their current unscrubbed behavior,
  matching the existing `Object.keys(rates).length < 2` guard pattern already
  used in the Algorithm Efficiency panel.
- With ≥ 2 entries, `activeRange` always starts at full span — scrubbing
  never starts pre-narrowed.
- No persistence: state lives in `TimelineTab`'s component state only.

## 9. Testing

- **`MonthRangeScrubber.test.tsx`** (new): renders with a fixed `months`
  array; asserts both thumbs render at correct initial positions; asserts
  changing a thumb calls `onChange` with a correctly clamped `[start, end]`
  tuple; asserts the lower thumb can't be dragged past the upper and vice
  versa.
- **Pure filtering logic** extracted into a small testable helper rather than
  living inline in JSX; unit-tested with fixture month arrays covering: full
  range (no-op), narrowed range, empty range, single-month range.
- **`TimelineTab.test.tsx`** (existing, from WP-3.1): extended with a case
  that changes the scrubber's range and asserts panel content shrinks
  accordingly (e.g. fewer creator-dominance cards render after narrowing).
- **`NicheDriftChart` coverage**: asserts the new `visibleRange` prop filters
  the plotted `data` array while headline text stays keyed off the
  unfiltered `result`.

All per existing project conventions: `TZ=UTC`, `ts-jest`, RTL,
`framer-motion` proxy-mocked the same way every other dashboard test already
does.
