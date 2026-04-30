# Algorithmic Mirror: Story, Fixes, and Narrative UI

**Date:** 2026-04-14
**Scope:** TikTokAnalyzer front-to-back. Fix heatmap, deepen pillar reasoning, correct deep-dive threshold (180s), rework anti-profile framing, wrap the dashboard in a scroll-driven narrative.

## Problem

The app surfaces forensic data but doesn't tell a story. Specific breaks:

1. **Heatmap not rendering** (or rendering as a degenerate 1D bar strip mistaken for broken).
2. **Psychographic pillars are bare keyword lists** — the viewer learns *what words* but not *what the cluster means about them*.
3. **"Deep dive" threshold is 15s**, which is a hook, not a commitment. Should be 180s (3 minutes).
4. **Anti-profile, sandbox, night pillars are structural copies** of the psychographic pillar — same extract_themes call on different buckets. No distinct framing.
5. **No connective tissue between sections.** Each module is a discrete dashboard. The experience should read like a story you scroll.

## Current State (with citations)

- `ghost_profile.py:118–140` — tiers: `<3s` graveyard, `3–15s` sandbox, `>15s` deep_lingers.
- `ghost_profile.py:156` — `hourly_heatmap` is a 1D dict keyed `"0"`–`"23"`. No day-of-week dimension.
- `psychographic.py:68–116` — `extract_themes` returns only `{top_keywords, top_phrases, top_emojis}`. No interpretation.
- `api/main.py:219–223` — `psychographic`, `anti_profile`, `sandbox`, `night` all call the same extractor on different buckets.
- `algorithmic-mirror/app/components/GhostProfileHUD.tsx` — ~700 lines, all helper components inlined (HourlyHeatmap:107, KeywordBars:181, VideoDeepDiveCard, etc.). Copy references "15 seconds" at line 630 and elsewhere.

## Design

### Phase 1 — Backend (Python)

#### 1.1 New engagement tier: `deep_dive` (>180s)

In `ghost_profile.py` stopwatch loop, add a fourth tier. Keep existing tiers for continuity; add the new one.

- `graveyard`: `<3s`
- `sandbox`: `3–15s`
- `sustained`: `15–180s` (renamed from `deep_lingers` in UI copy, data key stays `deep_lingers` for back-compat)
- `deep_dives`: `>180s` (NEW)

Return both lists and counts. Cap `time_spent` stays at 270s.

#### 1.2 Day-of-week heatmap

Extend stopwatch aggregation:
```
weekly_heatmap: Dict[int, Dict[int, int]]  # dow (0=Mon) -> hour -> count
```
Keep `hourly_heatmap` as a projection (sum across days) for backward compatibility.

#### 1.3 Pillar narrative layer (deterministic)

New function in `psychographic.py`:
```python
def build_pillar_narrative(
    pillar: str,           # "psychographic" | "anti_profile" | "sandbox" | "night"
    keywords, phrases, emojis,
    sample_titles: list[str],
) -> dict:
    return {
        "headline": str,          # one-line characterization
        "interpretation": str,    # 2-3 sentences, second person
        "evidence": list[str],    # 2-3 sample titles
    }
```

Deterministic rules:
- **headline**: template per pillar, filled with top cluster (see templates below).
- **interpretation**: chooses from a small library of sentence fragments based on top-keyword categories (e.g., "labor," "relationships," "humor," "news," "aesthetics"). Category tagging uses a static keyword→category map in `utils/pillar_categories.py`.
- **evidence**: top 3 titles from the source bucket ranked by time_spent (pillar) or by skip-speed (anti_profile).

Templates:
- psychographic: "The algorithm believes you are {category_phrase}."
- anti_profile: "The algorithm tested {category_phrase} on you. You refused."
- sandbox: "Currently under evaluation: {category_phrase}."
- night: "After midnight, you become someone who watches {category_phrase}."

#### 1.4 Anti-profile as contrast, not raw extraction

Compute anti-profile keywords as **set difference**: top graveyard keywords minus top psychographic keywords (the "rejection signature"). Expose both:
- `anti_profile.raw` — current behavior
- `anti_profile.signature` — contrast-filtered (new; default for UI display)

#### 1.5 API additions

`build_ghost_profile` output gains:
- `weekly_heatmap`
- `deep_dives` (list + count)

`/api/enrich` response gains, per pillar:
- `narrative: {headline, interpretation, evidence}`

### Phase 2 — Frontend fixes + narrative UI

#### 2.1 Heatmap fix

- Verify `heatmap` prop path in GhostProfileHUD parent wiring. Trace `ghostProfile.hourly_heatmap` → component.
- Replace the 24-bar strip with a 7×24 grid keyed on `weekly_heatmap`. Use opacity-scaled cells (min 0.1, max 1.0) on a single accent color to avoid the current orange/cyan hour-hack.
- Callout below: "Peak: {weekday} at {hour}."
- Fallback: if `weekly_heatmap` is missing, render the 1D hourly strip but log a console warning.

#### 2.2 Deep-dive threshold = 180s

- New section: **Deep Dives** sourced from `ghostProfile.deep_dives` (>180s). Copy: "More than three minutes. Full commitment."
- Rename existing "Deep Dive Videos" section to **Sustained Attention** (15–180s). Copy: "The algorithm held you here past the hook."
- Remove all "15 seconds" copy that implies deep dive.

#### 2.3 Per-pillar narrative card

Above the keyword bars in each pillar, render:
```
┌──────────────────────────────────────┐
│ HEADLINE (large, accent)             │
│ interpretation (body, muted)         │
│ ─ evidence title 1                    │
│ ─ evidence title 2                    │
│ ─ evidence title 3                    │
└──────────────────────────────────────┘
[keyword bars — now labeled "evidence: recurring terms"]
[phrase list — "evidence: recurring phrases"]
```

#### 2.4 Story scroll: SectionIntro

New component `app/components/modules/SectionIntro.tsx`:
```tsx
<SectionIntro
  chapter={3}
  title="Four theories of you"
  lede="The algorithm has a working hypothesis. Here are the four clusters it's testing."
/>
```

Chapters (in order):
1. **The Watch** — Stopwatch. "You handed TikTok X minutes. Here's how it spent them."
2. **The Shape of Attention** — Heatmap. "Your attention has a shape."
3. **Four Theories of You** — Pillars. "The algorithm has a theory of you."
4. **What You Refuse** — Anti-profile. "What you reject says as much as what you accept."
5. **Under Evaluation** — Sandbox. "The probes. Content the algorithm tested and discarded."
6. **Sustained Attention** — 15–180s. "Past the hook."
7. **Deep Dives** — >180s. "Full commitment."
8. **The Synthesis** — closing. Composed from pillar narratives.

#### 2.5 Progressive reveal

Wrap each chapter in an `IntersectionObserver` hook (`useReveal`) that applies `opacity-0 translate-y-4` → `opacity-100 translate-y-0` on enter. Respect `prefers-reduced-motion`.

### Phase 3 — Refactor + closing synthesis

#### 3.1 Module extraction

Move from GhostProfileHUD.tsx to `app/components/modules/`:
- `Stopwatch.tsx`
- `AttentionHeatmap.tsx`
- `PillarCard.tsx`
- `CreatorBars.tsx`
- `VideoDeepDiveCard.tsx`
- `SectionIntro.tsx`

GhostProfileHUD becomes a thin composition of chapters.

#### 3.2 Closing synthesis

New section at page bottom: **What This Means**. Composes a 4–5 sentence summary from pillar `headline` + `interpretation` fields. Deterministic: template stitches them.

## Agent execution plan

1. **Agent A (Sonnet)**: Phase 1 — backend. Lands new schema + tests. Must finish before B/C/D.
2. **Agent B (Sonnet)**: Phase 2.1 + 2.2 — heatmap fix and deep-dive threshold.
3. **Agent C (Sonnet)**: Phase 2.3 + 2.4 + 2.5 — pillar narrative cards, SectionIntro, reveal.
4. **Agent D (Sonnet)**: Phase 3 — module extraction + synthesis.

B/C/D run in parallel against A's schema. No Gemma agents.

## Non-goals

- LLM-generated narratives (deferred; deterministic first).
- Day-of-week controls / interactive heatmap filtering.
- Persistence / export.

## Risks

- **Category map quality** (1.3) determines interpretation quality. Seed with ~80 keyword→category mappings; accept imperfect categorization on first pass.
- **Module extraction** (3.1) risks touching too much at once. Guard with a commit per extracted module.
- **Anti-profile contrast** (1.4) can yield empty results if graveyard and psychographic overlap heavily. Fallback to raw extraction when signature is `<5` terms.

## Acceptance

- Heatmap renders a 7×24 grid with a peak callout.
- Every pillar shows a headline + interpretation above the bars.
- A section labeled "Deep Dives" renders only videos with `time_spent > 180`.
- Scrolling the dashboard reveals chapters with fade-in, each introduced by a SectionIntro.
- Closing synthesis paragraph appears at page bottom.
