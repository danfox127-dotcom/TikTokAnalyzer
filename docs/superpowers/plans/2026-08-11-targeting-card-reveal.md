# WP-3.4a Targeting Card Reveal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `TargetingCard.tsx` the wax-seal "case-file" reveal treatment — a one-shot seal-break animation on the `ok` state, and a permanent "INSUFFICIENT EVIDENCE" stamp on the gated state.

**Architecture:** A new stateless `Stamp` component renders a wax-seal graphic + label. `TargetingCard` gains local reveal state (`hasRevealed`) gated by `useReducedMotion()`: on `ok`, the stamp cracks/fades via framer-motion while segments cross-fade in underneath; on `insufficient_evidence`, the stamp renders permanently alongside the existing copy; `error` and `undefined` are untouched.

**Tech Stack:** Next.js 16, React 19, TypeScript, `ts-jest` + React Testing Library, `framer-motion`. No new dependencies.

## Global Constraints

- "Case-file flip" = wax-seal seal-break reveal (stamp cracks/fades, no literal rotation/flip) — not a 3D card flip or folder fold-open.
- The reveal auto-plays once on mount for `status === "ok"` when `!useReducedMotion()` — it is never a tap-to-reveal gate. Content is never hidden behind a required interaction.
- Under `useReducedMotion() === true`, the stamp never mounts and segments render immediately — no animation, no delay.
- The reveal never re-triggers on re-render — one-shot per mount only.
- The stamp is a wax-seal medallion (filled circle, radial-gradient oxblood fill, rotated, uppercase label) — not a rubber ink-stamp or rectangular "CONFIDENTIAL" box.
- The same `Stamp` component (different `label` prop) covers both the pre-reveal "SEALED" cover and the permanent "INSUFFICIENT EVIDENCE" state — one component, not two.
- `error` and `undefined` states are entirely unchanged from current behavior — no stamp, no motion.
- No changes to `TargetingCardResult`, `TargetingSegment`, or `engine/targetingCard.ts` — this is a rendering-layer-only change.
- No changes to `ClaimText`/`EvidencePanel`/evidence-tap behavior.
- Run TS tests with `TZ=UTC`; run `npx tsc --noEmit` before every commit.

---

### Task 1: `Stamp.tsx` — shared wax-seal stamp component

**Files:**
- Create: `algorithmic-mirror/app/components/Stamp.tsx`
- Test: `algorithmic-mirror/app/components/__tests__/Stamp.test.tsx`

**Interfaces:**
- Produces: `Stamp({ label }: { label: string })` — a stateless presentational component with no motion baked in, used by Task 2.

- [ ] **Step 1: Write the failing test**

```tsx
// algorithmic-mirror/app/components/__tests__/Stamp.test.tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { Stamp } from "../Stamp";

test("renders the given label", () => {
  render(<Stamp label="SEALED" />);
  expect(screen.getByText("SEALED")).toBeInTheDocument();
});

test("renders a different label", () => {
  render(<Stamp label="INSUFFICIENT EVIDENCE" />);
  expect(screen.getByText("INSUFFICIENT EVIDENCE")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest Stamp.test.tsx`
Expected: FAIL — `Cannot find module '../Stamp'`

- [ ] **Step 3: Write the implementation**

```tsx
// algorithmic-mirror/app/components/Stamp.tsx
"use client";
/**
 * WP-3.4a — small stateless wax-seal stamp graphic + label. Reused for the
 * pre-reveal "SEALED" cover on TargetingCard's ok state, and permanently on
 * its insufficient_evidence state ("INSUFFICIENT EVIDENCE"). No motion baked
 * in — callers decide whether/how it animates.
 */
import { ACCENT } from "./dashboardPrimitives";

export interface StampProps {
  label: string;
}

export function Stamp({ label }: StampProps) {
  return (
    <div
      style={{
        width: 90,
        height: 90,
        borderRadius: "50%",
        background: `radial-gradient(circle at 35% 30%, ${ACCENT}, #6b1818)`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "#f5efe4",
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        textAlign: "center",
        boxShadow: "0 3px 6px rgba(0,0,0,0.3)",
        transform: "rotate(4deg)",
        padding: 8,
        fontFamily: "var(--font-mono, monospace)",
      }}
    >
      {label}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest Stamp.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Typecheck and commit**

Run: `cd algorithmic-mirror && npx tsc --noEmit`
Expected: no errors

```bash
git add algorithmic-mirror/app/components/Stamp.tsx algorithmic-mirror/app/components/__tests__/Stamp.test.tsx
git commit -m "feat(targeting-card): add shared Stamp component"
```

---

### Task 2: `TargetingCard.tsx` — wire the reveal sequence

**Files:**
- Modify: `algorithmic-mirror/app/components/TargetingCard.tsx`
- Modify: `algorithmic-mirror/jest.mock-setup.js` — the project's GLOBAL framer-motion mock (applies to every test file automatically via `setupFiles` in `jest.config.cjs`)
- Modify: `algorithmic-mirror/__tests__/TargetingCardDashboard.test.tsx` — has its OWN local framer-motion mock that overrides the global one for that file
- Test: `algorithmic-mirror/__tests__/TargetingCard.test.tsx` (existing — extend, do not remove existing tests)

**Interfaces:**
- Consumes: Task 1's `Stamp({ label })`.
- Produces: `TargetingCard({ result }: { result?: TargetingCardResult })` — same signature as before, no new props.

**Why the global mock and a second test file need changes:** `useReducedMotion()` (from `framer-motion`) must be called unconditionally at the top of `TargetingCard`, per React's Rules of Hooks — it runs on every render regardless of `result.status`. This project has a GLOBAL framer-motion mock in `jest.mock-setup.js` (loaded via `setupFiles` for every test file) that currently only exports `{ motion, AnimatePresence }` — no `useReducedMotion`. Any test file with no local override (like `TargetingCard.test.tsx` and `InterestsTab.test.tsx`, which renders `TargetingCard` inside its tree) would call `undefined()` and crash once `TargetingCard` calls this hook. Separately, `TargetingCardDashboard.test.tsx` defines its OWN local `jest.mock("framer-motion", ...)` (local mocks fully replace the global one for that file, per Jest's module-registry precedence) — its local mock also lacks `useReducedMotion`, so it needs the identical fix even though its own fixture never reaches the `ok`-branch stamp.

- [ ] **Step 1: Fix the global framer-motion mock**

Replace the full contents of `algorithmic-mirror/jest.mock-setup.js`:

```js
// Mock framer-motion and lucide-react before modules are imported in tests
// Render motion components as plain div wrappers and strip animation props.
const React = require('react');
jest.mock('framer-motion', () => {
  const motion = new Proxy({}, {
    get: () => (props) => {
      const {
        initial, animate, transition,
        whileTap, whileHover, whileFocus, whileDrag,
        whileInView, viewport, onAnimationComplete,
        ...rest
      } = props || {};
      return React.createElement('div', rest, props && props.children);
    },
  });
  const AnimatePresence = ({ children }) => React.createElement(React.Fragment, null, children);
  const useReducedMotion = () => false;
  return { motion, AnimatePresence, useReducedMotion };
});

jest.mock('lucide-react', () => {
  const React = require('react');
  const createIcon = (name) => (props) => React.createElement('svg', { ...props, 'data-icon': name });
  return new Proxy({}, {
    get: (target, prop) => createIcon(prop)
  });
});
```

(The only changes from the current file: `onAnimationComplete` added to the destructured-and-discarded prop list, and a new `useReducedMotion` export returning `false`.)

- [ ] **Step 2: Fix `TargetingCardDashboard.test.tsx`'s local mock**

In `algorithmic-mirror/__tests__/TargetingCardDashboard.test.tsx`, find this block:

```tsx
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
```

Replace it with (adds `useReducedMotion` to the returned object — nothing else changes):

```tsx
jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, {
    get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
      const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
      void initial; void animate; void exit; void transition; void whileHover; void whileTap;
      return React.createElement(tag, dom, children as React.ReactNode);
    },
  });
  return {
    motion,
    AnimatePresence: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    useReducedMotion: () => false,
  };
});
```

- [ ] **Step 3: Write the failing tests**

Replace the full contents of `algorithmic-mirror/__tests__/TargetingCard.test.tsx`:

```tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { useReducedMotion } from "framer-motion";
import { TargetingCard } from "../app/components/TargetingCard";
import type { TargetingCardResult } from "../engine/targetingCard";

jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, onAnimationComplete, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap; void onAnimationComplete;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return {
    motion,
    AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children),
    useReducedMotion: jest.fn(() => false),
  };
});

beforeEach(() => {
  (useReducedMotion as jest.Mock).mockReturnValue(false);
});

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
    expect(screen.getByText(/TikTok admits/i)).toBeInTheDocument();
    expect(screen.getByText("Education")).toBeInTheDocument();
    expect(screen.getByText("Uncategorized interest")).toBeInTheDocument();
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

  test("ok + motion enabled: SEALED stamp is present alongside segments (structural wiring of the reveal sequence)", () => {
    render(<TargetingCard result={ok} />);
    expect(screen.getByText("SEALED")).toBeInTheDocument();
    expect(screen.getByText("Education")).toBeInTheDocument();
  });

  test("ok + reduced motion: no SEALED stamp, segments render immediately", () => {
    (useReducedMotion as jest.Mock).mockReturnValue(true);
    render(<TargetingCard result={ok} />);
    expect(screen.queryByText("SEALED")).not.toBeInTheDocument();
    expect(screen.getByText("Education")).toBeInTheDocument();
  });

  test("insufficient_evidence: renders the INSUFFICIENT EVIDENCE stamp alongside the existing gated copy", () => {
    render(<TargetingCard result={{
      moduleId: "targeting_card", status: "insufficient_evidence", taxonomy_version: "2026.03-1",
      requirements: { needed: "LLM topic pass (bring your own key)", had: "keyword fallback (no LLM key)" },
      claims: [], counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 },
    }} />);
    expect(screen.getByText("INSUFFICIENT EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText(/bring your own key/i)).toBeInTheDocument();
  });

  test("error: does not render any stamp", () => {
    render(<TargetingCard result={{
      moduleId: "targeting_card", status: "error", error: "malformed TopicResult", taxonomy_version: "2026.03-1",
      claims: [], counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 },
    }} />);
    expect(screen.queryByText("SEALED")).not.toBeInTheDocument();
    expect(screen.queryByText("INSUFFICIENT EVIDENCE")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run tests to verify the new ones fail**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/TargetingCard.test.tsx`
Expected: the 4 pre-existing tests still PASS; the 4 new tests FAIL — `Stamp` is never rendered by the current `TargetingCard.tsx`, so `screen.getByText("SEALED")` / `screen.getByText("INSUFFICIENT EVIDENCE")` find nothing.

- [ ] **Step 5: Write the implementation**

Replace the full contents of `algorithmic-mirror/app/components/TargetingCard.tsx`:

```tsx
"use client";
/**
 * WP-2.2 — Targeting Card. Renders the three InsightModuleResult states from
 * payload alone.
 * WP-3.4a — ok state gets a one-shot wax-seal reveal on mount; insufficient_evidence
 * gets a permanent "INSUFFICIENT EVIDENCE" stamp alongside its existing copy.
 */
import { useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { ShieldCheck, ShieldAlert, Lock, AlertTriangle } from "lucide-react";
import type { TargetingCardResult, TargetingSegment } from "../../engine/targetingCard";
import { ClaimText } from "./ClaimText";
import { Stamp } from "./Stamp";

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
      <ClaimText claim={seg}>{seg.evidence.length} watched videos</ClaimText>
      <div style={{ fontSize: 10, color: INK_DIM }}>{seg.method}</div>
    </div>
  );
}

export function TargetingCard({ result }: { result?: TargetingCardResult }) {
  const prefersReducedMotion = useReducedMotion();
  const [hasRevealed, setHasRevealed] = useState(false);
  const revealed = Boolean(prefersReducedMotion) || hasRevealed;
  const showStamp = !revealed;
  const contentTransition = prefersReducedMotion
    ? { duration: 0 }
    : { duration: 0.4, ease: "easeOut" as const, delay: 0.15 };

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
      <div style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "center" }}>
        <Stamp label="INSUFFICIENT EVIDENCE" />
        <div style={{ display: "flex", gap: 8, color: INK_DIM, fontSize: 12, alignItems: "flex-start" }}>
          <Lock size={15} style={{ marginTop: 2, flexShrink: 0 }} />
          <span>
            Run topic analysis with your own key to see exactly what advertisers can target.
            <br />
            <span style={{ fontSize: 11 }}>Needs {result.requirements?.needed}; have {result.requirements?.had}.</span>
          </span>
        </div>
      </div>
    );
  }

  const { counts } = result;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, position: "relative" }}>
      <AnimatePresence>
        {showStamp && (
          <motion.div
            key="seal"
            initial={{ scale: 1, opacity: 1 }}
            animate={{ scale: 1.15, opacity: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            onAnimationComplete={() => setHasRevealed(true)}
            style={{ display: "flex", justifyContent: "center" }}
          >
            <Stamp label="SEALED" />
          </motion.div>
        )}
      </AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: revealed ? 1 : 0 }}
        transition={contentTransition}
        style={{ display: "flex", flexDirection: "column", gap: 12 }}
      >
        <p style={{ fontSize: 12, color: INK_DIM }}>
          TikTok admits <strong style={{ color: INK }}>{counts.declared_ad_interest_count}</strong> interest categories;
          your watched behavior surfaced <strong style={{ color: INK }}>{counts.segment_count}</strong> targetable
          segments, <strong style={{ color: INK }}>{counts.confirmed_count}</strong> already on TikTok&apos;s list.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {result.claims.map((s) => <Segment key={s.id} seg={s} />)}
        </div>
      </motion.div>
    </div>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/TargetingCard.test.tsx`
Expected: PASS (8 tests)

Also run the full suite to confirm no regressions (this is the step that verifies the global-mock and `TargetingCardDashboard.test.tsx` fixes actually worked — `InterestsTab.test.tsx` and `TargetingCardDashboard.test.tsx` are the two files whose survival depends on Steps 1–2 being correct):

Run: `cd algorithmic-mirror && TZ=UTC npx jest`
Expected: all suites pass — specifically confirm `app/components/tabs/__tests__/InterestsTab.test.tsx` and `__tests__/TargetingCardDashboard.test.tsx` are both in the PASS list, not just "no new failures" in a truncated summary.

- [ ] **Step 7: Typecheck and commit**

Run: `cd algorithmic-mirror && npx tsc --noEmit`
Expected: no errors

```bash
git add algorithmic-mirror/app/components/TargetingCard.tsx algorithmic-mirror/__tests__/TargetingCard.test.tsx algorithmic-mirror/jest.mock-setup.js algorithmic-mirror/__tests__/TargetingCardDashboard.test.tsx
git commit -m "feat(targeting-card): wire wax-seal reveal sequence + INSUFFICIENT EVIDENCE stamp"
```
