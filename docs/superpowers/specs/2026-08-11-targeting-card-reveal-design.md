# WP-3.4a · Targeting Card Reveal — Design

**Status:** approved design, pre-implementation
**Date:** 2026-08-11
**Depends on:** WP-2.2 (Targeting Card data/logic, shipped), WP-3.2 (Confidence Visual Language — `ClaimText`/`EvidencePanel`, shipped)
**Part of:** WP-3.4 "Panels: Targeting Card, Demographics, Persona radar, Niche drift, Movement map" — marked `[L — split per panel]` in the master plan. This is the first of 4 independent sub-projects (Targeting Card, Demographics, Persona radar, Niche drift), each with its own spec/plan/implementation cycle.
**Refs:** implementation-plan WP-3.4

## 1. Purpose

Give `TargetingCard.tsx` the "case-file flip" visual treatment the master plan calls for. The component is currently — by its own code comment — "deliberately unstyled beyond the shared warm-paper register; the animated case-file panel is WP-3.4." This sub-project delivers that: a wax-seal reveal animation on the `ok` state, and a matching stamp graphic on the `insufficient_evidence` state.

## 2. Scope decomposition (settled during brainstorming, 2026-08-11)

The master plan bundles 5 panels under WP-3.4 and explicitly marks it `[L — split per panel]`. During brainstorming this was decomposed into 4 sub-projects (not 5 — see below), each independently spec'd, planned, and shipped:

1. **Targeting Card** (this spec)
2. Demographics
3. Persona radar
4. Niche drift

**"Movement map" is not a 5th sub-project.** No such component exists anywhere in the codebase; the closest thing is the "Location" card already living inside `DemographicPanel.tsx` (one of its 5 sub-cards: interests/location/age/gender/spending, from WP-2.3). "Movement map" polish is folded into the Demographics sub-project, applying the same redaction-reveal treatment to that existing card — not a new geo-visualization component.

## 3. Decisions (settled during brainstorming, 2026-08-11)

1. **"Case-file flip" = a wax-seal seal-break reveal, not a literal card flip.** Three visual directions were presented (3D perspective flip, folder fold-open, seal-break/stamp-reveal); seal-break was chosen — no rotation/perspective, a stamp graphic cracks/fades and the segment content cross-fades in underneath. This is the lightest-weight motion of the three and matches the app's existing stamp/tier visual language (`--stamp-blue`, dotted tier-inferred borders) more closely than a literal flip would.
2. **The reveal auto-plays once on mount — it is not a tap-to-reveal gate.** Content is never hidden behind a required interaction; the stamp cracks automatically the moment the card has `ok`-status data to show. This matches accessibility conventions already followed elsewhere in the app (no other panel gates its content behind a click) and avoids a "no-JS/reduced-motion fallback for an interaction gate" problem entirely — reduced motion just skips straight to the revealed state.
3. **The stamp graphic is a wax-seal medallion**, not a rubber ink-stamp or a rectangular "CONFIDENTIAL" file-stamp (both were presented and rejected). Solid filled circle, radial-gradient oxblood fill, rotated slightly, uppercase label text — an envelope-seal metaphor rather than a bureaucratic ink-stamp one.
4. **The same stamp component (different label) covers the master plan's separately-named "INSUFFICIENT EVIDENCE stamp state" requirement.** `insufficient_evidence` renders the wax-seal stamp permanently (no animation, no `AnimatePresence`) with label "INSUFFICIENT EVIDENCE", alongside — not instead of — the existing Lock icon + explanatory sentence (the sentence still carries the "needs X, have Y" confidence data a graphic alone can't convey).
5. **The `error` state stays exactly as it is today** — plain `AlertTriangle` + text, no stamp, no motion. An error is a transient/technical failure, not narrative dossier content worth treating as "sealed" — stamping it would misleadingly imply the error itself is meaningful evidence.

## 4. Architecture

```
algorithmic-mirror/app/components/
  Stamp.tsx              — new, small, stateless presentational component
  TargetingCard.tsx       — modified: adds the reveal sequence for the ok state,
                            renders Stamp on the insufficient_evidence state
```

```ts
// Stamp.tsx
interface StampProps {
  label: string; // e.g. "SEALED" or "INSUFFICIENT EVIDENCE"
}
export function Stamp({ label }: StampProps)
```

`Stamp` has no motion baked in — it's a plain wax-seal graphic + label, reusable in both the animated (`TargetingCard`'s `ok` branch) and static (`insufficient_evidence` branch) contexts without forcing motion where none is wanted.

`TargetingCard`'s signature is unchanged: `TargetingCard({ result }: { result?: TargetingCardResult })`. No new props; no changes to `TargetingCardResult`, `TargetingSegment`, or `engine/targetingCard.ts` — this is purely a rendering-layer change.

## 5. Data flow / reveal mechanics

No data changes. The only new state is local, ephemeral UI state inside `TargetingCard`:

- A `revealed` boolean. When `status === "ok"` and `useReducedMotion()` is `false`, it starts `false` and flips to `true` exactly once, driven by the crack animation's `onAnimationComplete` callback (not a magic-number `setTimeout`, so it's tied to the actual animation finishing). It never re-seals — no re-trigger on re-render, tab-switch, or data scrub.
- When `useReducedMotion()` is `true`, or `status !== "ok"`, `revealed` starts `true` immediately — no gate, no animation, segments render exactly as they do today.

The `ok`-branch sequence: `Stamp` (label "SEALED") wrapped in a `motion.div` animates `scale: 1 → 1.15, opacity: 1 → 0` over `{ duration: 0.4, ease: "easeOut" }` (a "crack apart" via scale-then-vanish — not the WP-3.3 layout-spring, since this is a one-shot entrance effect, not a reflow interaction). The segment list, in its own `motion.div`, cross-fades `opacity: 0 → 1` over the same duration with a ~0.15s delay, so the stamp is visibly gone before segments reach full opacity — avoiding a muddy overlap. Both wrapped in `AnimatePresence` so the reduced-motion path can cleanly skip straight to end-state (no stamp ever mounts).

The `insufficient_evidence` branch renders `Stamp` (label "INSUFFICIENT EVIDENCE") as a plain, permanent element — no `motion.div`, no `AnimatePresence` — next to the existing Lock icon and "needs X, have Y" copy, unchanged.

## 6. Visual detail

`Stamp`'s wax-seal graphic: a filled circle with a radial gradient (oxblood tones consistent with the existing `ACCENT` token, `#8b2323`-family), rotated a few degrees off-axis, drop-shadow for a slight embossed/3D feel, uppercase label text centered inside, sized to read clearly at the card's existing dimensions. Matches the "wax seal medallion" mockup approved during brainstorming — solid, ornate, envelope-seal feeling rather than a flat bureaucratic ink-stamp.

## 7. Testing

- **`Stamp.test.tsx`** (new, colocated in `app/components/__tests__/`): renders with a given `label` prop, asserts the label text appears in the DOM. Trivial coverage for a pure presentational component.
- **`TargetingCard.test.tsx`** (new — no test file exists for this component today): covers all four scenarios —
  - `status: "ok"`, `useReducedMotion` mocked `true`: segments render immediately; no `Stamp` anywhere in the DOM.
  - `status: "ok"`, `useReducedMotion` mocked `false`: `Stamp` (label "SEALED") is present; the framer-motion Proxy mock (same pattern used throughout this codebase) renders `motion.div` as a plain wrapper with animation props stripped, so both the stamp and the segment list are simultaneously present in the DOM under jsdom (the real crack/cross-fade timing doesn't execute under the mock) — the test asserts both are queryable, confirming the reveal sequence's structural wiring rather than its runtime timing.
  - `status: "insufficient_evidence"`: `Stamp` (label "INSUFFICIENT EVIDENCE") renders permanently alongside the existing Lock icon and "needs X, have Y" copy.
  - `status: "error"`: unchanged — plain `AlertTriangle` + text, no `Stamp` anywhere in the DOM.
  - `result: undefined`: unchanged — renders nothing.

All per existing project conventions: `TZ=UTC`, `ts-jest`, RTL, `framer-motion` proxy-mocked the same way every other dashboard test already does, extended with `useReducedMotion: () => <bool>` per test case.

## 8. Error handling / degradation

- `error` and `undefined` states are entirely unchanged from current behavior (see Decisions §5 and current `TargetingCard.tsx` source) — no new failure modes introduced.
- If `TargetingCardResult` itself is malformed upstream, that's an existing concern outside this WP's scope; this sub-project only changes how a well-formed `ok`/`insufficient_evidence` result is presented.

## 9. Out of scope (YAGNI / later sub-projects)

- The other 3 WP-3.4 sub-projects (Demographics — including the "Movement map"/Location card, Persona radar, Niche drift) — each gets its own spec/plan/implementation cycle.
- Any change to `TargetingCardResult`, `TargetingSegment`, or `engine/targetingCard.ts`.
- Any change to `ClaimText`/`EvidencePanel`/evidence-tap behavior — already functional, untouched.
- Re-triggering the reveal animation on re-render, tab-switch-and-back, or data changes — one-shot entrance effect only.
- Visual treatment for the `error` state.
