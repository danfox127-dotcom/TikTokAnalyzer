# SYS.TEARDOWN v2 — Addendum
### Visual design, sleep scrub, hosting & mobile, variable exports, and algorithm interpretation

*Companion to the main redesign plan · July 2026*

---

## 1. Visual design system

First, an observation from the code: the project has already pivoted away from "cyberpunk-noir." The current `globals.css` defines a **warm paper editorial register** — cream paper (`#f5efe4`), near-black ink, oxblood accent (`#8b2323`), highlighter yellow (`#f5d57a`), Fraunces display serif, JetBrains Mono for data. That pivot was the right call, and v2 should commit to it fully. The concept name: **the declassified dossier.** Everything below extends that metaphor.

### Palette

| Token | Hex | Role |
|---|---|---|
| Paper | `#f5efe4` | Base background (existing) |
| Ink | `#1a1610` | Primary text, **Recorded** data (existing) |
| Oxblood | `#8b2323` | **Derived** data — our computed metrics (existing accent) |
| Stamp blue | `#1f4e6b` | **Inferred** data — probabilistic claims. Bureaucratic ink-stamp blue |
| Highlighter | `#f5d57a` | Evidence emphasis, tap-target hints (existing) |
| Redaction black | `#0d0b08` | Redaction bars, the "hidden data" motif |
| After-hours inversion | ink bg / paper text | The night-shift and vulnerability-window chapters flip the whole palette dark — the one dramatic register shift in the experience |

The three-color confidence mapping (ink / oxblood / stamp blue) gives the Recorded–Derived–Inferred framework from the main plan a visual home. **Critical rule: never encode meaning in hue alone.** Every confidence tier pairs its color with a border texture (solid / hatched / dotted) and a text label. This is baseline accessibility for color-vision differences and it also survives screenshots, dark mode, and grayscale printing of the export dossier.

### Iconography

Use **Lucide** (1.5px stroke, ink-colored) as the base set for consistency and speed, but reserve a small custom set of *rubber-stamp motifs* for the identity moments — archetype labels, the Targeting Card segments, and chapter headers rendered as slightly-rotated, slightly-distressed uppercase stamps (pure CSS: rotation −2° to 2°, border, letterpress texture). Suggested icon mapping: fingerprint → identity chapter; stopwatch → attention/Stopwatch engine; crescent moon → night shift; crosshair → Targeting Card; map pin → movement narrative; radar → persona dimensions; eye → surveillance/off-platform tracking; a redaction bar (▮▮▮) → anything TikTok hides.

### Typography rules

Keep the existing stack (Fraunces / Source Serif 4 / JetBrains Mono). Add two hard rules: **every number is mono** (data reads as data), and **every stamp/label is condensed uppercase with wide tracking**. Prose stays serif and generous — the contrast between warm editorial prose and cold mono figures *is* the visual argument of the product.

### Animation language (Framer Motion, already in the stack)

- **Redaction reveal** — the signature move. Inferred claims first render as black redaction bars; on scroll-into-view (or tap), the bar slides away to expose the text beneath. Used for every demographic inference and the Targeting Card segments. It makes "TikTok knows this about you" physically feel like declassification.
- **Stamp slam** — archetype names and segment labels enter with a quick scale-overshoot (1.4 → 1.0) plus 2–3° rotation settle, like a stamp hitting paper. ~250ms, spring easing.
- **Case-file flip** — the Targeting Card reveal is a single 3D flip (rotateY) from a manila "CLASSIFIED" cover to the card. This is the screenshot moment; give it weight (600ms).
- **Counter roll-ups** — big stats (3,847 advertisers) count up on entry; mono font makes this satisfying.
- **Heatmap ignition** — hourly heatmap cells fade in sequentially by hour, left to right, so users literally watch their day get reconstructed.
- **Timeline scrubbing** — in Dossier mode, dragging the time scrubber morphs charts with springs rather than re-rendering, so the *change over time* is the perceptual event.
- **Evidence margin notes** — tapping a claim slides a note in from the margin (paper-clip motif) rather than opening a modal; keeps the document metaphor intact.
- Honor `prefers-reduced-motion` throughout: reveals become fades, counters render final values.

---

## 2. Sleep scrub — what exists, and three gaps

Confirmed: the AFK firewall is already in `ghost_profile.py`. Negative timestamp deltas are dropped as clock anomalies; any gap **≥ 20 minutes** (`SLEEP_THRESHOLD_S = 1200`) is scrubbed and resets the session; gaps over 5 minutes reset session-duration tracking. Displayed watch times are capped at 270s. So the basic "fell asleep / left it open" case is handled.

But reading the bucketing logic closely, there are three real gaps worth fixing in Phase 1:

**Gap 1 — the 3-to-20-minute dead zone.** Deltas between 180s and 1200s currently land in the *deep dive* bucket. A bathroom break, a phone call, or cooking with the app open reads as "full cognitive capture." The 270s display cap limits the time credited, but the deep-dive *count* — which feeds the persona dimensions — is inflated. Fix: add an **Abandoned bucket (300s–1200s)** that is excluded from engagement scoring, or better, *validate* long views: a 6-minute delta only counts as a deep dive if corroborated (the user liked/favorited/shared/commented on that video, or oEmbed shows the video is actually long-form). Uncorroborated long deltas get flagged ambiguous.

**Gap 2 — one fixed threshold for everyone.** 20 minutes is reasonable, but usage rhythms differ. Compute each user's delta distribution and flag anything beyond that user's 99th percentile as anomalous, with the 20-minute floor as a backstop. Cheap, and it makes the scrub adaptive.

**Gap 3 — the autoplay phantom session.** TikTok autoplays. Someone asleep at 2am doesn't generate one 20-minute gap — they generate a *run* of plausible-length views (30–180s each) with zero interactions. Heuristic: a sequence of ≥10 consecutive night-hour views with uniform-ish deltas and no engagement events = probable phantom session; exclude from behavioral scoring but *keep as a narrative artifact*. "You fell asleep to TikTok on approximately 14 nights. It kept counting." That's one of the most human moments the data can produce — the scrub becomes a feature, not just hygiene.

All scrub decisions should surface in the UI as a methodology stat ("we excluded 6.2 hours of likely-idle viewing") — it builds trust in every other number.

---

## 3. Hosting options — and one honest revision

The main plan recommended consolidating on the Python engine. Your mobile and privacy asks force the tradeoff into the open, so here it is plainly:

**Option A — Python single engine (server-required).** FastAPI on Fly.io (your Varys stack), Vercel frontend, Redis via Upstash, Supabase for Vault mode. Cheapest to reach from where the repo is today; the Python engine is the complete, tested one. *Cost:* "local mode" for non-technical users is impossible in the browser — local means "run Docker," which excludes almost everyone the product is for.

**Option B — TypeScript single engine (runs anywhere).** Finish the partial TS port in `supabase/functions/_shared/forensics/` and make *it* the single source of truth. The same engine then runs: (1) **in the browser** via a Web Worker — true local mode, the README promise kept literally, for everyone; (2) in Supabase Edge Functions or Cloudflare Workers for Vault mode; (3) inside a future native app. Python is retired to a test oracle (keep its test suite to validate the port).

**Recommendation revised: Option B.** Given that privacy-as-product and mobile are both on your list, TypeScript-everywhere resolves the engine duplication in the direction that serves the roadmap. It's more up-front work (the TS port is maybe 60% of the Python engine's logic), but it's the last time the work is duplicated. The LLM "Interpret" stage stays server-side either way (API keys can't live in the browser) — local mode simply ships without LLM narration, deterministic insights only, which is an honest and even marketable tier ("air-gapped analysis").

Hosting menu under Option B: **Cloudflare Pages + Workers** (fast, cheap, generous free tier, Workers run the TS engine at the edge) or **Vercel + Supabase Edge** (what you know). **Hugging Face Spaces** stays as the community/demo deployment — it now hosts Docker apps, not just Streamlit. A **Tauri desktop build** becomes nearly free once the engine is TS — a genuinely local .app/.exe for the privacy-maximalist audience, great for press.

---

## 4. Mobile — and the "get your data" link

**PWA first, native later.** The Next.js app becomes an installable PWA: manifest, service worker, offline shell. With the TS engine in a Web Worker, a phone can analyze the export with nothing leaving the device — and mobile is where the export lands anyway, since people request it from the TikTok app. File intake on mobile: iOS/Android file pickers handle the ZIP fine; add "open with" registration so tapping the downloaded export offers the analyzer. A React Native/Expo native app is a Phase 5+ decision and shares the TS engine either way.

**The data-download link — what's actually possible.** No app can request the export *for* the user (it's behind TikTok auth, takes 24–72h to prepare, and automating it would violate ToS and undermine the product's clean posture). What you *can* build is a **guided request flow** that removes every point of confusion:

1. A "Request your data" button deep-links to `https://www.tiktok.com/setting/download-your-data` (opens TikTok's in-app browser or web, already logged in on mobile).
2. Illustrated 3-step overlay: choose **JSON**, choose **All time** (this matters — see §5), submit.
3. The waiting room: the app schedules a **local notification for ~36 hours later** — "Your TikTok export is probably ready." This is the single highest-leverage retention feature in the product, because the 1–3 day wait is where you currently lose everyone.
4. While waiting: a full **demo dossier on synthetic data**, so the user experiences the product's payoff before their data arrives.

---

## 5. Variable export windows

Confirmed in code: there is currently **no date-span detection or adaptation** — a 30-day export and a 2-year export flow through identical math, and short windows will produce confidently wrong personas. TikTok lets users pick a date range at request time, and even "All time" exports cap some sections (watch history often only reaches back ~6 months). Plan:

**Detect.** In the Parse stage, compute min/max timestamps *per section* (watch history, searches, logins each have different spans) and emit a `coverage` object: span in days, entry counts, per-section windows.

**Gate.** Every insight module declares minimum data requirements, e.g.: persona dimensions need ≥30 days *and* ≥500 conscious views; rabbit-hole detection needs ≥60 days; movement narrative needs ≥5 login events; forecasting (§6) needs ≥90 days. Below threshold, the panel renders an "insufficient window" state — the stamp reads **INSUFFICIENT EVIDENCE** — with a one-line explanation and a link to re-request a longer export. A degraded-but-honest panel beats a confident wrong one, and the dossier aesthetic makes "insufficient evidence" feel native rather than broken.

**Normalize.** All comparative metrics become rates (per-week skip rate, per-week deep dives) rather than totals; temporal bucketing degrades gracefully (monthly → weekly for exports under 90 days).

**Guide.** An upfront coverage banner on load — "This export covers 47 days (Mar 3 – Apr 19). Full analysis unlocks at 90+ days" — plus the request-flow guidance (§4) steering users to "All time" *before* they submit, which prevents the problem at the source. The confidence system from the main plan absorbs the rest automatically: short window = lower confidence, visibly, everywhere.

---

## 6. Interpreting the algorithm over time — the ambitious one

Honest boundary first: the export records what you **watched**, not what you were **served**. We see the intersection of TikTok's recommendations and your behavior — never the candidate pool, never the videos you were shown and scrolled past unlogged. So fully reverse-engineering the recommender from one export is not possible, and the product should say so (it's a credibility asset). What *is* possible is reconstructing the **feedback loop between your actions and your feed** — which is most of what a user actually wants to know. Four analyses, all deterministic, all buildable on the per-month bucketing from the main plan:

**Seed-event attribution ("why am I seeing this?").** For each topic cluster, walk backward to the earliest *explicit* signal preceding the cluster's growth — a search, like, share, follow, or favorite. Searches are the gold standard because they're unambiguous intent. Output: "You searched 'sourdough starter' on Jan 12. Within 8 days, baking content grew from 1% to 9% of your watch time." Every cluster in the Dossier gets an origin story with a receipt.

**Algorithm responsiveness (your personal lag).** Across all seed events, measure the median days from explicit signal to measurable feed shift. That number — "TikTok reweights your feed within ~4 days of a new signal" — is a per-user metric nobody has ever shown people about themselves.

**What the algorithm listens to (reinforcement ranking).** Correlate each engagement type (like, share, comment, favorite, deep-dive linger, search) with subsequent cluster growth *for this user*. Output: a ranked list — "Your deep watches move your feed 3× more than your likes." This doubles as actionable advice: the ranking tells the user which behavior to change if they want a different feed. It aligns with what's publicly known about TikTok's recommender (watch-time completion dominates), so the LLM narration layer can connect the user's personal pattern to the documented mechanics.

**Decay curves and forecasting ("what to expect").** For each cluster, measure how long it persisted after the user stopped engaging — the feed's "memory," typically visualizable as a half-life. Then fit a simple per-cluster trend (share of watch time per month, with momentum) and project 30 days with a confidence band: "At current trajectory, true crime reaches ~40% of your feed by mid-August." Rendered in the dossier register — a **PROJECTED** stamp in stamp-blue, dotted-border chart region, explicitly labeled *trajectory, not prophecy.* Pair it with a data-grounded counterfactual: "In your history, skipping alone never shrank a cluster; the only decays followed zero-linger streaks of 2+ weeks."

Architecturally this is a new pipeline stage — **4.5 Attribute** — between Interpret and Narrate, plus one new Story chapter ("Why Your Feed Looks Like This") and one new Dossier panel ("Algorithm Physics": responsiveness, memory half-life, and the listening ranking as three stamped stat cards). It slots into **Phase 4** of the existing plan; it depends on the temporal bucketing (Phase 1) and semantic clusters (Phase 2) but nothing else new. Requires ≥90 days of coverage per §5's gates.

---

*Net changes to the main plan: engine recommendation revised from Python to TypeScript-everywhere (§3); sleep-scrub hardening added to Phase 1; coverage detection added to Phase 1; guided request flow + PWA added as Phase 3.5; the Attribution stage added to Phase 4.*
