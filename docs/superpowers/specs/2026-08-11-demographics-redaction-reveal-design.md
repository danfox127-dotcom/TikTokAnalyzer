# WP-3.4b · Demographics Redaction-Reveal — Design

**Status:** approved design, pre-implementation
**Date:** 2026-08-11
**Depends on:** WP-2.3 (Demographic inference module data/logic, shipped), WP-3.2 (Confidence Visual Language — `ClaimText`/`EvidencePanel`, shipped), WP-3.4a (Targeting Card reveal — established the one-shot reveal pattern this sub-project follows, shipped)
**Part of:** WP-3.4 "Panels: Targeting Card, Demographics, Persona radar, Niche drift, Movement map" — the second of 4 independent sub-projects (see [[wp3-4-panels-decisions]] memory / WP-3.4a's spec for the decomposition rationale, including why "Movement map" is not a separate 5th sub-project).
**Refs:** implementation-plan WP-3.4

## 1. Purpose

Give `DemographicPanel.tsx` the "redaction-reveal" treatment the master plan calls for. The component is currently — by its own code comment — rendering "the five inference cards from payload alone... The polished redaction-reveal panel is WP-3.4." This sub-project delivers that: a redaction-bar reveal animation per card on its `ok` state.

## 2. Scope note: this covers "Movement map" too

Per the WP-3.4a decomposition decision, "Movement map" is not a separate component or sub-project — it's the existing "Location" card, one of `DemographicPanel`'s 5 categories (interests/location/age/gender/spending). Its claims (home city, work city, trip cities) are plain text/array values rendered through the same generic `ClaimText` machinery as every other category — confirmed via `engine/locationNarrative.ts` and `claimStyle.ts`'s `renderClaimValue` (which already formats trip objects as `"City (Nd)"` strings). No map visualization is implied by the data shape or built here; Location gets the exact same redaction-reveal treatment as the other 4 categories, nothing category-specific.

## 3. Decisions (settled during brainstorming, 2026-08-11)

1. **A new, distinct "redaction bar" component — not a reuse of WP-3.4a's wax-seal `Stamp`.** The master plan uses different wording per panel ("case-file flip" for Targeting Card vs "redaction-reveal" for Demographics), a real signal these panels warrant different visual metaphors. A solid black bar (the `--redaction-black` CSS custom property, already defined in `globals.css` with the comment "redaction motif, reused by WP-3.4" — reserved for exactly this, unused until now) fades away to reveal the text underneath, fitting the PIPEDA/government-citation "declassified document" framing already established by each card's citation line.
2. **Reveals are per-card, independent — not one shared bar over the whole 5-card grid.** Unlike Targeting Card's single `status`, `DemographicPanel` renders 5 independently-computed cards, each with its own `ok`/`insufficient_evidence` status (age might be reconstructable while location isn't). A single shared bar would misrepresent 5 independent inferences as one all-or-nothing gate.
3. **`insufficient_evidence` cards do NOT get a redaction-bar marker — they keep today's plain Lock icon + explanatory text.** The redaction-bar metaphor implies something real is hidden underneath; that's false for `insufficient_evidence` cards, where `claims` is genuinely empty (there's no reconstructed value to redact — the export simply doesn't contain enough data). This is a deliberate divergence from Targeting Card's `insufficient_evidence` treatment (which DID get a permanent wax-seal stamp, since a stamp is a status marker with no implication of hidden content) — the two metaphors don't transfer identically.
4. **The module-level `error` state stays exactly as it is today** — plain `AlertTriangle` + text, no bars, no motion. Same reasoning as Targeting Card WP-3.4a: an error is a transient/technical failure, not narrative content worth a visual treatment.
5. **The reveal auto-plays once per card on mount** — same one-shot, never-re-triggering, `useReducedMotion()`-gated mechanics established in WP-3.4a's `TargetingCard`. Not a tap-to-reveal gate.

## 4. Architecture

```
algorithmic-mirror/app/components/
  RedactionBar.tsx        — new, small, stateless presentational component
  DemographicPanel.tsx    — modified: its internal `Card` sub-component gains
                            per-instance reveal state for the ok branch
```

```ts
// RedactionBar.tsx
interface RedactionBarProps {
  width?: string; // defaults to "100%" — lets a caller size it to its content
}
export function RedactionBar({ width }: RedactionBarProps)
```

`RedactionBar` has no motion baked in — a plain solid block using `var(--redaction-black)`, reusable in any future context needing the same visual without forcing motion. `DemographicPanel`'s exported signature is unchanged: `DemographicPanel({ result }: { result?: DemographicModuleResult })`. No new props; no changes to `DemographicModuleResult`, `DemographicCard`, `engine/demographics.ts`, or `engine/locationNarrative.ts` — purely a rendering-layer change.

## 5. Data flow / reveal mechanics

No data changes. Because `Card` is already instantiated once per category inside `DemographicPanel`'s `.map()`, giving `Card` its own local reveal state gives each of the 5 categories an independent reveal for free — no extra plumbing, no lifted state.

Per `Card` instance, for `status === "ok"`: a `hasRevealed` boolean starts `false`, flips to `true` exactly once via the bar's `onAnimationComplete` callback (not a timer), never resets. `revealed = Boolean(useReducedMotion()) || hasRevealed`. Under reduced motion, `RedactionBar` never mounts and the claims block renders immediately with `{ duration: 0 }`.

The claims block (the existing `.map()` over `card.claims`, each rendering `ClaimText` + its method line) sits in a `motion.div` cross-fading `opacity: 0 → 1` over `{ duration: 0.4, ease: "easeOut", delay: 0.15 }` (collapsing to `{ duration: 0 }` under reduced motion — same transition convention as Targeting Card). `RedactionBar` is absolutely positioned over that same claims area, in its own `motion.div` inside `AnimatePresence`, animating `opacity: 1 → 0` (a straight fade-out — "redaction lifting," not a crack/scale like the wax-seal) over `{ duration: 0.4, ease: "easeOut" }`, with `onAnimationComplete` flipping `hasRevealed`. `Card`'s outer container needs `position: relative` for the bar's absolute positioning to anchor correctly.

`insufficient_evidence` cards render exactly as today — plain Lock icon + "Not enough in your export..." text, no bar, no motion, no state.

## 6. Testing

- **`RedactionBar.test.tsx`** (new, colocated in `app/components/__tests__/`): renders with default and custom `width` props, asserts the rendered element carries the `--redaction-black` background. Trivial coverage for a pure presentational component, same class as `Stamp.test.tsx`.
- **`__tests__/DemographicPanel.test.tsx`** (exists already — 4 tests: ok+insufficient mixed fixture, trips-array rendering, module error, undefined). Extend it; do not remove existing tests. Its existing `ok` fixture already has a gender=`ok`/location=`insufficient_evidence` mix — reuse that shape for the new mixed-status independence test rather than inventing a new fixture. Add:
  - A card with `status: "ok"`, `useReducedMotion` mocked `true`: claims render immediately; no `RedactionBar` anywhere in the DOM for that card.
  - A card with `status: "ok"`, `useReducedMotion` mocked `false`: `RedactionBar` present over that card; claims are also present in the DOM (asserts the reveal sequence's structural wiring, not its runtime timing — the framer-motion mock never invokes `onAnimationComplete`, matching the established testing approach from Targeting Card's review).
  - A card with `status: "insufficient_evidence"`: plain Lock+text; no `RedactionBar` anywhere for that card.
  - Module `status: "error"`: unchanged — plain `AlertTriangle` + text, no bars anywhere (existing test already covers this; just confirm it still passes unchanged).
  - Independent per-card reveal, using the existing mixed ok/insufficient_evidence fixture: the `ok` card shows a bar, its `insufficient_evidence` sibling doesn't.

All per existing project conventions: `TZ=UTC`, `ts-jest`, RTL, `framer-motion` proxy-mocked the same way every other dashboard test already does, extended with `useReducedMotion: () => <bool>` per test case. `__tests__/DemographicPanel.test.tsx` itself currently has no local framer-motion mock and relies on the global one in `jest.mock-setup.js` — which already exports `useReducedMotion` as of WP-3.4a, so it needs no infrastructure fix.

**Known cross-file risk (same class caught in WP-3.4a's final review):** `__tests__/DemographicPanelDashboard.test.tsx` has its OWN local `jest.mock("framer-motion", ...)` that fully shadows the global one for that file, and it's currently missing `useReducedMotion`. That test clicks through to the Privacy tab and renders `DemographicPanel` with an `ok`-status card — once `Card` calls `useReducedMotion()` unconditionally, this file will crash without the same one-line fix applied to `TargetingCardDashboard.test.tsx` in WP-3.4a. (`ForensicDashboard.realdata.test.tsx` was already patched during WP-3.4a's post-review fix wave and also reaches the Privacy tab, so it's already safe.) The implementation plan must include this fix as an explicit task step, not leave it for the final review to rediscover a second time.

## 7. Error handling / degradation

- Module-level `error` and `undefined` states are entirely unchanged from current behavior — no new failure modes introduced.
- If `DemographicModuleResult` itself is malformed upstream, that's an existing engine concern outside this WP's scope.

## 8. Out of scope (YAGNI / later sub-projects)

- The remaining 2 WP-3.4 sub-projects (Persona radar, Niche drift) — each gets its own spec/plan/implementation cycle.
- Any change to `DemographicModuleResult`, `DemographicCard`, `engine/demographics.ts`, or `engine/locationNarrative.ts`.
- Any change to `ClaimText`/`EvidencePanel`/evidence-tap behavior — already functional, untouched.
- A literal map visualization for Location — confirmed not needed per §2.
- Re-triggering any card's reveal on re-render, tab-switch-and-back, or data changes — one-shot entrance effect only, per card.
- Visual treatment for the `insufficient_evidence` or module-level `error` states.
