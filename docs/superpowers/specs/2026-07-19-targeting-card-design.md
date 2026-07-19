# WP-2.2 · Targeting Card — Design

**Status:** approved design, pre-implementation
**Date:** 2026-07-19
**Depends on:** WP-2.1 (`TopicResult`, `/api/topics`, `keywordClusters`), WP-1.5 (`Claim`/`EvidenceRef`/`Tier` contract in `engine/types.ts`), Gate 2 (`data/tiktok-ad-taxonomy.json`, committed, v2026.03-1)
**Unblocks:** WP-2.3 (demographic module, interests card), WP-3.4 (polished Targeting Card panel)

## 1. Purpose

Turn the WP-2.1 topic clusters into an **advertiser Targeting Card**: map each
watched-video topic cluster onto TikTok's real ad taxonomy, and show the user the
segments an advertiser could target them by — anchored to real watched videos and
cross-referenced against the interest categories TikTok *already declares* about
them. The output is `targeting_card.segments[]` as inferred `Claim`s.

Ground rule (main plan): deterministic math first, evidence always. Every segment
cites the real videos behind it; if it can't, it doesn't ship (the card gates to
`insufficient_evidence` rather than guessing).

## 2. Decisions (settled during brainstorming, 2026-07-19)

1. **Architecture: client TS engine, bundled taxonomy.** A committed, generated
   `engine/taxonomyIndex.ts` gives the browser the 716 taxonomy names + version;
   validation and Claim assembly run in a new pure `engine/targetingCard.ts` next
   to `claims.ts`. One deterministic path serves BOTH the server LLM `TopicResult`
   and the client keyword fallback. Not server-side: the keyword/Local path never
   calls the server, so a server-only validator would leave Local mode unable to
   produce a card (split brain).
2. **Local / no-key mode = insufficient-evidence gate.** The card is a
   video-evidence artifact. Keyword-fallback clusters cite terms (`video_ids: []`)
   and can't meet "≥3 evidence videos", so a keyword-source `TopicResult` returns
   `status: "insufficient_evidence"`. Aligns with ground rule 3 (gate, don't
   degrade). Consequence: **no** pillar-category→taxonomy map is built (WP-2.1 had
   deferred that here; the gate makes it unnecessary — YAGNI).
3. **UI scope: engine data + minimal functional card.** WP-2.2 ships the engine
   module (segments as Claims in the payload) plus a plain `TargetingCard.tsx`
   rendering all three states from payload alone. The animated case-file-flip
   panel + stamp states stay WP-3.4.
4. **Advertiser cross-reference = match segments vs TikTok's declared
   `ad_interests`.** Per segment, a `tiktok_confirmed` flag: does TikTok already
   list this interest, or is it inferred-only? Card-level: "TikTok admits N
   categories; we found M; K overlap." This reinterprets the AC's literal
   "advertiser-count" using the actually-parsed ad data — the parser extracts
   `ad_interests` + `off_tiktok_activity`, not a literal advertiser list.
5. **Taxonomy match = STRICT.** Normalized (lowercase/trim) EXACT match against
   `TAXONOMY_NAMES`. Near-misses ("Fitness" vs the file's "Fitness & Workout")
   become "Uncategorized interest", not a lenient contains-match. A wrong
   advertiser anchor is a worse lie than an honest uncategorized, and it keeps the
   deterministic validation clean.
6. **Uncategorized bucket = SEPARATE segments.** Each unmatched cluster keeps its
   own name + videos (and still meets ≥3 videos on its own), rather than being
   collapsed into one union segment — preserves the distinct topics and evidence.

## 3. Data flow

`runEngine()` is synchronous and offline (it emits `topicCandidates` and nothing
network-bound). The `TopicResult` is **async** — from `POST /api/topics` (BYOK) or
the client-side `keywordClusters` fallback. So the targeting logic is a
**standalone pure function** the page calls *after* it has the `TopicResult`; it is
NOT inside `runEngine`.

```
runEngine(raw)                    → { …, claims, topicCandidates }   (sync, offline)
        │
page.tsx orchestration (the WP-2.1 topics step, already async):
        │  has key?  → POST /api/topics { videos: topicCandidates } → TopicResult (source:"llm")
        │  no key?   → keywordClusters(profile)                     → TopicResult (source:"keyword")
        ▼
buildTargetingCard(topicResult, profile)   ← NEW pure engine fn, no network
        ▼
payload.targeting_card = InsightModuleResult   (status + segment Claims + counts)
        ▼
<TargetingCard result={payload.targeting_card} />   ← NEW minimal 3-state component
                (ForensicDashboard Interests tab)
```

Nothing touches the parity-locked `buildGhostProfile`. `buildClaims` in `claims.ts`
is untouched; the targeting segments are their own `Claim[]` inside the module
result — same contract, assembled separately (exactly as WP-2.1 layered over the
orchestrator).

## 4. `engine/taxonomyIndex.ts` — generated + parity-tested

A committed, generated module so the browser gets the taxonomy without a runtime
file read:

```ts
// AUTO-GENERATED from data/tiktok-ad-taxonomy.json — do not edit by hand.
export const TAXONOMY_VERSION = "2026.03-1";
export const TAXONOMY_RETRIEVED = "2026-07-13";
export const TAXONOMY_NAMES: string[] = [ "Education", /* …716… */ ];
```

- **Generator:** `scripts/gen_taxonomy_index.py` reads the source JSON and writes
  the TS module. Mirrors the existing golden-fixture generator pattern
  (`scripts/gen_*_parity_fixture.py`).
- **Parity test:** `engine/__tests__/taxonomyIndex.test.ts` re-reads
  `data/tiktok-ad-taxonomy.json` and asserts the generated module matches (716
  names, `TAXONOMY_VERSION`, `TAXONOMY_RETRIEVED`), so a stale index fails CI. This
  is the one test allowed to touch `fs` — a Node-side build-parity check, not
  shipped to the browser.
- **Browser-safety:** the runtime import is a plain string array — no `fs`/`path`/
  `crypto`/`process`/`require`.

## 5. `engine/targetingCard.ts` — the module

`buildTargetingCard(topicResult: TopicResult, profile: any): InsightModuleResult` —
pure, no network. `InsightModuleResult` follows the plan §2 contract
(`moduleId`, `status`, `requirements?`, `claims`), extended with card-level counts.

### Guard first (insufficient-evidence gate)
Return `status: "insufficient_evidence"`, `claims: []`,
`requirements: { needed: "LLM topic pass (bring your own key)", had: "keyword fallback" }`
when ANY of:
- `topicResult.source === "keyword"`, or
- no clusters, or
- **no cluster survives the ≥3-video rule** (below).

### Per-cluster → segment (LLM path)
1. **Video-evidence bar:** a cluster ships only if `video_ids.length >= 3`;
   otherwise dropped. Enforces the AC "every segment cites ≥3 evidence videos."
   (The bar is applied to the *segment's* final evidence set — see grouping — so a
   merged matched segment must reach ≥3 across its union.)
2. **Taxonomy validation (strict):** normalize `taxonomy_hint` (lowercase/trim),
   look it up in a `Set` built from `TAXONOMY_NAMES` (normalized). Matched →
   `category = <canonical file name>`, `matched: true`. Unmatched / `null` →
   `matched: false`.
3. **Grouping (resolves id-uniqueness):**
   - **Matched clusters group BY canonical category** — one segment per distinct
     taxonomy category, `video_ids` = the deduped union across its clusters,
     `cluster_name` = the joined/representative cluster names, `confidence` = max of
     the grouped clusters. Same advertiser category = same segment. ID
     `targeting.segment.<slug(category)>` is unique by construction.
   - **Unmatched clusters stay SEPARATE** — one "Uncategorized interest" segment
     each (distinct topics, distinct evidence). ID
     `targeting.segment.uncategorized.<slug(cluster_name)>`, with a positional
     suffix breaking any residual cluster-name collision.
   - The ≥3-video bar (step 1) is checked on each final segment's evidence set;
     segments under the bar are dropped.
4. **Advertiser cross-reference:** `tiktok_confirmed = ` does the matched category
   OR the cluster name(s) match any string in the profile's declared `ad_interests`
   (normalized exact-or-contains, either direction)?

### Segment shape (an inferred `Claim`)
```ts
{
  // matched:  `targeting.segment.${slug(category)}`
  // unmatched:`targeting.segment.uncategorized.${slug(cluster_name)}` (+suffix if needed)
  id,
  tier: "inferred",
  value: {
    category,            // canonical taxonomy name, or "Uncategorized interest"
    cluster_name,        // representative / joined source cluster name(s)
    matched,             // boolean
    tiktok_confirmed,    // boolean
  },
  confidence,            // max of grouped clusters (LLM path → 0.7)
  evidence: video_ids.map(id => ({ kind: "video", id })),   // deduped union, length ≥ 3
  method:
    `Matched watched-video topics to TikTok ad taxonomy ${TAXONOMY_VERSION}; ` +
    `${matched ? "category confirmed in file" : "no taxonomy match (uncategorized)"}; ` +
    `${tiktok_confirmed ? "TikTok already lists this interest" : "not in TikTok's declared interests"}.`
}
```
- IDs are unique by construction (matched segments keyed by distinct category;
  unmatched keyed by cluster name + positional suffix). `validateClaims` rejects
  duplicate ids, so a `targetingCard.test.ts` case asserts uniqueness explicitly.
- Every segment passes the existing `validateClaims` (inferred ⇒ confidence in
  [0,1] + non-empty evidence — both hold by construction).

### Module result (card-level metadata, not Claims)
```ts
{
  moduleId: "targeting_card",
  status: "ok",
  claims: Segment[],
  counts: {
    declared_ad_interest_count,   // N — from profile declared ad_interests
    segment_count,                // M — segments shipped
    confirmed_count,              // K — segments with tiktok_confirmed
  },
  taxonomy_version: TAXONOMY_VERSION,
}
```

## 6. `app/components/TargetingCard.tsx` + wiring

Plain functional component. Warm-paper palette constants already used across the
codebase (`BORDER`/`INK`/`INK_DIM`/`ACCENT`), lucide icons only, **no animation**
(WP-3.4 owns the designed version). Renders the `InsightModuleResult`:

- **`ok`** → the "TikTok admits N; we found M; K overlap" summary line, then each
  segment: category (or "Uncategorized interest"), a `✓ TikTok confirms` /
  `⚠ inferred-only` chip, the video-evidence count, confidence, and the method
  string (with taxonomy version).
- **`insufficient_evidence`** → the gated state, driven by `requirements`: "Run
  topic analysis with your own key to see exactly what advertisers can target."
- **`error`** → a plain error note.

**Wiring:** in `page.tsx`, after the existing topics step yields a `TopicResult`,
call `buildTargetingCard(topicResult, profile)` and add it to the payload as
`targeting_card`. Render `<TargetingCard>` in the ForensicDashboard **Interests
tab**, next to the existing "Audience Labels Sold To Advertisers" panel.

## 7. Error handling / degradation

- **No key / keyword fallback** → `insufficient_evidence` (the default Local-mode
  path, not an error).
- **Zero clusters, or all clusters < 3 videos** → `insufficient_evidence`.
- **`taxonomy_hint` null or not in file** → segment ships as "Uncategorized
  interest" (`matched: false`), still citing its videos.
- **Missing/empty declared `ad_interests`** → `tiktok_confirmed` is `false` for all
  segments; `declared_ad_interest_count: 0`; still renders `ok`.
- **Malformed `TopicResult`** (unexpected shape) → `status: "error"` with a note,
  not a crash.

## 8. Testing (maps every AC)

### Engine (TS, no network, fixtures)
- `taxonomyIndex.test.ts` — generated module matches source (716 names, version,
  retrieved_date); stale index fails.
- `targetingCard.test.ts`:
  - **(AC)** LLM clusters → segments; matched vs strict-miss → "Uncategorized".
  - two matched clusters on the same category → ONE merged segment (deduped union
    of videos, max confidence); unmatched clusters stay separate.
  - **(AC)** segments with < 3 videos (after grouping) dropped; every shipped
    segment cites ≥ 3.
  - **(AC)** `method` echoes `TAXONOMY_VERSION`.
  - keyword source → `insufficient_evidence`; empty / all-dropped →
    `insufficient_evidence` with `requirements`.
  - `tiktok_confirmed` set from a fixture with declared `ad_interests`; counts
    (`declared_ad_interest_count`/`segment_count`/`confirmed_count`) correct.
  - **every produced segment passes `validateClaims`** (incl. unique ids across
    multiple uncategorized segments).
  - malformed `TopicResult` → `status: "error"`.

### Component (TS, jsdom)
- `TargetingCard.test.tsx` — renders all three states (`ok` / `insufficient_evidence`
  / `error`) from payload alone; the ok state shows the cross-ref summary and a
  confirmed/inferred chip.

## 9. Explicitly out of scope (YAGNI / later WPs)

- The animated case-file-flip panel + stamp states → WP-3.4.
- Pillar-category → taxonomy map for keyword mode → killed by the
  insufficient-evidence gate (decision 2).
- The other four WP-2.3 demographic cards (location, age, gender, spending) → WP-2.3.
- Parsing a literal advertiser list from the export → we cross-reference declared
  `ad_interests` instead (decision 4).
- Per-month temporal re-clustering → later.
- Any change to the parity-locked orchestrator (`buildGhostProfile`) or golden
  fixtures.

## 10. Open risks

- **Strict matching yields many "Uncategorized" segments** if the LLM's
  `taxonomy_hint` phrasing drifts from the file's exact names. Accepted: honest,
  and WP-2.1's prompt already feeds the model the exact taxonomy names, so
  well-behaved hints should match. Revisit lenient matching only if uncategorized
  dominates in practice.
- **`ad_interests` string shape vs taxonomy names** differ (TikTok's declared
  strings aren't guaranteed to equal taxonomy category names), so `tiktok_confirmed`
  uses normalized exact-or-contains and may under-count overlaps. Acceptable — it
  only ever *under*-claims confirmation, never over-claims.
- **Taxonomy index staleness** — mitigated by the parity test failing CI when the
  generated module drifts from the source file.
