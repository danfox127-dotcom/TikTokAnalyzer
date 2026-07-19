# Targeting Card (WP-2.2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Map the WP-2.1 topic clusters onto TikTok's real ad taxonomy and surface the advertiser segments a user could be targeted by, as inferred `Claim`s with real video evidence, cross-referenced against the interest categories TikTok already declares.

**Architecture:** A committed, generated `taxonomyIndex.ts` gives the browser the 716 taxonomy names + version. A pure `buildTargetingCard(topicResult, profile)` validates each cluster's `taxonomy_hint` (strict, deterministic), groups matched clusters by category, drops anything under a 3-video evidence bar, cross-references declared `ad_interests`, and emits an `InsightModuleResult` of segment Claims — or an `insufficient_evidence` gate when the keyword fallback (no LLM key) is all that's available. A minimal `TargetingCard.tsx` renders the three states; `page.tsx` runs the topics step and attaches the result to the payload.

**Tech Stack:** TypeScript (ts-jest, `algorithmic-mirror/engine/`), React 19 / Next 16 (`algorithmic-mirror/app/`), Python 3.12 (one generator script), `@testing-library/react`.

## Global Constraints

- **Client TS only** — validation + Claim assembly run in the engine; no server validator (the keyword/Local path never calls the server). The taxonomy ships to the browser as a generated string array.
- TS engine **runtime** files stay browser-safe: **no `fs`/`path`/`crypto`/`process`/`require`**. (The taxonomy-index *parity test* is the one exception — it is Node-side and may read the source JSON via `fs`.)
- **Strict taxonomy match:** normalized (`toLowerCase().trim()`) EXACT match against `TAXONOMY_NAMES`. Near-misses → "Uncategorized interest". No contains-matching for taxonomy.
- **≥3 video evidence** per shipping segment, checked on the FINAL (post-grouping) evidence set. Segments under the bar are dropped.
- **Matched clusters group BY canonical category** (one segment per distinct category = deduped union of videos, `max` confidence). **Unmatched clusters stay separate** (one segment each). All segment `id`s unique.
- Keyword-source `TopicResult`, zero clusters, or all-segments-dropped → `status: "insufficient_evidence"` with `requirements: { needed: "LLM topic pass (bring your own key)", had: <reason> }`.
- Each segment is an **inferred `Claim`** and must pass the existing `validateClaims` (confidence in [0,1] + non-empty evidence). `method` echoes `TAXONOMY_VERSION`.
- `tiktok_confirmed` = normalized exact-or-contains (either direction) of the category/cluster-name against `profile.declared_signals.ad_interests`.
- Do **not** modify the parity-locked orchestrator (`buildGhostProfile` / `ghostProfile.ts`), `claims.ts`, or any golden fixture.
- Component: warm-paper palette constants already used in the codebase, **lucide-react icons only**, **no animation** (WP-3.4 owns the designed panel).
- Run TS tests with `TZ=UTC`.

---

### Task 1: `taxonomyIndex.ts` — generated taxonomy module + parity test

**Files:**
- Create: `scripts/gen_taxonomy_index.py`
- Create (generated): `algorithmic-mirror/engine/taxonomyIndex.ts`
- Test: `algorithmic-mirror/engine/__tests__/taxonomyIndex.test.ts`

**Interfaces:**
- Produces: `TAXONOMY_VERSION: string`, `TAXONOMY_RETRIEVED: string`, `TAXONOMY_NAMES: string[]` (716 names from `data/tiktok-ad-taxonomy.json`).

- [ ] **Step 1: Write the generator script**

```python
# scripts/gen_taxonomy_index.py
"""WP-2.2 — generate the browser-safe taxonomy index from the committed source.
Run: python3 scripts/gen_taxonomy_index.py  (re-run whenever data/tiktok-ad-taxonomy.json changes)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "tiktok-ad-taxonomy.json")
OUT = os.path.join(ROOT, "algorithmic-mirror", "engine", "taxonomyIndex.ts")


def main() -> None:
    with open(SRC) as f:
        data = json.load(f)
    names = [c["name"] for c in data["categories"] if c.get("name")]
    body = ",\n  ".join(json.dumps(n) for n in names)
    content = (
        "// AUTO-GENERATED from data/tiktok-ad-taxonomy.json by "
        "scripts/gen_taxonomy_index.py — do not edit by hand.\n"
        f"export const TAXONOMY_VERSION = {json.dumps(data.get('version', ''))};\n"
        f"export const TAXONOMY_RETRIEVED = {json.dumps(data.get('retrieved_date', ''))};\n"
        "export const TAXONOMY_NAMES: string[] = [\n"
        f"  {body},\n"
        "];\n"
    )
    with open(OUT, "w") as f:
        f.write(content)
    print(f"wrote {OUT}: {len(names)} names")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the generator**

Run: `python3 scripts/gen_taxonomy_index.py`
Expected: `wrote .../algorithmic-mirror/engine/taxonomyIndex.ts: 716 names`

- [ ] **Step 3: Write the parity test**

```ts
// algorithmic-mirror/engine/__tests__/taxonomyIndex.test.ts
import fs from "fs";
import path from "path";
import { TAXONOMY_NAMES, TAXONOMY_VERSION, TAXONOMY_RETRIEVED } from "../taxonomyIndex";

// Node-side build-parity check: the committed generated module must match the
// source file (a stale index fails CI). This test may use fs; the runtime module
// it imports is a plain string array (browser-safe).
const src = JSON.parse(
  fs.readFileSync(path.join(__dirname, "../../../data/tiktok-ad-taxonomy.json"), "utf-8")
);
const names: string[] = src.categories.filter((c: any) => c?.name).map((c: any) => c.name);

test("generated taxonomy index matches the source file", () => {
  expect(TAXONOMY_NAMES).toEqual(names);
  expect(TAXONOMY_NAMES.length).toBe(716);
  expect(TAXONOMY_VERSION).toBe(src.version);
  expect(TAXONOMY_RETRIEVED).toBe(src.retrieved_date);
});
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/taxonomyIndex.test.ts`
Expected: PASS (1 test). (If it fails on module-not-found, the generator in Step 2 didn't write the file.)

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_taxonomy_index.py algorithmic-mirror/engine/taxonomyIndex.ts algorithmic-mirror/engine/__tests__/taxonomyIndex.test.ts
git commit -m "feat(engine): WP-2.2 generated taxonomy index + parity test"
```

---

### Task 2: `targetingCard.ts` — buildTargetingCard + segment Claims

**Files:**
- Create: `algorithmic-mirror/engine/targetingCard.ts`
- Test: `algorithmic-mirror/engine/__tests__/targetingCard.test.ts`

**Interfaces:**
- Consumes: `TAXONOMY_NAMES`, `TAXONOMY_VERSION` (Task 1); `TopicResult`, `TopicCluster` from `./keywordClusters` (WP-2.1: `TopicCluster { name; video_ids: string[]; taxonomy_hint: string | null; confidence: number; evidence_kind }`, `TopicResult { source: "llm" | "keyword"; clusters: TopicCluster[]; prompt_version; cached; usage? }`); `Claim`, `EvidenceRef` from `./types`; `validateClaims` from `./claims` (for the test only).
- Produces: `buildTargetingCard(topicResult: TopicResult, profile: any): TargetingCardResult`, plus exported types `TargetingSegment` and `TargetingCardResult`.

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/engine/__tests__/targetingCard.test.ts
import { buildTargetingCard } from "../targetingCard";
import { validateClaims } from "../claims";
import { TAXONOMY_VERSION } from "../taxonomyIndex";
import type { TopicResult } from "../keywordClusters";

// "Education" and "Personal Finance" are real taxonomy names; "Blahblah" is not.
const cluster = (name: string, taxonomy_hint: string | null, video_ids: string[], confidence = 0.7) =>
  ({ name, taxonomy_hint, video_ids, confidence, evidence_kind: "video" as const });
const llm = (clusters: any[]): TopicResult =>
  ({ source: "llm", clusters, prompt_version: "topics-v1", cached: false });
const profile = (ad_interests: string[] = []) => ({ declared_signals: { ad_interests } });

describe("buildTargetingCard", () => {
  test("keyword source → insufficient_evidence gate, no claims", () => {
    const res = buildTargetingCard(
      { source: "keyword", clusters: [], prompt_version: "topics-v1", cached: false },
      profile()
    );
    expect(res.status).toBe("insufficient_evidence");
    expect(res.requirements?.needed).toMatch(/bring your own key/i);
    expect(res.claims).toEqual([]);
  });

  test("matched cluster with ≥3 videos → inferred segment Claim citing the videos", () => {
    const res = buildTargetingCard(
      llm([cluster("study tips", "Education", ["1", "2", "3"])]),
      profile()
    );
    expect(res.status).toBe("ok");
    expect(res.claims).toHaveLength(1);
    const s = res.claims[0];
    expect(s.tier).toBe("inferred");
    expect((s.value as any).category).toBe("Education");
    expect((s.value as any).matched).toBe(true);
    expect(s.evidence.map((e) => e.id)).toEqual(["1", "2", "3"]);
    expect(s.method).toContain(TAXONOMY_VERSION);
    expect(validateClaims(res.claims)).toEqual([]); // valid Claim set
  });

  test("clusters under the 3-video bar are dropped; all-dropped → insufficient", () => {
    const res = buildTargetingCard(
      llm([cluster("thin", "Education", ["1", "2"])]),
      profile()
    );
    expect(res.status).toBe("insufficient_evidence");
    expect(res.requirements?.had).toMatch(/3/);
  });

  test("strict match: near-miss hint → Uncategorized interest (still ships with videos)", () => {
    const res = buildTargetingCard(
      llm([cluster("finance stuff", "Finance", ["1", "2", "3"])]), // not exactly a taxonomy name
      profile()
    );
    expect(res.status).toBe("ok");
    expect((res.claims[0].value as any).category).toBe("Uncategorized interest");
    expect((res.claims[0].value as any).matched).toBe(false);
  });

  test("two matched clusters on the same category → ONE merged segment (union videos, max confidence)", () => {
    const res = buildTargetingCard(
      llm([
        cluster("a", "Education", ["1", "2"], 0.7),
        cluster("b", "Education", ["2", "3", "4"], 0.9),
      ]),
      profile()
    );
    expect(res.claims).toHaveLength(1);
    expect(res.claims[0].evidence.map((e) => e.id).sort()).toEqual(["1", "2", "3", "4"]);
    expect(res.claims[0].confidence).toBe(0.9);
  });

  test("tiktok_confirmed flag + card-level counts from declared ad_interests", () => {
    const res = buildTargetingCard(
      llm([
        cluster("study tips", "Education", ["1", "2", "3"]),
        cluster("budget hacks", "Financial Services", ["4", "5", "6"]),
      ]),
      profile(["Education"]) // TikTok already lists Education, not Financial Services
    );
    const byCat = Object.fromEntries(res.claims.map((c) => [(c.value as any).category, c]));
    expect((byCat["Education"].value as any).tiktok_confirmed).toBe(true);
    expect((byCat["Financial Services"].value as any).tiktok_confirmed).toBe(false);
    expect(res.counts).toEqual({ declared_ad_interest_count: 1, segment_count: 2, confirmed_count: 1 });
  });

  test("two uncategorized clusters stay separate with unique ids", () => {
    const res = buildTargetingCard(
      llm([
        cluster("mystery one", null, ["1", "2", "3"]),
        cluster("mystery two", null, ["4", "5", "6"]),
      ]),
      profile()
    );
    expect(res.claims).toHaveLength(2);
    const ids = res.claims.map((c) => c.id);
    expect(new Set(ids).size).toBe(2); // unique
    expect(validateClaims(res.claims)).toEqual([]);
  });

  test("malformed TopicResult → status error, not a crash", () => {
    const res = buildTargetingCard({} as any, profile());
    expect(res.status).toBe("error");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/targetingCard.test.ts`
Expected: FAIL — `Cannot find module '../targetingCard'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// algorithmic-mirror/engine/targetingCard.ts
/**
 * WP-2.2 — Targeting Card engine. Pure, browser-safe: maps WP-2.1 topic clusters
 * onto TikTok's ad taxonomy and emits advertiser segments as inferred Claims with
 * real video evidence. Keyword-only (no LLM key) input gates to insufficient_evidence.
 */
import { TAXONOMY_NAMES, TAXONOMY_VERSION } from "./taxonomyIndex";
import type { Claim, EvidenceRef } from "./types";
import type { TopicResult } from "./keywordClusters";

const MIN_VIDEOS = 3;
const UNCATEGORIZED = "Uncategorized interest";

const norm = (s: string) => String(s ?? "").toLowerCase().trim();
const slug = (s: string) =>
  String(s ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");

// Strict, normalized exact-match lookup + canonical (file-cased) name.
const CANONICAL_BY_NORM = new Map<string, string>(TAXONOMY_NAMES.map((n) => [norm(n), n]));

export interface TargetingSegmentValue {
  category: string;
  cluster_name: string;
  matched: boolean;
  tiktok_confirmed: boolean;
}
export type TargetingSegment = Claim<TargetingSegmentValue>;

export interface TargetingCardResult {
  moduleId: "targeting_card";
  status: "ok" | "insufficient_evidence" | "error";
  requirements?: { needed: string; had: string };
  claims: TargetingSegment[];
  counts: { declared_ad_interest_count: number; segment_count: number; confirmed_count: number };
  taxonomy_version: string;
  error?: string;
}

export function buildTargetingCard(topicResult: TopicResult, profile: any): TargetingCardResult {
  const declared: string[] = profile?.declared_signals?.ad_interests ?? [];
  const declaredNorm = declared.map(norm).filter(Boolean);
  const base = { moduleId: "targeting_card" as const, taxonomy_version: TAXONOMY_VERSION };
  const zeroCounts = { declared_ad_interest_count: declared.length, segment_count: 0, confirmed_count: 0 };
  const insufficient = (had: string): TargetingCardResult => ({
    ...base, status: "insufficient_evidence",
    requirements: { needed: "LLM topic pass (bring your own key)", had },
    claims: [], counts: zeroCounts,
  });

  if (!topicResult || !Array.isArray((topicResult as any).clusters)) {
    return { ...base, status: "error", error: "malformed TopicResult", claims: [], counts: zeroCounts };
  }
  if (topicResult.source === "keyword") return insufficient("keyword fallback (no LLM key)");
  if (topicResult.clusters.length === 0) return insufficient("no topic clusters");

  // Group matched clusters by canonical category; keep unmatched separate.
  const matched = new Map<string, { videos: Set<string>; names: string[]; conf: number }>();
  const uncategorized: { name: string; videos: string[]; conf: number }[] = [];
  for (const c of topicResult.clusters) {
    const vids = Array.isArray(c.video_ids) ? c.video_ids.map(String) : [];
    const hitNorm = norm(String(c.taxonomy_hint ?? ""));
    const canonical = c.taxonomy_hint ? CANONICAL_BY_NORM.get(hitNorm) : undefined;
    if (canonical) {
      const g = matched.get(canonical) ?? { videos: new Set<string>(), names: [], conf: 0 };
      vids.forEach((v) => g.videos.add(v));
      g.names.push(c.name);
      g.conf = Math.max(g.conf, Number(c.confidence ?? 0));
      matched.set(canonical, g);
    } else {
      uncategorized.push({ name: c.name, videos: vids, conf: Number(c.confidence ?? 0) });
    }
  }

  const isConfirmed = (candidates: string[]): boolean => {
    const cn = candidates.map(norm).filter(Boolean);
    return declaredNorm.some((d) => cn.some((x) => x === d || x.includes(d) || d.includes(x)));
  };
  const makeSegment = (
    id: string, category: string, cluster_name: string, matchedFlag: boolean,
    videos: string[], confidence: number,
  ): TargetingSegment | null => {
    const uniq = [...new Set(videos)];
    if (uniq.length < MIN_VIDEOS) return null;
    const tiktok_confirmed = isConfirmed([category, cluster_name]);
    const evidence: EvidenceRef[] = uniq.map((v) => ({ kind: "video", id: v }));
    const method =
      `Matched watched-video topics to TikTok ad taxonomy ${TAXONOMY_VERSION}; ` +
      `${matchedFlag ? "category confirmed in file" : "no taxonomy match (uncategorized)"}; ` +
      `${tiktok_confirmed ? "TikTok already lists this interest" : "not in TikTok's declared interests"}.`;
    return {
      id, tier: "inferred", confidence, evidence, method,
      value: { category, cluster_name, matched: matchedFlag, tiktok_confirmed },
    };
  };

  const segments: TargetingSegment[] = [];
  for (const [category, g] of matched) {
    const s = makeSegment(`targeting.segment.${slug(category)}`, category, g.names.join(", "),
      true, [...g.videos], g.conf);
    if (s) segments.push(s);
  }
  const usedIds = new Set<string>();
  uncategorized.forEach((u, i) => {
    let id = `targeting.segment.uncategorized.${slug(u.name)}`;
    while (usedIds.has(id)) id = `${id}_${i}`;
    usedIds.add(id);
    const s = makeSegment(id, UNCATEGORIZED, u.name, false, u.videos, u.conf);
    if (s) segments.push(s);
  });

  if (segments.length === 0) return insufficient("no cluster met the ≥3 evidence-video bar");

  const confirmed_count = segments.filter((s) => s.value.tiktok_confirmed).length;
  return {
    ...base, status: "ok", claims: segments,
    counts: { declared_ad_interest_count: declared.length, segment_count: segments.length, confirmed_count },
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/targetingCard.test.ts`
Expected: PASS (8 tests). Then confirm no engine regression:
Run: `cd algorithmic-mirror && TZ=UTC npx jest engine`
Expected: PASS (all suites).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/targetingCard.ts algorithmic-mirror/engine/__tests__/targetingCard.test.ts
git commit -m "feat(engine): WP-2.2 buildTargetingCard — taxonomy-anchored segment Claims"
```

---

### Task 3: `TargetingCard.tsx` — minimal three-state component

**Files:**
- Create: `algorithmic-mirror/app/components/TargetingCard.tsx`
- Test: `algorithmic-mirror/__tests__/TargetingCard.test.tsx`

**Interfaces:**
- Consumes: `TargetingCardResult`, `TargetingSegment` from `../../engine/targetingCard` (Task 2).
- Produces: `export function TargetingCard({ result }: { result?: TargetingCardResult })`.

- [ ] **Step 1: Write the failing test**

```tsx
// algorithmic-mirror/__tests__/TargetingCard.test.tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { TargetingCard } from "../app/components/TargetingCard";
import type { TargetingCardResult } from "../engine/targetingCard";

const ok: TargetingCardResult = {
  moduleId: "targeting_card", status: "ok", taxonomy_version: "2026.03-1",
  counts: { declared_ad_interest_count: 5, segment_count: 2, confirmed_count: 1 },
  claims: [
    { id: "targeting.segment.education", tier: "inferred", confidence: 0.7,
      evidence: [{ kind: "video", id: "1" }, { kind: "video", id: "2" }, { kind: "video", id: "3" }],
      method: "…taxonomy 2026.03-1…",
      value: { category: "Education", cluster_name: "study tips", matched: true, tiktok_confirmed: true } },
    { id: "targeting.segment.uncategorized.mystery", tier: "inferred", confidence: 0.7,
      evidence: [{ kind: "video", id: "4" }, { kind: "video", id: "5" }, { kind: "video", id: "6" }],
      method: "…taxonomy 2026.03-1…",
      value: { category: "Uncategorized interest", cluster_name: "mystery", matched: false, tiktok_confirmed: false } },
  ],
};

describe("TargetingCard", () => {
  test("ok: renders the cross-reference summary and each segment", () => {
    render(<TargetingCard result={ok} />);
    expect(screen.getByText(/TikTok/i)).toBeInTheDocument();
    expect(screen.getByText("Education")).toBeInTheDocument();
    expect(screen.getByText("Uncategorized interest")).toBeInTheDocument();
    // confirmed vs inferred-only chips both present
    expect(screen.getByText(/TikTok confirms/i)).toBeInTheDocument();
    expect(screen.getByText(/inferred-only/i)).toBeInTheDocument();
  });

  test("insufficient_evidence: renders the gated 'bring your own key' state", () => {
    render(<TargetingCard result={{
      moduleId: "targeting_card", status: "insufficient_evidence", taxonomy_version: "2026.03-1",
      requirements: { needed: "LLM topic pass (bring your own key)", had: "keyword fallback (no LLM key)" },
      claims: [], counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 },
    }} />);
    expect(screen.getByText(/bring your own key/i)).toBeInTheDocument();
  });

  test("error: renders a plain error note", () => {
    render(<TargetingCard result={{
      moduleId: "targeting_card", status: "error", error: "malformed TopicResult", taxonomy_version: "2026.03-1",
      claims: [], counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 },
    }} />);
    expect(screen.getByText(/couldn't|error|unavailable/i)).toBeInTheDocument();
  });

  test("undefined result renders nothing", () => {
    const { container } = render(<TargetingCard result={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/TargetingCard.test.tsx`
Expected: FAIL — `Cannot find module '../app/components/TargetingCard'`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// algorithmic-mirror/app/components/TargetingCard.tsx
"use client";
/**
 * WP-2.2 — minimal, functional Targeting Card. Renders the three InsightModuleResult
 * states from payload alone. Deliberately unstyled beyond the shared warm-paper
 * register; the animated case-file panel is WP-3.4.
 */
import { ShieldCheck, ShieldAlert, Lock, AlertTriangle } from "lucide-react";
import type { TargetingCardResult, TargetingSegment } from "../../engine/targetingCard";

const BORDER = "rgba(26, 22, 16, 0.16)";
const INK = "#1a1610";
const INK_DIM = "rgba(26, 22, 16, 0.62)";
const ACCENT = "#8b2323";

function Segment({ seg }: { seg: TargetingSegment }) {
  const v = seg.value;
  return (
    <div style={{ padding: "10px 12px", border: `1px solid ${BORDER}`, display: "flex",
      flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600, color: INK }}>{v.category}</span>
        {v.tiktok_confirmed ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: ACCENT }}>
            <ShieldCheck size={13} /> TikTok confirms
          </span>
        ) : (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: INK_DIM }}>
            <ShieldAlert size={13} /> inferred-only
          </span>
        )}
      </div>
      <div style={{ fontSize: 11, color: INK_DIM }}>
        {seg.evidence.length} watched videos · confidence {seg.confidence}
      </div>
      <div style={{ fontSize: 10, color: INK_DIM }}>{seg.method}</div>
    </div>
  );
}

export function TargetingCard({ result }: { result?: TargetingCardResult }) {
  if (!result) return null;

  if (result.status === "error") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: INK_DIM, fontSize: 12 }}>
        <AlertTriangle size={15} /> Targeting analysis unavailable ({result.error ?? "error"}).
      </div>
    );
  }

  if (result.status === "insufficient_evidence") {
    return (
      <div style={{ display: "flex", gap: 8, color: INK_DIM, fontSize: 12, alignItems: "flex-start" }}>
        <Lock size={15} style={{ marginTop: 2, flexShrink: 0 }} />
        <span>
          Run topic analysis with your own key to see exactly what advertisers can target.
          <br />
          <span style={{ fontSize: 11 }}>Needs {result.requirements?.needed}; have {result.requirements?.had}.</span>
        </span>
      </div>
    );
  }

  const { counts } = result;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <p style={{ fontSize: 12, color: INK_DIM }}>
        TikTok admits <strong style={{ color: INK }}>{counts.declared_ad_interest_count}</strong> interest categories;
        your watched behavior surfaced <strong style={{ color: INK }}>{counts.segment_count}</strong> targetable
        segments, <strong style={{ color: INK }}>{counts.confirmed_count}</strong> already on TikTok&apos;s list.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {result.claims.map((s) => <Segment key={s.id} seg={s} />)}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/TargetingCard.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/TargetingCard.tsx algorithmic-mirror/__tests__/TargetingCard.test.tsx
git commit -m "feat(ui): WP-2.2 minimal TargetingCard — three-state render"
```

---

### Task 4: `topicStep.ts` — the topics-resolution step (BYOK → /api/topics, else keyword fallback)

**Files:**
- Create: `algorithmic-mirror/app/utils/topicStep.ts`
- Test: `algorithmic-mirror/__tests__/topicStep.test.ts`

**Interfaces:**
- Consumes: `keywordClusters`, `TopicResult` from `../../engine/keywordClusters`; `TopicCandidate` from `../../engine/topicCandidates` (`{ video_id: string; weight: number }`).
- Produces:
  - `readSavedKey(getItem: (k: string) => string | null): { provider: string; apiKey: string } | null`
  - `resolveTopicResult(opts: { topicCandidates: TopicCandidate[]; profile: any; getKey: () => { provider: string; apiKey: string } | null; post: <T>(path: string, body: unknown) => Promise<T | null> }): Promise<TopicResult>`

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/__tests__/topicStep.test.ts
import { readSavedKey, resolveTopicResult } from "../app/utils/topicStep";

describe("readSavedKey", () => {
  test("returns the first provider with a stored key", () => {
    const store: Record<string, string> = { "llm_api_key_gemini-flash": "AIzaXXX" };
    expect(readSavedKey((k) => store[k] ?? null)).toEqual({ provider: "gemini-flash", apiKey: "AIzaXXX" });
  });
  test("returns null when no key is stored", () => {
    expect(readSavedKey(() => null)).toBeNull();
  });
});

describe("resolveTopicResult", () => {
  const candidates = [{ video_id: "1", weight: 3 }, { video_id: "2", weight: 1 }];

  test("with a key: POSTs to /api/topics with provider+key query and returns the server TopicResult", async () => {
    const calls: string[] = [];
    const post = async <T>(path: string): Promise<T | null> => {
      calls.push(path);
      return { source: "llm", clusters: [], prompt_version: "topics-v1", cached: false } as unknown as T;
    };
    const res = await resolveTopicResult({
      topicCandidates: candidates, profile: {},
      getKey: () => ({ provider: "claude", apiKey: "sk-ant-1" }), post,
    });
    expect(res.source).toBe("llm");
    expect(calls[0]).toContain("/api/topics?");
    expect(calls[0]).toContain("provider=claude");
    expect(calls[0]).toContain("api_key=sk-ant-1");
  });

  test("no key: falls back to keywordClusters (source keyword), no POST", async () => {
    let posted = false;
    const res = await resolveTopicResult({
      topicCandidates: candidates,
      profile: { interest_clusters: [{ term: "coding", count: 3 }] },
      getKey: () => null,
      post: async () => { posted = true; return null; },
    });
    expect(res.source).toBe("keyword");
    expect(posted).toBe(false);
  });

  test("server returns null (offline/error) → keyword fallback", async () => {
    const res = await resolveTopicResult({
      topicCandidates: candidates, profile: { interest_clusters: [] },
      getKey: () => ({ provider: "claude", apiKey: "sk-ant-1" }),
      post: async () => null,
    });
    expect(res.source).toBe("keyword");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/topicStep.test.ts`
Expected: FAIL — `Cannot find module '../app/utils/topicStep'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// algorithmic-mirror/app/utils/topicStep.ts
/**
 * WP-2.2 — the topics-resolution step, dependency-injected so it is unit-testable
 * without a real network or localStorage. If a BYOK key is saved, POST the
 * watch-weighted candidates to /api/topics (server fetches titles + LLM-clusters);
 * otherwise fall back to the client keyword pass (which gates the card to
 * insufficient_evidence downstream).
 */
import { keywordClusters, type TopicResult } from "../../engine/keywordClusters";
import type { TopicCandidate } from "../../engine/topicCandidates";

// Same key convention LLMAnalysisView uses: `llm_api_key_<provider>`.
const PROVIDERS = ["claude", "gemini-pro", "gemini-flash"] as const;

export function readSavedKey(
  getItem: (k: string) => string | null
): { provider: string; apiKey: string } | null {
  for (const provider of PROVIDERS) {
    const apiKey = getItem(`llm_api_key_${provider}`);
    if (apiKey) return { provider, apiKey };
  }
  return null;
}

export async function resolveTopicResult(opts: {
  topicCandidates: TopicCandidate[];
  profile: any;
  getKey: () => { provider: string; apiKey: string } | null;
  post: <T>(path: string, body: unknown) => Promise<T | null>;
}): Promise<TopicResult> {
  const key = opts.getKey();
  if (key && opts.topicCandidates.length) {
    const q = new URLSearchParams({ api_key: key.apiKey, provider: key.provider });
    const res = await opts.post<TopicResult>(`/api/topics?${q.toString()}`, {
      videos: opts.topicCandidates,
    });
    if (res) return res;
  }
  return keywordClusters(opts.profile);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/topicStep.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/utils/topicStep.ts algorithmic-mirror/__tests__/topicStep.test.ts
git commit -m "feat(app): WP-2.2 topicStep — BYOK /api/topics with keyword fallback"
```

---

### Task 5: Wire the Targeting Card into the analyze flow + dashboard

**Files:**
- Modify: `algorithmic-mirror/app/page.tsx` (the `analyzeLocal` function + payload return)
- Modify: `algorithmic-mirror/app/components/GhostProfileHUD.tsx` (add `targeting_card?` to the `GhostProfile` interface)
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx` (render the panel in the Interests tab)
- Test: `algorithmic-mirror/__tests__/TargetingCardDashboard.test.tsx`

**Interfaces:**
- Consumes: `resolveTopicResult`, `readSavedKey` (Task 4); `buildTargetingCard`, `TargetingCardResult` (Task 2); `TargetingCard` (Task 3); the existing `postEnrich` + `API_URL` + `analyzeLocal` `out` (`out.topicCandidates`, `out.profile`) in `page.tsx`.
- Produces: `payload.targeting_card: TargetingCardResult`; a rendered `<TargetingCard>` in the ForensicDashboard Interests tab.

- [ ] **Step 1: Write the failing test**

This test mounts the dashboard with a minimal profile that carries a `targeting_card`, switches to the Interests tab, and asserts the panel renders. It reuses the mock setup other dashboard tests use.

```tsx
// algorithmic-mirror/__tests__/TargetingCardDashboard.test.tsx
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ForensicDashboard } from "../app/components/ForensicDashboard";
import type { GhostProfile } from "../app/components/GhostProfileHUD";

jest.mock("../app/components/CreatorGraph", () => ({ CreatorGraph: () => <div data-testid="creator-graph" /> }));
jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, {
    get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
      const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
      void initial; void animate; void exit; void transition; void whileHover; void whileTap;
      return React.createElement(tag, dom, children as React.ReactNode);
    },
  });
  return { motion, AnimatePresence: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children) };
});

// Minimal profile: only what the Interests tab touches. Pad with any field the
// component dereferences if the mount throws (optional-chained fields default fine).
const profile = {
  primary_archetype: { name: "The Balanced Viewer" },
  interest_clusters: [],
  targeting_card: {
    moduleId: "targeting_card", status: "insufficient_evidence", taxonomy_version: "2026.03-1",
    requirements: { needed: "LLM topic pass (bring your own key)", had: "keyword fallback (no LLM key)" },
    claims: [], counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 },
  },
} as unknown as GhostProfile;

test("Interests tab renders the Targeting Card panel from the payload", () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Interests & Keywords/i));
  expect(screen.getByText(/Targeting Card/i)).toBeInTheDocument();
  expect(screen.getByText(/bring your own key/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/TargetingCardDashboard.test.tsx`
Expected: FAIL — no "Targeting Card" panel (the tab doesn't render one yet). If the mount throws on a missing profile field, add that field to the minimal `profile` object above (keep it minimal).

- [ ] **Step 3a: Add `targeting_card` to the `GhostProfile` interface**

In `algorithmic-mirror/app/components/GhostProfileHUD.tsx`, add the import and the optional field to the `GhostProfile` interface (mirroring how `_local_mode?` was added):

```ts
import type { TargetingCardResult } from "../../engine/targetingCard";
```
```ts
  // WP-2.2 — advertiser targeting segments (present in browser-local payloads).
  targeting_card?: TargetingCardResult;
```

- [ ] **Step 3b: Render the panel in the Interests tab**

In `algorithmic-mirror/app/components/ForensicDashboard.tsx`, add the import near the other component imports:

```tsx
import { TargetingCard } from "./TargetingCard";
```

Inside the `{activeTab === "interests" && ( … )}` block, after the `08 · Audience Labels Sold To Advertisers` `DashboardPanel`'s closing `</div>` (the `md:col-span-2` wrapper), add a new full-width panel:

```tsx
                <div className="md:col-span-2">
                  <DashboardPanel label="09 · Targeting Card" accent={ACCENT}>
                    <SectionTitle>What Advertisers Can Target You By</SectionTitle>
                    <TargetingCard result={profile.targeting_card} />
                  </DashboardPanel>
                </div>
```

- [ ] **Step 3c: Run the topics step + build the card in `analyzeLocal`**

In `algorithmic-mirror/app/page.tsx`, add imports near the top (with the other engine/util imports):

```ts
import { resolveTopicResult, readSavedKey } from "./utils/topicStep";
import { buildTargetingCard } from "../engine/targetingCard";
```

In `analyzeLocal`, after the geo-enrichment block and immediately before the `return { …payload… }`, add:

```ts
  // WP-2.2 — topics step + Targeting Card. BYOK → /api/topics; else keyword
  // fallback (which gates the card to insufficient_evidence). Best-effort: any
  // failure leaves the card gated, never blocks the dossier.
  let targeting_card;
  try {
    const topicResult = await resolveTopicResult({
      topicCandidates: out.topicCandidates ?? [],
      profile: out.profile,
      getKey: () => readSavedKey((k) => localStorage.getItem(k)),
      post: postEnrich,
    });
    targeting_card = buildTargetingCard(topicResult, out.profile);
  } catch {
    targeting_card = undefined;
  }
```

Then add `targeting_card` to the returned payload object (alongside `claims`, `schema`, `_local_mode`):

```ts
    coverage: out.coverage, gates: out.gates, claims: out.claims, schema: out.schema,
    targeting_card,
    _local_mode: true,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/TargetingCardDashboard.test.tsx`
Expected: PASS. Then the whole frontend + engine suite to confirm no regression:
Run: `cd algorithmic-mirror && TZ=UTC npx jest`
Expected: PASS (all suites).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/page.tsx algorithmic-mirror/app/components/GhostProfileHUD.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx algorithmic-mirror/__tests__/TargetingCardDashboard.test.tsx
git commit -m "feat(app): WP-2.2 wire Targeting Card into analyze flow + Interests tab"
```

---

## Self-Review

**Spec coverage:**
- Client-TS bundled taxonomy → Task 1 (`taxonomyIndex.ts` + generator + parity test). ✓
- `buildTargetingCard` pure fn; strict match; group-by-category; ≥3 bar; uncategorized separate; insufficient gate; tiktok_confirmed; counts; method echoes version → Task 2 (impl + 8 tests). ✓
- Segments are inferred Claims passing `validateClaims`; unique ids → Task 2 tests (`validateClaims` assertions + unique-id test). ✓
- Minimal 3-state component (ok / insufficient / error) → Task 3. ✓
- Topics step (BYOK → /api/topics, else keyword fallback) → Task 4 (dependency-injected, unit-tested). ✓
- Wiring into analyze flow + Interests-tab render + `GhostProfile.targeting_card` field → Task 5. ✓
- Data flow: `buildTargetingCard` runs post-topics, not in `runEngine` → Tasks 4+5 (page.tsx calls it after `resolveTopicResult`). ✓
- Out of scope (animated panel, pillar→taxonomy map, other WP-2.3 cards, literal advertiser list) → not built. ✓

**Placeholder scan:** none — every code and test step is complete. The one soft instruction ("pad the minimal profile if the mount throws") is a real, bounded fallback for an existing large component, not a placeholder for missing logic.

**Type consistency:** `TargetingCardResult`/`TargetingSegment` defined in Task 2 are imported unchanged in Tasks 3 and 5. `TopicResult`/`TopicCandidate` come from the WP-2.1 modules (`keywordClusters.ts`, `topicCandidates.ts`) with the exact shapes used. `resolveTopicResult`/`readSavedKey` signatures in Task 4 match their call in Task 5. `Claim`/`EvidenceRef` from `types.ts` match `validateClaims` expectations (inferred ⇒ confidence + non-empty evidence). `profile.declared_signals.ad_interests` is the real field (confirmed in `api/ghost_profile.py`).

**Note for the implementer:** the AC "every segment cites ≥3 evidence videos" is enforced in `makeSegment` (returns `null` under `MIN_VIDEOS`), verified by the drop test in Task 2. The AC "taxonomy file version echoed in the method string" is verified by the `TAXONOMY_VERSION` assertion in Task 2. The AC "card renders from payload alone" is verified by Tasks 3 and 5 rendering purely from the passed result — no fetches at render time.
