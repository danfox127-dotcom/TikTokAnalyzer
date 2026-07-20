# WP-2.4 · Persona Engine v2 — Design

**Status:** approved design, pre-implementation
**Date:** 2026-07-20
**Depends on:** the profile emitted by `buildGhostProfile` (behavioral_nodes, stopwatch_metrics, academic_insights, search_rhythm, comment_voice, share_behavior), WP-1.4 (`TemporalSeries`)
**Unblocks:** WP-3.4 (polished Persona radar panel)
**Refs:** implementation-plan WP-2.4 / §3d

## 1. Purpose

Replace the archetype `if`-statement cascade with a **6-dimension persona vector**
(0–100 each) computed from existing profile metrics, and map that vector to a named
archetype via a **config map of centroids** (not code branches). Every formula is
exposed in a `method` string; the archetype is presented as a *reading*, not a fact.

## 2. Decisions (settled during brainstorming, 2026-07-20)

1. **Architecture: new TS persona LAYER, supersede + deprecate the old.** A pure
   `engine/persona.ts` `buildPersona(profile)` computes the dimensions from the
   already-emitted profile and maps to archetype regions, emitted as a new `persona`
   payload field (like `targeting_card`/`demographics`). `buildGhostProfile` is
   UNTOUCHED (no parity risk, no fixture regeneration). The new persona is the
   authoritative archetype in the UI; the old `primary_archetype`/`sub_archetypes`
   stay as a DEPRECATED alias for one release (the WP-1.7 echo-index precedent).
   Persona is TS-only (the browser-local default path); the legacy Python path keeps
   the old archetype — acceptable, WP-2.4's AC is frontend.
2. **Nocturnality is a descriptive MODIFIER, not an archetype axis.** "Nocturnal" is
   *when*, not *who*; welding it into an archetype ("Nocturnal Seeker") lets a user
   back into an identity just by being awake at night. So nocturnality is a radar
   dimension AND a rendered **prefix** ("Nocturnal"/"Diurnal"/none), but is **dropped
   from the centroid distance math**. Deliberate break from the plan's "keep existing
   names" line — retire the "Nocturnal Seeker" centroid.
3. **"The Seeker" is earned by SEARCH.** Replace the retired centroid with
   "The Seeker" (high exploration+search, high-ish intentionality, low capture).
   Search is the one unambiguous "went looking" signal, so **search intensity folds
   into the exploration dimension** — the Seeker is search-earned at any hour.

## 3. The six dimensions (0–100, formula in each `method`)

All inputs already live on `profile`; each score clamps to [0,100]; absent inputs
contribute 0. (Exact field paths pinned in the plan.)

1. **Intentionality** — deliberate/curated (100) vs passively fed (0):
   `0.5·followed_pct + 0.3·min(100, explicit_vs_implicit_ratio·50) + 0.2·skip_rate_pct`
2. **Capture susceptibility** — captured (100) vs resistant (0):
   `0.5·algorithmic_pct + 0.3·min(100, max_session_secs/3600·100) + 0.2·linger_rate_pct`
3. **Nocturnality** — night owl (100) vs diurnal (0):
   `min(100, night_shift_ratio·2)` — descriptive dimension + prefix source, NOT in the
   centroid distance.
4. **Exploration (incl. search)** — exploratory/seeking (100) vs narrow (0):
   `0.4·(100 − echo_concentration_pct) + 0.3·min(100, distinct_creators/50·100) + 0.3·min(100, total_searches/50·100)`
   (search saturates at 50 searches; distinct-creators at 50 — both tunable constants)
5. **Expressiveness** — expressive (100) vs lurker (0), **benchmark-calibrated**:
   anchored on 59.2% never comment / 73.5% never post — any commenting places a user
   above the 59th percentile: `if comments>0: 59 + min(41, volume/length bonus)` else
   `min(59, like/share activity)`. The 59/26.5 anchors are constants; the `method`
   cites the benchmarks.
6. **Parasociality** — parasocial (100) vs transactional (0):
   `0.5·echo_concentration_pct + 0.3·followed_pct + 0.2·comment-reference score`

**Coverage gate:** persona requires the registry minimum (**≥30 days AND ≥500
conscious views**, §3c) — below that, `buildPersona` returns `insufficient_evidence`
rather than scoring noise.

## 4. Archetype regions (nearest-centroid over the 5 "who" dimensions)

Config map: each base archetype → a centroid over the 5 "who" dimensions
(Int / Cap / Exp / Expr / Para — nocturnality excluded). Starting centroids (tunable):

| Base archetype | Int | Cap | Exp | Expr | Para |
|---|---|---|---|---|---|
| The Intentional Curator | 85 | 20 | 60 | 70 | 50 |
| The Seeker | 70 | 25 | 90 | 55 | 40 |
| The Algorithmic Captured | 20 | 90 | 25 | 25 | 65 |
| The Passive Observer | 30 | 55 | 40 | 10 | 30 |
| The Balanced Viewer | 50 | 50 | 50 | 50 | 50 |

- **Primary** = nearest centroid (Euclidean over the 5 dims).
- **Secondary** = 2nd-nearest, emitted only if `secondDist ≤ firstDist + SECONDARY_GAP`
  (start 25) — so every user gets exactly one primary and *up to* one secondary.
- **Confidence** (primary is an `inferred` reading) = `clamp(1 − firstDist/maxDist, 0, 1)`,
  rounded. The Balanced Viewer midpoint centroid wins geometrically when nothing is
  extreme, replacing the old `else "Balanced Viewer"` fallback.
- **Nocturnality modifier** (from dimension 3): `≥66 → "Nocturnal"`, `≤33 → "Diurnal"`,
  else `""`. `display_name = [modifier] + base_archetype` (e.g. "Nocturnal Curator").

## 5. Payload shape

```ts
interface PersonaResult {
  status: "ok" | "insufficient_evidence" | "error";
  dimensions: {
    intentionality: number; capture_susceptibility: number; nocturnality: number;
    exploration: number; expressiveness: number; parasociality: number;
  };                                          // radar-chart-ready, 0–100 each
  base_archetype: string;
  nocturnality_modifier: "Nocturnal" | "Diurnal" | "";
  display_name: string;                       // modifier + base
  secondary?: string;
  confidence: number;                         // 0–1, primary reading
  monthly?: TemporalSeries<PersonaDimensions>; // WP-1.4 per-month vector
  requirements?: { needed: string; had: string }; // when insufficient
  method: string;                             // dimension formulas + centroid method
}
```

`buildPersona` emits `PersonaResult`; it does **not** touch `claims.ts` — the old
`identity.archetype` claim stays for the one-release deprecation window.

## 6. Data flow

```
runEngine(raw) → { parsed, profile, claims, topicCandidates, … }
        │   profile already carries every dimension input
        ▼
buildPersona(profile)   ← NEW pure fn (engine/persona.ts), no network
        ▼
EngineResult.persona → payload.persona
        ▼
<PersonaRadar result={profile.persona} />   ← minimal radar; polished = WP-3.4
```

Surfaced in `pipeline.ts` `runEngineFromParsed` (like `topicCandidates`), so it rides
the existing browser-local flow with no page.tsx enrichment step needed.

## 7. UI

Minimal `app/components/PersonaRadar.tsx`: a plain 6-axis radar (recharts is already a
dependency) rendering the dimension vector + `display_name` + secondary + confidence,
from payload alone; three states (ok / insufficient_evidence / error). Wired into the
dashboard (Overview/Persona area). Lucide icons only; the polished animated radar is
WP-3.4.

## 8. Error handling / degradation

- Coverage below ≥30 days / ≥500 conscious views → `insufficient_evidence` with
  `requirements`.
- Missing individual metrics → that dimension contributes 0 (never NaN; guard with
  `Number.isFinite`).
- Malformed `profile` → `status: "error"`, no crash.
- Empty monthly data → `monthly` omitted; the top-level vector still renders.

## 9. Testing (maps every AC)

### Engine (TS, no network, fixtures)
- `persona.test.ts`:
  - **(AC)** each of the 6 dimension formulas — boundary + clamping (e.g. a
    high-followed/high-explicit fixture → high intentionality; a marathon-session
    fixture → high capture).
  - search intensity lifts exploration (a heavy-search fixture scores higher than an
    identical no-search one).
  - **(AC)** nearest-centroid picks the right primary for archetypal fixtures; a
    heavy-search fixture lands **"The Seeker"**; a midpoint fixture lands
    "The Balanced Viewer".
  - **(AC)** secondary emitted only when `secondDist ≤ firstDist + 25`; exactly one
    primary always.
  - nocturnality prefix thresholds (≥66 Nocturnal, ≤33 Diurnal, else none);
    `display_name` composition.
  - coverage gate → `insufficient_evidence`; malformed profile → `error`.
  - determinism (same profile → same result); every numeric dimension is finite.

### Component (TS, jsdom)
- `PersonaRadar.test.tsx`: renders all three states; ok state shows `display_name` +
  the six axes.

## 10. Out of scope (YAGNI / later WPs)

- Touching `buildGhostProfile` / `claims.ts` (old archetype stays deprecated one
  release; retiring it is a follow-up).
- The polished animated Persona radar panel → WP-3.4.
- A Python persona (TS-only; the legacy Python path keeps the old archetype).
- WP-2.5 niche-drift.
- Feeding persona into the LLM export prompt.

## 11. Open risks

- **The dimension weights are interpretive.** Mitigated by exposing every formula in
  `method`, keeping them deterministic, and presenting the archetype as a reading. The
  weights + centroids are config, tunable without code changes.
- **Monthly per-dimension series** depends on the profile exposing enough per-month
  metrics; where a month lacks inputs, its vector uses whatever is present (absent → 0)
  and is clearly a lower-confidence point. If per-month metric coverage proves too thin
  in practice, `monthly` can be dropped to a follow-up without affecting the top-level
  vector.
- **Expressiveness benchmark anchors** (59/26.5) are population constants from platform
  stats, not the user's data — they calibrate the *scale*, and the `method` says so.
