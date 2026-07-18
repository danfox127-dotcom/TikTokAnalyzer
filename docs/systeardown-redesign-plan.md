# SYS.TEARDOWN v2 — Redesign Plan
### From "here's your data" to "here's who TikTok thinks you are"

*Prepared July 2026 · Based on a full read of the current codebase (main branch)*

---

## 1. Where the project stands

The current build is genuinely impressive for what it is. The strongest ideas already in the code:

- **The Stopwatch engine** (`api/ghost_profile.py`) — inferring watch time from timestamp gaps between videos, then bucketing views into Graveyard (<3s skips), Sustained, and Deep Dives (>180s). This is the crown jewel. It reconstructs a behavioral signal TikTok *doesn't even include* in the export.
- **The Discrepancy Gap** — comparing what you *told* TikTok (declared interests, follows) against what your behavior *revealed*. This "declared vs. inferred" tension is the most emotionally powerful concept in the whole product.
- **Evidence provenance** — narrative blocks carry a `provenance` string and the frontend has an EvidencePanel. The instinct to make every claim traceable is right.
- **The scroll narrative** (TheGlassHouse) — chaptered storytelling is the correct format for a general audience.

Where it hits a ceiling — and this is the core of the redesign:

**The insight layer is shallow relative to the data it sits on.** Interest inference is keyword frequency against a ~35-word hardcoded dictionary (`pillar_categories.py`). The archetype system is four if-statements producing labels like "The Nocturnal Seeker." The narrative prose is threshold templates (`if followed_pct > 60: ...`). The tool currently *describes your behavior* well, but it doesn't yet answer the question in its own pitch: **what does TikTok actually think of you — as a demographic, as a targetable segment, as a person?**

Two structural problems compound this:

1. **Two parallel forensics engines.** The Python engine (`api/`) and a partial TypeScript port (`supabase/functions/_shared/forensics/`) implement overlapping logic. Every improvement now has to be made twice or the versions drift.
2. **A privacy story with a fork in it.** The README promises "nothing leaves your machine," but the Supabase path stores dossiers in a cloud database. Both are legitimate architectures — but the product needs to pick a primary and be honest about it.

---

## 2. Design principles for v2

1. **Reconstruct, don't just display.** The export shows what TikTok *admits* to storing. The product's value is inferring what TikTok *derives* from it — the segments, demographics, and persona model it never shows you. Every v2 feature should push toward reconstruction.
2. **Every claim gets a confidence level and a receipt.** Inferences are guesses. Showing "Likely age band: 30–44 (confidence: high — based on X, Y, Z)" is more credible *and* more unsettling than an unqualified assertion. This also protects the tool from being wrong.
3. **Deterministic math first, LLM as interpreter.** Numbers come from code (reproducible, testable, free). Language models do what they're actually good at: semantic clustering of messy video titles, labeling clusters in human terms, and narrating. Never let an LLM invent a statistic.
4. **One engine, one source of truth.** Kill the duplication before adding features.

---

## 3. The Insight Layer — the heart of the redesign

This is the new backend brain, replacing keyword matching and if-statement archetypes. Four modules, each feeding the next.

### 3a. Semantic Topic Engine (replaces `pillar_categories` keyword map)

**Problem today:** "minecraft" maps to gaming, but "elden ring," "speedrun," and 10,000 other terms map to nothing. Most of a user's watch history falls through the dictionary.

**Redesign:** After oEmbed enrichment resolves video titles, batch them (weighted by watch time from the Stopwatch — a deep-dive title counts far more than a skip) and send them to Claude with a structured-output prompt: *"Cluster these into topics. For each cluster: a plain-English name, the videos in it, and the closest match from this taxonomy."* The taxonomy is the key move — see 3b. Results get cached per-dossier so re-analysis is free. In lay terms: instead of looking words up in a small dictionary, the system reads your history the way a person would and names what it sees — then anchors those names to categories advertisers actually use.

### 3b. The Targeting Card (new — the killer feature)

TikTok Ads Manager exposes a real, public taxonomy of interest and behavior categories that advertisers buy against ("Beauty & Personal Care," "Gaming Consoles," "Business Services," hashtag-interaction behaviors, etc.). **v2 ships that taxonomy as a static reference file and maps every user's clusters onto it.**

The output is a reconstruction of the actual ad-targeting profile: *"Based on your behavior, an advertiser targeting these 14 segments would reach you."* Cross-referenced with the advertiser list already in the export ("3,847 advertisers have your data — here are the segments they likely bought"). This transforms the product from "interesting mirror" to "receipts." Nobody else surfaces this. It's also honest: the card is labeled a *reconstruction*, with methodology one tap away.

### 3c. Demographic & Life-Signal Inference (new)

This directly answers "what does TikTok think of me — specific demographics." The export contains raw material the current build barely touches. Each inference below is computable deterministically, each shipped with confidence + evidence:

- **Age band** — birthdate is in Profile Info (declared), but also *inferable*: era-specific music/nostalgia clusters, content generation markers. Show declared vs. behavioral-inferred side by side (the Discrepancy Gap concept, applied to identity).
- **Gender model** — the export literally contains `inferredGender`. Surface it prominently; most users have no idea TikTok stores an inference about their gender separate from anything they declared.
- **Location & movement** — login IPs are already geo-enriched (`ip_geo.py`). v2 turns the login history into a *movement narrative*: home base, work location (daytime IP pattern), trips, carrier changes. "TikTok watched you travel to Denver in March."
- **Work schedule & employment type** — the hourly heatmap already exists. Layer inference on top: 9-to-5 pattern vs. shift work vs. irregular; lunch-break spikes; the night-shift signal already computed.
- **Life stage & household** — parenting clusters, wedding content, home-buying content, pet content → life-stage flags advertisers pay premiums for.
- **Income proxy** — shop orders + product browsing + luxury/budget content mix. Framed carefully ("signals an advertiser would read as…"), never as a judgment.
- **Emotional-state windows** — the most sensitive and most important one: late-night wellness/anxiety content clusters, breakup-content spikes. Framed as *"windows when you're most targetable,"* which the code already gestures at with `vulnerability_window`.

### 3d. Persona Engine v2 (replaces the four if-statements)

Instead of hardcoded labels, score the user on **six continuous dimensions**, each 0–100, each computed from existing metrics:

| Dimension | Fed by |
|---|---|
| **Intentionality** | followed % vs. algorithmic % |
| **Capture susceptibility** | linger rate, deep-dive %, session lengths |
| **Nocturnality** | night-shift ratio, night-linger % |
| **Exploration vs. monogamy** | echo-chamber index, distinct-creator counts |
| **Expressiveness** | explicit-vs-implicit ratio (comments/shares vs. silent watching) |
| **Parasociality** | concentration of time in top creators, DM-share behavior |

Archetypes become *named regions* of this space (the existing names — Intentional Curator, Nocturnal Seeker — survive as labels), rendered as a radar chart. This gives you nuance ("you're 80% Curator with a Nocturnal streak") instead of a single bucket, and every score has a formula you can defend.

### 3e. Temporal Evolution (new dimension across everything)

Everything above currently computes over the whole export as one blob. The single biggest analytical upgrade is **adding a time axis**: bucket the watch history by month and recompute clusters per bucket. This unlocks:

- **Rabbit-hole detection** — "In February, true-crime content went from 2% to 31% of your watch time in nine days." The algorithm's acceleration, made visible.
- **The algorithm's learning curve** — how fast TikTok's model of you converged after account creation.
- **Interest death** — clusters the algorithm abandoned when you stopped rewarding them.

---

## 4. Frontend redesign — two modes, one spine

Keep the cyberpunk-forensic identity. The change is structural: the current app is one long story. v2 is **Story + Dossier**.

**Story Mode (evolved Glass House).** The scroll narrative stays as the first-run experience, restructured around the new insight layer — proposed chapter arc: *They Watched You Log In* (movement narrative) → *Who They Think You Are* (demographics + Targeting Card reveal, the emotional peak) → *How They Learned It* (Stopwatch + evidence) → *When You're Most Vulnerable* (temporal + emotional windows) → *The Gap* (declared vs. inferred identity). The Targeting Card reveal is the shareable moment — design it like flipping over a case file.

**Dossier Mode (new explorer).** After the story, users land in a persistent workspace: the radar-chart persona view, a **timeline scrubber** that re-renders every panel for a selected month range, cluster drill-downs (tap a topic → the actual videos, watch times, creators behind it), the movement map, and the full Targeting Card with per-segment evidence. This is where the tool becomes something people return to rather than experience once.

**Universal confidence UI.** A three-tier visual language used everywhere: **Recorded** (TikTok's own data, solid), **Derived** (computed by our math, hatched), **Inferred** (probabilistic, dotted + confidence %). This single convention does more for credibility than anything else in the plan.

**Export as artifact.** A designed one-page "dossier" PDF/image — the Targeting Card, radar chart, and headline stats. This is the growth loop: it's screenshot-bait by design.

---

## 5. Backend redesign

**Consolidate to one engine.** Recommendation: **keep Python/FastAPI as the sole forensics engine and retire the TypeScript Supabase port.** The Python engine is more complete, better tested (the `tests/` suite covers it), and matches your existing Fly.io + FastAPI comfort zone from Varys. Supabase stays for what it's good at — auth, dossier persistence, storage — but stops duplicating analysis logic.

**Resolve the privacy fork explicitly.** Offer two honest tiers instead of one blurry promise: **Local mode** (analysis runs, nothing persists — the current README promise, kept) and **Vault mode** (opt-in Supabase persistence so the timeline features and re-visits work, encrypted, deletable, plainly explained). The privacy story becomes a feature instead of a liability.

**Pipeline as five explicit stages,** each cacheable, each independently testable:

1. **Parse** — existing parsers, unchanged.
2. **Enrich** — oEmbed titles via Redis cache, IP geo. Existing, hardened.
3. **Measure** — Stopwatch, heatmaps, echo index, dimension scores. Pure deterministic Python. *Now computed per-month as well as overall* (§3e).
4. **Interpret** — the LLM stage: semantic clustering, taxonomy mapping, cluster labeling. Structured JSON outputs only, validated against schemas, cached per dossier. One Claude call batch per dossier keeps cost predictable.
5. **Narrate** — deterministic blocks first (existing 9-block system, expanded), optional LLM narration layered on top, never inventing numbers.

**Schema versioning.** The parser already juggles multiple export layouts with fallback paths. Formalize it: a small compatibility layer that fingerprints the export version and logs unknown keys — so when TikTok changes the format again (it will), you find out from a log line, not a broken dashboard.

---

## 6. Phasing

**Phase 1 — Foundation (consolidation).** Retire the TS engine; add per-month bucketing to the Measure stage; implement the Recorded/Derived/Inferred confidence framework in the API payload. No new UI yet. *This phase makes every later phase cheaper.*

**Phase 2 — The Insight Layer.** Semantic Topic Engine + TikTok ad taxonomy file + Targeting Card + Persona Engine v2 dimensions. API now returns the full reconstructed profile.

**Phase 3 — Dossier Mode.** The explorer UI: radar chart, timeline scrubber, cluster drill-downs, confidence visual language throughout.

**Phase 4 — Story v2 + Export.** Restructure Glass House chapters around the new insights; build the shareable dossier export; demographic inference panels.

**Phase 5 — Later.** Instagram parity through the same pipeline (parser exists; insight layer doesn't), longitudinal re-upload comparison ("your profile, six months later"), YouTube bridge expansion.

## Non-goals for v2

- **No live TikTok API integration** — the export-based, adversarial-analysis posture is the identity. Don't dilute it.
- **No multi-user/social features** — comparisons like "you vs. typical user" can use published research benchmarks, not other users' data. Anything else undermines the privacy story.
- **No real-time monitoring** — this is a forensic snapshot tool, not a surveillance dashboard of your own.
- **No Instagram insight parity in v2** — parse it, show basics, but the deep layer is TikTok-first until the model is proven.

## Open questions

1. **Taxonomy sourcing** — TikTok's ad category list is public via Ads Manager docs but changes; decide on a snapshot-and-version approach vs. periodic manual refresh. *(You — one-time research task, good fit for your SEO/SEM background.)*
2. **LLM cost ceiling** — a 36k-video export could generate large clustering calls; needs a sampling strategy (weight by watch time, cap at N titles). *(Engineering decision, resolvable in Phase 2.)*
3. **Emotional-window ethics** — how bluntly to present "vulnerability windows"? Recommend framing + a methods link, but worth deciding deliberately before Phase 4. *(Product/editorial — you.)*
4. **Vault mode encryption** — client-side encryption before Supabase upload, or rely on RLS + at-rest? Affects whether "we can't read your dossier" is literally true. *(Engineering, blocking for Vault launch only.)*

---

*Everything in §3 is computable from data the parsers already extract. The redesign is less about new data collection and more about finally cashing the check the existing pipeline wrote.*
