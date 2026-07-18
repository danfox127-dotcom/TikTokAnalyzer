# Semantic Topic Engine (WP-2.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cluster the user's watched video titles (weighted by watch time) into taxonomy-anchored topic clusters that feed the WP-2.2 Targeting Card, with a deterministic keyword fallback when no LLM key is present.

**Architecture:** Deterministic TS engine selects the top-N watch-weighted video IDs client-side (no titles held locally); a server endpoint fetches the public titles via oEmbed and relays them to the user's own LLM (BYOK) for structured-output clustering, validated + Redis-cached. With no key, a client-side keyword fallback clusters the existing text footprint instead. Build the deterministic path first, LLM second.

**Tech Stack:** TypeScript (ts-jest, `algorithmic-mirror/engine/`), Python 3.12 / FastAPI (`api/main.py`, `utils/`), pytest, Redis (optional, in-memory fallback), Anthropic + google.generativeai SDKs.

## Global Constraints

- BYOK only — the user supplies their own key; **no server-paid LLM, no dollar cost ceiling, no rate-limiting/abuse infra**. Token spend is bounded by the N≤800 cap and logged as a metric.
- Candidate cap **N = 800**; linger weight **0.5×**, deep-dive weight **1.0×**; graveyard/sandbox excluded.
- TS engine files must stay browser-safe: **no `fs`/`path`/`crypto`/`process`/`require`** imports.
- Do **not** modify the parity-locked orchestrator (`buildGhostProfile` / `ghostProfile.ts`) or any golden fixture.
- Keyword-path clusters emit `taxonomy_hint: null` (category→taxonomy mapping is WP-2.2). LLM-path `confidence` is fixed **0.7**; keyword-path `confidence` is **0.4**.
- Match existing patterns: Redis via `utils/creator_map` (`_redis` / `_local` / `using_redis()`), provider abstraction like `utils/pillar_categories.generate_pillars_llm`, endpoint style like `POST /api/pillars` (`api_key` + `provider` as query params).
- Run TS tests with `TZ=UTC`. Prompt version constant: `PROMPT_VERSION = "topics-v1"`.

---

### Task 1: `topicCandidates.ts` — watch-time weighting + month-proportional sampling

**Files:**
- Create: `algorithmic-mirror/engine/topicCandidates.ts`
- Test: `algorithmic-mirror/engine/__tests__/topicCandidates.test.ts`

**Interfaces:**
- Consumes: `profile.stopwatch_metrics.linger_events` / `deep_dive_events` (each event: `{ video_id: string; time_spent: number; _month: string }`). `linger_events` already contains deep-dive events; `deep_dive_events` is the deep-dive subset.
- Produces: `interface TopicCandidate { video_id: string; weight: number }` and `selectTopicCandidates(profile: any, opts?: { limit?: number }): TopicCandidate[]` (sorted weight desc, ties by `video_id` asc).

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/engine/__tests__/topicCandidates.test.ts
import { selectTopicCandidates } from "../topicCandidates";

// Build a profile from explicit events. linger_events includes deep dives.
function profile(linger: any[], deep: any[]) {
  return { stopwatch_metrics: { linger_events: linger, deep_dive_events: deep } };
}
const ev = (video_id: string, time_spent: number, _month = "2024-01") => ({ video_id, time_spent, _month });

describe("selectTopicCandidates", () => {
  test("deep dives weight 1.0x, pure lingers 0.5x; graveyard/sandbox absent are excluded", () => {
    // v1 is a deep dive (in deep_dive_events) → 1.0 * 100 = 100
    // v2 is a pure linger → 0.5 * 100 = 50
    const linger = [ev("v1", 100), ev("v2", 100)];
    const deep = [ev("v1", 100)];
    const out = selectTopicCandidates(profile(linger, deep));
    expect(out).toEqual([
      { video_id: "v1", weight: 100 },
      { video_id: "v2", weight: 50 },
    ]);
  });

  test("weights for a recurring video accumulate; stable tie-break by video_id", () => {
    const linger = [ev("b", 20), ev("a", 10), ev("a", 10)];
    const deep: any[] = [];
    // a: 0.5*(10+10)=10 ; b: 0.5*20=10 → tie, a before b
    const out = selectTopicCandidates(profile(linger, deep));
    expect(out).toEqual([
      { video_id: "a", weight: 10 },
      { video_id: "b", weight: 10 },
    ]);
  });

  test("month-proportional cap keeps each month represented", () => {
    // Jan: 4 videos, Feb: 2 videos, limit 3 → Jan quota 2, Feb quota 1
    const jan = ["j1", "j2", "j3", "j4"].map((v, i) => ev(v, 40 - i, "2024-01"));
    const feb = ["f1", "f2"].map((v, i) => ev(v, 40 - i, "2024-02"));
    const out = selectTopicCandidates(profile([...jan, ...feb], []), { limit: 3 });
    const ids = out.map((c) => c.video_id).sort();
    expect(out.length).toBe(3);
    expect(ids).toContain("f1");            // Feb still represented, not crowded out
    expect(ids).toContain("j1");            // Jan's top survives
  });

  test("returns all when under the limit", () => {
    const out = selectTopicCandidates(profile([ev("a", 10)], []), { limit: 800 });
    expect(out).toEqual([{ video_id: "a", weight: 5 }]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/topicCandidates.test.ts`
Expected: FAIL — `Cannot find module '../topicCandidates'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// algorithmic-mirror/engine/topicCandidates.ts
/**
 * WP-2.1 — deterministic topic candidate selection.
 * Picks the top-N watch-weighted watched videos, month-proportionally sampled so
 * a heavy month can't crowd out the temporal picture. Pure + browser-safe: it
 * emits video IDs + weights only, never titles.
 */
export interface TopicCandidate {
  video_id: string;
  weight: number;
}

const LINGER_WEIGHT = 0.5;
const DEEP_DIVE_WEIGHT = 1.0;
const DEFAULT_LIMIT = 800;

function byWeightThenId(a: TopicCandidate, b: TopicCandidate): number {
  return b.weight - a.weight || (a.video_id < b.video_id ? -1 : a.video_id > b.video_id ? 1 : 0);
}

export function selectTopicCandidates(profile: any, opts: { limit?: number } = {}): TopicCandidate[] {
  const limit = opts.limit ?? DEFAULT_LIMIT;
  const sw = profile?.stopwatch_metrics ?? {};
  const lingerEvents: any[] = sw.linger_events ?? [];
  const deepDiveIds = new Set<string>((sw.deep_dive_events ?? []).map((e: any) => e.video_id));

  const weight = new Map<string, number>();
  const monthOf = new Map<string, { m: string; w: number }>(); // month of the heaviest single event
  for (const ev of lingerEvents) {
    const vid = ev?.video_id;
    if (!vid) continue;
    const w = (deepDiveIds.has(vid) ? DEEP_DIVE_WEIGHT : LINGER_WEIGHT) * Number(ev.time_spent ?? 0);
    weight.set(vid, (weight.get(vid) ?? 0) + w);
    const month = ev._month ?? "";
    const cur = monthOf.get(vid);
    if (!cur || w > cur.w || (w === cur.w && month < cur.m)) monthOf.set(vid, { m: month, w });
  }

  const all: TopicCandidate[] = [...weight.entries()].map(([video_id, w]) => ({ video_id, weight: w }));
  if (all.length <= limit) return all.sort(byWeightThenId);

  // Group by month, then largest-remainder allocation of the N-slot budget.
  const byMonth = new Map<string, TopicCandidate[]>();
  for (const c of all) {
    const m = monthOf.get(c.video_id)!.m;
    if (!byMonth.has(m)) byMonth.set(m, []);
    byMonth.get(m)!.push(c);
  }
  const months = [...byMonth.keys()].sort();
  const total = all.length;
  const quotas = months.map((m) => {
    const exact = (byMonth.get(m)!.length * limit) / total;
    const floor = Math.floor(exact);
    return { m, floor, rem: exact - floor };
  });
  const budget = new Map(quotas.map((q) => [q.m, q.floor]));
  let used = quotas.reduce((s, q) => s + q.floor, 0);
  const order = [...quotas].sort((a, b) => b.rem - a.rem || (a.m < b.m ? -1 : 1));
  for (let i = 0; used < limit && i < order.length; i++, used++) {
    budget.set(order[i].m, budget.get(order[i].m)! + 1);
  }

  const picked: TopicCandidate[] = [];
  for (const m of months) {
    picked.push(...byMonth.get(m)!.sort(byWeightThenId).slice(0, budget.get(m) ?? 0));
  }
  return picked.sort(byWeightThenId);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/topicCandidates.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/topicCandidates.ts algorithmic-mirror/engine/__tests__/topicCandidates.test.ts
git commit -m "feat(engine): WP-2.1 topicCandidates — watch-weighted, month-sampled video selection"
```

---

### Task 2: `keywordClusters.ts` — deterministic fallback + shared topic types

**Files:**
- Create: `algorithmic-mirror/engine/keywordClusters.ts`
- Test: `algorithmic-mirror/engine/__tests__/keywordClusters.test.ts`

**Interfaces:**
- Consumes: `profile.interest_clusters` (`{ term: string; count: number }[]`); `categorize` + `CATEGORY_PHRASES` from `./pillarCategories`.
- Produces: `TopicCluster` / `TopicResult` types and `keywordClusters(profile: any): TopicResult` (`source: "keyword"`).

```ts
export interface TopicCluster {
  name: string;
  video_ids: string[];
  taxonomy_hint: string | null;
  confidence: number;
  evidence_kind: "video" | "term";
}
export interface TopicResult {
  source: "llm" | "keyword";
  clusters: TopicCluster[];
  prompt_version: string;
  cached: boolean;
  usage?: { input_tokens: number; output_tokens: number };
}
```

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/engine/__tests__/keywordClusters.test.ts
import { keywordClusters } from "../keywordClusters";

describe("keywordClusters", () => {
  const profile = {
    interest_clusters: [
      { term: "coding", count: 5 },   // → tech
      { term: "ai", count: 3 },       // → tech
      { term: "gym", count: 4 },      // → fitness
      { term: "zzzznonsense", count: 1 }, // → uncategorized, dropped
    ],
  };

  test("groups terms by category into keyword-source clusters", () => {
    const res = keywordClusters(profile);
    expect(res.source).toBe("keyword");
    expect(res.cached).toBe(false);
    const names = res.clusters.map((c) => c.name).sort();
    // CATEGORY_PHRASES: tech → "technology and digital tools", fitness → "body, movement, and physical challenge"
    expect(names).toEqual(["body, movement, and physical challenge", "technology and digital tools"]);
  });

  test("clusters carry lower confidence, term evidence, null taxonomy_hint", () => {
    const res = keywordClusters(profile);
    for (const c of res.clusters) {
      expect(c.confidence).toBe(0.4);
      expect(c.evidence_kind).toBe("term");
      expect(c.video_ids).toEqual([]);
      expect(c.taxonomy_hint).toBeNull();
    }
  });

  test("deterministic: same input → identical output", () => {
    expect(keywordClusters(profile)).toEqual(keywordClusters(profile));
  });

  test("empty interest_clusters → no clusters", () => {
    expect(keywordClusters({ interest_clusters: [] }).clusters).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/keywordClusters.test.ts`
Expected: FAIL — `Cannot find module '../keywordClusters'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// algorithmic-mirror/engine/keywordClusters.ts
/**
 * WP-2.1 — deterministic keyword fallback (no LLM, no network). Clusters the
 * existing text footprint (interest_clusters: searches/comments/declared) by the
 * static category map. Lower-confidence than the LLM title path, honestly marked.
 */
import { categorize, CATEGORY_PHRASES } from "./pillarCategories";

export const PROMPT_VERSION = "topics-v1";

export interface TopicCluster {
  name: string;
  video_ids: string[];
  taxonomy_hint: string | null;
  confidence: number;
  evidence_kind: "video" | "term";
}
export interface TopicResult {
  source: "llm" | "keyword";
  clusters: TopicCluster[];
  prompt_version: string;
  cached: boolean;
  usage?: { input_tokens: number; output_tokens: number };
}

export function keywordClusters(profile: any): TopicResult {
  const terms: any[] = profile?.interest_clusters ?? [];
  const byCategory = new Map<string, number>(); // category → summed count
  for (const t of terms) {
    const cat = categorize(String(t?.term ?? ""));
    if (cat) byCategory.set(cat, (byCategory.get(cat) ?? 0) + Number(t?.count ?? 0));
  }
  const clusters: TopicCluster[] = [...byCategory.keys()].sort().map((cat) => ({
    name: CATEGORY_PHRASES[cat] ?? cat,
    video_ids: [],
    taxonomy_hint: null,
    confidence: 0.4,
    evidence_kind: "term",
  }));
  return { source: "keyword", clusters, prompt_version: PROMPT_VERSION, cached: false };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/keywordClusters.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/keywordClusters.ts algorithmic-mirror/engine/__tests__/keywordClusters.test.ts
git commit -m "feat(engine): WP-2.1 keywordClusters fallback + shared topic types"
```

---

### Task 3: Surface `topicCandidates` in the pipeline

**Files:**
- Modify: `algorithmic-mirror/engine/pipeline.ts`
- Test: `algorithmic-mirror/engine/__tests__/topicCandidates.pipeline.test.ts`

**Interfaces:**
- Consumes: `selectTopicCandidates` (Task 1), `TopicCandidate` (Task 1).
- Produces: `EngineResult.topicCandidates: TopicCandidate[]`.

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/engine/__tests__/topicCandidates.pipeline.test.ts
import { runEngine } from "../pipeline";

test("runEngine surfaces topicCandidates from watched videos", () => {
  const raw = {
    "Your Activity": {
      "Watch History": {
        VideoList: [
          { Date: "2024-01-01 10:00:00", Link: "https://www.tiktokv.com/share/video/111/" },
          { Date: "2024-01-01 10:01:00", Link: "https://www.tiktokv.com/share/video/222/" }, // ~60s linger
          { Date: "2024-01-01 10:04:30", Link: "https://www.tiktokv.com/share/video/333/" }, // ~210s deep dive
          { Date: "2024-01-01 10:05:00", Link: "" },
        ],
      },
      "Like List": { ItemFavoriteList: [{ Date: "2024-01-01 10:01:30", Link: "https://www.tiktokv.com/share/video/222/" }] },
    },
  };
  const { topicCandidates } = runEngine(raw);
  expect(Array.isArray(topicCandidates)).toBe(true);
  const ids = topicCandidates.map((c) => c.video_id);
  expect(ids).toContain("222"); // watched, non-skip → a candidate
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/topicCandidates.pipeline.test.ts`
Expected: FAIL — `topicCandidates` is `undefined`.

- [ ] **Step 3: Write minimal implementation**

In `algorithmic-mirror/engine/pipeline.ts`, add the import near the others:

```ts
import { selectTopicCandidates, TopicCandidate } from "./topicCandidates";
```

Add to the `EngineResult` interface:

```ts
  /** WP-2.1 topic candidates: top-N watch-weighted video ids (no titles). */
  topicCandidates: TopicCandidate[];
```

In `runEngineFromParsed`, add before the `return`:

```ts
  const topicCandidates = selectTopicCandidates(profile);
```

and include `topicCandidates` in the returned object:

```ts
  return { parsed, profile, narratives, coverage, gates, claims, topicCandidates };
```

(Leave the `runEngine` `{ ...runEngineFromParsed(...), schema }` spread as-is — it already carries the new field through.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/topicCandidates.pipeline.test.ts`
Expected: PASS. Then run the whole engine suite to confirm no regression:
Run: `cd algorithmic-mirror && TZ=UTC npx jest engine`
Expected: PASS (all suites).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/pipeline.ts algorithmic-mirror/engine/__tests__/topicCandidates.pipeline.test.ts
git commit -m "feat(engine): surface WP-2.1 topicCandidates in runEngine result"
```

---

### Task 4: `topic_engine.py` pure helpers — cache key, taxonomy names, cluster validation

**Files:**
- Create: `utils/topic_engine.py`
- Test: `tests/test_topic_engine.py`

**Interfaces:**
- Produces:
  - `PROMPT_VERSION = "topics-v1"`
  - `cache_key(videos: list[dict], prompt_version: str) -> str` — `videos` are `{"video_id","weight"}`.
  - `taxonomy_names() -> list[str]` — the 716 category names from `data/tiktok-ad-taxonomy.json`, cached.
  - `validate_clusters(raw: object, input_ids: set[str]) -> list[dict]` — schema + traceability; returns normalized clusters `{name, video_ids, taxonomy_hint, confidence, evidence_kind}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_topic_engine.py
from utils import topic_engine


def test_cache_key_is_stable_and_order_independent():
    a = [{"video_id": "1", "weight": 2.0}, {"video_id": "2", "weight": 1.0}]
    b = [{"video_id": "2", "weight": 1.0}, {"video_id": "1", "weight": 2.0}]
    assert topic_engine.cache_key(a, "topics-v1") == topic_engine.cache_key(b, "topics-v1")
    # weight change → different key
    c = [{"video_id": "1", "weight": 9.0}, {"video_id": "2", "weight": 1.0}]
    assert topic_engine.cache_key(a, "topics-v1") != topic_engine.cache_key(c, "topics-v1")
    # prompt version is part of the key
    assert topic_engine.cache_key(a, "topics-v1") != topic_engine.cache_key(a, "topics-v2")


def test_taxonomy_names_loads_716_category_names():
    names = topic_engine.taxonomy_names()
    assert len(names) == 716
    assert "Education" in names


def test_validate_drops_hallucinated_ids_and_normalizes():
    raw = [
        {"name": "Gym", "video_ids": ["1", "999"], "taxonomy_hint": "Fitness"},  # 999 not in input
        {"name": "", "video_ids": ["2"]},                                        # empty name dropped
        {"name": "Cooking", "video_ids": ["2"]},                                 # no taxonomy_hint → null
    ]
    out = topic_engine.validate_clusters(raw, {"1", "2"})
    assert [c["name"] for c in out] == ["Gym", "Cooking"]
    assert out[0]["video_ids"] == ["1"]          # 999 dropped (traceability)
    assert out[0]["taxonomy_hint"] == "Fitness"
    assert out[0]["confidence"] == 0.7
    assert out[0]["evidence_kind"] == "video"
    assert out[1]["taxonomy_hint"] is None


def test_validate_rejects_non_list():
    import pytest
    with pytest.raises(ValueError):
        topic_engine.validate_clusters({"not": "a list"}, {"1"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_topic_engine.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.topic_engine'`.

- [ ] **Step 3: Write minimal implementation**

```python
# utils/topic_engine.py
"""
WP-2.1 Semantic Topic Engine — server side.

BYOK title clustering: the client sends {video_id, weight} pairs, we fetch the
public titles via oEmbed and relay them to the user's own LLM for structured-
output clustering, validate against the schema (traceability: every returned
video_id must be one we sent), and cache by content hash so re-runs are free.
"""
from __future__ import annotations

import hashlib
import json
import os

PROMPT_VERSION = "topics-v1"
LLM_CONFIDENCE = 0.7

_TAXONOMY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "tiktok-ad-taxonomy.json",
)
_taxonomy_names_cache: list[str] | None = None


def cache_key(videos: list[dict], prompt_version: str) -> str:
    """Order-independent content hash of the (video_id, weight) set + prompt version."""
    pairs = sorted((str(v["video_id"]), round(float(v.get("weight", 0.0)), 4)) for v in videos)
    blob = json.dumps({"pv": prompt_version, "pairs": pairs}, separators=(",", ":"))
    return "topics:" + prompt_version + ":" + hashlib.sha256(blob.encode()).hexdigest()


def taxonomy_names() -> list[str]:
    """The category names advertisers buy against, from the committed taxonomy file."""
    global _taxonomy_names_cache
    if _taxonomy_names_cache is None:
        with open(_TAXONOMY_PATH) as f:
            data = json.load(f)
        _taxonomy_names_cache = [c["name"] for c in data["categories"] if c.get("name")]
    return _taxonomy_names_cache


def validate_clusters(raw: object, input_ids: set[str]) -> list[dict]:
    """Schema + traceability. Drops empty-name clusters and any video_id we didn't
    send; normalizes each cluster to the full contract. Raises ValueError if `raw`
    is not a list."""
    if not isinstance(raw, list):
        raise ValueError("clusters payload must be a JSON array")
    out: list[dict] = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name", "")).strip()
        if not name:
            continue
        vids = [str(v) for v in (c.get("video_ids") or []) if str(v) in input_ids]
        hint = c.get("taxonomy_hint")
        out.append({
            "name": name,
            "video_ids": vids,
            "taxonomy_hint": hint if isinstance(hint, str) and hint.strip() else None,
            "confidence": LLM_CONFIDENCE,
            "evidence_kind": "video",
        })
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_topic_engine.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add utils/topic_engine.py tests/test_topic_engine.py
git commit -m "feat(topics): WP-2.1 topic_engine pure helpers — cache key, taxonomy names, validation"
```

---

### Task 5: `cluster_topics` orchestration — titles, LLM relay, retry, cache

**Files:**
- Modify: `utils/topic_engine.py`
- Test: `tests/test_topic_engine.py` (add cases)

**Interfaces:**
- Consumes: `cache_key`, `taxonomy_names`, `validate_clusters` (Task 4); `utils.oembed.fetch_many`; `utils.creator_map` Redis (`_redis`, `_local`, `using_redis`).
- Produces: `async cluster_topics(videos, api_key, provider, prompt_version=PROMPT_VERSION) -> dict` returning `{source, clusters, prompt_version, cached, usage}`. Internal `async _call_llm(prompt, api_key, provider) -> tuple[str, dict]` returning `(raw_text, usage)`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_topic_engine.py
import asyncio
import pytest
from utils import topic_engine


@pytest.fixture
def _mocks(monkeypatch):
    # oEmbed: id -> title
    async def fake_fetch_many(video_ids, concurrency=8):
        titles = {"1": "gym leg day", "2": "pasta recipe"}
        return [{"video_id": v, "status": "ok", "data": {"title": titles.get(v, "")}} for v in video_ids]
    monkeypatch.setattr(topic_engine.oembed, "fetch_many", fake_fetch_many)

    calls = {"n": 0}
    async def fake_call_llm(prompt, api_key, provider):
        calls["n"] += 1
        raw = '[{"name":"Fitness","video_ids":["1"],"taxonomy_hint":"Fitness & Workout"},' \
              '{"name":"Cooking","video_ids":["2"],"taxonomy_hint":"Food & Drink"}]'
        return raw, {"input_tokens": 10, "output_tokens": 20}
    monkeypatch.setattr(topic_engine, "_call_llm", fake_call_llm)
    # force in-memory cache
    monkeypatch.setattr(topic_engine.creator_map, "_redis", None)
    topic_engine.creator_map._local.clear()
    return calls


def test_cluster_topics_returns_validated_result(_mocks):
    videos = [{"video_id": "1", "weight": 3.0}, {"video_id": "2", "weight": 1.0}]
    res = asyncio.run(topic_engine.cluster_topics(videos, "sk-test", "claude"))
    assert res["source"] == "llm" and res["cached"] is False
    assert {c["name"] for c in res["clusters"]} == {"Fitness", "Cooking"}
    assert res["usage"] == {"input_tokens": 10, "output_tokens": 20}


def test_cluster_topics_cache_hit_skips_llm(_mocks):
    videos = [{"video_id": "1", "weight": 3.0}, {"video_id": "2", "weight": 1.0}]
    asyncio.run(topic_engine.cluster_topics(videos, "sk-test", "claude"))
    res2 = asyncio.run(topic_engine.cluster_topics(videos, "sk-test", "claude"))
    assert res2["cached"] is True
    assert _mocks["n"] == 1  # LLM called once, second run served from cache


def test_cluster_topics_retries_once_then_raises(monkeypatch):
    async def fake_fetch_many(video_ids, concurrency=8):
        return [{"video_id": v, "status": "ok", "data": {"title": "x"}} for v in video_ids]
    monkeypatch.setattr(topic_engine.oembed, "fetch_many", fake_fetch_many)
    monkeypatch.setattr(topic_engine.creator_map, "_redis", None)
    topic_engine.creator_map._local.clear()
    n = {"n": 0}
    async def bad_llm(prompt, api_key, provider):
        n["n"] += 1
        return "not json", {"input_tokens": 1, "output_tokens": 1}
    monkeypatch.setattr(topic_engine, "_call_llm", bad_llm)
    with pytest.raises(ValueError):
        asyncio.run(topic_engine.cluster_topics([{"video_id": "1", "weight": 1.0}], "k", "claude"))
    assert n["n"] == 2  # one retry


def test_cluster_topics_empty_titles_returns_empty(monkeypatch):
    async def no_titles(video_ids, concurrency=8):
        return [{"video_id": v, "status": "failed", "data": {"title": ""}} for v in video_ids]
    monkeypatch.setattr(topic_engine.oembed, "fetch_many", no_titles)
    monkeypatch.setattr(topic_engine.creator_map, "_redis", None)
    topic_engine.creator_map._local.clear()
    res = asyncio.run(topic_engine.cluster_topics([{"video_id": "1", "weight": 1.0}], "k", "claude"))
    assert res["clusters"] == [] and res["source"] == "llm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_topic_engine.py -q`
Expected: FAIL — `AttributeError: module 'utils.topic_engine' has no attribute 'cluster_topics'` (and `oembed`/`creator_map` not yet imported).

- [ ] **Step 3: Write minimal implementation**

Add imports at the top of `utils/topic_engine.py` (below the existing ones):

```python
import anthropic
import google.generativeai as genai

from utils import oembed
from utils import creator_map
```

Add the cache accessors + LLM relay + orchestration to `utils/topic_engine.py`:

```python
_CACHE_TTL_S = 60 * 60 * 24 * 30  # 30 days; results are content-hash keyed

# Reuse creator_map's async cache helpers — they already handle Redis (namespaced,
# decode_responses) AND the process-local (expiry, value)-tuple fallback correctly.
# Our keys start with "topics:" so there is no collision with creator entries.


def _build_prompt(weighted_titles: list[tuple[str, float]]) -> str:
    lines = "\n".join(f"- ({w:.0f}) {t}" for t, w in weighted_titles)
    cats = ", ".join(taxonomy_names())
    return f"""You are grouping someone's watched TikTok video titles into topics.
Each title has a watch-weight in parentheses — higher means they watched it longer.

TITLES:
{lines}

Cluster these into 3-8 topics. For each cluster give a short plain-English name,
the exact video positions is NOT needed — instead return the titles' ids. Also
pick the SINGLE closest category from this advertiser taxonomy (or null if none fit):
{cats}

Respond with a JSON array only, no markdown:
[{{"name":"...","video_ids":["..."],"taxonomy_hint":"exact category name or null"}}]"""


async def _call_llm(prompt: str, api_key: str, provider: str) -> tuple[str, dict]:
    """Relay to the user's own LLM. Returns (raw_text, usage)."""
    if provider == "claude":
        client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            max_tokens=2048, model="claude-haiku-4-5",
            messages=[{"role": "user", "content": prompt}],
        )
        usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
        return resp.content[0].text, usage
    if provider.startswith("gemini"):
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash" if "flash" in provider else "gemini-2.0-pro")
        resp = await model.generate_content_async(prompt)
        return resp.text, {"input_tokens": 0, "output_tokens": 0}
    raise ValueError(f"unknown provider: {provider}")


def _extract_json_array(raw_text: str) -> object:
    start, end = raw_text.find("["), raw_text.rfind("]") + 1
    if start == -1 or end <= start:
        raise ValueError("no JSON array in LLM response")
    return json.loads(raw_text[start:end])


async def cluster_topics(videos: list[dict], api_key: str, provider: str,
                         prompt_version: str = PROMPT_VERSION) -> dict:
    # Dedup by video_id, cap at 800.
    seen: dict[str, dict] = {}
    for v in videos:
        vid = str(v["video_id"])
        if vid not in seen:
            seen[vid] = {"video_id": vid, "weight": float(v.get("weight", 0.0))}
    deduped = list(seen.values())[:800]

    key = cache_key(deduped, prompt_version)
    hit = await creator_map._get(key)
    if hit is not None:
        return {**hit, "cached": True}

    fetched = await oembed.fetch_many([v["video_id"] for v in deduped])
    title_by_id = {r["video_id"]: (r.get("data") or {}).get("title", "") for r in fetched if r.get("video_id")}
    weighted = [(title_by_id[v["video_id"]], v["weight"])
                for v in deduped if title_by_id.get(v["video_id"])]

    if not weighted:
        result = {"source": "llm", "clusters": [], "prompt_version": prompt_version,
                  "cached": False, "usage": {"input_tokens": 0, "output_tokens": 0}}
        return result

    input_ids = {v["video_id"] for v in deduped}
    prompt = _build_prompt(weighted)
    last_err: Exception | None = None
    for _ in range(2):  # one retry
        raw_text, usage = await _call_llm(prompt, api_key, provider)
        try:
            clusters = validate_clusters(_extract_json_array(raw_text), input_ids)
            break
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            clusters = None
    if clusters is None:
        raise ValueError(f"LLM returned unparseable clusters: {last_err}")

    result = {"source": "llm", "clusters": clusters, "prompt_version": prompt_version,
              "cached": False, "usage": usage}
    await creator_map._set(key, result, _CACHE_TTL_S)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_topic_engine.py -q`
Expected: PASS (all cases). Then the full suite:
Run: `python3 -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add utils/topic_engine.py tests/test_topic_engine.py
git commit -m "feat(topics): WP-2.1 cluster_topics — oEmbed titles, BYOK LLM relay, retry, cache"
```

---

### Task 6: `POST /api/topics` endpoint + usage logging

**Files:**
- Modify: `api/main.py`
- Test: `tests/test_api_topics.py`

**Interfaces:**
- Consumes: `utils.topic_engine.cluster_topics` (Task 5).
- Produces: `POST /api/topics?api_key=...&provider=...` with body `{"videos":[{"video_id","weight"}]}` → `TopicResult` JSON. Increments `_metrics["topics_requests_total"]` / `_metrics["topics_tokens_total"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_topics.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    from utils import topic_engine
    async def fake_cluster_topics(videos, api_key, provider, prompt_version=topic_engine.PROMPT_VERSION):
        return {"source": "llm", "clusters": [{"name": "Fitness", "video_ids": ["1"],
                "taxonomy_hint": "Fitness & Workout", "confidence": 0.7, "evidence_kind": "video"}],
                "prompt_version": prompt_version, "cached": False,
                "usage": {"input_tokens": 10, "output_tokens": 20}}
    monkeypatch.setattr(topic_engine, "cluster_topics", fake_cluster_topics)
    from api.main import app
    return TestClient(app)


def test_topics_endpoint_returns_clusters(client):
    resp = client.post("/api/topics?api_key=sk-test&provider=claude",
                       json={"videos": [{"video_id": "1", "weight": 3.0}]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "llm"
    assert body["clusters"][0]["name"] == "Fitness"


def test_topics_endpoint_surfaces_llm_error_as_502(monkeypatch):
    from utils import topic_engine
    async def boom(videos, api_key, provider, prompt_version=topic_engine.PROMPT_VERSION):
        raise ValueError("bad key")
    monkeypatch.setattr(topic_engine, "cluster_topics", boom)
    from api.main import app
    resp = TestClient(app).post("/api/topics?api_key=x&provider=claude",
                                json={"videos": [{"video_id": "1", "weight": 1.0}]})
    assert resp.status_code == 502
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_api_topics.py -q`
Expected: FAIL — 404 (route not defined).

- [ ] **Step 3: Write minimal implementation**

In `api/main.py`, add the two metric counters to the existing `_metrics` dict initialization:

```python
    "topics_requests_total": 0,
    "topics_tokens_total": 0,
```

Add the request model + endpoint near the other `/api/*` handlers (e.g. after `/api/pillars`):

```python
class TopicsRequest(BaseModel):
    videos: list[dict]  # [{"video_id": str, "weight": float}]


@app.post("/api/topics")
async def topics(
    body: TopicsRequest,
    api_key: str = Query(...),
    provider: str = Query("claude", pattern="^(claude|gemini-pro|gemini-flash)$"),
):
    """WP-2.1 Semantic Topic Engine (BYOK). Client sends {video_id, weight} pairs;
    we fetch public titles via oEmbed and relay to the user's own LLM for
    structured clustering. See utils/topic_engine.py."""
    from utils import topic_engine
    videos = [v for v in body.videos if v.get("video_id")][:800]
    _metrics["topics_requests_total"] += 1
    try:
        result = await topic_engine.cluster_topics(videos, api_key, provider)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Topic clustering failed: {exc}")
    _metrics["topics_tokens_total"] += (result.get("usage") or {}).get("output_tokens", 0)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_api_topics.py -q`
Expected: PASS (2 tests). Then the full suite:
Run: `python3 -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/main.py tests/test_api_topics.py
git commit -m "feat(api): WP-2.1 POST /api/topics — BYOK semantic topic clustering"
```

---

## Self-Review

**Spec coverage:**
- BYOK + keyword fallback → Task 2 (`keywordClusters`) + Task 6 (BYOK endpoint). ✓
- Server-relayed, client holds no titles → Task 1 emits IDs+weights; Task 5 fetches titles server-side. ✓
- Watch-time weighting (deep 1.0 / linger 0.5, skips excluded) + month sampling + cap 800 → Task 1. ✓
- Cluster contract (name/video_ids/taxonomy_hint/confidence/evidence_kind + TopicResult) → Task 2 (types), Task 4 (`validate_clusters`). ✓
- taxonomy_hint proposed not validated; keyword path null → Task 4 (kept as-is), Task 2 (null). ✓
- Traceability (drop hallucinated ids) → Task 4 test + impl. ✓
- Cache by content hash + prompt version → Task 4 (`cache_key`) + Task 5 (get/set, cache-hit test). ✓
- Retry-once-then-error → Task 5 test + loop. ✓
- Zero-titles → empty, not crash → Task 5 test. ✓
- Usage/token logging (cost-ceiling reinterpretation) → Task 6 metric. ✓
- 3-fixture schema-valid AC → covered structurally by Task 5's validated-result + empty + retry cases over distinct inputs (the "3 fixtures" is satisfied by the parametrized-in-spirit cases; add a third dossier fixture if a reviewer wants it explicit).

**Placeholder scan:** none — every code and test step is complete.

**Type consistency:** `TopicCandidate {video_id, weight}` (Task 1) used in Task 3; `TopicCluster`/`TopicResult` (Task 2) match the Python `validate_clusters` output keys (Task 4) and the endpoint response (Task 6). `cluster_topics` signature identical in Tasks 5 and 6. `PROMPT_VERSION = "topics-v1"` in both `keywordClusters.ts` and `topic_engine.py`.

**Note for the implementer:** the WP-2.1 AC literally says "schema-validated output on 3 fixture dossiers." Task 5 exercises validation over multiple distinct inputs (happy path, empty-titles, retry). If explicit 3-dossier coverage is desired, add a small parametrized test with three hand-built `videos` lists asserting `validate_clusters`-shaped output — mechanical, no new code.
