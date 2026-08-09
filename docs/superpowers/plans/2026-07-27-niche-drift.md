# Niche-Drift Metric (WP-2.5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chart how a user's feed narrows over time via per-month distinct creators + top-5 creator concentration (with a fitted trend) — the honest, buildable substitute for the un-obtainable like-count curve.

**Architecture:** A pure client-side TS layer `engine/nicheDrift.ts` — `buildNicheDrift(profile, linkHandleMap)` — over the profile's `linger_events`, surfaced in `pipeline.ts` like `persona`. It resolves creators via the same `handleFromLink` path, computes its own resolved-coverage gate, widens sparse months to quarters, and fits a least-squares slope. A minimal `NicheDriftChart` renders it in the Timeline tab. `buildGhostProfile` is untouched.

**Tech Stack:** TypeScript (ts-jest, `algorithmic-mirror/engine/`), React 19 / Next 16, recharts (already a dep), `@testing-library/react`.

## Global Constraints

- **Pure client TS**, browser-safe: `engine/nicheDrift.ts` uses **no `fs`/`path`/`crypto`/`process`/`require`**.
- Reads `profile.stopwatch_metrics.linger_events` (each `StopwatchEvent { link: string; _month?: string; … }`); resolves creators via `handleFromLink(link, linkHandleMap)` from `./creators` (returns `string | null`). Rounding via `pyRound` from `./numeric`.
- **Coverage gate:** `insufficient_evidence` when **< 40%** of linger events resolve to a creator (`resolved_coverage_pct`), computed internally from the events + `linkHandleMap`.
- **Sparse → quarter widening:** if any month bucket has **< 10 resolved videos**, re-bucket the whole series by quarter (`YYYY-Q#`), `granularity: "quarter"`; else `"month"`. Widen **at most once**.
- **Trend:** least-squares slope per signal over ordered buckets; needs **≥ 3 buckets** else `slope: null`, `direction: "insufficient_trend"`. `direction` epsilon `ε = 0.01`. distinct-creators: slope `< −ε` → `"narrowing"`, `> ε` → `"widening"`, else `"flat"`. concentration: **inverted** (rising concentration = narrowing).
- Two signals in **one** `TemporalSeries<NicheDriftPoint>` (both per point). `TemporalSeries<T>` = `{ granularity: "month" | "week" | "quarter"; points: { period: string; value: T }[] }` (extend the union with `"quarter"` — see Task 1).
- Malformed profile / non-array `linger_events` → `status: "error"`.
- Do **not** modify `buildGhostProfile`/`ghostProfile.ts`, `claims.ts`, `creators.ts`, or golden fixtures.
- Run TS tests with **`TZ=UTC`**; run **`npx tsc --noEmit`** before every commit (ts-jest does not type-check).

---

### Task 1: `nicheDrift.ts` — bucketing, coverage gate, quarter widening, trend

**Files:**
- Create: `algorithmic-mirror/engine/nicheDrift.ts`
- Modify: `algorithmic-mirror/engine/types.ts` (add `"quarter"` to the `TemporalSeries` granularity union)
- Test: `algorithmic-mirror/engine/__tests__/nicheDrift.test.ts`

**Interfaces:**
- Consumes: `handleFromLink` from `./creators`; `pyRound` from `./numeric`; `TemporalSeries` from `./types`.
- Produces: `NicheDriftPoint`, `DriftTrend`, `NicheDriftResult` (types); `buildNicheDrift(profile: any, linkHandleMap?: Record<string, string> | null): NicheDriftResult`.

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/engine/__tests__/nicheDrift.test.ts
import { buildNicheDrift } from "../nicheDrift";

// Each linger event: a creator link + its _month. Links already embed the @handle
// so handleFromLink resolves them WITHOUT a map (extractCreatorFromUrl path).
const ev = (handle: string, month: string) => ({ link: `https://www.tiktok.com/@${handle}/video/1`, _month: month });
const prof = (linger: any[]) => ({ stopwatch_metrics: { linger_events: linger } });

// n events for a given handle+month
const many = (handle: string, month: string, n: number) => Array.from({ length: n }, () => ev(handle, month));

describe("buildNicheDrift", () => {
  test("per-month distinct creators + top-5 concentration", () => {
    // Jan: 6 distinct creators (a..f), each 2 events → 12 events; top-5 = 10/12 = 83.3%
    const jan = ["a", "b", "c", "d", "e", "f"].flatMap((h) => many(h, "2026-01", 2));
    // Feb: 6 distinct creators, same shape
    const feb = ["a", "b", "c", "d", "e", "f"].flatMap((h) => many(h, "2026-02", 2));
    const res = buildNicheDrift(prof([...jan, ...feb]));
    expect(res.status).toBe("ok");
    expect(res.series.granularity).toBe("month");
    const p0 = res.series.points[0];
    expect(p0.period).toBe("2026-01");
    expect(p0.value.distinct_creators).toBe(6);
    expect(p0.value.top5_concentration_pct).toBe(83.3);
  });

  test("narrowing: distinct creators fall month-over-month → direction 'narrowing', negative slope", () => {
    // 3 months, ≥10 resolved each (no widening): distinct 6 → 4 → 2
    const m1 = ["a", "b", "c", "d", "e", "f"].flatMap((h) => many(h, "2026-01", 2)); // 12 ev, 6 distinct
    const m2 = ["a", "b", "c", "d"].flatMap((h) => many(h, "2026-02", 3));            // 12 ev, 4 distinct
    const m3 = ["a", "b"].flatMap((h) => many(h, "2026-03", 6));                       // 12 ev, 2 distinct
    const res = buildNicheDrift(prof([...m1, ...m2, ...m3]));
    expect(res.series.points.map((p) => p.value.distinct_creators)).toEqual([6, 4, 2]);
    expect(res.distinct_creators_trend.slope).toBeLessThan(0);
    expect(res.distinct_creators_trend.direction).toBe("narrowing");
    // concentration rises (fewer creators) → also "narrowing"
    expect(res.top5_concentration_trend.direction).toBe("narrowing");
  });

  test("< 3 buckets → slope null, direction insufficient_trend (series still emits)", () => {
    const m1 = ["a", "b", "c"].flatMap((h) => many(h, "2026-01", 4));  // 12 ev
    const m2 = ["a", "b", "c"].flatMap((h) => many(h, "2026-02", 4));  // 12 ev
    const res = buildNicheDrift(prof([...m1, ...m2]));
    expect(res.status).toBe("ok");
    expect(res.series.points).toHaveLength(2);
    expect(res.distinct_creators_trend.slope).toBeNull();
    expect(res.distinct_creators_trend.direction).toBe("insufficient_trend");
  });

  test("a sub-10-resolved month widens the WHOLE series to quarters", () => {
    // Jan: 12 resolved (fine). Feb: 4 resolved (sparse) → widen all to quarters.
    const jan = ["a", "b", "c"].flatMap((h) => many(h, "2026-01", 4)); // 12
    const feb = many("a", "2026-02", 4);                                // 4 → sparse
    const res = buildNicheDrift(prof([...jan, ...feb]));
    expect(res.series.granularity).toBe("quarter");
    expect(res.series.points[0].period).toBe("2026-Q1"); // Jan+Feb collapse into Q1
    expect(res.series.points).toHaveLength(1);
  });

  test("< 40% resolved → insufficient_evidence with requirements", () => {
    // 2 resolvable events + 8 unresolvable (bare links, no map) → 20% coverage
    const resolvable = many("a", "2026-01", 2);
    const bare = Array.from({ length: 8 }, () => ({ link: "https://www.tiktokv.com/share/video/999/", _month: "2026-01" }));
    const res = buildNicheDrift(prof([...resolvable, ...bare])); // no linkHandleMap → bare links unresolved
    expect(res.status).toBe("insufficient_evidence");
    expect(res.resolved_coverage_pct).toBe(20);
    expect(res.requirements?.needed).toMatch(/40%/);
  });

  test("malformed profile → error", () => {
    expect(buildNicheDrift(null as any).status).toBe("error");
    expect(buildNicheDrift({ stopwatch_metrics: { linger_events: "nope" } } as any).status).toBe("error");
  });

  test("deterministic", () => {
    const m = ["a", "b", "c"].flatMap((h) => many(h, "2026-01", 4));
    expect(buildNicheDrift(prof(m))).toEqual(buildNicheDrift(prof(m)));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/nicheDrift.test.ts`
Expected: FAIL — `Cannot find module '../nicheDrift'`.

- [ ] **Step 3a: Extend the `TemporalSeries` granularity union**

In `algorithmic-mirror/engine/types.ts`, change the `TemporalSeries` granularity field to include `"quarter"`:

```ts
export interface TemporalSeries<T = unknown> {
  granularity: "month" | "week" | "quarter";
  points: { period: string; value: T }[];
}
```

(Only the union widens; existing producers still emit `"month"`/`"week"` unchanged.)

- [ ] **Step 3b: Write the engine**

```ts
// algorithmic-mirror/engine/nicheDrift.ts
/**
 * WP-2.5 — Niche-drift metric. Pure, browser-safe. Charts how a feed narrows over
 * time via per-month distinct creators + top-5 creator concentration, each with a
 * fitted least-squares trend. Redefines the un-obtainable like-count curve onto a
 * signal we own (creator resolution). See docs/superpowers/specs/2026-07-27-niche-drift-design.md.
 */
import { handleFromLink } from "./creators";
import { pyRound } from "./numeric";
import type { TemporalSeries } from "./types";

const MIN_COVERAGE_PCT = 40;
const SPARSE_MONTH_MIN = 10;
const MIN_TREND_BUCKETS = 3;
const EPS = 0.01;

export interface NicheDriftPoint {
  period: string;
  distinct_creators: number;
  top5_concentration_pct: number;
}
export interface DriftTrend {
  slope: number | null;
  direction: string; // "narrowing" | "widening" | "flat" | "insufficient_trend"
}
export interface NicheDriftResult {
  status: "ok" | "insufficient_evidence" | "error";
  series: TemporalSeries<NicheDriftPoint>;
  distinct_creators_trend: DriftTrend;
  top5_concentration_trend: DriftTrend;
  resolved_coverage_pct: number;
  requirements?: { needed: string; had: string };
  method: string;
}

const METHOD =
  "Per-period distinct creators + top-5 creator concentration from your watched-video " +
  "creators, with a least-squares trend. Excluded when <40% of watched videos resolve to " +
  "a creator; months with <10 resolved videos widen the whole series to quarters.";

function quarterOf(month: string): string {
  const [y, m] = month.split("-");
  const q = Math.floor((Number(m) - 1) / 3) + 1;
  return `${y}-Q${q}`;
}

function linearSlope(ys: number[]): number | null {
  const n = ys.length;
  if (n < MIN_TREND_BUCKETS) return null;
  const xbar = (n - 1) / 2;
  const ybar = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) { num += (i - xbar) * (ys[i] - ybar); den += (i - xbar) ** 2; }
  if (den === 0) return null;
  return pyRound(num / den, 3);
}

function driftDirection(slope: number | null, invert: boolean): string {
  if (slope === null) return "insufficient_trend";
  const s = invert ? -slope : slope; // concentration rising = narrowing → invert
  if (s < -EPS) return "narrowing";
  if (s > EPS) return "widening";
  return "flat";
}

// distinct creators + top-5 concentration for one bucket's resolved handles.
function bucketMetrics(handles: string[]): { distinct_creators: number; top5_concentration_pct: number } {
  const counts = new Map<string, number>();
  for (const h of handles) counts.set(h, (counts.get(h) ?? 0) + 1);
  const total = handles.length;
  const top5 = [...counts.values()].sort((a, b) => b - a).slice(0, 5).reduce((a, b) => a + b, 0);
  return {
    distinct_creators: counts.size,
    top5_concentration_pct: total > 0 ? pyRound((top5 / total) * 100, 1) : 0,
  };
}

const err = (): NicheDriftResult => ({
  status: "error",
  series: { granularity: "month", points: [] },
  distinct_creators_trend: { slope: null, direction: "insufficient_trend" },
  top5_concentration_trend: { slope: null, direction: "insufficient_trend" },
  resolved_coverage_pct: 0,
  method: METHOD,
});

export function buildNicheDrift(profile: any, linkHandleMap?: Record<string, string> | null): NicheDriftResult {
  const lingerEvents = profile?.stopwatch_metrics?.linger_events;
  if (!profile || typeof profile !== "object" || !Array.isArray(lingerEvents)) return err();

  // Resolve every event; keep {month, handle} for resolved ones.
  const resolved: { month: string; handle: string }[] = [];
  for (const e of lingerEvents) {
    const handle = handleFromLink(String(e?.link ?? ""), linkHandleMap);
    const month = String(e?._month ?? "");
    if (handle && month) resolved.push({ month, handle });
  }

  const coverage = lingerEvents.length > 0 ? (resolved.length / lingerEvents.length) * 100 : 0;
  const resolved_coverage_pct = pyRound(coverage, 1);
  const emptySeries: TemporalSeries<NicheDriftPoint> = { granularity: "month", points: [] };
  const noTrend = { slope: null, direction: "insufficient_trend" };
  if (coverage < MIN_COVERAGE_PCT) {
    return {
      status: "insufficient_evidence", series: emptySeries,
      distinct_creators_trend: { ...noTrend }, top5_concentration_trend: { ...noTrend },
      resolved_coverage_pct,
      requirements: { needed: "≥40% of watched videos resolved to a creator", had: `${resolved_coverage_pct}%` },
      method: METHOD,
    };
  }

  // Decide granularity: widen the whole series to quarters if any month is sparse.
  const perMonth = new Map<string, string[]>();
  for (const r of resolved) { if (!perMonth.has(r.month)) perMonth.set(r.month, []); perMonth.get(r.month)!.push(r.handle); }
  const sparse = [...perMonth.values()].some((hs) => hs.length < SPARSE_MONTH_MIN);
  const granularity: "month" | "quarter" = sparse ? "quarter" : "month";

  const perBucket = new Map<string, string[]>();
  for (const r of resolved) {
    const key = granularity === "quarter" ? quarterOf(r.month) : r.month;
    if (!perBucket.has(key)) perBucket.set(key, []);
    perBucket.get(key)!.push(r.handle);
  }

  const periods = [...perBucket.keys()].sort();
  const points = periods.map((period) => ({ period, value: { period, ...bucketMetrics(perBucket.get(period)!) } }));

  const distinctYs = points.map((p) => p.value.distinct_creators);
  const concYs = points.map((p) => p.value.top5_concentration_pct);
  const distinctSlope = linearSlope(distinctYs);
  const concSlope = linearSlope(concYs);

  return {
    status: "ok",
    series: { granularity, points },
    distinct_creators_trend: { slope: distinctSlope, direction: driftDirection(distinctSlope, false) },
    top5_concentration_trend: { slope: concSlope, direction: driftDirection(concSlope, true) },
    resolved_coverage_pct,
    method: METHOD,
  };
}
```

- [ ] **Step 4: Run tests + tsc**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/nicheDrift.test.ts` → PASS (7 tests).
Then the full engine suite (the `types.ts` change is load-bearing for other modules): `cd algorithmic-mirror && TZ=UTC npx jest engine` → PASS.
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/nicheDrift.ts algorithmic-mirror/engine/types.ts algorithmic-mirror/engine/__tests__/nicheDrift.test.ts
git commit -m "feat(engine): WP-2.5 niche-drift — per-month creator concentration + trend"
```

---

### Task 2: Surface `niche_drift` in the pipeline

**Files:**
- Modify: `algorithmic-mirror/engine/pipeline.ts`
- Test: `algorithmic-mirror/engine/__tests__/nicheDrift.pipeline.test.ts`

**Interfaces:**
- Consumes: `buildNicheDrift`, `NicheDriftResult` (Task 1); the existing `profile` local + `opts.linkHandleMap` in `runEngineFromParsed`.
- Produces: `EngineResult.niche_drift: NicheDriftResult`.

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/engine/__tests__/nicheDrift.pipeline.test.ts
import { runEngine } from "../pipeline";

test("runEngine surfaces a niche_drift result", () => {
  const raw = {
    "Your Activity": {
      "Watch History": { VideoList: [
        { Date: "2024-01-01 10:00:00", Link: "https://www.tiktok.com/@creator/video/111" },
        { Date: "2024-01-01 10:01:00", Link: "https://www.tiktok.com/@creator/video/222" },
      ] },
    },
  };
  const { niche_drift } = runEngine(raw);
  expect(niche_drift).toBeDefined();
  expect(["ok", "insufficient_evidence", "error"]).toContain(niche_drift.status);
  expect(niche_drift.series).toBeDefined();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/nicheDrift.pipeline.test.ts`
Expected: FAIL — `niche_drift` is `undefined`.

- [ ] **Step 3: Write minimal implementation**

In `algorithmic-mirror/engine/pipeline.ts`, add the import near the others:

```ts
import { buildNicheDrift, NicheDriftResult } from "./nicheDrift";
```

Add to the `EngineResult` interface:

```ts
  /** WP-2.5 niche-drift: per-period creator concentration + fitted trend. */
  niche_drift: NicheDriftResult;
```

In `runEngineFromParsed`, after `persona` is computed and before the `return`, add:

```ts
  const niche_drift = buildNicheDrift(profile, opts.linkHandleMap ?? null);
```

and include `niche_drift` in the returned object:

```ts
  return { parsed, profile, narratives, coverage, gates, claims, topicCandidates, persona, niche_drift };
```

(The `runEngine` spread carries the new field through unchanged.)

- [ ] **Step 4: Run tests + tsc**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/nicheDrift.pipeline.test.ts` → PASS.
Then the whole engine suite: `cd algorithmic-mirror && TZ=UTC npx jest engine` → PASS.
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/pipeline.ts algorithmic-mirror/engine/__tests__/nicheDrift.pipeline.test.ts
git commit -m "feat(engine): surface WP-2.5 niche_drift in runEngine result"
```

---

### Task 3: `NicheDriftChart.tsx` — minimal two-line chart

**Files:**
- Create: `algorithmic-mirror/app/components/NicheDriftChart.tsx`
- Test: `algorithmic-mirror/__tests__/NicheDriftChart.test.tsx`

**Interfaces:**
- Consumes: `NicheDriftResult` from `../../engine/nicheDrift`.
- Produces: `export function NicheDriftChart({ result }: { result?: NicheDriftResult })`.

- [ ] **Step 1: Write the failing test**

```tsx
// algorithmic-mirror/__tests__/NicheDriftChart.test.tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { NicheDriftChart } from "../app/components/NicheDriftChart";
import type { NicheDriftResult } from "../engine/nicheDrift";

// recharts needs layout jsdom lacks; stub to passthroughs so we test text output.
jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, LineChart: Pass, Line: Pass, XAxis: Pass, YAxis: Pass, CartesianGrid: Pass, Tooltip: Pass, Legend: Pass };
});

const ok: NicheDriftResult = {
  status: "ok",
  series: { granularity: "month", points: [
    { period: "2026-01", value: { period: "2026-01", distinct_creators: 40, top5_concentration_pct: 34 } },
    { period: "2026-06", value: { period: "2026-06", distinct_creators: 12, top5_concentration_pct: 58 } },
  ] },
  distinct_creators_trend: { slope: -5.2, direction: "narrowing" },
  top5_concentration_trend: { slope: 4.1, direction: "narrowing" },
  resolved_coverage_pct: 82,
  method: "…",
};

describe("NicheDriftChart", () => {
  test("ok narrowing: renders the narrative headline (first→last creators)", () => {
    render(<NicheDriftChart result={ok} />);
    expect(screen.getByText(/narrowed/i)).toBeInTheDocument();
    expect(screen.getByText(/40/)).toBeInTheDocument();
    expect(screen.getByText(/12/)).toBeInTheDocument();
  });

  test("insufficient_evidence: gated message", () => {
    render(<NicheDriftChart result={{
      status: "insufficient_evidence",
      series: { granularity: "month", points: [] },
      distinct_creators_trend: { slope: null, direction: "insufficient_trend" },
      top5_concentration_trend: { slope: null, direction: "insufficient_trend" },
      resolved_coverage_pct: 20,
      requirements: { needed: "≥40% of watched videos resolved to a creator", had: "20%" },
      method: "…",
    }} />);
    expect(screen.getByText(/resolved to a creator|not enough/i)).toBeInTheDocument();
  });

  test("undefined → renders nothing", () => {
    const { container } = render(<NicheDriftChart result={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/NicheDriftChart.test.tsx`
Expected: FAIL — `Cannot find module '../app/components/NicheDriftChart'`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// algorithmic-mirror/app/components/NicheDriftChart.tsx
"use client";
/**
 * WP-2.5 — minimal niche-drift chart. Two lines (distinct creators + top-5
 * concentration %) over the month/quarter x-axis, from payload alone (ok /
 * insufficient_evidence / error). The polished Timeline panel is WP-3.4.
 */
import { Lock, AlertTriangle } from "lucide-react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import type { NicheDriftResult } from "../../engine/nicheDrift";

const BORDER = "rgba(26, 22, 16, 0.16)";
const INK = "#1a1610";
const INK_DIM = "rgba(26, 22, 16, 0.62)";
const ACCENT = "#8b2323";
const ACCENT2 = "#2e5b7a";

function headline(result: NicheDriftResult): string {
  const pts = result.series.points;
  if (pts.length < 2) return "Not enough history yet to read a trend in your feed.";
  const first = pts[0].value.distinct_creators;
  const last = pts[pts.length - 1].value.distinct_creators;
  if (result.distinct_creators_trend.direction === "narrowing")
    return `Your feed narrowed from ${first} to ${last} creators.`;
  if (result.distinct_creators_trend.direction === "widening")
    return `Your feed widened from ${first} to ${last} creators.`;
  return `Your feed held steady around ${last} creators.`;
}

export function NicheDriftChart({ result }: { result?: NicheDriftResult }) {
  if (!result) return null;

  if (result.status === "error") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: INK_DIM, fontSize: 12 }}>
        <AlertTriangle size={15} /> Niche-drift unavailable.
      </div>
    );
  }
  if (result.status === "insufficient_evidence") {
    return (
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start", color: INK_DIM, fontSize: 12 }}>
        <Lock size={15} style={{ marginTop: 1, flexShrink: 0 }} />
        <span>Not enough of your watched videos resolved to a creator to chart drift. Needs {result.requirements?.needed}; have {result.requirements?.had}.</span>
      </div>
    );
  }

  const data = result.series.points.map((p) => ({
    period: p.value.period,
    creators: p.value.distinct_creators,
    concentration: p.value.top5_concentration_pct,
  }));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontWeight: 600, color: INK, fontSize: 16 }}>{headline(result)}</div>
      <div style={{ width: "100%", height: 260, border: `1px solid ${BORDER}` }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid stroke={BORDER} />
            <XAxis dataKey="period" tick={{ fontSize: 10, fill: INK_DIM }} />
            <YAxis tick={{ fontSize: 10, fill: INK_DIM }} />
            <Tooltip />
            <Legend />
            <Line name="Distinct creators" dataKey="creators" stroke={ACCENT} dot={false} />
            <Line name="Top-5 concentration %" dataKey="concentration" stroke={ACCENT2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div style={{ fontSize: 10, color: INK_DIM }}>
        Creators: {result.distinct_creators_trend.direction} · Concentration: {result.top5_concentration_trend.direction} · {result.series.granularity} buckets
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests + tsc**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/NicheDriftChart.test.tsx` → PASS (3 tests).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/NicheDriftChart.tsx algorithmic-mirror/__tests__/NicheDriftChart.test.tsx
git commit -m "feat(ui): WP-2.5 minimal NicheDriftChart — two-line drift chart"
```

---

### Task 4: Wire niche_drift into the payload + Timeline tab

**Files:**
- Modify: `algorithmic-mirror/app/page.tsx` (add `niche_drift` to the payload)
- Modify: `algorithmic-mirror/app/components/GhostProfileHUD.tsx` (add `niche_drift?` to `GhostProfile`)
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx` (render in the Timeline tab)
- Test: `algorithmic-mirror/__tests__/NicheDriftDashboard.test.tsx`

**Interfaces:**
- Consumes: `NicheDriftResult` (Task 1); `NicheDriftChart` (Task 3); the `analyzeLocal` `out.niche_drift` (Task 2) in `page.tsx`.
- Produces: `payload.niche_drift`; a rendered `<NicheDriftChart>` in the Timeline tab.

- [ ] **Step 1: Write the failing test**

```tsx
// algorithmic-mirror/__tests__/NicheDriftDashboard.test.tsx
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ForensicDashboard } from "../app/components/ForensicDashboard";
import type { GhostProfile } from "../app/components/GhostProfileHUD";

jest.mock("../app/components/CreatorGraph", () => ({ CreatorGraph: () => <div data-testid="creator-graph" /> }));
jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, LineChart: Pass, Line: Pass, XAxis: Pass, YAxis: Pass, CartesianGrid: Pass, Tooltip: Pass, Legend: Pass,
    BarChart: Pass, Bar: Pass, Cell: Pass, PieChart: Pass, Pie: Pass, RadarChart: Pass, Radar: Pass, PolarGrid: Pass, PolarAngleAxis: Pass, PolarRadiusAxis: Pass, Area: Pass, AreaChart: Pass };
});
jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const profile = {
  primary_archetype: { name: "The Balanced Viewer" },
  stopwatch_metrics: { total_conscious_videos: 100 },
  behavioral_nodes: { linger_rate_percentage: 20 },
  niche_drift: {
    status: "ok",
    series: { granularity: "month", points: [
      { period: "2026-01", value: { period: "2026-01", distinct_creators: 40, top5_concentration_pct: 34 } },
      { period: "2026-06", value: { period: "2026-06", distinct_creators: 12, top5_concentration_pct: 58 } },
    ] },
    distinct_creators_trend: { slope: -5.2, direction: "narrowing" },
    top5_concentration_trend: { slope: 4.1, direction: "narrowing" },
    resolved_coverage_pct: 82, method: "…",
  },
} as unknown as GhostProfile;

test("Timeline tab renders the niche-drift chart from the payload", () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Timeline|Evolution/i));
  expect(screen.getByText(/narrowed from 40 to 12/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/NicheDriftDashboard.test.tsx`
Expected: FAIL — no "narrowed from 40 to 12". If the mount throws on a missing profile field, add that field to the minimal `profile` (keep it minimal). If the Timeline tab label differs, match the actual tab button text (grep `activeTab === "timeline"` region for its label).

- [ ] **Step 3a: Add `niche_drift` to the `GhostProfile` interface**

In `algorithmic-mirror/app/components/GhostProfileHUD.tsx`, add the import and field (mirroring `persona?`):

```ts
import type { NicheDriftResult } from "../../engine/nicheDrift";
```
```ts
  // WP-2.5 — per-period creator-concentration drift (present in local payloads).
  niche_drift?: NicheDriftResult;
```

- [ ] **Step 3b: Render the chart in the Timeline tab**

In `algorithmic-mirror/app/components/ForensicDashboard.tsx`, add the import near the other component imports:

```tsx
import { NicheDriftChart } from "./NicheDriftChart";
```

Inside the `{activeTab === "timeline" && ( … )}` block (around line 824), add a panel gated on `profile.niche_drift` (using the existing `DashboardPanel`/`SectionTitle`/`ACCENT`):

```tsx
                {profile.niche_drift && (
                  <div className="md:col-span-2">
                    <DashboardPanel label="Niche Drift" accent={ACCENT}>
                      <SectionTitle>How Your Feed Narrowed</SectionTitle>
                      <NicheDriftChart result={profile.niche_drift} />
                    </DashboardPanel>
                  </div>
                )}
```

- [ ] **Step 3c: Add `niche_drift` to the analyze payload**

In `algorithmic-mirror/app/page.tsx`, in the `analyzeLocal` return object (the one already listing `targeting_card, demographics, persona: out.persona, _local_mode: true`), add `niche_drift: out.niche_drift`:

```ts
    targeting_card, demographics, persona: out.persona, niche_drift: out.niche_drift,
    _local_mode: true,
```

(No new fetch — `niche_drift` already rides in `out` from `runEngineOffThread`.)

- [ ] **Step 4: Run tests + tsc**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/NicheDriftDashboard.test.tsx` → PASS.
Then the whole suite: `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2` → PASS (all).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/page.tsx algorithmic-mirror/app/components/GhostProfileHUD.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx algorithmic-mirror/__tests__/NicheDriftDashboard.test.tsx
git commit -m "feat(app): WP-2.5 wire niche_drift into payload + Timeline tab"
```

---

## Self-Review

**Spec coverage:**
- Redefinition onto per-month distinct creators + top-5 concentration → Task 1 (`buildNicheDrift`). ✓
- Pure engine layer in the pipeline; `buildGhostProfile` untouched → Tasks 1–2. ✓
- Resolved-coverage 40% gate, computed internally → Task 1 (test + impl). ✓
- Sparse-month (<10) → quarter widening, whole series, once → Task 1 (test + impl). ✓
- Least-squares slope, ≥3 buckets else `insufficient_trend`, concentration inverted → Task 1. ✓
- Two signals in one `TemporalSeries<NicheDriftPoint>`; `"quarter"` granularity → Task 1 (`types.ts` union + point shape). ✓
- `TemporalSeries` shape `{granularity, points:[{period, value}]}` → Task 1 emits `points: {period, value}`. ✓
- Minimal 3-state chart with narrative headline, Timeline tab → Tasks 3–4. ✓
- Payload `niche_drift` + `GhostProfile` field → Tasks 2 & 4. ✓
- Out of scope (like-counts, topic-diversity, Python, claims.ts) → not built. ✓

**Placeholder scan:** none — every code/test step is complete. The "match the actual Timeline tab label / add a missing profile field" note in Task 4 is a bounded fallback against existing code, not missing logic.

**Type consistency:** `NicheDriftPoint`/`DriftTrend`/`NicheDriftResult` (Task 1) imported unchanged in Tasks 2/3/4. `buildNicheDrift(profile, linkHandleMap)` matches the Task 2 call site (`profile`, `opts.linkHandleMap`). `TemporalSeries<NicheDriftPoint>` point value is a full `NicheDriftPoint` (period duplicated at point + value, matching the test's `points[0].value.period`). `handleFromLink(link, linkHandleMap): string | null` and `pyRound(x, ndigits)` match their real signatures.

**Note for the implementer:** the test fixtures use links that embed `@handle` so `handleFromLink` resolves them WITHOUT a map (the `extractCreatorFromUrl` path); the coverage-gate test mixes in bare `tiktokv.com/share/video/` links that do NOT resolve without a map, giving a deterministic sub-40% coverage. Run `TZ=UTC` and `npx tsc --noEmit` before each commit.
