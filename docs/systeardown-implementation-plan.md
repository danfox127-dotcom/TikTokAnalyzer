# SYS.TEARDOWN v2 — Implementation Plan
### Agent-ready work packages, contracts, and acceptance criteria

*Companion to: `systeardown-redesign-plan.md` (the what and why), `systeardown-redesign-addendum.md` (visual system, hosting, mobile, variable windows, attribution), `systeardown-research-integration.md` (research-driven corrections). This document is the build order. Agents implementing a work package should read the relevant sections of those docs first — each WP lists its references.*

---

## 0. Ground rules for all agents

1. **Deterministic math lives in code; LLMs interpret.** No LLM call may produce a number that is displayed as a statistic. LLM outputs are labels, cluster assignments, and narration only, always validated against a JSON schema before use.
2. **Every user-facing claim carries a tier.** All insight payloads must include `tier: "recorded" | "derived" | "inferred"` and, for inferred claims, `confidence: number (0–1)` plus `evidence: EvidenceRef[]`. No exceptions. If a claim can't cite evidence, it doesn't ship.
3. **Coverage gates before computation.** Every insight module declares `minCoverage` requirements (see §2 contracts) and must return an `insufficient_evidence` payload rather than a degraded guess when unmet.
4. **Do not break the Python test suite until Gate 0 resolves.** The existing `tests/` directory is the behavioral oracle for the port. Tests are ported before logic is ported.
5. **Preserve existing documents and code paths until a WP explicitly retires them.** No drive-by refactors outside a WP's stated file scope.
6. **Never invent TikTok export keys.** The parser handles multiple export layouts; when encountering an unknown structure, log it via the schema-fingerprint mechanism (WP-1.6), don't guess.

---

## 1. Decision gates (need Dan's sign-off before dependent WPs start)

**GATE 0 — Engine language.** Recommendation on file: TypeScript-everywhere (finish the port in `supabase/functions/_shared/forensics/`, Python retires to test oracle). Alternative: keep Python/FastAPI and accept no browser-local mode. *Blocks: WP-1.1, and the target paths of every engine WP.* Everything below is written assuming **Option B (TypeScript)**; if Dan chooses Option A, the same WPs apply with `api/*.py` targets and WP-1.1 is dropped.

**GATE 1 — Privacy tiers.** Confirm the two-tier model: Local mode (browser Web Worker, nothing persisted, no LLM stage) and Vault mode (Supabase persistence, LLM narration, opt-in). Decide client-side encryption vs. RLS-only for Vault. *Blocks: WP-3.5, WP-5.2.*

**GATE 2 — Taxonomy snapshot.** Dan sources the TikTok Ads Manager interest/behavior category list (one-time research task) and commits it as `data/tiktok-ad-taxonomy.json` with a `version` and `retrieved_date` field. *Blocks: WP-2.2.*

**GATE 3 — Vulnerability-window framing.** Editorial decision on how bluntly emotional-state inferences are presented. *Blocks: WP-4.3 copy only, not its computation.*

---

## 2. Shared contracts (implement first — everything depends on these)

These are the data shapes agents must conform to. Define once in a shared types module (`packages/engine/types.ts` or equivalent) and generate/mirror for the frontend.

```ts
type Tier = "recorded" | "derived" | "inferred";

interface EvidenceRef {
  kind: "video" | "search" | "login" | "like" | "share" | "comment" |
        "follow" | "order" | "settings" | "external_source";
  id?: string;            // video_id, etc.
  link?: string;
  timestamp?: string;     // ISO 8601
  note?: string;          // e.g. "watched 4m12s at 2:47am"
  citation?: string;      // for external_source: e.g. "PIPEDA 2025-003 ¶62"
}

interface Claim<T = unknown> {
  id: string;             // stable key, e.g. "demo.age_band"
  tier: Tier;
  value: T;
  confidence?: number;    // required when tier === "inferred"
  evidence: EvidenceRef[];
  method: string;         // one-line plain-language formula description
}

interface Coverage {
  overall: { start: string; end: string; days: number };
  perSection: Record<string, { start: string; end: string; count: number }>;
  // sections: watch_history, searches, likes, shares, comments, logins,
  // follows, orders, off_platform, favorites
}

interface InsightModuleResult {
  moduleId: string;
  status: "ok" | "insufficient_evidence" | "error";
  requirements?: { needed: string; had: string };  // when insufficient
  claims: Claim[];
}

type MonthKey = `${number}-${string}`;  // "2026-03"
interface TemporalSeries<T> { byMonth: Record<MonthKey, T>; overall: T; }
```

**Stopwatch bucket enum (revised per addendum §2 and research-integration §4):**
`clock_anomaly` (delta < 0, dropped) · `graveyard` (< 3s) · `sandbox` (3–15s) · `linger` (15–180s) · `deep_dive` (180–300s, or up to duration-scrub limit when duration known) · `abandoned` (300s–1200s, uncorroborated) · `sleep_scrubbed` (≥ 1200s, or > 3× video duration when duration known) · `phantom_session` (run detection, WP-1.3).
Corroboration promotes `abandoned` → `deep_dive` when the video was liked/favorited/shared/commented, or when known duration supports the watch time.

---

## 3. Work packages

Sizing: **S** ≈ single focused session · **M** ≈ 1–2 sessions · **L** ≈ multi-session, split further at implementation time. Each WP states: goal / scope / spec references / acceptance criteria (AC).

### Phase 1 — Foundation

**WP-1.1 · Complete the TypeScript engine port [L]** *(Gate 0)*
Scope: `supabase/functions/_shared/forensics/` → promote to a standalone `packages/engine/` consumable by (a) a browser Web Worker, (b) Deno/edge, (c) Node. Port remaining Python logic from `api/ghost_profile.py`, `utils/psychographic.py`, `parsers/tiktok.py`. Port the Python `tests/` suite first; run both engines against the same fixture exports and diff outputs.
AC: engine has zero runtime dependencies on server-only APIs; test-fixture parity with Python within float tolerance; runs in a Worker against a 40k-video fixture in < 30s on a mid-range laptop.

**WP-1.2 · Coverage detection & gating [M]**
Scope: Parse stage emits the `Coverage` object (per-section min/max timestamps, counts). Implement a `requireCoverage(moduleId, coverage)` guard used by every insight module; central registry of per-module minimums (initial values: persona ≥ 30 days & ≥ 500 conscious views; rabbit-hole ≥ 60 days; movement ≥ 5 logins; attribution/forecast ≥ 90 days).
Refs: addendum §5.
AC: a 20-day fixture export produces `insufficient_evidence` for persona/attribution and `ok` for stopwatch basics; coverage banner data present in the API payload.

**WP-1.3 · Sleep-scrub hardening [M]**
Scope: implement revised bucket enum (§2 above): `abandoned` bucket; duration-aware scrub (> 3× duration when oEmbed/metadata supplies duration, threshold fallback otherwise); per-user adaptive anomaly flag (beyond user's p99 delta, 20-min floor); phantom-session detector (≥ 10 consecutive night-hour views, 30–180s deltas, zero engagement events in window → excluded from scoring, retained as `phantom_sessions` artifact with count and total hours).
Refs: addendum §2; research-integration §4.
AC: unit tests for each bucket boundary; a synthetic asleep-autoplay fixture is detected; scrub summary stats (`excluded_hours`, `phantom_nights`) present in payload; persona-dimension inputs exclude `abandoned` and `phantom_session` events.

**WP-1.4 · Temporal bucketing [M]**
Scope: extend the Measure stage so every metric that currently computes overall also computes per-month (`TemporalSeries<T>`); degrade to per-week when coverage < 90 days. The existing `monthly_data` skip/total tracker in the stopwatch is the seed — generalize the pattern.
AC: stopwatch buckets, cluster shares (post-WP-2.1), night-shift ratio, and explicit/implicit ratio all emit `TemporalSeries`; snapshot tests on fixtures.

**WP-1.5 · Confidence/tier plumbing [M]**
Scope: refactor all existing insight outputs into the `Claim` contract (§2). Existing provenance strings in `api/narratives.py` blocks map to `EvidenceRef[]`. Frontend receives tiers but no UI work yet (that's WP-3.2).
AC: every field in the dossier payload is either a `Claim` or structural metadata; schema validation test passes on full fixture run.

**WP-1.6 · Export schema fingerprinting [S]**
Scope: fingerprint each uploaded export (top-level keys, section names, sample record shapes → hash + human-readable diff vs. known layouts). Log unknown keys; expose `schema_version` and `unknown_sections[]` in payload.
AC: known fixtures map to named layouts; a mutated fixture logs the delta without crashing the parse.

**WP-1.7 · Split Echo Chamber Index [S]**
Scope: replace single index with `daily_concentration` (mean share of daily conscious watch time in that day's top-5 clusters) and `cluster_churn` (mean day-over-day replacement rate of top-5). Flag `true_bubble` only when concentration high AND churn low (thresholds configurable; start: concentration > 0.6, churn < 0.4). Include published benchmarks as constants with citations (typical ≈ 0.5 concentration, ≈ 0.79 churn).
Refs: research-integration §2.
AC: computed per-month; benchmark comparison fields present; old index retained as deprecated alias for one release.

### Phase 2 — Insight Layer

**WP-2.1 · Semantic Topic Engine [L]**
Scope: replaces keyword matching in `utils/pillar_categories.py`. Pipeline: after oEmbed enrichment, select titles weighted by watch time (deep dives full weight, lingers partial, graveyard/sandbox excluded), cap at N titles per batch (start N = 800, sampled proportionally across months so temporal analysis isn't biased); one structured-output LLM call per dossier returning `{ clusters: [{ name, video_ids[], taxonomy_hint }] }`; validate against schema; cache result keyed by dossier hash + prompt version. Server-side only (Vault mode); Local mode falls back to the keyword map, labeled lower-confidence.
Refs: main plan §3a; ground rule 1.
AC: schema-validated output on 3 fixture dossiers; cache hit on re-run; every video in a cluster is traceable (cluster → video_ids → EvidenceRefs); cost per dossier logged and under a configurable ceiling.

**WP-2.2 · Targeting Card [M]** *(Gate 2)*
Scope: map WP-2.1 clusters onto `data/tiktok-ad-taxonomy.json` (LLM `taxonomy_hint` proposes; deterministic validation confirms the category exists in the file; unmatched clusters surface as "uncategorized interest"). Output: `targeting_card.segments[]` as `Claim`s (tier: inferred) with per-segment evidence and the advertiser-count cross-reference from the export's ad data.
AC: card renders from payload alone; every segment cites ≥ 3 evidence videos; taxonomy file version echoed in the card's method string.

**WP-2.3 · Demographic inference module [L]**
Scope: five cards mirroring the regulator-confirmed inference categories — interests (from WP-2.1/2.2), location (movement narrative from login IP geo: home base = modal night-hours location; trips = ≥ 2 consecutive days elsewhere), age band (declared birthdate as recorded tier + behavioral estimate output in TikTok's documented advertising brackets 13-17/18-24/25-34/35-44/45-54/55+), gender (surface the export's `inferredGender` verbatim, recorded tier), spending power (orders + product browsing + cluster mix → low/mid/high proxy, inferred tier, conservative confidence). Each card carries the `citation` EvidenceRef to PIPEDA 2025-003.
Refs: main plan §3c; research-integration §5.
AC: each card is a `Claim` with method string; location narrative unit-tested on synthetic login fixtures (home/work/trip detection); no card renders without meeting coverage gates.

**WP-2.4 · Persona Engine v2 [M]**
Scope: replace archetype if-statements with six 0–100 dimension scores (intentionality, capture susceptibility, nocturnality, exploration↔monogamy, expressiveness, parasociality) computed from existing metrics; formulas documented in each `method` string. Archetypes become named regions over the dimension vector (keep existing names; define regions in a config map, not code branches). Expressiveness calibrated against platform benchmarks (73.5% never post / 59.2% never comment).
Refs: main plan §3d.
AC: dimension formulas unit-tested; every user maps to exactly one primary archetype + up to one secondary; radar-chart-ready payload; per-month series via WP-1.4.

**WP-2.5 · Niche-drift metric [S]**
Scope: monthly mean/median like-count of consciously watched videos (where oEmbed supplies counts), with fitted trend.
Refs: research-integration §3.
AC: `TemporalSeries` output; handles months with sparse enrichment by widening to quarters; excluded when < 40% of videos have counts.

### Phase 3 — Dossier Mode (frontend)

*All frontend WPs: read `/mnt/skills/public/frontend-design/SKILL.md` equivalent conventions in-repo; design tokens per addendum §1 (extend `globals.css` — stamp blue `#1f4e6b`, redaction black `#0d0b08`, texture classes `tier-recorded|derived|inferred`). Framer Motion; honor `prefers-reduced-motion`.*

**WP-3.1 · Dossier shell & navigation [M]** — persistent post-story workspace in `algorithmic-mirror/`; panel grid; routes/state for Story ↔ Dossier. AC: all panels lazy-load from the single dossier payload; no per-panel refetch.

**WP-3.2 · Confidence visual language [M]** — implement the three-tier system (color + border texture + label, never hue alone); `<ClaimText>` and `<ClaimStat>` components that render any `Claim` with tap-through evidence margin-note (extend existing EvidencePanel). AC: a11y contrast checks pass; grayscale screenshot still distinguishes tiers; every panel uses the components (lint rule or review checklist).

**WP-3.3 · Timeline scrubber [M]** — global month-range control re-rendering panels from `TemporalSeries` data with spring morphs. AC: scrub is client-side only (no recompute); < 100ms panel update on fixture data.

**WP-3.4 · Panels: Targeting Card, Demographics, Persona radar, Niche drift, Movement map [L — split per panel]** — case-file flip for Targeting Card; redaction-reveal for demographic inferences; stamp-slam labels; INSUFFICIENT EVIDENCE stamp state for gated panels. AC per panel: renders all three states (ok / insufficient / error); evidence tap works; reduced-motion fallback.

**WP-3.5 · Local mode (browser engine) + PWA [L]** *(Gates 0, 1)* — engine in a Web Worker; ZIP intake client-side; PWA manifest + service worker; guided data-request flow with deep link and local notification (~36h); demo dossier from synthetic fixture. AC: full analysis of a 40k-video fixture with network disabled (minus LLM stage, which shows its Local-mode fallback state); Lighthouse PWA installable.

### Phase 4 — Story v2, Attribution, Export

**WP-4.1 · Attribution stage ("4.5 Attribute") [L]**
Scope: new engine stage between Interpret and Narrate. Components: (a) seed-event attribution — for each cluster, earliest explicit signal (search > follow > favorite) preceding growth, with a reverse-causality guard: the cluster's watch-share trend in the 14 days *before* the signal must be flat/absent for the signal to qualify as a seed; (b) folk-theory test — replicate the CHI methodology per-user: cluster-similarity of the K videos before vs. after each like/share event, output the before/after comparison; (c) responsiveness lag — median days from qualifying seed to measurable share shift; (d) decay half-life per cluster after engagement stops; (e) 30-day per-cluster trend projection with confidence band, labeled PROJECTED.
Refs: addendum §6; research-integration §1. Requires ≥ 90 days coverage.
AC: reverse-causality guard unit-tested against a fixture where the surge precedes the like; projections never render without the band and label; all outputs are `Claim`s.

**WP-4.2 · Story v2 chapter restructure [M]** — Glass House chapters per addendum §4 arc; new chapter "Why Your Feed Looks Like This" from WP-4.1; night chapters use the inverted palette. AC: story consumes only payload data; every chapter stat is a rendered `Claim`.

**WP-4.3 · Vulnerability windows [S]** *(Gate 3 for copy)* — computation: night-linger clusters × emotional-content categories → time windows; framing per Dan's editorial decision. AC: computation behind a feature flag until Gate 3 clears.

**WP-4.4 · Export dossier artifact [M]** — one-page shareable PDF/PNG: Targeting Card, radar, headline stats, tier legend. AC: renders server-side and client-side (Local mode); grayscale-legible.

### Phase 5 — parked (Instagram insight parity, longitudinal re-upload comparison, native app). Do not start without a new plan doc.

---

## 4. Dependency graph (critical path)

```
GATE 0 → WP-1.1 → WP-1.2 → WP-1.5 → { WP-1.3, WP-1.4, WP-1.6, WP-1.7 }
WP-1.4 + WP-2.1 → WP-2.2 (needs GATE 2) → WP-2.3
WP-1.3 + WP-1.7 → WP-2.4 ;  WP-1.4 → WP-2.5
WP-1.5 → WP-3.2 → WP-3.1 → WP-3.3 → WP-3.4
GATE 0 + GATE 1 + WP-1.1 → WP-3.5
WP-1.4 + WP-2.1 → WP-4.1 → WP-4.2 ;  GATE 3 → WP-4.3 ;  WP-3.4 → WP-4.4
```

## 5. Suggested agent routing (Dan's stack)

- **Antigravity (autonomous executor):** WP-1.3, 1.4, 1.6, 1.7, 2.4, 2.5, 3.3 — well-bounded specs with unit-testable ACs.
- **Claude Code (thinking partner / reviewer):** WP-1.1 (port decisions), WP-2.1–2.3 (LLM pipeline + prompt design), WP-4.1 (methodology-sensitive), and review of every merged WP against ground rules 1–3.
- **Gemini (large-context reader):** parity diffing Python vs. TS outputs in WP-1.1; auditing the full payload against the Claim contract in WP-1.5.
- Per existing convention: update Obsidian `session-state.md` and run `/handoff` at each WP boundary; one WP per branch; WP ID in every commit message.

## 6. Definition of done (per phase)

A phase is done when: all its WPs' ACs pass in CI; the fixture suite (small 2k-video export, large 40k, short-window 20-day, malformed-schema) runs green end-to-end; no payload field escapes the Claim contract; and a human (Dan) has clicked through the affected UI states including every `insufficient_evidence` stamp.
