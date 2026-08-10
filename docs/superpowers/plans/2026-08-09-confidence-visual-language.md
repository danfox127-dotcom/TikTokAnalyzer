# Confidence Visual Language (WP-3.2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every `Claim` a shared tier visual language (color + border texture + label, never hue alone) via `ClaimText`/`ClaimStat` components, extend `EvidencePanel` to render a `Claim` directly, surface the previously-invisible `profile.claims` list in a new Evidence Log tab, and retrofit the two existing panels (`TargetingCard`, `DemographicPanel`) that already emit real `Claim[]`.

**Architecture:** A pure `claimStyle.ts` module (tier→visual mapping + value formatting) backs two presentational components, `ClaimText` (inline, unboxed — for embedding inside a panel's own existing card) and `ClaimStat` (standalone bordered stat-card — for the new Evidence Log grid). Both open a self-contained `EvidencePanel` instance on tap. `PersonaRadar`/`NicheDriftChart` are untouched (not Claim-shaped).

**Tech Stack:** TypeScript (ts-jest, `algorithmic-mirror/`), React 19 / Next 16, `@testing-library/react`, existing `framer-motion`/`lucide-react`.

## Global Constraints

- Tier→visual mapping is exhaustive over `Tier = "recorded" | "derived" | "inferred"` (from `engine/types.ts`): Recorded = solid border, `var(--ink)`; Derived = dashed border, `var(--accent)` (oxblood); Inferred = dotted border, `var(--stamp-blue)`. Every tier always carries a visible text label ("Recorded"/"Derived"/"Inferred") — never color alone.
- New tokens in `globals.css`: `--stamp-blue: #1f4e6b;` `--redaction-black: #0d0b08;` (both WCAG-AA-verified against `--paper`: 7.77:1 and 17.17:1 respectively — do not change these hex values).
- `ClaimText`/`ClaimStat` consume the real `Claim<T>`/`EvidenceRef` types from `engine/types.ts` — no new data shape.
- **`ClaimText` is unboxed/inline** — used inside a panel that already owns its own bordered container (`TargetingCard`'s `Segment`, `DemographicPanel`'s `Card`). **`ClaimStat` is a standalone bordered card** — used only where there is no pre-existing box (the new Evidence Log grid). Do not nest `ClaimStat` inside an already-bordered element.
- An unrelated, module-private `function Claim(...)` + `type ClaimMeta` already exist in `TheGlassHouse.tsx` (narrative "Story" mode, `{title, claim: string, payload}` shape, not exported). This is a coincidental naming collision, not the same contract — do not modify `TheGlassHouse.tsx`, and do not confuse its `ClaimMeta` with the WP-1.5 `Claim` type.
- `EvidencePanel`'s existing string-based API (`{ open, title, claim: string, payload, onClose }`) must keep working unchanged for its one existing caller (`TheGlassHouse.tsx`) — the new `claimObj?: Claim` prop is additive only.
- Do **not** modify `buildGhostProfile`/`ghostProfile.ts`, `claims.ts`, `PersonaRadar.tsx`, `NicheDriftChart.tsx`, or golden fixtures.
- Run TS tests with `TZ=UTC`; run `npx tsc --noEmit` before every commit (ts-jest does not type-check).

---

### Task 1: `claimStyle.ts` — tier mapping + shared value formatter + design tokens

**Files:**
- Create: `algorithmic-mirror/app/components/claimStyle.ts`
- Modify: `algorithmic-mirror/app/globals.css`
- Test: `algorithmic-mirror/app/components/__tests__/claimStyle.test.ts`

**Interfaces:**
- Consumes: `Tier` from `../../engine/types`.
- Produces: `tierMeta(tier: Tier): TierMeta` where `TierMeta = { label: "Recorded"|"Derived"|"Inferred"; color: string; borderStyle: "solid"|"dashed"|"dotted"; className: string }`; `renderClaimValue(v: unknown): string`.

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/app/components/__tests__/claimStyle.test.ts
import { tierMeta, renderClaimValue } from "../claimStyle";

describe("tierMeta", () => {
  test("recorded: solid ink", () => {
    const m = tierMeta("recorded");
    expect(m).toEqual({ label: "Recorded", color: "#1a1610", borderStyle: "solid", className: "tier-recorded" });
  });
  test("derived: dashed oxblood", () => {
    const m = tierMeta("derived");
    expect(m).toEqual({ label: "Derived", color: "#8b2323", borderStyle: "dashed", className: "tier-derived" });
  });
  test("inferred: dotted stamp-blue", () => {
    const m = tierMeta("inferred");
    expect(m).toEqual({ label: "Inferred", color: "#1f4e6b", borderStyle: "dotted", className: "tier-inferred" });
  });
  test("unknown tier at runtime → safe neutral default, does not throw", () => {
    expect(() => tierMeta("bogus" as any)).not.toThrow();
    const m = tierMeta("bogus" as any);
    expect(m.label).toBe("Unknown");
    expect(m.className).toBe("tier-recorded"); // fall back to the most conservative (solid/ink) styling
  });
});

describe("renderClaimValue", () => {
  test("primitive values stringify plainly", () => {
    expect(renderClaimValue("female")).toBe("female");
    expect(renderClaimValue(42)).toBe("42");
    expect(renderClaimValue(true)).toBe("true");
  });
  test("array of strings joins with comma", () => {
    expect(renderClaimValue(["Education", "Financial Services"])).toBe("Education, Financial Services");
  });
  test("array of trip-shaped objects renders city + days, not [object Object]", () => {
    const v = [{ city: "Miami", start: "2026-01-04", end: "2026-01-05", days: 2 }];
    expect(renderClaimValue(v)).toBe("Miami (2d)");
    expect(renderClaimValue(v)).not.toMatch(/object Object/);
  });
  test("plain object falls back to JSON", () => {
    expect(renderClaimValue({ a: 1 })).toBe('{"a":1}');
  });
  test("null/undefined render as empty string", () => {
    expect(renderClaimValue(null)).toBe("");
    expect(renderClaimValue(undefined)).toBe("");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/__tests__/claimStyle.test.ts`
Expected: FAIL — `Cannot find module '../claimStyle'`.

- [ ] **Step 3a: Add the design tokens to `globals.css`**

In `algorithmic-mirror/app/globals.css`, inside the existing `:root { ... }` block, immediately after the line `--accent:     #8b2323; /* oxblood — highlights, claim markers, accents */`, add:

```css
  --stamp-blue:      #1f4e6b; /* Inferred-tier claims — bureaucratic ink-stamp blue */
  --redaction-black: #0d0b08; /* redaction motif, reused by WP-3.4 */
```

After the existing `.neon-glow { ... }` block at the end of the file, append the three tier texture classes:

```css
/* ── WP-3.2 confidence-tier textures — color + border-style + (label rendered by
   the component, never by CSS alone) ─────────────────────────────────────────── */
.tier-recorded {
  border: 1px solid var(--ink);
  color: var(--ink);
}
.tier-derived {
  border: 1px dashed var(--accent);
  color: var(--accent);
}
.tier-inferred {
  border: 1px dotted var(--stamp-blue);
  color: var(--stamp-blue);
}
```

- [ ] **Step 3b: Write `claimStyle.ts`**

```ts
// algorithmic-mirror/app/components/claimStyle.ts
/**
 * WP-3.2 — shared confidence-tier visual language. Single source of truth for
 * tier → {color, border texture, label}, so no component hardcodes tier colors.
 * Never encode tier meaning in color alone — every tierMeta() consumer must also
 * show `label` and apply `borderStyle`/`className`.
 */
import type { Tier } from "../../engine/types";

export interface TierMeta {
  label: string;
  color: string;
  borderStyle: "solid" | "dashed" | "dotted";
  className: string;
}

const TIER_META: Record<Tier, TierMeta> = {
  recorded: { label: "Recorded", color: "#1a1610", borderStyle: "solid", className: "tier-recorded" },
  derived: { label: "Derived", color: "#8b2323", borderStyle: "dashed", className: "tier-derived" },
  inferred: { label: "Inferred", color: "#1f4e6b", borderStyle: "dotted", className: "tier-inferred" },
};

/** Safe for a tier value from untrusted/malformed data — never throws. */
export function tierMeta(tier: Tier): TierMeta {
  return TIER_META[tier] ?? { label: "Unknown", color: "#1a1610", borderStyle: "solid", className: "tier-recorded" };
}

/**
 * Formats a Claim's `value` for display. Ported from DemographicPanel's local
 * renderValue (WP-2.3) — handles the trip-object-array shape (city/days) that
 * previously regressed to "[object Object]" before that fix.
 */
export function renderClaimValue(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) {
    return v
      .map((x) => (x && typeof x === "object" && "city" in x
        ? `${(x as any).city} (${(x as any).days}d)`
        : String(x)))
      .join(", ");
  }
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/__tests__/claimStyle.test.ts`
Expected: PASS (10 tests).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/claimStyle.ts algorithmic-mirror/app/components/__tests__/claimStyle.test.ts algorithmic-mirror/app/globals.css
git commit -m "feat(ui): WP-3.2 claimStyle — tier visual-language mapping + shared value formatter"
```

---

### Task 2: `EvidencePanel.tsx` — accept a `Claim` directly

**Files:**
- Modify: `algorithmic-mirror/app/components/EvidencePanel.tsx`
- Test: `algorithmic-mirror/app/components/__tests__/EvidencePanel.test.tsx`

**Interfaces:**
- Consumes: `tierMeta` from `./claimStyle` (Task 1); `Claim`, `EvidenceRef` from `../../engine/types`.
- Produces: `EvidencePanel` gains an optional `claimObj?: Claim` prop. Existing `{ open, title, claim, payload, onClose }` behavior is unchanged when `claimObj` is omitted.

- [ ] **Step 1: Write the failing test**

```tsx
// algorithmic-mirror/app/components/__tests__/EvidencePanel.test.tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { EvidencePanel } from "../EvidencePanel";
import type { Claim } from "../../../engine/types";

jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const claim: Claim = {
  id: "attention.skip_rate_pct", tier: "derived", value: 42,
  method: "Share of conscious views skipped in under 3 seconds.",
  evidence: [{ kind: "video", note: "1200 skips / 3400 conscious views" }],
};

describe("EvidencePanel", () => {
  test("legacy string-based API still works unchanged (regression)", () => {
    render(<EvidencePanel open title="Skip Rate" claim="raw claim text" payload={{ a: 1 }} onClose={jest.fn()} />);
    expect(screen.getByText("Skip Rate")).toBeInTheDocument();
    expect(screen.getByText(/raw claim text/)).toBeInTheDocument();
  });

  test("claimObj path: shows the tier badge, method, and evidence list", () => {
    render(<EvidencePanel open title={null} claim={null} payload={null} claimObj={claim} onClose={jest.fn()} />);
    expect(screen.getByText(/derived/i)).toBeInTheDocument();
    expect(screen.getByText(claim.method)).toBeInTheDocument();
    expect(screen.getByText(/1200 skips \/ 3400 conscious views/)).toBeInTheDocument();
  });

  test("claimObj with empty evidence shows the no-evidence note, not a crash", () => {
    const empty: Claim = { ...claim, evidence: [] };
    render(<EvidencePanel open title={null} claim={null} payload={null} claimObj={empty} onClose={jest.fn()} />);
    expect(screen.getByText(/no evidence captured/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/__tests__/EvidencePanel.test.tsx`
Expected: FAIL — `claimObj` prop not recognized / tier text not rendered.

- [ ] **Step 3: Modify `EvidencePanel.tsx`**

Add the imports at the top (after the existing `lucide-react` import):

```ts
import { tierMeta } from "./claimStyle";
import type { Claim } from "../../engine/types";
```

Add `claimObj?: Claim;` to the `Props` interface:

```ts
interface Props {
  open: boolean;
  title: string | null;
  claim: string | null;
  payload: unknown;
  onClose: () => void;
  claimObj?: Claim;
}
```

Update the function signature to destructure it:

```ts
export function EvidencePanel({ open, title, claim, payload, onClose, claimObj }: Props) {
```

Replace the header's title/claim block — find:

```tsx
                <div
                  style={{
                    fontFamily: "var(--font-display, 'Fraunces', 'Playfair Display', serif)",
                    fontSize: 22,
                    lineHeight: 1.15,
                    fontWeight: 600,
                    color: "#1a1610",
                    letterSpacing: "-0.01em",
                  }}
                >
                  {title ?? "Evidence"}
                </div>
                {claim && (
                  <div
                    style={{
                      marginTop: 10,
                      padding: "8px 12px",
                      borderLeft: "3px solid #8b6b3a",
                      background: "rgba(139, 107, 58, 0.08)",
                      fontStyle: "italic",
                      fontSize: 13,
                      lineHeight: 1.5,
                      color: "#3a3024",
                    }}
                  >
                    &ldquo;{claim}&rdquo;
                  </div>
                )}
```

Replace with:

```tsx
                <div
                  style={{
                    fontFamily: "var(--font-display, 'Fraunces', 'Playfair Display', serif)",
                    fontSize: 22,
                    lineHeight: 1.15,
                    fontWeight: 600,
                    color: "#1a1610",
                    letterSpacing: "-0.01em",
                  }}
                >
                  {claimObj ? title ?? "Evidence" : title ?? "Evidence"}
                </div>
                {claimObj && (
                  <div
                    style={{
                      marginTop: 10,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "3px 8px",
                      fontSize: 10,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      ...(() => { const m = tierMeta(claimObj.tier); return { border: `1px ${m.borderStyle} ${m.color}`, color: m.color }; })(),
                    }}
                  >
                    {tierMeta(claimObj.tier).label}
                  </div>
                )}
                {claimObj && (
                  <div
                    style={{
                      marginTop: 10,
                      padding: "8px 12px",
                      borderLeft: "3px solid #8b6b3a",
                      background: "rgba(139, 107, 58, 0.08)",
                      fontStyle: "italic",
                      fontSize: 13,
                      lineHeight: 1.5,
                      color: "#3a3024",
                    }}
                  >
                    {claimObj.method}
                  </div>
                )}
                {!claimObj && claim && (
                  <div
                    style={{
                      marginTop: 10,
                      padding: "8px 12px",
                      borderLeft: "3px solid #8b6b3a",
                      background: "rgba(139, 107, 58, 0.08)",
                      fontStyle: "italic",
                      fontSize: 13,
                      lineHeight: 1.5,
                      color: "#3a3024",
                    }}
                  >
                    &ldquo;{claim}&rdquo;
                  </div>
                )}
```

Replace the body's raw-JSON `<pre>` block — find:

```tsx
              <pre
                style={{
                  fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                  fontSize: 11.5,
                  lineHeight: 1.7,
                  color: "#2a241b",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  background: "#fdfbf6",
                  border: "1px solid rgba(30, 27, 24, 0.12)",
                  padding: "18px 20px",
                  margin: 0,
                }}
              >
                {payload === null || payload === undefined
                  ? "// no evidence captured for this claim"
                  : JSON.stringify(payload, null, 2)}
              </pre>
```

Replace with:

```tsx
              {claimObj ? (
                claimObj.evidence.length === 0 ? (
                  <div style={{ fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)", fontSize: 12, color: "#6a5e4a", fontStyle: "italic" }}>
                    no evidence captured for this claim
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {claimObj.evidence.map((e, i) => (
                      <div key={i} style={{ background: "#fdfbf6", border: "1px solid rgba(30, 27, 24, 0.12)", padding: "12px 16px" }}>
                        <div style={{ fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.15em", color: "#8a7c64", marginBottom: 6 }}>
                          {e.kind}
                        </div>
                        {e.note && <div style={{ fontSize: 12.5, color: "#2a241b" }}>{e.note}</div>}
                        {e.link && <div style={{ fontSize: 11, color: "#6a5e4a", wordBreak: "break-word" }}>{e.link}</div>}
                        {e.timestamp && <div style={{ fontSize: 11, color: "#8a7c64" }}>{e.timestamp}</div>}
                        {e.citation && <div style={{ fontSize: 11, fontStyle: "italic", color: "#8a7c64" }}>{e.citation}</div>}
                      </div>
                    ))}
                  </div>
                )
              ) : (
                <pre
                  style={{
                    fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 11.5,
                    lineHeight: 1.7,
                    color: "#2a241b",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    background: "#fdfbf6",
                    border: "1px solid rgba(30, 27, 24, 0.12)",
                    padding: "18px 20px",
                    margin: 0,
                  }}
                >
                  {payload === null || payload === undefined
                    ? "// no evidence captured for this claim"
                    : JSON.stringify(payload, null, 2)}
                </pre>
              )}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/__tests__/EvidencePanel.test.tsx`
Expected: PASS (3 tests).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/EvidencePanel.tsx algorithmic-mirror/app/components/__tests__/EvidencePanel.test.tsx
git commit -m "feat(ui): WP-3.2 EvidencePanel — accept a Claim directly (additive, string API unchanged)"
```

---

### Task 3: `ClaimText.tsx` + `ClaimStat.tsx`

**Files:**
- Create: `algorithmic-mirror/app/components/ClaimText.tsx`
- Create: `algorithmic-mirror/app/components/ClaimStat.tsx`
- Test: `algorithmic-mirror/app/components/__tests__/ClaimText.test.tsx`
- Test: `algorithmic-mirror/app/components/__tests__/ClaimStat.test.tsx`

**Interfaces:**
- Consumes: `tierMeta`, `renderClaimValue` from `./claimStyle` (Task 1); `EvidencePanel` from `./EvidencePanel` (Task 2); `Claim` from `../../engine/types`.
- Produces: `ClaimText({ claim, children? }: { claim: Claim; children?: React.ReactNode })`; `ClaimStat({ claim, label, children? }: { claim: Claim; label: string; children?: React.ReactNode })`. Both self-contained: own their evidence-panel-open state, render their own `EvidencePanel`.

- [ ] **Step 1: Write the failing tests**

```tsx
// algorithmic-mirror/app/components/__tests__/ClaimText.test.tsx
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ClaimText } from "../ClaimText";
import type { Claim } from "../../../engine/types";

jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const claim: Claim = {
  id: "demo.gender", tier: "recorded", value: "female",
  method: "TikTok's own inferred-gender label, taken verbatim from your export.",
  evidence: [{ kind: "settings", note: "stored inferredGender" }],
};

describe("ClaimText", () => {
  test("default: renders the formatted value and the tier label", () => {
    render(<ClaimText claim={claim} />);
    expect(screen.getByText("female")).toBeInTheDocument();
    expect(screen.getByText(/recorded/i)).toBeInTheDocument();
  });

  test("children override the default value display", () => {
    render(<ClaimText claim={claim}><span>custom content</span></ClaimText>);
    expect(screen.getByText("custom content")).toBeInTheDocument();
    expect(screen.queryByText("female")).not.toBeInTheDocument();
  });

  test("clicking opens the evidence panel showing the method", () => {
    render(<ClaimText claim={claim} />);
    fireEvent.click(screen.getByText("female"));
    expect(screen.getByText(claim.method)).toBeInTheDocument();
  });
});
```

```tsx
// algorithmic-mirror/app/components/__tests__/ClaimStat.test.tsx
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ClaimStat } from "../ClaimStat";
import type { Claim } from "../../../engine/types";

jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const claim: Claim = {
  id: "attention.skip_rate_pct", tier: "derived", value: 42,
  method: "Share of conscious views skipped in under 3 seconds.",
  evidence: [{ kind: "video", note: "1200 skips / 3400 conscious views" }],
};

describe("ClaimStat", () => {
  test("renders label, value, tier badge, and method", () => {
    render(<ClaimStat claim={claim} label="Skip Rate" />);
    expect(screen.getByText("Skip Rate")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText(/derived/i)).toBeInTheDocument();
    expect(screen.getByText(claim.method)).toBeInTheDocument();
  });

  test("children override the default value display", () => {
    render(<ClaimStat claim={claim} label="Skip Rate"><span>90th percentile</span></ClaimStat>);
    expect(screen.getByText("90th percentile")).toBeInTheDocument();
    expect(screen.queryByText("42")).not.toBeInTheDocument();
  });

  test("clicking opens the evidence panel showing the evidence note", () => {
    render(<ClaimStat claim={claim} label="Skip Rate" />);
    fireEvent.click(screen.getByText("42"));
    expect(screen.getByText(/1200 skips \/ 3400 conscious views/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/__tests__/ClaimText.test.tsx app/components/__tests__/ClaimStat.test.tsx`
Expected: FAIL — `Cannot find module '../ClaimText'` / `'../ClaimStat'`.

- [ ] **Step 3a: Write `ClaimText.tsx`**

```tsx
// algorithmic-mirror/app/components/ClaimText.tsx
"use client";
/**
 * WP-3.2 — inline, unboxed Claim renderer. For embedding inside a panel that
 * already owns its own bordered container (e.g. TargetingCard's Segment,
 * DemographicPanel's Card) — do NOT nest this inside ClaimStat or another box.
 */
import { useState } from "react";
import type { Claim } from "../../engine/types";
import { tierMeta, renderClaimValue } from "./claimStyle";
import { EvidencePanel } from "./EvidencePanel";

export function ClaimText({ claim, children }: { claim: Claim; children?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const meta = tierMeta(claim.tier);
  return (
    <>
      <span
        onClick={() => setOpen(true)}
        role="button"
        tabIndex={0}
        style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12 }}
      >
        <span className={meta.className} style={{ padding: "1px 2px" }}>
          {children ?? renderClaimValue(claim.value)}
        </span>
        <span style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.08em", color: meta.color }}>
          {meta.label}
        </span>
      </span>
      <EvidencePanel open={open} title={null} claim={null} payload={null} claimObj={claim} onClose={() => setOpen(false)} />
    </>
  );
}
```

- [ ] **Step 3b: Write `ClaimStat.tsx`**

```tsx
// algorithmic-mirror/app/components/ClaimStat.tsx
"use client";
/**
 * WP-3.2 — standalone stat-card Claim renderer (LABEL / VALUE / tier badge /
 * method), for panels with no pre-existing box, e.g. the Evidence Log grid.
 */
import { useState } from "react";
import type { Claim } from "../../engine/types";
import { tierMeta, renderClaimValue } from "./claimStyle";
import { EvidencePanel } from "./EvidencePanel";

export function ClaimStat({ claim, label, children }: { claim: Claim; label: string; children?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const meta = tierMeta(claim.tier);
  return (
    <>
      <div
        onClick={() => setOpen(true)}
        role="button"
        tabIndex={0}
        className={meta.className}
        style={{ padding: "10px 12px", cursor: "pointer", display: "flex", flexDirection: "column", gap: 4 }}
      >
        <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(26,22,16,0.62)" }}>
          {label}
        </div>
        <div style={{ fontSize: 16, fontWeight: 600, color: meta.color }}>
          {children ?? renderClaimValue(claim.value)}
        </div>
        <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.08em", color: meta.color }}>
          {meta.label}
        </div>
        <div style={{ fontSize: 10, color: "rgba(26,22,16,0.62)" }}>{claim.method}</div>
      </div>
      <EvidencePanel open={open} title={label} claim={null} payload={null} claimObj={claim} onClose={() => setOpen(false)} />
    </>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/__tests__/ClaimText.test.tsx app/components/__tests__/ClaimStat.test.tsx`
Expected: PASS (6 tests).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/ClaimText.tsx algorithmic-mirror/app/components/ClaimStat.tsx algorithmic-mirror/app/components/__tests__/ClaimText.test.tsx algorithmic-mirror/app/components/__tests__/ClaimStat.test.tsx
git commit -m "feat(ui): WP-3.2 ClaimText + ClaimStat — shared tier-aware Claim renderers"
```

---

### Task 4: `ClaimsPanel.tsx` + Evidence Log tab

**Files:**
- Create: `algorithmic-mirror/app/components/ClaimsPanel.tsx`
- Test: `algorithmic-mirror/app/components/__tests__/ClaimsPanel.test.tsx`
- Modify: `algorithmic-mirror/app/components/GhostProfileHUD.tsx` (add `claims?: Claim[]` to `GhostProfile`)
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx` (add the Evidence Log tab)
- Test: `algorithmic-mirror/__tests__/ClaimsDashboard.test.tsx`

**Interfaces:**
- Consumes: `ClaimStat` (Task 3); `Claim`, `Tier` from `../../engine/types`; `profile.claims` (already flows through the payload via `page.tsx:142` — `claims: out.claims` — this task only adds the missing TS field + the panel that reads it).
- Produces: `ClaimsPanel({ claims }: { claims?: Claim[] })`; `GhostProfile.claims?: Claim[]`; a rendered Evidence Log tab.

- [ ] **Step 1: Write the failing tests**

```tsx
// algorithmic-mirror/app/components/__tests__/ClaimsPanel.test.tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { ClaimsPanel } from "../ClaimsPanel";
import type { Claim } from "../../../engine/types";

jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const claims: Claim[] = [
  { id: "declared.follower_count", tier: "recorded", value: 120, method: "From the export.", evidence: [{ kind: "follow" }] },
  { id: "attention.skip_rate_pct", tier: "derived", value: 42, method: "Computed.", evidence: [{ kind: "video" }] },
  { id: "identity.archetype", tier: "inferred", value: "The Seeker", method: "Nearest centroid.", confidence: 0.7, evidence: [{ kind: "video" }] },
];

describe("ClaimsPanel", () => {
  test("groups claims by tier with per-tier counts", () => {
    render(<ClaimsPanel claims={claims} />);
    expect(screen.getByText(/1 recorded/i)).toBeInTheDocument();
    expect(screen.getByText(/1 derived/i)).toBeInTheDocument();
    expect(screen.getByText(/1 inferred/i)).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("The Seeker")).toBeInTheDocument();
  });

  test("empty/undefined claims → a plain note, not a crash", () => {
    render(<ClaimsPanel claims={[]} />);
    expect(screen.getByText(/no claims/i)).toBeInTheDocument();
    render(<ClaimsPanel claims={undefined} />);
    expect(screen.getAllByText(/no claims/i).length).toBeGreaterThan(0);
  });
});
```

```tsx
// algorithmic-mirror/__tests__/ClaimsDashboard.test.tsx
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
  claims: [
    { id: "declared.follower_count", tier: "recorded", value: 120, method: "From the export.", evidence: [{ kind: "follow" }] },
  ],
} as unknown as GhostProfile;

test("Evidence Log tab renders the claims panel from the payload", () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Evidence Log/i));
  expect(screen.getByText("120")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/__tests__/ClaimsPanel.test.tsx __tests__/ClaimsDashboard.test.tsx`
Expected: FAIL — `ClaimsPanel` module not found; "Evidence Log" text not found.

- [ ] **Step 3a: Write `ClaimsPanel.tsx`**

```tsx
// algorithmic-mirror/app/components/ClaimsPanel.tsx
"use client";
/**
 * WP-3.2 — Evidence Log. Surfaces profile.claims (the WP-1.5 output — skip rate,
 * night shift, archetype, dissonance, etc.), grouped by tier. This data has never
 * been rendered anywhere before this panel.
 */
import type { Claim, Tier } from "../../engine/types";
import { ClaimStat } from "./ClaimStat";
import { tierMeta } from "./claimStyle";

const TIER_ORDER: Tier[] = ["recorded", "derived", "inferred"];

function labelFor(id: string): string {
  const last = id.split(".").pop() ?? id;
  return last.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function ClaimsPanel({ claims }: { claims?: Claim[] }) {
  if (!claims || claims.length === 0) {
    return <div style={{ fontSize: 12, color: "rgba(26,22,16,0.62)", fontStyle: "italic" }}>No claims in this payload.</div>;
  }

  const byTier = new Map<Tier, Claim[]>();
  for (const c of claims) {
    if (!byTier.has(c.tier)) byTier.set(c.tier, []);
    byTier.get(c.tier)!.push(c);
  }

  const counts = TIER_ORDER.map((t) => `${byTier.get(t)?.length ?? 0} ${tierMeta(t).label.toLowerCase()}`).join(" · ");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ fontSize: 12, color: "rgba(26,22,16,0.62)" }}>{counts}</div>
      {TIER_ORDER.map((tier) => {
        const group = byTier.get(tier);
        if (!group || group.length === 0) return null;
        return (
          <div key={tier} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: tierMeta(tier).color }}>
              {tierMeta(tier).label}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10 }}>
              {group.map((c) => <ClaimStat key={c.id} claim={c} label={labelFor(c.id)} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 3b: Add `claims` to `GhostProfile`**

In `algorithmic-mirror/app/components/GhostProfileHUD.tsx`, add the import near the other `engine` type imports:

```ts
import type { Claim } from "../../engine/types";
```

Add the field to the `GhostProfile` interface (mirroring `persona?`/`niche_drift?`):

```ts
  // WP-1.5/WP-3.2 — the flat claim list (recorded/derived/inferred), surfaced in the Evidence Log tab.
  claims?: Claim[];
```

- [ ] **Step 3c: Wire the Evidence Log tab into `ForensicDashboard.tsx`**

Add the import near the other component imports:

```tsx
import { ClaimsPanel } from "./ClaimsPanel";
```

Add `"claims"` to the `Tab` union — find:

```ts
type Tab = "overview" | "behavior" | "timeline" | "network" | "interests" | "privacy" | "ai";
```

Replace with:

```ts
type Tab = "overview" | "behavior" | "timeline" | "network" | "interests" | "privacy" | "ai" | "claims";
```

Add `ScrollText` to the lucide-react import — find:

```ts
import {
  Activity,
  Network,
  Search,
  LayoutDashboard,
  ArrowLeft,
  Lock,
  Zap,
  TrendingUp
} from "lucide-react";
```

Replace with:

```ts
import {
  Activity,
  Network,
  Search,
  LayoutDashboard,
  ArrowLeft,
  Lock,
  Zap,
  TrendingUp,
  ScrollText
} from "lucide-react";
```

Add a new `SidebarItem` immediately after the "AI Forensic Analyst" one — find:

```tsx
          <SidebarItem 
            icon={Zap} 
            label="AI Forensic Analyst" 
            active={activeTab === "ai"} 
            onClick={() => setActiveTab("ai")} 
          />
        </nav>
```

Replace with:

```tsx
          <SidebarItem 
            icon={Zap} 
            label="AI Forensic Analyst" 
            active={activeTab === "ai"} 
            onClick={() => setActiveTab("ai")} 
          />
          <SidebarItem 
            icon={ScrollText} 
            label="Evidence Log" 
            active={activeTab === "claims"} 
            onClick={() => setActiveTab("claims")} 
          />
        </nav>
```

Add the tab content immediately after the "ai" tab block — find:

```tsx
            {activeTab === "ai" && (
              <div>
                <LLMAnalysisView 
                  file={sourceFile!} 
                  apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
                  onBack={() => setActiveTab("overview")}
                />
              </div>
            )}
          </motion.div>
```

Replace with:

```tsx
            {activeTab === "ai" && (
              <div>
                <LLMAnalysisView 
                  file={sourceFile!} 
                  apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
                  onBack={() => setActiveTab("overview")}
                />
              </div>
            )}
            {activeTab === "claims" && (
              <div>
                <DashboardPanel label="Evidence Log" accent={ACCENT}>
                  <SectionTitle>Every Claim, By Tier</SectionTitle>
                  <ClaimsPanel claims={profile.claims} />
                </DashboardPanel>
              </div>
            )}
          </motion.div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/__tests__/ClaimsPanel.test.tsx __tests__/ClaimsDashboard.test.tsx`
Expected: PASS.
Then the whole suite: `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2` → PASS (all).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/ClaimsPanel.tsx algorithmic-mirror/app/components/__tests__/ClaimsPanel.test.tsx algorithmic-mirror/app/components/GhostProfileHUD.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx algorithmic-mirror/__tests__/ClaimsDashboard.test.tsx
git commit -m "feat(app): WP-3.2 Evidence Log tab — surface profile.claims for the first time"
```

---

### Task 5: Retrofit `TargetingCard.tsx`

**Files:**
- Modify: `algorithmic-mirror/app/components/TargetingCard.tsx`
- Test: `algorithmic-mirror/__tests__/TargetingCard.test.tsx` (verify unchanged, run only)

**Interfaces:**
- Consumes: `ClaimText` (Task 3). `TargetingSegment = Claim<TargetingSegmentValue>` already satisfies `ClaimText`'s `claim: Claim` prop.

- [ ] **Step 1: Confirm the existing test still describes the desired behavior**

Read `algorithmic-mirror/__tests__/TargetingCard.test.tsx` (unchanged by this task) — it asserts `TikTok admits`, the `Education`/`Uncategorized interest` category text, and the confirmed/inferred-only chips are present. None of these assert on the literal old confidence-line text, so this retrofit must keep them passing without modification.

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/TargetingCard.test.tsx`
Expected: PASS (already passing — this is the pre-retrofit baseline, confirm before editing).

- [ ] **Step 2: Modify `TargetingCard.tsx`**

Add the import near the other imports:

```tsx
import { ClaimText } from "./ClaimText";
```

In the `Segment` function, replace the confidence/count line — find:

```tsx
      <div style={{ fontSize: 11, color: INK_DIM }}>
        {seg.evidence.length} watched videos · confidence {seg.confidence}
      </div>
      <div style={{ fontSize: 10, color: INK_DIM }}>{seg.method}</div>
```

Replace with:

```tsx
      <ClaimText claim={seg}>{seg.evidence.length} watched videos</ClaimText>
      <div style={{ fontSize: 10, color: INK_DIM }}>{seg.method}</div>
```

- [ ] **Step 3: Run the existing test to confirm no regression**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/TargetingCard.test.tsx`
Expected: PASS (same 4 tests as before — the retrofit is additive UI, not a behavior change).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 4: Commit**

```bash
git add algorithmic-mirror/app/components/TargetingCard.tsx
git commit -m "refactor(ui): WP-3.2 retrofit TargetingCard to use ClaimText for the tier badge"
```

---

### Task 6: Retrofit `DemographicPanel.tsx`

**Files:**
- Modify: `algorithmic-mirror/app/components/DemographicPanel.tsx`
- Test: `algorithmic-mirror/__tests__/DemographicPanel.test.tsx` (verify unchanged, run only)

**Interfaces:**
- Consumes: `ClaimText` (Task 3), `renderClaimValue` no longer needed locally (dropped in favor of the shared one `ClaimText` already uses internally).

- [ ] **Step 1: Confirm the existing test still describes the desired behavior**

Read `algorithmic-mirror/__tests__/DemographicPanel.test.tsx` (unchanged by this task) — it asserts `getByText("female")` (the raw value), `getByText(/recorded/i)` (the tier label — `ClaimText` renders this), and the Miami-trips-not-`[object Object]` regression test. All three must keep passing.

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/DemographicPanel.test.tsx`
Expected: PASS (baseline, confirm before editing).

- [ ] **Step 2: Modify `DemographicPanel.tsx`**

Add the import near the other imports:

```tsx
import { ClaimText } from "./ClaimText";
```

Delete the local `renderValue` function entirely — find and remove:

```ts
function renderValue(v: unknown): string {
  if (Array.isArray(v)) {
    return v
      .map((x) => (x && typeof x === "object" && "city" in x
        ? `${(x as any).city} (${(x as any).days}d)`
        : String(x)))
      .join(", ");
  }
  if (v && typeof v === "object") return JSON.stringify(v);
  return String(v);
}
```

(This exact logic now lives in `claimStyle.ts`'s `renderClaimValue`, used internally by `ClaimText`.)

In the `Card` function, replace the claims-rendering block — find:

```tsx
          {card.claims.map((c) => (
            <div key={c.id} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <div>
                <span style={{ color: INK, fontWeight: 500 }}>{renderValue(c.value)}</span>{" "}
                <span style={{ fontSize: 10, textTransform: "uppercase", color: ACCENT, letterSpacing: "0.05em" }}>
                  {c.tier}{c.confidence != null ? ` · ${c.confidence}` : ""}
                </span>
              </div>
              <div style={{ fontSize: 10, color: INK_DIM }}>{c.method}</div>
            </div>
          ))}
```

Replace with:

```tsx
          {card.claims.map((c) => (
            <div key={c.id} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <ClaimText claim={c} />
              <div style={{ fontSize: 10, color: INK_DIM }}>{c.method}</div>
            </div>
          ))}
```

- [ ] **Step 3: Run the existing test to confirm no regression**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/DemographicPanel.test.tsx`
Expected: PASS (same 4 tests as before, including the Miami-trips regression).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors (confirms `INK`/`ACCENT` are still used elsewhere in the file and no unused-import breaks anything — if either becomes unused, remove it from the import line, verifying against the rest of the file first).

- [ ] **Step 4: Run the whole suite for final confirmation**

Run: `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2`
Expected: PASS (all suites, no regressions from Tasks 1–6 combined).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/DemographicPanel.tsx
git commit -m "refactor(ui): WP-3.2 retrofit DemographicPanel to use ClaimText, drop local renderValue"
```

---

## Self-Review

**Spec coverage:**
- Design tokens (`--stamp-blue`, `--redaction-black`) + verified WCAG contrast → Task 1. ✓
- Tier texture classes (solid/dashed/dotted, never hue alone, always a label) → Task 1 (`tierMeta`) + Task 3 (components always render `meta.label`). ✓
- `ClaimText`/`ClaimStat` consuming the real `Claim` type → Task 3. ✓
- `EvidencePanel` extension, additive, old API unchanged → Task 2 (explicit regression test). ✓
- New Evidence Log panel surfacing previously-invisible `profile.claims` → Task 4. ✓
- `PersonaRadar`/`NicheDriftChart` untouched → no task modifies them. ✓
- Retrofit `TargetingCard`/`DemographicPanel`, existing tests unchanged and still pass → Tasks 5–6. ✓
- `ClaimStat` used only where no pre-existing box (Evidence Log); `ClaimText` used inside existing boxes (both retrofits) → resolved as a technical necessity found while reading the actual current markup (nested-border collision), documented in Global Constraints. ✓
- Out-of-scope items (dossier shell, WP-3.4 stamp/hatch/animation, search/filter, full 9-component token migration) → not built. ✓

**Placeholder scan:** none — every code/test step is complete, all diffs shown as exact find/replace against verified current source.

**Type consistency:** `TierMeta`/`tierMeta`/`renderClaimValue` (Task 1) imported unchanged by `EvidencePanel` (Task 2), `ClaimText`/`ClaimStat` (Task 3), and `ClaimsPanel` (Task 4). `ClaimText`/`ClaimStat` prop shapes (`{ claim: Claim; children?: ReactNode }` / `{ claim: Claim; label: string; children?: ReactNode }`) used identically across Tasks 4–6. `EvidencePanel`'s `claimObj?: Claim` prop matches exactly what Tasks 3–4 pass. `GhostProfile.claims?: Claim[]` (Task 4) matches what `ClaimsPanel` (Task 4) and the dashboard test expect.

**Note for the implementer:** `page.tsx` already returns `claims: out.claims` in the analyze payload (line 142, since WP-1.5) — Task 4 does NOT touch `page.tsx`; the data was already flowing, only the TS field declaration and the rendering panel were missing. Do not add a redundant payload wire-up.
