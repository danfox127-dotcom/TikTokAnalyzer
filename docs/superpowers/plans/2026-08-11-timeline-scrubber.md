# WP-3.3 Timeline Scrubber Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dual-handle month-range scrubber to the Dossier's Timeline tab that narrows its four time-based panels (Niche Drift, Algorithm Efficiency, Creator Dominance, Topic Trends) to a sub-window of history, client-side only.

**Architecture:** A new pure-function module (`monthRange.ts`) provides trivial array/object filtering by period key. A new `MonthRangeScrubber` component (two overlaid native `<input type="range">` thumbs) drives an `activeRange` state added to `TimelineTab.tsx`, which filters each panel's already-rendered dataset before mapping it to JSX. `NicheDriftChart` gets a new optional `visibleRange` prop that narrows only its plotted chart points, leaving its headline/trend text anchored to the full history. A final task adds framer-motion layout/fade transitions so panel content reflows smoothly as the range narrows.

**Tech Stack:** Next.js 16 (App Router, Turbopack), React 19, TypeScript, `ts-jest` + React Testing Library, `framer-motion`, `recharts`. No new dependencies.

## Global Constraints

- `TheGlassHouse.tsx` is orphaned dead code (unrelated WP-3.1 finding) — never touch it in any task here.
- Filtering is a pure, trivial array/object filter — no recomputation of trends, slopes, or aggregates (satisfies "client-side only, no recompute").
- The niche-drift headline sentence and narrowing/widening trend badge always read the full, unfiltered `NicheDriftResult` — only the chart's plotted points change with the scrub.
- `niche_drift.series` may use quarter-granularity keys (`"2025-Q1"`) when the other three panels always use month keys (`"2025-01"`) — the scrubber's own axis is always months; a quarter point is kept whenever its month range *overlaps* the selected window at all (not only when fully contained).
- The scrubber is a dual-handle range slider (two overlaid native `<input type="range">` elements sharing one visual track) — no new dependency.
- Scoped to `TimelineTab.tsx` only — no state is lifted to `DossierShell.tsx`, no other tab is touched.
- No persistence: `activeRange` lives in `TimelineTab`'s component state only; it resets to full-span on remount, never written to the URL or localStorage.
- When the month-union has 0 or 1 entries, the scrubber does not render at all and every panel shows its full, unfiltered data (matches the existing `Object.keys(rates).length < 2` guard already in the Algorithm Efficiency panel).
- Motion uses the transition `{ type: "spring", stiffness: 320, damping: 18 }` — the same spring values as this codebase's `SPRING_HOVER` in `FileDropzone.tsx` — not a new curve. Respects `prefers-reduced-motion` via framer-motion's `useReducedMotion()` hook.
- Avoid `<style jsx>` (styled-jsx): this project runs tests under plain `ts-jest`, not Next's Babel/SWC pipeline, so styled-jsx's special `jsx` attribute is not stripped under test and would produce an invalid-DOM-attribute warning. Use a plain global CSS class in `app/globals.css` instead, referencing the existing `--ink` / `--accent` custom properties already defined there.
- Run TS tests with `TZ=UTC`; run `npx tsc --noEmit` before every commit.

---

### Task 1: `monthRange.ts` — pure filtering helpers

**Files:**
- Create: `algorithmic-mirror/app/utils/monthRange.ts`
- Test: `algorithmic-mirror/__tests__/monthRange.test.ts`

**Interfaces:**
- Produces: `unionMonths(...monthLists: string[][]): string[]`, `isMonthInRange(month: string, range: [string, string]): boolean`, `filterEntriesByRange<T>(entries: [string, T][], range: [string, string]): [string, T][]`, `quarterOverlapsRange(quarterKey: string, range: [string, string]): boolean` — all named exports, used by Tasks 3 and 4.

- [ ] **Step 1: Write the failing tests**

```ts
// algorithmic-mirror/__tests__/monthRange.test.ts
import { unionMonths, isMonthInRange, filterEntriesByRange, quarterOverlapsRange } from "../app/utils/monthRange";

describe("unionMonths", () => {
  test("dedupes and sorts across multiple lists", () => {
    expect(unionMonths(["2025-03", "2025-01"], ["2025-02", "2025-01"], []))
      .toEqual(["2025-01", "2025-02", "2025-03"]);
  });
  test("empty input returns empty array", () => {
    expect(unionMonths([], [])).toEqual([]);
  });
});

describe("isMonthInRange", () => {
  test("inclusive at both boundaries", () => {
    expect(isMonthInRange("2025-01", ["2025-01", "2025-03"])).toBe(true);
    expect(isMonthInRange("2025-03", ["2025-01", "2025-03"])).toBe(true);
  });
  test("inside the range", () => {
    expect(isMonthInRange("2025-02", ["2025-01", "2025-03"])).toBe(true);
  });
  test("outside the range", () => {
    expect(isMonthInRange("2024-12", ["2025-01", "2025-03"])).toBe(false);
    expect(isMonthInRange("2025-04", ["2025-01", "2025-03"])).toBe(false);
  });
});

describe("filterEntriesByRange", () => {
  const entries: [string, number][] = [["2025-01", 1], ["2025-02", 2], ["2025-03", 3]];
  test("full range is a no-op", () => {
    expect(filterEntriesByRange(entries, ["2025-01", "2025-03"])).toEqual(entries);
  });
  test("narrowed range drops entries outside it", () => {
    expect(filterEntriesByRange(entries, ["2025-02", "2025-02"])).toEqual([["2025-02", 2]]);
  });
  test("range outside all entries returns empty", () => {
    expect(filterEntriesByRange(entries, ["2026-01", "2026-06"])).toEqual([]);
  });
});

describe("quarterOverlapsRange", () => {
  test("range fully inside the quarter overlaps", () => {
    expect(quarterOverlapsRange("2025-Q1", ["2025-02", "2025-02"])).toBe(true);
  });
  test("range partially overlapping the quarter's end overlaps", () => {
    // Q2 = Apr-Jun; range ends in April, inside Q2
    expect(quarterOverlapsRange("2025-Q2", ["2025-01", "2025-04"])).toBe(true);
  });
  test("range entirely after the quarter does not overlap", () => {
    // Q1 = Jan-Mar
    expect(quarterOverlapsRange("2025-Q1", ["2025-04", "2025-05"])).toBe(false);
  });
  test("range entirely before the quarter does not overlap", () => {
    // Q3 = Jul-Sep
    expect(quarterOverlapsRange("2025-Q3", ["2025-01", "2025-03"])).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd algorithmic-mirror && TZ=UTC npx jest monthRange.test.ts`
Expected: FAIL — `Cannot find module '../app/utils/monthRange'`

- [ ] **Step 3: Write the implementation**

```ts
// algorithmic-mirror/app/utils/monthRange.ts
/**
 * WP-3.3 — pure month-range filtering helpers for the Timeline scrubber.
 * No React, no side effects — trivial filters, safe to unit-test directly.
 */

export function unionMonths(...monthLists: string[][]): string[] {
  const set = new Set<string>();
  for (const list of monthLists) {
    for (const month of list) set.add(month);
  }
  return [...set].sort();
}

export function isMonthInRange(month: string, range: [string, string]): boolean {
  const [start, end] = range;
  return month >= start && month <= end;
}

export function filterEntriesByRange<T>(
  entries: [string, T][],
  range: [string, string],
): [string, T][] {
  return entries.filter(([month]) => isMonthInRange(month, range));
}

function quarterMonthBounds(quarterKey: string): [string, string] {
  const [year, q] = quarterKey.split("-Q");
  const quarterNum = Number(q);
  const startMonthNum = (quarterNum - 1) * 3 + 1;
  const endMonthNum = startMonthNum + 2;
  const pad = (n: number) => String(n).padStart(2, "0");
  return [`${year}-${pad(startMonthNum)}`, `${year}-${pad(endMonthNum)}`];
}

export function quarterOverlapsRange(quarterKey: string, range: [string, string]): boolean {
  const [qStart, qEnd] = quarterMonthBounds(quarterKey);
  const [rStart, rEnd] = range;
  return qStart <= rEnd && rStart <= qEnd;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest monthRange.test.ts`
Expected: PASS (12 tests)

- [ ] **Step 5: Typecheck and commit**

Run: `cd algorithmic-mirror && npx tsc --noEmit`
Expected: no errors

```bash
git add algorithmic-mirror/app/utils/monthRange.ts algorithmic-mirror/__tests__/monthRange.test.ts
git commit -m "feat(timeline): add pure month-range filtering helpers"
```

---

### Task 2: `MonthRangeScrubber.tsx` — dual-handle range slider component

**Files:**
- Create: `algorithmic-mirror/app/components/MonthRangeScrubber.tsx`
- Modify: `algorithmic-mirror/app/globals.css` (append scrubber thumb styles)
- Test: `algorithmic-mirror/app/components/__tests__/MonthRangeScrubber.test.tsx`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `MonthRangeScrubber({ months, value, onChange }: MonthRangeScrubberProps)` where `interface MonthRangeScrubberProps { months: string[]; value: [string, string]; onChange: (range: [string, string]) => void; }` — used by Task 4. Renders two `<input type="range">` elements with `aria-label="Start month"` and `aria-label="End month"`.

- [ ] **Step 1: Write the failing tests**

```tsx
// algorithmic-mirror/app/components/__tests__/MonthRangeScrubber.test.tsx
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MonthRangeScrubber } from "../MonthRangeScrubber";

const months = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05"];

test("renders start and end month labels", () => {
  render(<MonthRangeScrubber months={months} value={["2025-01", "2025-05"]} onChange={() => {}} />);
  expect(screen.getByText("2025-01")).toBeInTheDocument();
  expect(screen.getByText("2025-05")).toBeInTheDocument();
});

test("dragging the start thumb forward calls onChange with the new start, unchanged end", () => {
  const onChange = jest.fn();
  render(<MonthRangeScrubber months={months} value={["2025-01", "2025-05"]} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("Start month"), { target: { value: "2" } });
  expect(onChange).toHaveBeenCalledWith(["2025-03", "2025-05"]);
});

test("dragging the end thumb backward calls onChange with unchanged start, new end", () => {
  const onChange = jest.fn();
  render(<MonthRangeScrubber months={months} value={["2025-01", "2025-05"]} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("End month"), { target: { value: "2" } });
  expect(onChange).toHaveBeenCalledWith(["2025-01", "2025-03"]);
});

test("the start thumb cannot be dragged past the end thumb", () => {
  const onChange = jest.fn();
  render(<MonthRangeScrubber months={months} value={["2025-01", "2025-02"]} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("Start month"), { target: { value: "4" } });
  expect(onChange).toHaveBeenCalledWith(["2025-02", "2025-02"]);
});

test("the end thumb cannot be dragged before the start thumb", () => {
  const onChange = jest.fn();
  render(<MonthRangeScrubber months={months} value={["2025-03", "2025-04"]} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("End month"), { target: { value: "0" } });
  expect(onChange).toHaveBeenCalledWith(["2025-03", "2025-03"]);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd algorithmic-mirror && TZ=UTC npx jest MonthRangeScrubber.test.tsx`
Expected: FAIL — `Cannot find module '../MonthRangeScrubber'`

- [ ] **Step 3: Write the implementation**

```tsx
// algorithmic-mirror/app/components/MonthRangeScrubber.tsx
"use client";
/**
 * WP-3.3 — dual-handle month-range scrubber. Two overlaid native
 * <input type="range"> thumbs sharing one visual track (styles in
 * globals.css under .month-scrubber-input); no new dependency.
 */
import { BORDER, ACCENT, INK_DIM } from "./dashboardPrimitives";

export interface MonthRangeScrubberProps {
  months: string[];
  value: [string, string];
  onChange: (range: [string, string]) => void;
}

export function MonthRangeScrubber({ months, value, onChange }: MonthRangeScrubberProps) {
  const maxIndex = months.length - 1;
  const startIndex = months.indexOf(value[0]);
  const endIndex = months.indexOf(value[1]);

  function handleStartChange(e: React.ChangeEvent<HTMLInputElement>) {
    const next = Math.min(Number(e.target.value), endIndex);
    onChange([months[next], months[endIndex]]);
  }
  function handleEndChange(e: React.ChangeEvent<HTMLInputElement>) {
    const next = Math.max(Number(e.target.value), startIndex);
    onChange([months[startIndex], months[next]]);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: "16px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, fontFamily: "var(--font-mono, monospace)", color: INK_DIM, letterSpacing: "0.1em" }}>
        <span>{value[0]}</span>
        <span>{value[1]}</span>
      </div>
      <div style={{ position: "relative", height: 24 }}>
        <div style={{ position: "absolute", top: 11, left: 0, right: 0, height: 2, background: BORDER }} />
        <div
          style={{
            position: "absolute",
            top: 11,
            height: 2,
            background: ACCENT,
            left: `${(startIndex / maxIndex) * 100}%`,
            right: `${100 - (endIndex / maxIndex) * 100}%`,
          }}
        />
        <input
          type="range"
          className="month-scrubber-input"
          aria-label="Start month"
          min={0}
          max={maxIndex}
          value={startIndex}
          onChange={handleStartChange}
        />
        <input
          type="range"
          className="month-scrubber-input"
          aria-label="End month"
          min={0}
          max={maxIndex}
          value={endIndex}
          onChange={handleEndChange}
        />
      </div>
    </div>
  );
}
```

Append to the end of `algorithmic-mirror/app/globals.css`:

```css

/* ── WP-3.3 month-range scrubber — two overlaid <input type="range"> thumbs
   sharing one visual track. Only the thumb captures pointer events; the
   track itself is transparent and non-interactive so both handles stay
   independently draggable. ───────────────────────────────────────────── */
.month-scrubber-input {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  margin: 0;
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  pointer-events: none;
}
.month-scrubber-input::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  pointer-events: auto;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--ink);
  cursor: pointer;
  margin-top: 4px;
}
.month-scrubber-input::-moz-range-thumb {
  pointer-events: auto;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--ink);
  cursor: pointer;
  border: none;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest MonthRangeScrubber.test.tsx`
Expected: PASS (5 tests)

- [ ] **Step 5: Typecheck and commit**

Run: `cd algorithmic-mirror && npx tsc --noEmit`
Expected: no errors

```bash
git add algorithmic-mirror/app/components/MonthRangeScrubber.tsx algorithmic-mirror/app/components/__tests__/MonthRangeScrubber.test.tsx algorithmic-mirror/app/globals.css
git commit -m "feat(timeline): add MonthRangeScrubber dual-handle slider component"
```

---

### Task 3: `NicheDriftChart.tsx` — optional `visibleRange` prop

**Files:**
- Modify: `algorithmic-mirror/app/components/NicheDriftChart.tsx`
- Test: `algorithmic-mirror/__tests__/NicheDriftChart.test.tsx` (existing — extend, do not remove existing tests)

**Interfaces:**
- Consumes: Task 1's `isMonthInRange(month, range)` and `quarterOverlapsRange(quarterKey, range)`.
- Produces: `NicheDriftChart({ result, visibleRange }: { result?: NicheDriftResult; visibleRange?: [string, string] })` — used by Task 4.

- [ ] **Step 1: Write the failing tests**

Replace the `jest.mock("recharts", ...)` block and add these two new `test(...)` blocks inside the existing `describe("NicheDriftChart", ...)` in `algorithmic-mirror/__tests__/NicheDriftChart.test.tsx` (keep every existing `test(...)` in that file unchanged):

```tsx
// Replace the existing jest.mock("recharts", ...) block at the top of the file with:
jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  const LineChart = ({ children, data }: any) =>
    React.createElement("div", { "data-testid": "linechart", "data-points": String((data ?? []).length) }, children);
  return { ResponsiveContainer: Pass, LineChart, Line: Pass, XAxis: Pass, YAxis: Pass, CartesianGrid: Pass, Tooltip: Pass, Legend: Pass };
});

// Add inside describe("NicheDriftChart", ...), after the existing "undefined → renders nothing" test:
  test("no visibleRange: plots every point", () => {
    render(<NicheDriftChart result={ok} />);
    expect(screen.getByTestId("linechart")).toHaveAttribute("data-points", "2");
  });

  test("visibleRange narrows the plotted points but not the headline", () => {
    render(<NicheDriftChart result={ok} visibleRange={["2026-01", "2026-01"]} />);
    expect(screen.getByTestId("linechart")).toHaveAttribute("data-points", "1");
    // headline still reads the full, unfiltered result (40 → 12), not the visible slice
    expect(screen.getByText(/narrowed/i)).toBeInTheDocument();
    expect(screen.getByText(/40/)).toBeInTheDocument();
    expect(screen.getByText(/12/)).toBeInTheDocument();
  });

  test("visibleRange with quarter granularity keeps a quarter whose range overlaps at all", () => {
    const quarterly: NicheDriftResult = {
      ...ok,
      series: { granularity: "quarter", points: [
        { period: "2026-Q1", value: { period: "2026-Q1", distinct_creators: 40, top5_concentration_pct: 34 } },
        { period: "2026-Q3", value: { period: "2026-Q3", distinct_creators: 12, top5_concentration_pct: 58 } },
      ] },
    };
    render(<NicheDriftChart result={quarterly} visibleRange={["2026-02", "2026-02"]} />);
    // 2026-02 falls inside Q1 (Jan-Mar), not Q3 (Jul-Sep)
    expect(screen.getByTestId("linechart")).toHaveAttribute("data-points", "1");
  });
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd algorithmic-mirror && TZ=UTC npx jest NicheDriftChart.test.tsx`
Expected: the 3 new tests FAIL (`visibleRange` prop doesn't exist yet, `data-testid="linechart"` attribute not asserted by the old mock's Pass-through); the 4 pre-existing tests still PASS.

- [ ] **Step 3: Write the implementation**

In `algorithmic-mirror/app/components/NicheDriftChart.tsx`, add the import and change the component signature + data computation. The full modified file:

```tsx
"use client";
/**
 * WP-2.5 — minimal niche-drift chart. Two lines (distinct creators + top-5
 * concentration %) over the month/quarter x-axis, from payload alone (ok /
 * insufficient_evidence / error). The polished Timeline panel is WP-3.4.
 * WP-3.3 — optional `visibleRange` narrows which points are plotted; the
 * headline and trend badges always read the full, unfiltered `result`.
 */
import { Lock, AlertTriangle } from "lucide-react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import type { NicheDriftResult } from "../../engine/nicheDrift";
import { isMonthInRange, quarterOverlapsRange } from "../utils/monthRange";

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
  if (result.distinct_creators_trend.direction === "insufficient_trend")
    return `Too few periods yet to read a trend — ${last} creators most recently.`;
  return `Your feed held steady around ${last} creators.`;
}

export function NicheDriftChart({ result, visibleRange }: { result?: NicheDriftResult; visibleRange?: [string, string] }) {
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

  const visiblePoints = visibleRange
    ? result.series.points.filter((p) =>
        result.series.granularity === "quarter"
          ? quarterOverlapsRange(p.value.period, visibleRange)
          : isMonthInRange(p.value.period, visibleRange)
      )
    : result.series.points;
  const data = visiblePoints.map((p) => ({
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest NicheDriftChart.test.tsx`
Expected: PASS (7 tests: 4 pre-existing + 3 new)

- [ ] **Step 5: Typecheck and commit**

Run: `cd algorithmic-mirror && npx tsc --noEmit`
Expected: no errors

```bash
git add algorithmic-mirror/app/components/NicheDriftChart.tsx algorithmic-mirror/__tests__/NicheDriftChart.test.tsx
git commit -m "feat(timeline): add visibleRange prop to NicheDriftChart"
```

---

### Task 4: `TimelineTab.tsx` — wire the scrubber and filter the four panels

**Files:**
- Modify: `algorithmic-mirror/app/components/tabs/TimelineTab.tsx`
- Test: `algorithmic-mirror/app/components/tabs/__tests__/TimelineTab.test.tsx` (existing — extend)

**Interfaces:**
- Consumes: Task 1's `unionMonths`, `isMonthInRange`, `filterEntriesByRange`; Task 2's `MonthRangeScrubber`; Task 3's `NicheDriftChart` with its new `visibleRange` prop.
- Produces: `TimelineTab({ profile }: { profile: GhostProfile })` — same signature as before (unchanged); no new exports consumed by later tasks besides the file itself, which Task 5 modifies further.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `algorithmic-mirror/app/components/tabs/__tests__/TimelineTab.test.tsx`:

```tsx
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { TimelineTab } from "../TimelineTab";
import type { GhostProfile } from "../../GhostProfileHUD";

jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, LineChart: Pass, Line: Pass, XAxis: Pass, YAxis: Pass, CartesianGrid: Pass, Tooltip: Pass, Legend: Pass };
});

const minimalProfile = {
  stopwatch_metrics: {},
} as unknown as GhostProfile;

const richProfile = {
  stopwatch_metrics: {
    monthly_skip_rates: { "2026-01": 40, "2026-02": 35, "2026-03": 50 },
  },
  skip_anomalies: [
    { month: "2026-03", skip_rate: 50, baseline_avg: 38, delta: 12, direction: "spike" as const },
  ],
  monthly_creator_trends: {
    "2026-01": [{ handle: "@one", count: 10 }],
    "2026-02": [{ handle: "@two", count: 8 }],
    "2026-03": [{ handle: "@three", count: 5 }],
  },
  monthly_topic_trends: {
    "2026-01": [{ term: "cooking", count: 12 }],
    "2026-02": [{ term: "hiking", count: 9 }],
    "2026-03": [{ term: "coding", count: 7 }],
  },
} as unknown as GhostProfile;

test("TimelineTab renders without throwing", () => {
  const { container } = render(<TimelineTab profile={minimalProfile} />);
  expect(container).not.toBeEmptyDOMElement();
});

test("with < 2 months of history, no scrubber renders", () => {
  render(<TimelineTab profile={minimalProfile} />);
  expect(screen.queryByLabelText("Start month")).not.toBeInTheDocument();
});

test("with >= 2 months of history, the scrubber renders spanning the full range", () => {
  render(<TimelineTab profile={richProfile} />);
  expect(screen.getByLabelText("Start month")).toBeInTheDocument();
  expect(screen.getByText("2026-01")).toBeInTheDocument();
  expect(screen.getByText("2026-03")).toBeInTheDocument();
});

test("narrowing the range hides creator/topic cards outside it", () => {
  render(<TimelineTab profile={richProfile} />);
  expect(screen.getByText("@one")).toBeInTheDocument();
  expect(screen.getByText("@three")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("End month"), { target: { value: "0" } });

  expect(screen.getByText("@one")).toBeInTheDocument();
  expect(screen.queryByText("@three")).not.toBeInTheDocument();
});

test("narrowing the range drops out-of-window anomalies", () => {
  render(<TimelineTab profile={richProfile} />);
  expect(screen.getByText(/anomaly/i)).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("End month"), { target: { value: "0" } });

  expect(screen.queryByText(/anomaly/i)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd algorithmic-mirror && TZ=UTC npx jest tabs/__tests__/TimelineTab.test.tsx`
Expected: FAIL — no `aria-label="Start month"` element exists yet (scrubber not wired in).

- [ ] **Step 3: Write the implementation**

Replace the full contents of `algorithmic-mirror/app/components/tabs/TimelineTab.tsx`:

```tsx
"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
/** WP-3.3 — month-range scrubber narrows the panels below to a sub-window of history. */
import { useState } from "react";
import type { GhostProfile } from "../GhostProfileHUD";
import { NicheDriftChart } from "../NicheDriftChart";
import { MonthRangeScrubber } from "../MonthRangeScrubber";
import { unionMonths, isMonthInRange, filterEntriesByRange } from "../../utils/monthRange";
import { BORDER, ACCENT, MODULE_A, MODULE_B, VIBE_ACCENT, INK, INK_DIM, INK_GHOST, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

export function TimelineTab({ profile }: { profile: GhostProfile }) {
  const skipRates = profile.stopwatch_metrics.monthly_skip_rates ?? {};
  const creatorTrends = profile.monthly_creator_trends ?? {};
  const topicTrends = profile.monthly_topic_trends ?? {};
  const months = unionMonths(Object.keys(skipRates), Object.keys(creatorTrends), Object.keys(topicTrends));
  const showScrubber = months.length >= 2;

  const [range, setRange] = useState<[string, string]>(
    showScrubber ? [months[0], months[months.length - 1]] : ["", ""]
  );
  const activeRange: [string, string] | null = showScrubber ? range : null;

  const visibleSkipEntries = (activeRange ? filterEntriesByRange(Object.entries(skipRates), activeRange) : Object.entries(skipRates))
    .sort(([a], [b]) => a.localeCompare(b));
  const visibleAnomalies = activeRange
    ? (profile.skip_anomalies ?? []).filter((a) => isMonthInRange(a.month, activeRange))
    : (profile.skip_anomalies ?? []);
  const visibleCreatorEntries = (activeRange ? filterEntriesByRange(Object.entries(creatorTrends), activeRange) : Object.entries(creatorTrends))
    .sort(([a], [b]) => a.localeCompare(b));
  const visibleTopicEntries = (activeRange ? filterEntriesByRange(Object.entries(topicTrends), activeRange) : Object.entries(topicTrends))
    .sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="grid grid-cols-1 gap-8">
      {showScrubber && (
        <MonthRangeScrubber months={months} value={range} onChange={setRange} />
      )}

      {profile.niche_drift && (
        <div className="md:col-span-2">
          <DashboardPanel label="Niche Drift" accent={ACCENT}>
            <SectionTitle>How Your Feed Narrowed</SectionTitle>
            <NicheDriftChart result={profile.niche_drift} visibleRange={activeRange ?? undefined} />
          </DashboardPanel>
        </div>
      )}

      {/* Algorithm efficiency + anomaly flags */}
      {(() => {
        if (!skipRates || Object.keys(skipRates).length < 2) return null;
        const maxRate = Math.max(...visibleSkipEntries.map(([, v]) => v), 1);
        const anomalyMonths = new Set(visibleAnomalies.map(a => a.month));
        return (
          <DashboardPanel label="· Algorithm Efficiency Timeline" accent={ACCENT}>
            <SectionTitle>Skip Rate Over Time</SectionTitle>
            <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
              When the skip rate goes down, the algorithm has a better read on you — it's serving content you actually want. When it spikes, something changed: your tastes shifted, the algorithm lost its calibration, or the platform started pushing content you didn't ask for.
            </div>
            <div style={{ display: "flex", gap: 4, alignItems: "flex-end", height: 80, marginBottom: 8 }}>
              {visibleSkipEntries.map(([month, rate]) => {
                const isAnomaly = anomalyMonths.has(month);
                const color = isAnomaly ? MODULE_B : VIBE_ACCENT;
                return (
                  <div key={month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                    {isAnomaly && <div style={{ width: 6, height: 6, borderRadius: "50%", background: MODULE_B, flexShrink: 0 }} title="Anomaly detected" />}
                    <div style={{ width: "100%", height: `${Math.max((rate / maxRate) * 72, 4)}px`, background: color, opacity: isAnomaly ? 1 : 0.65 }} title={`${month}: ${rate}% skip`} />
                  </div>
                );
              })}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: INK_GHOST, fontFamily: "var(--font-mono, monospace)", marginBottom: 16 }}>
              <span>{visibleSkipEntries[0]?.[0]}</span>
              <span>{visibleSkipEntries[visibleSkipEntries.length - 1]?.[0]}</span>
            </div>
            {visibleAnomalies.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {visibleAnomalies.map((a, i) => (
                  <div key={i} style={{ padding: "12px 16px", border: `1px solid ${MODULE_B}40`, background: `${MODULE_B}08` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: MODULE_B }}>{a.month} · anomaly</span>
                      <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: INK }}>{a.skip_rate}% <span style={{ color: INK_GHOST }}>vs {a.baseline_avg}% baseline</span></span>
                    </div>
                    <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6 }}>
                      Skip rate {a.direction === "spike" ? "spiked" : "dipped"} {Math.abs(a.delta)}pp from your baseline. This could mean the algorithm lost its read on you, your tastes shifted, the platform changed what it was pushing, or a data purge disrupted the recommendation model. The data alone can't say which.
                    </div>
                  </div>
                ))}
              </div>
            )}
          </DashboardPanel>
        );
      })()}

      {/* Monthly creator dominance */}
      {(() => {
        if (!creatorTrends || Object.keys(creatorTrends).length === 0) return null;
        return (
          <DashboardPanel label="· Creator Dominance by Month" accent={VIBE_ACCENT}>
            <SectionTitle accent={VIBE_ACCENT}>Who You Were Watching</SectionTitle>
            <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
              The creators you lingered on most, month by month. Shifts here show the algorithm changing what it thinks you want — or you actively seeking something new.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16 }}>
              {visibleCreatorEntries.map(([month, creators]) => (
                <div key={month} style={{ border: `1px solid ${BORDER}`, padding: 16 }}>
                  <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 12 }}>{month}</div>
                  {creators.length === 0 ? (
                    <div style={{ fontSize: 11, color: INK_GHOST }}>No resolved creators</div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {creators.map((c, i) => (
                        <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                          <span style={{ color: i === 0 ? VIBE_ACCENT : INK_DIM, fontFamily: "var(--font-mono, monospace)" }}>{c.handle}</span>
                          <span style={{ color: INK_GHOST }}>{c.count}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </DashboardPanel>
        );
      })()}

      {/* Monthly topic trends */}
      {(() => {
        if (!topicTrends || Object.keys(topicTrends).length === 0) return null;
        return (
          <DashboardPanel label="· Topic Trends by Month" accent={MODULE_A}>
            <SectionTitle accent={MODULE_A}>What You Were Into</SectionTitle>
            <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
              Top keywords from your searches and comments each month. A snapshot of what was on your mind.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16 }}>
              {visibleTopicEntries.map(([month, topics]) => (
                <div key={month} style={{ border: `1px solid ${BORDER}`, padding: 16 }}>
                  <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 12 }}>{month}</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                    {topics.map((t, i) => (
                      <span key={i} style={{ fontSize: 10, padding: "3px 8px", background: i === 0 ? `${MODULE_A}20` : "transparent", border: `1px solid ${i === 0 ? MODULE_A : BORDER}`, color: i === 0 ? MODULE_A : INK_DIM }}>
                        {t.term}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </DashboardPanel>
        );
      })()}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest tabs/__tests__/TimelineTab.test.tsx`
Expected: PASS (5 tests)

Also run the full suite to confirm no regressions:

Run: `cd algorithmic-mirror && TZ=UTC npx jest`
Expected: all suites pass (same pass count as before this task, plus the new/extended ones)

- [ ] **Step 5: Typecheck and commit**

Run: `cd algorithmic-mirror && npx tsc --noEmit`
Expected: no errors

```bash
git add algorithmic-mirror/app/components/tabs/TimelineTab.tsx algorithmic-mirror/app/components/tabs/__tests__/TimelineTab.test.tsx
git commit -m "feat(timeline): wire month-range scrubber into TimelineTab"
```

---

### Task 5: `TimelineTab.tsx` — spring-morph transitions on scrub

**Files:**
- Modify: `algorithmic-mirror/app/components/tabs/TimelineTab.tsx` (from Task 4's state)
- Modify: `algorithmic-mirror/app/components/tabs/__tests__/TimelineTab.test.tsx` (from Task 4's state — add framer-motion mock + one new test)

**Interfaces:**
- Consumes: Task 4's `TimelineTab.tsx` (filtering already wired; this task only adds motion wrapping around the same filtered arrays — no new filtering logic).
- Produces: same `TimelineTab({ profile }: { profile: GhostProfile })` signature — this is the last task touching this file.

- [ ] **Step 1: Add the framer-motion mock and the new regression test**

Add this `jest.mock("framer-motion", ...)` block right after the existing `jest.mock("recharts", ...)` block in `algorithmic-mirror/app/components/tabs/__tests__/TimelineTab.test.tsx` — this is the final, correct form (it already strips `layout` along with the other animation-only props, matching the Proxy pattern used in every other WP-3.1 tab test):

```tsx
jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, layout, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap; void layout;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return {
    motion,
    AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children),
    useReducedMotion: () => false,
  };
});
```

And add this test at the end of the file (after the existing tests). It's a regression guard, not a feature test — it stays green right now (Step 2), because `TimelineTab.tsx` doesn't use `framer-motion` yet so there's nothing to warn about. Its real job is to catch the specific mistake of forgetting to strip a new animation prop from the mock; that's checked for real once Step 3 wires `motion.div`/`layout` into the component and this test runs again in Step 4.

```tsx
test("motion wrapper props do not leak onto the DOM (no React 'unknown prop' warnings)", () => {
  const spy = jest.spyOn(console, "error").mockImplementation(() => {});
  render(<TimelineTab profile={richProfile} />);
  expect(spy).not.toHaveBeenCalled();
  spy.mockRestore();
});
```

- [ ] **Step 2: Run tests to verify nothing broke**

Run: `cd algorithmic-mirror && TZ=UTC npx jest tabs/__tests__/TimelineTab.test.tsx`
Expected: PASS (6 tests) — the 5 tests from Task 4 are unaffected by adding a mock for a module `TimelineTab.tsx` doesn't import yet, and the new regression test passes vacuously (no motion code exists yet to trigger a warning). This confirms the starting state before Step 3's real change.

- [ ] **Step 3: Add motion wrapping to the implementation**

Replace the full contents of `algorithmic-mirror/app/components/tabs/TimelineTab.tsx`:

```tsx
"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
/** WP-3.3 — month-range scrubber narrows the panels below to a sub-window of history. */
import { useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import type { GhostProfile } from "../GhostProfileHUD";
import { NicheDriftChart } from "../NicheDriftChart";
import { MonthRangeScrubber } from "../MonthRangeScrubber";
import { unionMonths, isMonthInRange, filterEntriesByRange } from "../../utils/monthRange";
import { BORDER, ACCENT, MODULE_A, MODULE_B, VIBE_ACCENT, INK, INK_DIM, INK_GHOST, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

const SPRING = { type: "spring", stiffness: 320, damping: 18 } as const;

export function TimelineTab({ profile }: { profile: GhostProfile }) {
  const prefersReducedMotion = useReducedMotion();
  const transition = prefersReducedMotion ? { duration: 0 } : SPRING;

  const skipRates = profile.stopwatch_metrics.monthly_skip_rates ?? {};
  const creatorTrends = profile.monthly_creator_trends ?? {};
  const topicTrends = profile.monthly_topic_trends ?? {};
  const months = unionMonths(Object.keys(skipRates), Object.keys(creatorTrends), Object.keys(topicTrends));
  const showScrubber = months.length >= 2;

  const [range, setRange] = useState<[string, string]>(
    showScrubber ? [months[0], months[months.length - 1]] : ["", ""]
  );
  const activeRange: [string, string] | null = showScrubber ? range : null;

  const visibleSkipEntries = (activeRange ? filterEntriesByRange(Object.entries(skipRates), activeRange) : Object.entries(skipRates))
    .sort(([a], [b]) => a.localeCompare(b));
  const visibleAnomalies = activeRange
    ? (profile.skip_anomalies ?? []).filter((a) => isMonthInRange(a.month, activeRange))
    : (profile.skip_anomalies ?? []);
  const visibleCreatorEntries = (activeRange ? filterEntriesByRange(Object.entries(creatorTrends), activeRange) : Object.entries(creatorTrends))
    .sort(([a], [b]) => a.localeCompare(b));
  const visibleTopicEntries = (activeRange ? filterEntriesByRange(Object.entries(topicTrends), activeRange) : Object.entries(topicTrends))
    .sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="grid grid-cols-1 gap-8">
      {showScrubber && (
        <MonthRangeScrubber months={months} value={range} onChange={setRange} />
      )}

      {profile.niche_drift && (
        <div className="md:col-span-2">
          <DashboardPanel label="Niche Drift" accent={ACCENT}>
            <SectionTitle>How Your Feed Narrowed</SectionTitle>
            <NicheDriftChart result={profile.niche_drift} visibleRange={activeRange ?? undefined} />
          </DashboardPanel>
        </div>
      )}

      {/* Algorithm efficiency + anomaly flags */}
      {(() => {
        if (!skipRates || Object.keys(skipRates).length < 2) return null;
        const maxRate = Math.max(...visibleSkipEntries.map(([, v]) => v), 1);
        const anomalyMonths = new Set(visibleAnomalies.map(a => a.month));
        return (
          <DashboardPanel label="· Algorithm Efficiency Timeline" accent={ACCENT}>
            <SectionTitle>Skip Rate Over Time</SectionTitle>
            <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
              When the skip rate goes down, the algorithm has a better read on you — it's serving content you actually want. When it spikes, something changed: your tastes shifted, the algorithm lost its calibration, or the platform started pushing content you didn't ask for.
            </div>
            <div style={{ display: "flex", gap: 4, alignItems: "flex-end", height: 80, marginBottom: 8 }}>
              <AnimatePresence>
                {visibleSkipEntries.map(([month, rate]) => {
                  const isAnomaly = anomalyMonths.has(month);
                  const color = isAnomaly ? MODULE_B : VIBE_ACCENT;
                  return (
                    <motion.div
                      key={month}
                      layout={!prefersReducedMotion}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={transition}
                      style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}
                    >
                      {isAnomaly && <div style={{ width: 6, height: 6, borderRadius: "50%", background: MODULE_B, flexShrink: 0 }} title="Anomaly detected" />}
                      <div style={{ width: "100%", height: `${Math.max((rate / maxRate) * 72, 4)}px`, background: color, opacity: isAnomaly ? 1 : 0.65 }} title={`${month}: ${rate}% skip`} />
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: INK_GHOST, fontFamily: "var(--font-mono, monospace)", marginBottom: 16 }}>
              <span>{visibleSkipEntries[0]?.[0]}</span>
              <span>{visibleSkipEntries[visibleSkipEntries.length - 1]?.[0]}</span>
            </div>
            {visibleAnomalies.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <AnimatePresence>
                  {visibleAnomalies.map((a) => (
                    <motion.div
                      key={a.month}
                      layout={!prefersReducedMotion}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={transition}
                      style={{ padding: "12px 16px", border: `1px solid ${MODULE_B}40`, background: `${MODULE_B}08` }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                        <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: MODULE_B }}>{a.month} · anomaly</span>
                        <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: INK }}>{a.skip_rate}% <span style={{ color: INK_GHOST }}>vs {a.baseline_avg}% baseline</span></span>
                      </div>
                      <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6 }}>
                        Skip rate {a.direction === "spike" ? "spiked" : "dipped"} {Math.abs(a.delta)}pp from your baseline. This could mean the algorithm lost its read on you, your tastes shifted, the platform changed what it was pushing, or a data purge disrupted the recommendation model. The data alone can't say which.
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </DashboardPanel>
        );
      })()}

      {/* Monthly creator dominance */}
      {(() => {
        if (!creatorTrends || Object.keys(creatorTrends).length === 0) return null;
        return (
          <DashboardPanel label="· Creator Dominance by Month" accent={VIBE_ACCENT}>
            <SectionTitle accent={VIBE_ACCENT}>Who You Were Watching</SectionTitle>
            <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
              The creators you lingered on most, month by month. Shifts here show the algorithm changing what it thinks you want — or you actively seeking something new.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16 }}>
              <AnimatePresence>
                {visibleCreatorEntries.map(([month, creators]) => (
                  <motion.div
                    key={month}
                    layout={!prefersReducedMotion}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={transition}
                    style={{ border: `1px solid ${BORDER}`, padding: 16 }}
                  >
                    <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 12 }}>{month}</div>
                    {creators.length === 0 ? (
                      <div style={{ fontSize: 11, color: INK_GHOST }}>No resolved creators</div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        {creators.map((c, i) => (
                          <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                            <span style={{ color: i === 0 ? VIBE_ACCENT : INK_DIM, fontFamily: "var(--font-mono, monospace)" }}>{c.handle}</span>
                            <span style={{ color: INK_GHOST }}>{c.count}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </DashboardPanel>
        );
      })()}

      {/* Monthly topic trends */}
      {(() => {
        if (!topicTrends || Object.keys(topicTrends).length === 0) return null;
        return (
          <DashboardPanel label="· Topic Trends by Month" accent={MODULE_A}>
            <SectionTitle accent={MODULE_A}>What You Were Into</SectionTitle>
            <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
              Top keywords from your searches and comments each month. A snapshot of what was on your mind.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16 }}>
              <AnimatePresence>
                {visibleTopicEntries.map(([month, topics]) => (
                  <motion.div
                    key={month}
                    layout={!prefersReducedMotion}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={transition}
                    style={{ border: `1px solid ${BORDER}`, padding: 16 }}
                  >
                    <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 12 }}>{month}</div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                      {topics.map((t, i) => (
                        <span key={i} style={{ fontSize: 10, padding: "3px 8px", background: i === 0 ? `${MODULE_A}20` : "transparent", border: `1px solid ${i === 0 ? MODULE_A : BORDER}`, color: i === 0 ? MODULE_A : INK_DIM }}>
                          {t.term}
                        </span>
                      ))}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </DashboardPanel>
        );
      })()}
    </div>
  );
}
```

Note the anomaly card's `key` changed from the array index (`key={i}`) to `key={a.month}` — a stable identifier is required for `AnimatePresence` to correctly animate individual items in and out; an index-based key would misattribute exit animations when the anomaly list's composition changes between scrub positions.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest tabs/__tests__/TimelineTab.test.tsx`
Expected: PASS (6 tests: the 5 from Task 4 + this task's new one). This run is the meaningful check for the "no unknown prop" regression test: `TimelineTab.tsx` now renders real `motion.div` elements with a `layout` prop, so if Step 1's mock had NOT already stripped `layout`, this specific run would fail here with a captured `console.error` call (React's "Unknown prop `layout`" DOM warning). Passing here confirms the mock correctly handles every animation prop the component now uses.

Also run the full suite to confirm no regressions:

Run: `cd algorithmic-mirror && TZ=UTC npx jest`
Expected: all suites pass

- [ ] **Step 5: Typecheck and commit**

Run: `cd algorithmic-mirror && npx tsc --noEmit`
Expected: no errors

```bash
git add algorithmic-mirror/app/components/tabs/TimelineTab.tsx algorithmic-mirror/app/components/tabs/__tests__/TimelineTab.test.tsx
git commit -m "feat(timeline): add spring-morph transitions to scrubbed panels"
```
