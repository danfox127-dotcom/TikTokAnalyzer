# WP-3.1 · Dossier Shell & Navigation — Design

**Status:** approved design, pre-implementation
**Date:** 2026-08-10
**Depends on:** the existing `ForensicDashboard.tsx` (all Phase 2 + WP-3.2 panels already wired into its 8 tabs)
**Unblocks:** WP-3.3 (Timeline scrubber), WP-3.4 (polished panel treatments)
**Refs:** implementation-plan WP-3.1; dependency graph `WP-1.5 → WP-3.2 → WP-3.1 → WP-3.3 → WP-3.4`

## 1. Purpose

Formalize the "persistent post-story workspace" into a proper shell: extract the
1190-line monolithic `ForensicDashboard.tsx` (8 tabs' worth of inline JSX, grown
organically across 6+ WPs) into a thin orchestrator + a reusable `DossierShell` +
one component per tab, each lazy-loaded via `next/dynamic()` so the initial
dashboard bundle doesn't ship every recharts-heavy panel regardless of which tab
is active.

## 2. Decisions (settled during brainstorming, 2026-08-10)

1. **Dossier-only — no Story mode.** `TheGlassHouse.tsx` (1705 lines, the "Story"
   narrative component) is confirmed **orphaned**: not imported or reachable from
   any path in `page.tsx`. The live flow already goes `upload → dashboard`
   directly ("Pivot: Bypass cinematic surface/transition, go straight to tools" —
   an existing code comment). This WP treats `ForensicDashboard` as the sole real
   destination and does not revive, modify, or delete `TheGlassHouse.tsx` — it
   stays exactly as-is, untouched, still orphaned. (Deleting it is a legitimate
   future cleanup, explicitly not part of this WP.)
2. **"Panel grid" = the existing card-grid layout within a tab**, not a new
   requirement that all 8 tabs render simultaneously. (E.g. Overview's
   `FourPillarsPanel` + `PersonaRadar` side by side via `DashboardPanel` cards —
   already how several tabs are laid out today.)
3. **Real code-splitting via `next/dynamic()`**, not just a data-layer
   reinterpretation of "lazy-load." This project uses plain `ts-jest`, not
   `next/jest` — there is no built-in synchronous-resolution support for dynamic
   imports under test, and the async nature of a real dynamic `import()` cannot
   be mocked away (it's inherent, not an artifact of a missing mock). Accepted
   cost: the 5 existing dashboard tests that click a tab and assert content
   synchronously must change `getByText` → `await findByText` (mechanical,
   one-line-per-assertion, identical coverage/intent — RTL's standard pattern for
   async-rendered content).
4. **"No per-panel refetch" is already true by construction** (the browser-local
   architecture produces one full payload via `analyzeLocal()`; no panel does its
   own fetch) — this WP formalizes/preserves that property through the extraction
   rather than introducing it new.

## 3. Architecture / file structure

```
algorithmic-mirror/app/components/
  dashboardPrimitives.tsx    — DashboardPanel, SectionTitle, SidebarItem,
                                StopwatchFunnel, CreatorLedger (moved, unchanged)
  DossierShell.tsx           — sidebar nav + header + reset button + tab-switch
                                wrapper; owns `activeTab` state; the next/dynamic
                                lookup map
  tabs/
    OverviewTab.tsx            { profile: GhostProfile }
    BehaviorTab.tsx            { profile: GhostProfile }
    NetworkTab.tsx              { profile: GhostProfile }
    TimelineTab.tsx             { profile: GhostProfile }
    InterestsTab.tsx            { profile: GhostProfile }
    PrivacyTab.tsx                { profile: GhostProfile }
    AiTab.tsx                     { sourceFile: File; apiUrl: string; onBack: () => void }
    ClaimsTab.tsx                 { profile: GhostProfile }
  ForensicDashboard.tsx      — shrinks to a thin orchestrator (~60–80 lines):
                                wires <DossierShell profile={...} onReset={...}
                                sourceFile={...} />, no rendering logic of its own
```

`DossierShell.tsx` builds the lazy lookup:
```ts
const TAB_COMPONENTS: Record<Tab, ComponentType<any>> = {
  overview: dynamic(() => import("./tabs/OverviewTab").then(m => m.OverviewTab)),
  behavior: dynamic(() => import("./tabs/BehaviorTab").then(m => m.BehaviorTab)),
  // ...one entry per tab
};
```
`next/dynamic` is a Next.js built-in — no new dependency. Each entry creates its
own JS chunk; switching tabs triggers a chunk fetch the first time (cached after),
instead of every tab's code shipping in the initial bundle.

**Untouched by this WP:** `PersonaRadar.tsx`, `NicheDriftChart.tsx`,
`TargetingCard.tsx`, `DemographicPanel.tsx`, `ClaimsPanel.tsx`, and every engine
file — each tab wrapper consumes them exactly as today, just from a new home file.

## 4. Data flow

Unchanged at the data layer: `page.tsx`'s `analyzeLocal()` still produces one
`GhostProfile` payload, passed to `ForensicDashboard` → `DossierShell` →
whichever tab is active. The only new mechanic is *when* each tab's JS loads
(on first activation, not on initial dashboard mount) — never *what* data it
receives or *how many times* it's fetched.

## 5. Error handling / degradation

If a lazy chunk fails to load (network/build issue), `next/dynamic` renders
nothing by default. `DossierShell` supplies a minimal `loading` fallback (plain
"Loading…" text) so a slow chunk shows a state rather than a blank pane. No
retry/error-boundary machinery — out of scope.

## 6. Testing

**Existing test migration (5 files, mechanical, identical coverage):**
`TargetingCardDashboard.test.tsx`, `DemographicPanelDashboard.test.tsx`,
`PersonaRadarDashboard.test.tsx`, `NicheDriftDashboard.test.tsx`,
`ClaimsDashboard.test.tsx` — each test's post-click assertion changes from
`expect(screen.getByText(...))` to `expect(await screen.findByText(...))`, the
enclosing `test(...)` marked `async`. No fixture, click, or assertion-target
changes — only the query mechanics, adapted for genuinely-async lazy content.

**New tests:**
- `DossierShell.test.tsx` — all 8 tab labels render in the sidebar; clicking a
  tab switches `activeTab` and (async) renders that tab's lazy-loaded content;
  the reset button fires `onReset`.
- One smoke test per extracted tab component — mounts with a minimal `profile`
  fixture, asserts no throw. (Behavioral coverage for *what* each tab shows
  already lives in the 5 migrated dashboard tests plus each panel's own
  component tests from Phase 2 / WP-3.2 — these are extraction-safety checks,
  not new behavioral coverage.)
- No special `next/dynamic` mock needed — Jest resolves real dynamic imports
  natively; tests just await resolution.

## 7. Out of scope (YAGNI / later WPs)

- Real Next.js routes / URL-addressable tabs — current single-page state model
  (the `View` union in `page.tsx`) stays as-is.
- Reviving, modifying, or deleting `TheGlassHouse.tsx` — left exactly as-is.
- Any change to `PersonaRadar`/`NicheDriftChart`/`TargetingCard`/
  `DemographicPanel`/`ClaimsPanel`/engine files — consumed as-is.
- A literal simultaneous multi-panel grid (all 8 tabs visible at once).
- WP-3.3 (Timeline scrubber) and WP-3.4 (polished panel treatments) — this WP
  builds the shell they plug into, nothing more.
- Retry/error-boundary UI for failed lazy-chunk loads — a minimal loading
  fallback only.
- Any Python/backend change — pure frontend refactor.

## 8. Open risks

- **`next/dynamic` under `ts-jest` (not `next/jest`) is a real, somewhat unusual
  combination** — while the async-resolution behavior is standard React/webpack
  dynamic-import semantics (not Next.js-specific magic), if a genuinely
  unexpected interaction surfaces during implementation, the fallback is to
  verify empirically task-by-task rather than assume; the plan should treat the
  first tab's dynamic-import test as the proof-of-pattern for the rest.
- **Extraction risk is low but not zero** — the file-split touches every tab's
  markup; each extraction is verified against its own existing dashboard test
  (via the migrated `findByText` assertions) so a copy/paste error surfaces
  immediately as a task-level test failure, not a silent regression.
