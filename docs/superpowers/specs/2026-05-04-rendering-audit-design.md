# Rendering Audit & Retrofit Design

**Goal:** Inventory what `/api/analyze` emits vs. what the frontend renders, fix the type-system drift that's hiding the gap, retrofit `SurfaceDataDisplay` to the Miami Day Art‑Deco mock, and lock iconography to lucide‑react.

**Out of scope for this pass:** Re‑authoring narrative copy. Adding new analytical fields to the backend. The bright→dark *transition* mechanic itself (already exists as `PhaseTransition`).

---

## Part 1 — Audit

### Backend ground truth (`/api/analyze` response)

Top-level keys emitted by `build_ghost_profile` + injected by `api/main.py`:

| Key | Notes |
|---|---|
| `status` | always `"success"` |
| `interest_clusters` | from `footprint["interest_clusters"]` |
| `interest_phrases` | from `footprint["top_phrases"]` |
| `stopwatch_metrics` | viewing volume, hourly heatmap, weekly heatmap, etc. |
| `behavioral_nodes` | peak_hour, skip/linger/night rates, social-graph % |
| `primary_archetype` | name, sub_archetypes, dissonance, atomic_traits |
| `creator_entities.vibe_cluster` | now also: display_name, thumbnail, genre, archetype, confidence |
| `creator_entities.graveyard` | same shape, skip_count instead of linger_count |
| `academic_insights` | explicit/implicit, echo-chamber index |
| `night_shift` | percentage, count, window |
| `digital_footprint` | login_count, unique_ips, devices, recent_logins[] (city + country_name added by geo enrich) |
| `search_rhythm` | total_searches, hourly_histogram, recent_searches[] |
| `discrepancy_gap` | declared_surface_sample, inferred_creator_handles, declared/inferred counts |
| `enrichment_targets` | per-bucket events + following_usernames |
| `declared_signals` | settings_interests, ad_interests, recent_searches, follow counts |
| `ad_profile` | advertiser categories, vulnerability_window, peak_ad_hour, off-platform, shop |
| `comment_voice` | shape TBD — emitted, untouched on the FE |
| `share_behavior` | shape TBD — emitted, untouched on the FE |
| `transparency_gap` | shape TBD — emitted, untouched on the FE |
| `shadow_clusters?` | optional LLM-derived thematic groupings (only when `?api_key=…`) |
| `narrative_blocks` | 9-block dossier; rendered only by `NarrativeReportView` |

### What `TheGlassHouse.tsx` actually consumes

`TheGlassHouse` is a five‑section editorial essay (Prologue + Chapters 1–4 + Epilogue), 1,705 lines. Sourced from the inventory:

| Section | Reads | Notes |
|---|---|---|
| Prologue | `academic_insights`, `night_shift.percentage`, `behavioral_nodes.peak_hour`, `stopwatch_metrics.total_conscious_videos` | Only consumes `peak_hour` from `behavioral_nodes` |
| Ch.1 Digital Footprint | `digital_footprint.{login_count,unique_ips,unique_devices,recent_logins}` | `recent_logins` rendered as raw timestamps |
| Ch.2 Whispered Interests | `declared_signals.{settings_interests,ad_interests}`, `academic_insights.explicit_vs_implicit_ratio`, `creator_entities.vibe_cluster`, `discrepancy_gap.declared_surface_sample` | New vibe fields ignored |
| Ch.3 Psychographic | `creator_entities.vibe_cluster`, `declared_signals.ad_interests` | Same fields again, no new data |
| Ch.4 Feedback Loop | `search_rhythm.{total_searches,hourly_histogram,recent_searches}`, `stopwatch_metrics.total_conscious_videos` | Hourly bar has no Y‑axis label |
| Epilogue | — | Pure narrative + nav |

### Coverage gap — emitted but never rendered anywhere

| Field | Status |
|---|---|
| `interest_clusters` | unrendered |
| `interest_phrases` | unrendered |
| `comment_voice` | unrendered |
| `share_behavior` | unrendered |
| `transparency_gap` | unrendered |
| `shadow_clusters` | unrendered (typed only) |
| `creator_entities.graveyard` | unrendered (only the HUD uses it) |
| `creator_entities.vibe_cluster.{display_name, thumbnail, genre, archetype, confidence}` | unrendered (we just added `display_name`/`thumbnail` from oEmbed; nothing reads them yet) |
| `behavioral_nodes.{skip_rate_percentage, linger_rate_percentage, night_shift_ratio, night_lingers_count, social_graph_followed_pct, social_graph_algorithmic_pct}` | unrendered (only `peak_hour` is read) |
| `primary_archetype.{sub_archetypes, dissonance, atomic_traits}` | unrendered in `TheGlassHouse` (loosely referenced in Prologue) |
| `ad_profile.{vulnerability_window, peak_ad_hour, off_platform_tracked, off_platform_events}` | unrendered in `TheGlassHouse` (Surface uses `shop_*` only) |

### Coverage gap — rendered but unexplained

These appear in `TheGlassHouse` as bare numbers / arrays with no caption or unit:

1. `digital_footprint.recent_logins` — raw timestamp/IP rows, no friendly date format, no city
2. `creator_entities.vibe_cluster[].linger_count` — count without a unit ("what does 47 mean?")
3. Chapter 2 explicit‑vs‑implicit bar chart — no Y‑axis scale annotation
4. Chapter 4 hourly histogram — no axis label clarifying whether the values are searches, watches, or minutes

### Type drift (the 52 TS errors)

1. **`declared_signals` is missing from `GhostProfile`** (read in 3 components, not in the type)
2. **`_evidence` is declared twice** with conflicting shapes — once narrow (settings_interests/ad_interests/…), once wide (prologue/feedback_loop/discrepancy/…). Real shape is the wide one, used by `Claim` payloads
3. **`graveyard.handle` typed as `string` but TheGlassHouse reads `g.handle` and tries `count` → mapped to `skip_count`** — fine after my last commit, no error here
4. **`ad_profile.shop_products` typed but Surface accesses without optional chain** — minor

### Iconography

Already 100% **lucide‑react**. No Material Symbols imports anywhere. The only thing to do is set policy: ban Material Symbols imports going forward (lint rule or just code review). The Miami Day mock the user pasted uses Material Symbols — those are placeholder; we will substitute with lucide equivalents when retrofitting Surface.

---

## Part 2 — Spec

### A. Type drift fixes (`GhostProfileHUD.tsx`)

One commit to make TypeScript happy and reflect reality. Edits to the `GhostProfile` interface:

```ts
declared_signals?: {
  settings_interests: string[];
  ad_interests: string[];
  recent_searches: string[];
  following_count: number;
  follower_count: number;
};

// Single _evidence definition, claim-keyed, opaque payloads:
_evidence?: Record<string, unknown>;

interest_clusters?: { cluster: string; weight: number }[];   // verify shape against ghost_profile.py footprint["interest_clusters"]
interest_phrases?: { phrase: string; weight: number }[];     // verify shape
comment_voice?: Record<string, unknown>;                     // start opaque, narrow when we render
share_behavior?: Record<string, unknown>;                    // ditto
transparency_gap?: Record<string, unknown>;                  // ditto
```

Verify the cluster/phrases shapes by reading `api/ghost_profile.py` in the same task; tighten the `Record<string, unknown>` types as soon as we render each field (Part D).

### B. Surface retrofit — Miami Day Art Deco

Replace the body of `algorithmic-mirror/app/components/SurfaceDataDisplay.tsx` while keeping its public contract (`{ profile, onReveal }`) and its scroll‑sentinel reveal behavior unchanged.

Visual language from the user's HTML mock:
- Background `#fbf8ff` → `#f2ede6` gradient (preserve)
- Frame style: `border: 4px solid #1a1410; box-shadow: 6px 6px 0 #f28482` ("art-deco-border") and `…0 #c7eae1` ("art-deco-border-alt")
- Corner clip: `clip-path: polygon(10px 0, 100% 0, 100% calc(100% - 10px), calc(100% - 10px) 100%, 0 100%, 0 10px)` for accents only — not every card
- Type: Epilogue 800/900 for headlines, Space Grotesk 700 caps for labels, Be Vietnam Pro for body. Add to `app/layout.tsx` font loading.
- Accent palette: `#9c4141` primary, `#f28482` primary-container, `#45645e` secondary, `#c7eae1` secondary-container

Section structure — **same data, retrofitted shell**:

| Section | Currently | Retrofit |
|---|---|---|
| Header | "TIKTOK DATA EXPORT" pill | Top app bar with bordered logo + lucide icons (Bell, Settings) — replace Material Symbols |
| Hero | Soft "told TikTok about yourself" copy | Hero with split layout: art-deco-clip headline on left, framed image-or-pattern on right |
| Profile stats | Following/Followers count cards | Same data, art-deco-border'd cards with offset shadows |
| Declared interests | TagCloud | Grid of icon tiles (4-up), each tile = lucide icon + caps label, art-deco-border'd |
| Ad categories | TagCloud | TagCloud retained inside an art-deco-border'd panel |
| Recent searches | TagCloud | Same |
| TikTok Shop | List | Bordered list inside accent panel |
| ATT permission card | Permission rows | Keep — already strong; reskin border/shadow only |
| Algorithm Note (NEW) | — | Two‑column "what this data means" panel pulling 1–2 sentence explanations from a central copy file |
| Sentinel + chevron | Existing | Same |

**Constraint:** every numeric or list value rendered gets a one‑line caption pulled from `app/copy/explanations.ts` (new file, str→str map keyed by data field name). This eliminates the "rendered without explanation" issue across Surface in one move and gives us a place to refine wording.

Lucide substitutions for the mock's Material Symbols:
- `notifications` → `Bell`
- `settings` → `Settings`
- `architecture` → `Compass` (or `Building`)
- `palette` → `Palette`
- `flight_takeoff` → `Plane`
- `music_note` → `Music`
- `category` → `Tag`
- `badge` → `IdCard`
- `memory` → `Cpu`
- `info` → `Info`

### C. Lucide consolidation policy

Add to `algorithmic-mirror/AGENTS.md` (one paragraph): icons come from `lucide-react`. Do not import `@material-symbols/*` or load the Material Symbols webfont. If a glyph isn't in lucide, ask before reaching elsewhere.

### D. Render-the-orphans plan (after Surface retrofit lands)

These are the unrendered fields from the audit, with proposed surfaces. Implementation is a follow‑on plan, not this spec:

| Field | Where to render | Treatment |
|---|---|---|
| `comment_voice` | Dossier block (already a slot in `narrative_blocks`); if absent, add explicit "Comment Voice" section at end of `TheGlassHouse` Ch.3 | Stat row + 2-3 example comments |
| `share_behavior` | Dossier block; mirrors comment_voice | Topic donut + 1-line explanation |
| `transparency_gap` | Dossier; renders bar of data‑category counts | Already specified in deterministic-narrative spec |
| `shadow_clusters` | New section between Ch.2 and Ch.3, conditional on `api_key` | 2‑3 cluster cards with label + hedged description |
| `creator_entities.graveyard` | Ch.3 sidebar: "Creators it showed you that you skipped" | Mini list with skip_count |
| `vibe_cluster.display_name + thumbnail` | Replace bare `@handle` text in Ch.2/Ch.3 with avatar + display name + monospaced handle | Pure presentation upgrade |
| `vibe_cluster.genre/archetype` | Conditional badge on each creator chip when `confidence > 0` | Indicates LLM enrichment ran |
| `behavioral_nodes.{skip,linger,night,social_graph}` | New "Vital Signs" mini‑grid in Prologue | Existing Prologue under‑uses `behavioral_nodes` |
| `primary_archetype.{sub_archetypes,dissonance}` | Prologue dissonance alert is already wired; show sub_archetypes as confidence-stacked list | Pure type fix + 30 lines of render |
| `interest_clusters / interest_phrases` | Ch.2 — replace plain TagCloud with weighted cluster blocks | Use `weight` for opacity/scale |
| `ad_profile.{vulnerability_window, off_platform_*}` | Surface retrofit "Algorithm Note" panel | Single sentence each, deterministic copy |

### E. Pre-existing scratchpad

`test_on_real_data.py` at repo root is a Gemini scratchpad with a hardcoded user-machine path. Move to `scripts/dev_smoke.py` and add `scripts/` to repo conventions. Not blocking.

### F. Deprecated SDK migration (separate cleanup)

`google.generativeai` is officially EOL (FutureWarning at every test run). Migrate to `google.genai` in a dedicated commit. Touches: `api/main.py`, `utils/creators.py`, `utils/pillar_categories.py`, `api/narratives.py`. Sketch:

```python
# old
import google.generativeai as genai
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-3-pro")
response = await model.generate_content_async(prompt, stream=True)

# new
from google import genai
from google.genai import types
client = genai.Client(api_key=api_key)
response = await client.aio.models.generate_content_stream(
    model="gemini-3-pro",
    contents=prompt,
)
```

Test impact: existing tests don't touch Gemini paths, so the migration is mechanical.

---

## Execution order

1. **Type drift fixes** (`GhostProfileHUD.tsx` interface) — single commit, brings TS errors to zero or close to it.
2. **Surface retrofit** — `SurfaceDataDisplay.tsx` rewrite + `app/copy/explanations.ts` + AGENTS.md icon policy.
3. **Render-the-orphans plan** — separate spec, sequenced field-by-field once Surface is happy.
4. **`google.generativeai` migration** — independent cleanup commit.
5. **Scratchpad relocation** — drive‑by.

Steps 1–2 unblock the Surface→Dark scroll story you're already prototyping. Step 3 is the big rendering work and gets its own plan after we've validated the Surface aesthetic on real data.
