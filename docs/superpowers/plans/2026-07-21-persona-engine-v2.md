# Persona Engine v2 (WP-2.4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the archetype `if`-statement cascade with a 6-dimension persona vector (0–100 each) computed from existing profile metrics, mapped to a named archetype via a config map of centroids, with nocturnality as a descriptive prefix.

**Architecture:** A pure client-side TS layer `engine/persona.ts` — `buildPersona(profile, coverage)` — computed over the already-emitted profile, surfaced in `pipeline.ts` like `topicCandidates`. `buildGhostProfile` is UNTOUCHED (no parity risk). A minimal `PersonaRadar` renders it; the old archetype fields stay as a deprecated alias for one release.

**Tech Stack:** TypeScript (ts-jest, `algorithmic-mirror/engine/`), React 19 / Next 16, recharts (already a dep), `@testing-library/react`.

## Global Constraints

- **Pure client TS**, browser-safe: `engine/persona.ts` uses **no `fs`/`path`/`crypto`/`process`/`require`**.
- Every dimension score clamps to **[0,100]**; absent inputs contribute **0** (guard with `Number.isFinite`, never NaN).
- `night_shift_ratio`, `skip_rate_percentage`, `linger_rate_percentage`, `social_graph_*_pct`, `echo_chamber_index_pct` are already **percentages (0–100)**.
- Nocturnality is **excluded from the centroid distance** — it is a radar axis + a rendered prefix only.
- Nearest-centroid over the **5 "who" dimensions** (intentionality, capture_susceptibility, exploration, expressiveness, parasociality); **primary** = nearest, **secondary** = 2nd-nearest only if `secondDist ≤ firstDist + 25`, **confidence** = `clamp01(1 − firstDist/maxDist)`.
- Coverage gate reuses the existing `requireCoverage("persona", coverage, { consciousViews })` (registry already has `persona: { minDays: 30, minConsciousViews: 500 }`).
- `buildPersona` does **not** modify `buildGhostProfile`/`ghostProfile.ts`, `claims.ts`, `archetypes.ts`, or golden fixtures — the old `primary_archetype`/`sub_archetypes` stay as a deprecated alias.
- Exact profile field paths (verified): `behavioral_nodes.{social_graph_followed_pct, social_graph_algorithmic_pct, skip_rate_percentage, linger_rate_percentage, night_shift_ratio}`, `academic_insights.{explicit_vs_implicit_ratio, echo_chamber_index_pct, echo_chamber_distinct_creators}`, `stopwatch_metrics.{max_session_duration, total_conscious_videos}`, `search_rhythm.total_searches`, `comment_voice.{total_comments, long_comment_pct, references_detected}`, `share_behavior.total_shares`.
- `monthly` per-dimension series is **out of scope this plan** (spec §11 escape hatch: the other 4 dimensions lack per-month inputs; a full monthly vector needs new plumbing). `PersonaResult.monthly` is not populated.
- Run TS tests with **`TZ=UTC`**; run **`npx tsc --noEmit`** before every commit (ts-jest does not type-check).

---

### Task 1: `persona.ts` — dimensions + types

**Files:**
- Create: `algorithmic-mirror/engine/persona.ts`
- Test: `algorithmic-mirror/engine/__tests__/persona.test.ts`

**Interfaces:**
- Produces: `PersonaDimensions`, `PersonaResult` (types); `computeDimensions(profile: any): PersonaDimensions`.

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/engine/__tests__/persona.test.ts
import { computeDimensions } from "../persona";

// a profile with the dimension inputs; omitted fields default to 0
const prof = (over: any = {}) => ({
  behavioral_nodes: { social_graph_followed_pct: 0, social_graph_algorithmic_pct: 0,
    skip_rate_percentage: 0, linger_rate_percentage: 0, night_shift_ratio: 0, ...(over.bn ?? {}) },
  academic_insights: { explicit_vs_implicit_ratio: 0, echo_chamber_index_pct: 0,
    echo_chamber_distinct_creators: 0, ...(over.ai ?? {}) },
  stopwatch_metrics: { max_session_duration: 0, total_conscious_videos: 0, ...(over.sw ?? {}) },
  search_rhythm: { total_searches: 0, ...(over.sr ?? {}) },
  comment_voice: { total_comments: 0, long_comment_pct: 0, references_detected: {}, ...(over.cv ?? {}) },
  share_behavior: { total_shares: 0, ...(over.sb ?? {}) },
});

describe("computeDimensions", () => {
  test("all-zero profile → dimensions finite & clamped; exploration has an echo-inverse base", () => {
    const d = computeDimensions(prof());
    for (const v of Object.values(d)) {
      expect(Number.isFinite(v)).toBe(true);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
    // Everything reads 0 with no data EXCEPT exploration: low echo-concentration
    // scores as exploratory (0.4·(100−0)=40). Never user-facing — empty profiles
    // gate to insufficient_evidence upstream.
    expect(d.intentionality).toBe(0);
    expect(d.capture_susceptibility).toBe(0);
    expect(d.nocturnality).toBe(0);
    expect(d.expressiveness).toBe(0);
    expect(d.parasociality).toBe(0);
    expect(d.exploration).toBe(40);
  });

  test("intentionality blends followed% + explicit ratio + skip%", () => {
    // 0.5*80 + 0.3*min(100, 1*50) + 0.2*50 = 40 + 15 + 10 = 65
    const d = computeDimensions(prof({ bn: { social_graph_followed_pct: 80, skip_rate_percentage: 50 }, ai: { explicit_vs_implicit_ratio: 1 } }));
    expect(d.intentionality).toBe(65);
  });

  test("capture blends algorithmic% + session length + linger%", () => {
    // 0.5*100 + 0.3*min(100, 3600/3600*100) + 0.2*0 = 50 + 30 = 80
    const d = computeDimensions(prof({ bn: { social_graph_algorithmic_pct: 100 }, sw: { max_session_duration: 3600 } }));
    expect(d.capture_susceptibility).toBe(80);
  });

  test("nocturnality doubles night_shift_ratio, clamped", () => {
    expect(computeDimensions(prof({ bn: { night_shift_ratio: 25 } })).nocturnality).toBe(50);
    expect(computeDimensions(prof({ bn: { night_shift_ratio: 80 } })).nocturnality).toBe(100); // 160→100
  });

  test("exploration folds in search intensity (heavy search > no search)", () => {
    const base = { ai: { echo_chamber_index_pct: 40, echo_chamber_distinct_creators: 25 } };
    const noSearch = computeDimensions(prof({ ...base, sr: { total_searches: 0 } })).exploration;
    const heavy = computeDimensions(prof({ ...base, sr: { total_searches: 50 } })).exploration;
    expect(heavy).toBeGreaterThan(noSearch);
    // 0.4*60 + 0.3*50 + 0.3*100 = 24 + 15 + 30 = 69
    expect(heavy).toBe(69);
  });

  test("expressiveness: any comment lifts above the 59th-percentile anchor; none caps below it", () => {
    expect(computeDimensions(prof({ cv: { total_comments: 0 }, sb: { total_shares: 0 } })).expressiveness).toBe(0);
    expect(computeDimensions(prof({ cv: { total_comments: 1 } })).expressiveness).toBeGreaterThanOrEqual(59);
    expect(computeDimensions(prof({ cv: { total_comments: 0 }, sb: { total_shares: 5 } })).expressiveness).toBeLessThan(59);
  });

  test("parasociality blends echo concentration + followed% + comment references", () => {
    // 0.5*80 + 0.3*50 + 0.2*min(100, 2*10) = 40 + 15 + 4 = 59
    const d = computeDimensions(prof({ ai: { echo_chamber_index_pct: 80 }, bn: { social_graph_followed_pct: 50 },
      cv: { references_detected: { song: ["a"], creator: ["b"] } } }));
    expect(d.parasociality).toBe(59);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/persona.test.ts`
Expected: FAIL — `Cannot find module '../persona'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// algorithmic-mirror/engine/persona.ts
/**
 * WP-2.4 — Persona Engine v2. Pure, browser-safe. Computes a 6-dimension persona
 * vector (0–100) from the already-emitted profile, then maps the 5 "who" dimensions
 * to a named archetype via a config map of centroids (nocturnality is a descriptive
 * prefix, not an archetype axis). Every formula is deterministic and exposed in `method`.
 */

export interface PersonaDimensions {
  intentionality: number;
  capture_susceptibility: number;
  nocturnality: number;
  exploration: number;
  expressiveness: number;
  parasociality: number;
}

export interface PersonaResult {
  status: "ok" | "insufficient_evidence" | "error";
  dimensions: PersonaDimensions;
  base_archetype: string;
  nocturnality_modifier: "Nocturnal" | "Diurnal" | "";
  display_name: string;
  secondary?: string;
  confidence: number;
  requirements?: { needed: string; had: string };
  method: string;
}

const clamp = (n: number): number => Math.max(0, Math.min(100, Number.isFinite(n) ? n : 0));

export function computeDimensions(profile: any): PersonaDimensions {
  const bn = profile?.behavioral_nodes ?? {};
  const ai = profile?.academic_insights ?? {};
  const sw = profile?.stopwatch_metrics ?? {};
  const sr = profile?.search_rhythm ?? {};
  const cv = profile?.comment_voice ?? {};
  const sb = profile?.share_behavior ?? {};

  const followed = Number(bn.social_graph_followed_pct ?? 0);
  const algo = Number(bn.social_graph_algorithmic_pct ?? 0);
  const skip = Number(bn.skip_rate_percentage ?? 0);
  const linger = Number(bn.linger_rate_percentage ?? 0);
  const night = Number(bn.night_shift_ratio ?? 0);
  const explicit = Number(ai.explicit_vs_implicit_ratio ?? 0);
  const echoPct = Number(ai.echo_chamber_index_pct ?? 0);
  const distinct = Number(ai.echo_chamber_distinct_creators ?? 0);
  const sessSecs = Number(sw.max_session_duration ?? 0);
  const searches = Number(sr.total_searches ?? 0);
  const comments = Number(cv.total_comments ?? 0);
  const longPct = Number(cv.long_comment_pct ?? 0);
  const shares = Number(sb.total_shares ?? 0);
  const refs = cv.references_detected ?? {};
  const refCount = Object.values(refs).reduce(
    (s: number, arr: any) => s + (Array.isArray(arr) ? arr.length : 0), 0);

  return {
    intentionality: clamp(0.5 * followed + 0.3 * Math.min(100, explicit * 50) + 0.2 * skip),
    capture_susceptibility: clamp(0.5 * algo + 0.3 * Math.min(100, (sessSecs / 3600) * 100) + 0.2 * linger),
    nocturnality: clamp(Math.min(100, night * 2)),
    exploration: clamp(
      0.4 * (100 - echoPct) + 0.3 * Math.min(100, (distinct / 50) * 100) + 0.3 * Math.min(100, (searches / 50) * 100)),
    expressiveness: comments > 0
      ? clamp(59 + Math.min(41, comments * 2 + longPct * 0.2))   // above the "59.2% never comment" anchor
      : clamp(Math.min(58, shares * 2)),                          // never-commenters stay below 59
    parasociality: clamp(0.5 * echoPct + 0.3 * followed + 0.2 * Math.min(100, refCount * 10)),
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/persona.test.ts` → PASS (7 tests).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/persona.ts algorithmic-mirror/engine/__tests__/persona.test.ts
git commit -m "feat(engine): WP-2.4 persona dimensions — 6 scores from existing metrics"
```

---

### Task 2: `persona.ts` — archetype centroids + `buildPersona` orchestrator

**Files:**
- Modify: `algorithmic-mirror/engine/persona.ts`
- Test: `algorithmic-mirror/engine/__tests__/persona.test.ts` (add cases)

**Interfaces:**
- Consumes: `computeDimensions` (Task 1); `requireCoverage` from `./coverage` (`requireCoverage(moduleId, coverage, { consciousViews }) → { status, requirements? }`).
- Produces: `ARCHETYPE_CENTROIDS`, `nocturnalityModifier(n)`, `buildPersona(profile, coverage): PersonaResult`.

- [ ] **Step 1: Write the failing test**

```ts
// add to algorithmic-mirror/engine/__tests__/persona.test.ts
import { buildPersona, nocturnalityModifier } from "../persona";

// coverage that clears the persona gate (≥30 days); consciousViews via the profile
const goodCoverage = { overall: { start: "2026-01-01", end: "2026-06-01", days: 150 }, perSection: {} };
const seekerProfile = () => prof({
  ai: { echo_chamber_index_pct: 10, echo_chamber_distinct_creators: 60, explicit_vs_implicit_ratio: 1 },
  sr: { total_searches: 80 }, bn: { social_graph_followed_pct: 60 },
  sw: { total_conscious_videos: 2000 },
});

describe("buildPersona", () => {
  test("nocturnalityModifier thresholds", () => {
    expect(nocturnalityModifier(70)).toBe("Nocturnal");
    expect(nocturnalityModifier(20)).toBe("Diurnal");
    expect(nocturnalityModifier(50)).toBe("");
  });

  test("heavy-search profile → primary 'The Seeker'; exactly one primary", () => {
    const res = buildPersona(seekerProfile(), goodCoverage);
    expect(res.status).toBe("ok");
    expect(res.base_archetype).toBe("The Seeker");
    expect(res.confidence).toBeGreaterThan(0);
    expect(typeof res.display_name).toBe("string");
  });

  test("nocturnal prefix composes the display name (dropping 'The')", () => {
    const res = buildPersona(prof({ ...(seekerProfile() as any), bn: { night_shift_ratio: 45, social_graph_followed_pct: 60 },
      ai: { echo_chamber_index_pct: 10, echo_chamber_distinct_creators: 60 }, sr: { total_searches: 80 }, sw: { total_conscious_videos: 2000 } }), goodCoverage);
    expect(res.nocturnality_modifier).toBe("Nocturnal");        // 45*2=90 ≥ 66
    expect(res.display_name).toBe("Nocturnal Seeker");
  });

  test("midpoint profile → 'The Balanced Viewer'", () => {
    const mid = prof({ bn: { social_graph_followed_pct: 50, social_graph_algorithmic_pct: 50, skip_rate_percentage: 50, linger_rate_percentage: 50 },
      ai: { echo_chamber_index_pct: 50, echo_chamber_distinct_creators: 25, explicit_vs_implicit_ratio: 1 },
      sw: { max_session_duration: 1800, total_conscious_videos: 2000 }, sr: { total_searches: 25 }, cv: { total_comments: 1 } });
    expect(buildPersona(mid, goodCoverage).base_archetype).toBe("The Balanced Viewer");
  });

  test("coverage below gate → insufficient_evidence with requirements", () => {
    const res = buildPersona(seekerProfile(), { overall: { start: "", end: "", days: 5 }, perSection: {} });
    expect(res.status).toBe("insufficient_evidence");
    expect(res.requirements?.needed).toMatch(/days/i);
  });

  test("malformed profile → status error", () => {
    expect(buildPersona(null as any, goodCoverage).status).toBe("error");
  });

  test("deterministic: same input → identical result", () => {
    expect(buildPersona(seekerProfile(), goodCoverage)).toEqual(buildPersona(seekerProfile(), goodCoverage));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/persona.test.ts`
Expected: FAIL — `buildPersona` / `nocturnalityModifier` not exported.

- [ ] **Step 3: Write minimal implementation**

Add the import at the top of `algorithmic-mirror/engine/persona.ts`:

```ts
import { requireCoverage, type Coverage } from "./coverage";
```

Add below `computeDimensions`:

```ts
// The 5 "who" dimensions the archetype centroids live in (nocturnality is a prefix,
// not an axis). Tunable config — retuning archetypes is data, not code branches.
const WHO_DIMS = [
  "intentionality", "capture_susceptibility", "exploration", "expressiveness", "parasociality",
] as const;

interface Centroid { name: string; v: Record<(typeof WHO_DIMS)[number], number>; }

export const ARCHETYPE_CENTROIDS: Centroid[] = [
  { name: "The Intentional Curator", v: { intentionality: 85, capture_susceptibility: 20, exploration: 60, expressiveness: 70, parasociality: 50 } },
  { name: "The Seeker",              v: { intentionality: 70, capture_susceptibility: 25, exploration: 90, expressiveness: 55, parasociality: 40 } },
  { name: "The Algorithmic Captured",v: { intentionality: 20, capture_susceptibility: 90, exploration: 25, expressiveness: 25, parasociality: 65 } },
  { name: "The Passive Observer",    v: { intentionality: 30, capture_susceptibility: 55, exploration: 40, expressiveness: 10, parasociality: 30 } },
  { name: "The Balanced Viewer",     v: { intentionality: 50, capture_susceptibility: 50, exploration: 50, expressiveness: 50, parasociality: 50 } },
];

const SECONDARY_GAP = 25;
const MAX_DIST = Math.sqrt(WHO_DIMS.length) * 100; // max Euclidean over 5 dims of range 100

const METHOD =
  "6 dimensions (0–100) from your behavioral metrics; archetype = nearest centroid over the 5 identity " +
  "dimensions (nocturnality is a descriptive prefix, not an axis). Expressiveness is anchored on platform " +
  "benchmarks (59.2% never comment / 73.5% never post).";

function distance(dims: PersonaDimensions, c: Centroid): number {
  let s = 0;
  for (const k of WHO_DIMS) { const d = (dims as any)[k] - c.v[k]; s += d * d; }
  return Math.sqrt(s);
}

export function nocturnalityModifier(nocturnality: number): "Nocturnal" | "Diurnal" | "" {
  if (nocturnality >= 66) return "Nocturnal";
  if (nocturnality <= 33) return "Diurnal";
  return "";
}

function zeroDims(): PersonaDimensions {
  return { intentionality: 0, capture_susceptibility: 0, nocturnality: 0, exploration: 0, expressiveness: 0, parasociality: 0 };
}

export function buildPersona(profile: any, coverage: Coverage): PersonaResult {
  if (!profile || typeof profile !== "object") {
    return { status: "error", dimensions: zeroDims(), base_archetype: "", nocturnality_modifier: "", display_name: "", confidence: 0, method: "malformed profile" };
  }
  const dimensions = computeDimensions(profile);
  const gate = requireCoverage("persona", coverage ?? { overall: { start: "", end: "", days: 0 }, perSection: {} },
    { consciousViews: Number(profile?.stopwatch_metrics?.total_conscious_videos ?? 0) });
  if (gate.status !== "ok") {
    return { status: "insufficient_evidence", dimensions, base_archetype: "", nocturnality_modifier: "", display_name: "", confidence: 0, requirements: gate.requirements, method: METHOD };
  }

  const ranked = ARCHETYPE_CENTROIDS
    .map((c) => ({ name: c.name, d: distance(dimensions, c) }))
    .sort((a, b) => a.d - b.d || (a.name < b.name ? -1 : 1));
  const primary = ranked[0];
  const secondary = ranked[1] && ranked[1].d <= primary.d + SECONDARY_GAP ? ranked[1].name : undefined;
  const modifier = nocturnalityModifier(dimensions.nocturnality);
  const bare = primary.name.replace(/^The /, "");
  const display_name = modifier ? `${modifier} ${bare}` : primary.name;
  const confidence = Math.round(Math.max(0, Math.min(1, 1 - primary.d / MAX_DIST)) * 100) / 100;

  return { status: "ok", dimensions, base_archetype: primary.name, nocturnality_modifier: modifier, display_name, secondary, confidence, method: METHOD };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/persona.test.ts` → PASS (all).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/persona.ts algorithmic-mirror/engine/__tests__/persona.test.ts
git commit -m "feat(engine): WP-2.4 archetype centroids + buildPersona orchestrator"
```

---

### Task 3: Surface `persona` in the pipeline

**Files:**
- Modify: `algorithmic-mirror/engine/pipeline.ts`
- Test: `algorithmic-mirror/engine/__tests__/persona.pipeline.test.ts`

**Interfaces:**
- Consumes: `buildPersona`, `PersonaResult` (Task 2); the existing `profile` + `coverage` locals in `runEngineFromParsed`.
- Produces: `EngineResult.persona: PersonaResult`.

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/engine/__tests__/persona.pipeline.test.ts
import { runEngine } from "../pipeline";

test("runEngine surfaces a persona result", () => {
  const raw = {
    "Your Activity": {
      "Watch History": { VideoList: [
        { Date: "2024-01-01 10:00:00", Link: "https://www.tiktokv.com/share/video/111/" },
        { Date: "2024-01-01 10:01:00", Link: "https://www.tiktokv.com/share/video/222/" },
      ] },
    },
  };
  const { persona } = runEngine(raw);
  expect(persona).toBeDefined();
  expect(["ok", "insufficient_evidence", "error"]).toContain(persona.status);
  expect(typeof persona.dimensions.intentionality).toBe("number");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/persona.pipeline.test.ts`
Expected: FAIL — `persona` is `undefined`.

- [ ] **Step 3: Write minimal implementation**

In `algorithmic-mirror/engine/pipeline.ts`, add the import near the others:

```ts
import { buildPersona, PersonaResult } from "./persona";
```

Add to the `EngineResult` interface:

```ts
  /** WP-2.4 persona: 6-dimension vector + archetype (supersedes the old primary_archetype). */
  persona: PersonaResult;
```

In `runEngineFromParsed`, after `coverage` is computed and before the `return`, add:

```ts
  const persona = buildPersona(profile, coverage);
```

and include `persona` in the returned object:

```ts
  return { parsed, profile, narratives, coverage, gates, claims, topicCandidates, persona };
```

(The `runEngine` spread `{ ...runEngineFromParsed(...), schema }` carries the new field through unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/persona.pipeline.test.ts` → PASS.
Then the whole engine suite: `cd algorithmic-mirror && TZ=UTC npx jest engine` → PASS.
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/pipeline.ts algorithmic-mirror/engine/__tests__/persona.pipeline.test.ts
git commit -m "feat(engine): surface WP-2.4 persona in runEngine result"
```

---

### Task 4: `PersonaRadar.tsx` — minimal radar component

**Files:**
- Create: `algorithmic-mirror/app/components/PersonaRadar.tsx`
- Test: `algorithmic-mirror/__tests__/PersonaRadar.test.tsx`

**Interfaces:**
- Consumes: `PersonaResult` from `../../engine/persona`.
- Produces: `export function PersonaRadar({ result }: { result?: PersonaResult })`.

- [ ] **Step 1: Write the failing test**

```tsx
// algorithmic-mirror/__tests__/PersonaRadar.test.tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { PersonaRadar } from "../app/components/PersonaRadar";
import type { PersonaResult } from "../engine/persona";

// recharts needs layout that jsdom lacks; stub to plain passthroughs so we test
// the component's own text output, not SVG geometry.
jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, RadarChart: Pass, PolarGrid: Pass, PolarAngleAxis: Pass, PolarRadiusAxis: Pass, Radar: Pass };
});

const ok: PersonaResult = {
  status: "ok",
  dimensions: { intentionality: 70, capture_susceptibility: 25, nocturnality: 90, exploration: 88, expressiveness: 55, parasociality: 40 },
  base_archetype: "The Seeker", nocturnality_modifier: "Nocturnal", display_name: "Nocturnal Seeker",
  secondary: "The Intentional Curator", confidence: 0.72, method: "…",
};

describe("PersonaRadar", () => {
  test("ok: shows display name, secondary, confidence", () => {
    render(<PersonaRadar result={ok} />);
    expect(screen.getByText("Nocturnal Seeker")).toBeInTheDocument();
    expect(screen.getByText(/Intentional Curator/)).toBeInTheDocument();
    expect(screen.getByText(/72%|0\.72/)).toBeInTheDocument();
  });

  test("insufficient_evidence: gated message", () => {
    render(<PersonaRadar result={{ status: "insufficient_evidence", dimensions: ok.dimensions, base_archetype: "", nocturnality_modifier: "", display_name: "", confidence: 0, requirements: { needed: "≥30 days and ≥500 conscious views", had: "5 days" }, method: "" }} />);
    expect(screen.getByText(/not enough|insufficient|30 days/i)).toBeInTheDocument();
  });

  test("undefined → renders nothing", () => {
    const { container } = render(<PersonaRadar result={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/PersonaRadar.test.tsx`
Expected: FAIL — `Cannot find module '../app/components/PersonaRadar'`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// algorithmic-mirror/app/components/PersonaRadar.tsx
"use client";
/**
 * WP-2.4 — minimal Persona radar. Renders the 6-dimension vector + composed archetype
 * from payload alone (ok / insufficient_evidence / error). The polished animated radar
 * is WP-3.4. recharts (already a dep) draws the axes; the text summary carries the label.
 */
import { Lock, AlertTriangle } from "lucide-react";
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from "recharts";
import type { PersonaResult } from "../../engine/persona";

const BORDER = "rgba(26, 22, 16, 0.16)";
const INK = "#1a1610";
const INK_DIM = "rgba(26, 22, 16, 0.62)";
const ACCENT = "#8b2323";

const AXES: { key: keyof PersonaResult["dimensions"]; label: string }[] = [
  { key: "intentionality", label: "Intentionality" },
  { key: "capture_susceptibility", label: "Capture" },
  { key: "nocturnality", label: "Nocturnality" },
  { key: "exploration", label: "Exploration" },
  { key: "expressiveness", label: "Expressiveness" },
  { key: "parasociality", label: "Parasociality" },
];

export function PersonaRadar({ result }: { result?: PersonaResult }) {
  if (!result) return null;

  if (result.status === "error") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: INK_DIM, fontSize: 12 }}>
        <AlertTriangle size={15} /> Persona unavailable.
      </div>
    );
  }
  if (result.status === "insufficient_evidence") {
    return (
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start", color: INK_DIM, fontSize: 12 }}>
        <Lock size={15} style={{ marginTop: 1, flexShrink: 0 }} />
        <span>Not enough watched history to read a persona yet. Needs {result.requirements?.needed}; have {result.requirements?.had}.</span>
      </div>
    );
  }

  const data = AXES.map((a) => ({ axis: a.label, value: result.dimensions[a.key] }));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div>
        <span style={{ fontWeight: 600, color: INK, fontSize: 18 }}>{result.display_name}</span>{" "}
        <span style={{ fontSize: 11, color: ACCENT }}>{Math.round(result.confidence * 100)}% fit</span>
      </div>
      {result.secondary && (
        <div style={{ fontSize: 11, color: INK_DIM }}>Secondary reading: {result.secondary}</div>
      )}
      <div style={{ width: "100%", height: 280, border: `1px solid ${BORDER}` }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="70%">
            <PolarGrid />
            <PolarAngleAxis dataKey="axis" tick={{ fontSize: 10, fill: INK_DIM }} />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
            <Radar dataKey="value" stroke={ACCENT} fill={ACCENT} fillOpacity={0.35} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 10, color: INK_DIM }}>
        {AXES.map((a) => (
          <span key={a.key}>{a.label} <strong style={{ color: INK }}>{result.dimensions[a.key]}</strong></span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/PersonaRadar.test.tsx` → PASS (3 tests).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/PersonaRadar.tsx algorithmic-mirror/__tests__/PersonaRadar.test.tsx
git commit -m "feat(ui): WP-2.4 minimal PersonaRadar — 6-axis radar + archetype"
```

---

### Task 5: Wire persona into the payload + dashboard

**Files:**
- Modify: `algorithmic-mirror/app/page.tsx` (add `persona` to the payload)
- Modify: `algorithmic-mirror/app/components/GhostProfileHUD.tsx` (add `persona?` to `GhostProfile`)
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx` (render in the Overview tab)
- Test: `algorithmic-mirror/__tests__/PersonaRadarDashboard.test.tsx`

**Interfaces:**
- Consumes: `PersonaResult` (Task 2); `PersonaRadar` (Task 4); the `analyzeLocal` `out.persona` (Task 3) in `page.tsx`.
- Produces: `payload.persona`; a rendered `<PersonaRadar>` in the Overview tab.

- [ ] **Step 1: Write the failing test**

```tsx
// algorithmic-mirror/__tests__/PersonaRadarDashboard.test.tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { ForensicDashboard } from "../app/components/ForensicDashboard";
import type { GhostProfile } from "../app/components/GhostProfileHUD";

jest.mock("../app/components/CreatorGraph", () => ({ CreatorGraph: () => <div data-testid="creator-graph" /> }));
jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, RadarChart: Pass, PolarGrid: Pass, PolarAngleAxis: Pass, PolarRadiusAxis: Pass, Radar: Pass,
    // some dashboard children may use other recharts pieces; stub broadly:
    BarChart: Pass, Bar: Pass, XAxis: Pass, YAxis: Pass, Tooltip: Pass, Cell: Pass, PieChart: Pass, Pie: Pass, LineChart: Pass, Line: Pass, CartesianGrid: Pass, Area: Pass, AreaChart: Pass };
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
  persona: {
    status: "ok",
    dimensions: { intentionality: 70, capture_susceptibility: 25, nocturnality: 90, exploration: 88, expressiveness: 55, parasociality: 40 },
    base_archetype: "The Seeker", nocturnality_modifier: "Nocturnal", display_name: "Nocturnal Seeker", confidence: 0.72, method: "…",
  },
} as unknown as GhostProfile;

test("Overview tab renders the Persona radar from the payload", () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  expect(screen.getByText("Nocturnal Seeker")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/PersonaRadarDashboard.test.tsx`
Expected: FAIL — no "Nocturnal Seeker". If the mount throws on a missing profile field, add that field to the minimal `profile` (keep it minimal).

- [ ] **Step 3a: Add `persona` to the `GhostProfile` interface**

In `algorithmic-mirror/app/components/GhostProfileHUD.tsx`, add the import and field (mirroring `demographics?`):

```ts
import type { PersonaResult } from "../../engine/persona";
```
```ts
  // WP-2.4 — persona vector + archetype (supersedes primary_archetype; present in local payloads).
  persona?: PersonaResult;
```

- [ ] **Step 3b: Render the radar in the Overview tab**

In `algorithmic-mirror/app/components/ForensicDashboard.tsx`, add the import near the other component imports:

```tsx
import { PersonaRadar } from "./PersonaRadar";
```

Inside the `{activeTab === "overview" && ( … )}` block, add a panel gated on `profile.persona` (using the existing `DashboardPanel`/`SectionTitle`/`ACCENT`), placed after the archetype headline area:

```tsx
                {profile.persona && (
                  <div className="md:col-span-2">
                    <DashboardPanel label="Persona Engine" accent={ACCENT}>
                      <SectionTitle>Your Six Dimensions</SectionTitle>
                      <PersonaRadar result={profile.persona} />
                    </DashboardPanel>
                  </div>
                )}
```

- [ ] **Step 3c: Add `persona` to the analyze payload**

In `algorithmic-mirror/app/page.tsx`, in the `analyzeLocal` return object (the one that already lists `claims: out.claims, … targeting_card, demographics, _local_mode: true`), add `persona: out.persona`:

```ts
    coverage: out.coverage, gates: out.gates, claims: out.claims, schema: out.schema,
    targeting_card, demographics, persona: out.persona,
    _local_mode: true,
```

(No new fetch or step — `persona` already rides in `out` from `runEngineOffThread`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/PersonaRadarDashboard.test.tsx` → PASS.
Then the whole suite: `cd algorithmic-mirror && TZ=UTC npx jest` → PASS (all).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/page.tsx algorithmic-mirror/app/components/GhostProfileHUD.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx algorithmic-mirror/__tests__/PersonaRadarDashboard.test.tsx
git commit -m "feat(app): WP-2.4 wire persona into payload + Overview radar"
```

---

## Self-Review

**Spec coverage:**
- Client-TS layer over profile, buildGhostProfile untouched → Tasks 1–3. ✓
- 6 dimension formulas from existing metrics, exposed in `method`, clamped/finite → Task 1. ✓
- Search intensity folded into exploration → Task 1 (search term + test). ✓
- Nocturnality as prefix, excluded from centroid distance → Task 2 (WHO_DIMS omits it; `nocturnalityModifier`). ✓
- Archetype centroids config + nearest-centroid, exactly one primary + up to one secondary, confidence → Task 2. ✓
- "The Seeker" earned by search → Task 2 (heavy-search fixture → Seeker test). ✓
- Coverage gate via `requireCoverage("persona", …)` → Task 2. ✓
- Radar-chart-ready payload + minimal component → Tasks 2 (shape) + 4 (radar). ✓
- Wiring: `persona` in payload + `GhostProfile` field + Overview render → Task 5. ✓
- Old archetype deprecated (untouched) → no task modifies `archetypes.ts`/`claims.ts`. ✓
- `monthly` deliberately out of scope (spec §11) → not populated; noted in Global Constraints.

**Placeholder scan:** none — every code/test step is complete. "Add missing profile field if the mount throws" is a bounded fallback against an existing large component.

**Type consistency:** `PersonaDimensions`/`PersonaResult` (Task 1) used unchanged in Tasks 2/3/4/5. `buildPersona(profile, coverage)` signature matches the Task 3 call site (`profile`, `coverage` both in `runEngineFromParsed`). `requireCoverage(moduleId, coverage, { consciousViews })` matches `coverage.ts`. `WHO_DIMS` keys match `PersonaDimensions` field names. `Coverage` type imported from `./coverage`.

**Note for the implementer:** run `npx tsc --noEmit` before each commit — a prior WP shipped an `any`-poisoned implicit-any that jest (ts-jest transpile-only) passed but `next build` would reject. Keep `TZ=UTC` so any date-derived metric is deterministic.
