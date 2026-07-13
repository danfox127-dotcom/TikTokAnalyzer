# SYS.TEARDOWN v2 — Research Integration
### What the notebook sources change in the plan

*Reviewed: Masood et al., "Counting How the Seconds Count" (CHI 2026, UIUC — 100 donated TikTok exports, 2.65M videos) and the PIPEDA #2025-003 joint findings (Canadian privacy regulators' investigation of TikTok, Sept 2025). These two turned out to be the highest-leverage sources; the CHI paper uses literally the same data exports this product parses.*

---

## 1. A correction: likes don't steer the feed the way the plan assumed

The most important finding, and it cuts against part of the Attribution design in the previous addendum. The CHI study tested the near-universal folk theory that liking or sharing a video immediately shifts recommendations toward that content. **It doesn't.** Measuring content-similarity around 83,000+ like events, they found videos recommended *after* a like are no closer to the liked video than before — in fact, the videos *preceding* the like were consistently more similar. The causality runs backward: a run of similar content produces the like; the like doesn't produce the run. If anything, the algorithm treats an interaction as an engagement peak and gets *more* exploratory afterward.

Three consequences for the plan:

- **Seed-event attribution must be reweighted.** Searches and follows remain strong explicit signals (search is unambiguous intent the feed demonstrably responds to). Likes and shares should be treated as *symptoms* of a cluster already surging — markers of engagement peaks, not causes of feed shifts. The attribution logic needs a reverse-causality guard: a cluster's growth must precede-test against the engagement event, not just co-occur with it.
- **The "reinforcement ranking" gets reframed as myth-busting.** Instead of claiming to rank "what the algorithm listens to" (which naive correlation would get wrong for exactly this reason), the product can run the CHI paper's own test on the *user's* data: "You liked 214 videos believing it shaped your feed. Here's what actually happened after each one." Replicating a peer-reviewed methodology on the user's personal export is a stronger, more defensible feature than the original design — and a far better story.
- **Watch time stays king.** This validates the Stopwatch engine as the product's center of gravity: sustained watching, not button-pressing, is what the algorithm demonstrably responds to. The paper also predicts watch behavior from content alone at 70% accuracy — evidence that content-based clustering (our Semantic Topic Engine) captures real signal.

## 2. The micro-bubble model — a better Echo Chamber Index

The CHI data shows the "filter bubble" is really a **multi-timescale phenomenon**: on any single day, users spend ~50% of watch time in just their top 5 content clusters — but ~4 of those top 5 change by the *next day*. Over six months, only ~21% of time lands in the all-time top 5. Daily tunnel vision, long-term drift.

The current single-number echo-chamber index misses this entirely. Replace it with two metrics: **daily concentration** (how deep today's tunnel is) and **cluster churn** (how fast the tunnels rotate). A user with high concentration *and* low churn is in a genuine long-term bubble — rare and worth flagging loudly. High concentration with high churn is just how TikTok works, and saying so honestly differentiates the product from lazy filter-bubble discourse. Bonus: the paper's population statistics (50% daily top-5 concentration, ~79% daily churn, ~332 videos/day, ~1 hr/day) give us **published benchmarks for "you vs. the typical user" comparisons** — the main plan wanted comparisons without multi-user data, and this is the sourcing that makes it possible.

## 3. Niche drift — a new chartable metric

The paper found that over time TikTok recommends progressively *less popular* videos to each user (average like-counts of watched videos decline steadily) while total watch time rises — the algorithm trading mass appeal for personal precision. Since oEmbed enrichment can return engagement counts, the product can chart each user's own **niche-drift curve**: "In January, your average video had 2.1M likes. By June: 340K. TikTok stopped showing you what's popular and started showing you what's *yours*." One line chart, deeply felt. Slots into the temporal evolution work (Phase 2) at near-zero extra cost.

## 4. A smarter sleep scrub, borrowed directly

Both the CHI paper and the Zannettou dataset it builds on scrub AFK anomalies by discarding views where inferred watch time exceeds **3× the video's actual duration**. That's more principled than our fixed 20-minute threshold or the proposed 270-second cap, because it adapts per video — a 10-minute delta on a 4-minute video is plausible; on a 12-second video it's an abandoned phone. Requires video duration from enrichment, which oEmbed doesn't always supply — so implement as: duration-based scrub where duration is known, current threshold as fallback. Also validating: the timestamp-delta watch-time method itself is now used in peer-reviewed work, which the methodology page should cite in the Stopwatch's defense.

## 5. The demographic module gets TikTok's actual buckets

The PIPEDA findings are the regulatory gold the Targeting Card needed. Canadian privacy commissioners, with subpoena-grade access, documented that TikTok maintains **three separate age-estimation models**, including an **advertising age model that classifies every user into: 13–17, 18–24, 25–34, 35–44, 45–54, 55+**. The demographic inference panel should output *these exact brackets* — the product is no longer guessing at categories; it's reconstructing the literal segmentation TikTok runs. The regulators also confirmed the full set of attributes TikTok infers about each user: **interests, location (approximated to ~3 km²), age range, gender, and spending power**. Those five regulator-confirmed categories become the five cards of the demographic panel, each labeled "TikTok is documented to infer this" — Recorded-tier framing with a government citation, not our speculation.

## 6. New Recorded-tier narrative material (all citable to the findings)

- TikTok's own inventory of data elements collected per user runs **31 pages** — an opening-chapter stat that needs no embellishment.
- TikTok runs **computer vision and audio analytics on video content — including facial analysis to infer the age and gender** of people appearing in videos, feeding content recommendation and ad delivery. Regulators classified this as biometric information that users were never adequately told about. This belongs in the "How They Learned It" chapter: the export shows behavioral tracking; the findings prove the camera-side analysis the export *doesn't* show.
- The regulators found ad labeling on TikTok often small or missing, and observed sensitive targeting options (e.g., transgender-related hashtags) available in Ads Manager that TikTok itself couldn't explain — context for the Targeting Card's "segments an advertiser could buy" framing.
- **Population benchmark:** TikTok told regulators that 73.5% of users never post and 59.2% never comment. This calibrates the Expressiveness persona dimension against the platform's real distribution — a user who comments even occasionally is already in the expressive minority.
- Off-platform inflows (Pixel, Events API, measurement partners) are regulator-documented, strengthening the export's "Off TikTok Activity" panel with sourcing for *how* that data arrives.

## 7. Plan deltas, consolidated

| Plan item | Change |
|---|---|
| Attribution stage (Phase 4) | Add reverse-causality guard; demote likes/shares to symptom markers; add "test the folk theory on your own data" feature |
| Echo Chamber Index (Phase 1–2) | Split into daily concentration + cluster churn; flag only high-concentration/low-churn as true bubbles |
| Temporal evolution (Phase 2) | Add niche-drift curve (avg. popularity of watched videos over time) |
| Sleep scrub (Phase 1) | Duration-aware scrub (>3× video length) where duration known; threshold fallback otherwise |
| Demographic panel (Phase 2) | Output TikTok's documented advertising age brackets; structure panel around the five regulator-confirmed inference categories |
| Comparisons ("you vs. typical") | Now sourced: CHI 2026 population stats + PIPEDA engagement stats; no multi-user data needed |
| Methodology page | Cite CHI 2026 / Zannettou for watch-time inference; cite PIPEDA findings for demographic claims |

*Net effect: the plan got more honest and more powerful at the same time. The two changes that matter most: the algorithm-interpretation feature is now built on tested findings instead of folk theory, and the demographic reconstruction is anchored to categories a government investigation confirmed TikTok actually uses.*
