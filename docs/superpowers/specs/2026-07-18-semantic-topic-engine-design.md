# WP-2.1 · Semantic Topic Engine — Design

**Status:** approved design, pre-implementation
**Date:** 2026-07-18
**Depends on:** WP-1.1 (engine port), WP-1.4 (temporal `_month` keys on events), Gate 2 (`data/tiktok-ad-taxonomy.json`, committed)
**Unblocks:** WP-2.2 (Targeting Card)

## 1. Purpose

Replace the small static keyword dictionary (`utils/pillar_categories.py`) with a
semantic clustering pass that reads the user's actually-watched video **titles**
(weighted by watch time) and names the topics the way a person would — then
anchors each topic to the real TikTok ad taxonomy. The output is
taxonomy-anchored topic clusters that feed the WP-2.2 Targeting Card.

Ground rule (main plan): deterministic math first, LLM as interpreter. The LLM
only clusters and labels messy titles and proposes a taxonomy match; it never
invents a statistic.

## 2. Decisions (settled during brainstorming)

- **Key & cost model: BYOK + keyword fallback.** The user supplies their own
  Claude/Gemini key (the existing Four Pillars mechanism) and thereby opts in to
  sending titles to their LLM. With no key, the engine falls back to a
  deterministic keyword clustering over the text the browser already has,
  labeled lower-confidence. No server-paid LLM, no cost-ceiling / abuse infra.
- **Primary consumer: the WP-2.2 Targeting Card.** This spec delivers the
  *engine* (titles → taxonomy-anchored clusters). It does not build a dedicated
  cluster UI, does not validate `taxonomy_hint` against the file, and does not
  build `Claim`s — those are WP-2.2.
- **Architecture: server-relayed clustering; the client never holds titles.** The
  client sends video IDs + locally-computed watch weights; the server fetches the
  public titles via oEmbed and clusters them. Titles exist only server-side,
  transiently. Built deterministic-path-first, LLM second.

## 3. Data flow

### LLM path (BYOK, opt-in)
1. **TS engine (client, deterministic):** from `stopwatch_metrics.linger_events` +
   `deep_dive_events`, compute a per-video weight, rank, take top-N (start 800)
   sampled proportionally across months. Output: `{ video_id, weight }[]` — IDs
   and numbers only, no titles.
2. **`POST /api/topics` (server):** receives the `{video_id, weight}` pairs +
   `api_key`/`provider`. Fetches titles via oEmbed (existing cached path), builds
   the weighted title list, relays to the LLM with a structured-output prompt +
   the ad-taxonomy category names.
3. Returns schema-validated `{ clusters: [{ name, video_ids[], taxonomy_hint }] }`,
   Redis-cached by `hash(video_ids+weights+prompt_version)` so a re-run is free.

### Keyword fallback (default, no key)
Runs entirely in the client over the existing `interest_clusters` (text footprint:
searches / comments / declared interests) mapped through the ported
`pillarCategories.ts`. Same cluster shape, `source: "keyword"`, lower confidence,
no titles, no server call — preserves the local-default "nothing leaves" posture.

### Where things live
- Deterministic weighting/sampling + keyword fallback → `algorithmic-mirror/engine/`
  (`topicCandidates.ts`, `keywordClusters.ts`), surfaced via `pipeline.ts`. Keyword
  clusters computed lazily by the caller only when there is no key.
- LLM relay + oEmbed titles + cache + validation → `api/main.py` (`/api/topics`) +
  new `utils/topic_engine.py`.
- Nothing added to the parity-locked orchestrator (`buildGhostProfile`).

## 4. Cluster contract

```ts
interface TopicCluster {
  name: string;                  // plain-English, LLM- or keyword-derived
  video_ids: string[];           // traceable evidence — always a subset of the input
  taxonomy_hint: string | null;  // proposed match into the ad taxonomy (NOT yet validated)
  confidence: number;            // 0–1
  evidence_kind: "video" | "term";
}
interface TopicResult {
  source: "llm" | "keyword";
  clusters: TopicCluster[];
  prompt_version: string;        // bumped when the prompt changes → cache key + reproducibility
  cached: boolean;
  usage?: { input_tokens: number; output_tokens: number }; // LLM path only
}
```

**Taxonomy anchoring is a proposal, not a validation.** The LLM receives the
ad-taxonomy category names from `data/tiktok-ad-taxonomy.json` and proposes the
closest `taxonomy_hint` per cluster. WP-2.1 does not confirm the hint exists —
that deterministic check (else "uncategorized interest") is WP-2.2. Keyword-path
clusters emit `taxonomy_hint: null` — the category→taxonomy mapping is WP-2.2's job.

**Traceability (AC):** a validation pass drops any `video_id` not in the input
set, keeping "cluster → video_ids → real watched videos" intact.

**Handoff to WP-2.2:** the Targeting Card consumes `TopicResult`, validates each
`taxonomy_hint` against the file, and wraps surviving clusters as `Claim`s
(tier `inferred`, WP-1.5 contract) with `video_ids` as `EvidenceRef`s. WP-2.1
stops at the raw clusters.

## 5. Deterministic engine pieces (built + tested first, no LLM)

### `engine/topicCandidates.ts` → `selectTopicCandidates(profile, { limit = 800 })`
- Reads `linger_events` + `deep_dive_events` (each carries `video_id`,
  `time_spent`, `_month`).
- Weight per event: **deep-dive = `time_spent` (1.0×); linger = `time_spent × 0.5`;
  graveyard/sandbox excluded.** Aggregate by `video_id` (sum on recurrence).
- **Month-proportional sampling:** distribute the 800-slot budget across months in
  proportion to each month's candidate count; take top-weighted within each month.
  Ties broken by `video_id` (stable-tie discipline from the echo work).
- Output: sorted `{ video_id, weight }[]`. Pure, deterministic, no network.

### `engine/keywordClusters.ts` → `keywordClusters(profile)` (fallback)
- Reads `interest_clusters` (`{ term, count }[]`).
- Maps each term via `pillarCategories.ts` `categorize`, groups by category, emits
  one `TopicCluster` per category: `name` from `CATEGORY_PHRASES`,
  `evidence_kind: "term"`, `video_ids: []`, `confidence: 0.4`, `taxonomy_hint: null`
  (the category→taxonomy mapping is WP-2.2's job, which owns the taxonomy file).
- Fully deterministic.

### Constants (approved)
- Linger weight `0.5×` (vs deep-dive `1.0×`).
- Candidate cap `N = 800`.

## 6. Server: `/api/topics`, LLM, validation, caching

### `utils/topic_engine.py` → `cluster_topics(videos, api_key, provider, prompt_version)`
1. Dedup `video_id`s, cap at 800.
2. **Cache check** — Redis key `topics:{prompt_version}:{sha256(sorted video_id+weight pairs)}`.
   Hit → return with `cached: true`, no LLM call. Reuses `creator_map`'s Redis
   client + in-memory fallback pattern.
3. **Titles** — `oembed.fetch_many(video_ids)` (per-video cached); drop misses;
   pair each title with its weight.
4. **LLM call** — user's key, provider-abstracted like `generate_pillars_llm`.
   Structured-output prompt: weighted titles + ad-taxonomy category names →
   `{ clusters: [{ name, video_ids, taxonomy_hint }] }`.
5. **Validate** — names non-empty; every `video_id` ∈ input (drop hallucinations);
   `taxonomy_hint` is `string|null`. Invalid JSON/schema → one retry, then raise.
6. Attach `confidence` (LLM path: fixed **0.7**; a title-coverage-derived value is
   a possible future refinement, not this spec), `source: "llm"`, `usage` from the
   response. Cache the validated result (long TTL). Return.

### `POST /api/topics` (mirrors `/api/pillars`)
- `api_key` + `provider` as query params; `{ videos: [{video_id, weight}] }` in the
  body; `prompt_version` is a server constant.
- Caps to 800, calls `cluster_topics`, logs token usage into `_metrics`, returns
  `TopicResult`.
- A bad key / quota / provider error surfaces as **HTTP 502 with a clear detail**
  so the client can show it and offer the keyword fallback.

### Cost-ceiling reinterpretation (deliberate divergence from the written AC)
The plan says "cost per dossier under a configurable ceiling." Because we landed on
**BYOK (the user pays)**, there is no dollar ceiling to enforce. This AC is
reinterpreted as: the **N≤800 title cap bounds token spend**, and we **log
per-call token usage** (a metric) for observability. No hard `$` guard, no billing
infra.

## 7. Error handling / degradation

- **No key** → client runs `keywordClusters` locally (the default, not an error).
- **LLM fails** (bad key, quota, provider down) → `/api/topics` returns 502 + clear
  detail; the client surfaces it and falls back to keyword clusters (lower-confidence).
- **Schema-invalid LLM output** → one retry in `topic_engine`, then 502.
- **Partial oEmbed misses** → cluster whatever resolved; **zero titles resolved** →
  empty clusters with a reason, not a crash.
- **Hallucinated `video_id`s** → dropped by the traceability validation.
- **Too little watch data** → if `selectTopicCandidates` yields **fewer than 20
  videos**, return `[]` (not enough watched content to cluster meaningfully) rather
  than clustering noise.
- **Redis down** → in-memory fallback (same as `creator_map`).

## 8. Testing (maps every AC)

### Deterministic engine (TS, no LLM, fixtures)
- `topicCandidates`: deep-dive 1.0 vs linger 0.5 weighting; graveyard/sandbox
  excluded; per-video dedup; month-proportional cap; stable tie-break.
- `keywordClusters`: term→category grouping; stable output; shape.

### Server (Python, mocked oEmbed + mocked LLM)
- **(AC)** 3 fixture dossiers → schema-valid clusters.
- **(AC)** cache-hit on re-run → no second LLM call, `cached: true`.
- **(AC)** traceability → an injected hallucinated ID is dropped; every output ID ∈ input.
- **(AC)** usage/token metric increments.
- Retry-then-502 path; claude/gemini provider smoke.

### Fallback determinism
- `keywordClusters` same input → same output (no nondeterminism).

## 9. Explicitly out of scope (YAGNI / later WPs)

- Validating `taxonomy_hint` against the file and the "uncategorized interest"
  bucket → WP-2.2.
- Building `Claim`s / the Targeting Card UI → WP-2.2.
- Per-month temporal re-clustering (plan §3c) → later.
- Server-paid LLM, dollar cost ceiling, rate limiting, abuse protection →
  excluded by the BYOK decision.
- A dedicated "Topic Map" dashboard view → not this spec.

## 10. Open risks

- **Taxonomy prompt size:** ~716 category names in the prompt is a few K tokens per
  call. Acceptable for BYOK; revisit if it dominates cost.
- **LLM nondeterminism vs cache:** the cache stores the first result for a given
  input hash, so re-runs are stable, but two different users with identical inputs
  share a cached labeling. Acceptable (content-hash keyed, not user-keyed).
- **Fallback signal mismatch:** the keyword path clusters declared/searched text,
  not watched titles — a genuinely weaker signal, honestly marked lower-confidence.
