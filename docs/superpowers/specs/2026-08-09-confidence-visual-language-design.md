# WP-3.2 · Confidence Visual Language — Design

**Status:** approved design, pre-implementation
**Date:** 2026-08-09
**Depends on:** WP-1.5 (`Claim`/`EvidenceRef`/`Tier` in `engine/types.ts`, `profile.claims`), the existing `EvidencePanel.tsx`, `globals.css` warm-paper tokens
**Unblocks:** WP-3.1 (dossier shell), WP-3.4 (polished panel treatments)
**Refs:** implementation-plan WP-3.2; redesign-addendum §1 (visual design system)

## 1. Purpose

Give the `Claim` contract — recorded / derived / inferred, each with a `method`
string and `evidence[]` — a single, shared visual language instead of every panel
inventing its own ad hoc tier text. Two things are true today that this WP fixes:
`profile.claims` (the full WP-1.5 output: skip rate, night shift, archetype,
sub-archetypes, dissonance, etc.) **is never rendered anywhere**, and the two panels
that do render real `Claim[]` (`TargetingCard`, `DemographicPanel`) show tier and
confidence as raw inline text with no shared component behind it.

## 2. Decisions (settled during brainstorming, 2026-08-09)

1. **Add a new Evidence Log tab surfacing `profile.claims`.** Rather than shipping
   the shared components with no real end-to-end consumer beyond two retrofits, a
   new minimal panel proves them on the previously-invisible WP-1.5 data — genuinely
   new, currently-hidden information reaching the UI for the first time.
2. **`PersonaRadar` / `NicheDriftChart` are explicitly out of scope.** Neither emits
   a `Claim` (no `tier` field) — forcing synthetic tier semantics onto a trend line
   or an archetype-distance score would be artificial. Their visual-language pass is
   **WP-3.4** (already itemizes both as "polished panels").
3. **"Hatched" (addendum §1) = dashed border, not a diagonal-stripe fill.** Keeps the
   base components CSS-simple; a literal diagonal hatch is reserved for the WP-3.4
   rubber-stamp motif treatment, not baked into the shared primitives now.
4. **Retrofit scope is claim-rendering only.** `TargetingCard`/`DemographicPanel`
   keep their existing layout, 3-state gating, and local non-claim chrome (headers,
   icons) untouched — only the inline tier/confidence text is replaced with the
   shared components. A full palette-token migration across all 9 components that
   currently duplicate `INK`/`BORDER`/`ACCENT` is explicitly deferred, not part of
   this WP.

**Deferred items and where they land** (not abandoned):
- PersonaRadar/NicheDriftChart polish, diagonal-hatch stamp texture, animated/
  case-file treatments → **WP-3.4**.
- Dossier shell/nav rebuild → **WP-3.1** (the very next WP).
- Evidence Log search/filter, full 9-component token migration → no assigned WP;
  open follow-ups, not blocking anything here.

## 3. Verified a11y baseline

Computed WCAG contrast ratios (relative luminance, sRGB) against the paper
background `#f5efe4`:

| Token | Hex | Ratio vs. paper | AA normal text (≥4.5) |
|---|---|---|---|
| Ink (Recorded) | `#1a1610` | 15.73:1 | ✅ |
| Oxblood (Derived) | `#8b2323` | 7.77:1 | ✅ |
| Stamp blue (Inferred) | `#1f4e6b` | 7.77:1 | ✅ |
| Redaction black | `#0d0b08` | 17.17:1 | ✅ |

All four pass AA for normal text, not just large text — the addendum's palette was
already accessible; this WP just formalizes it into reusable tokens/classes.

## 4. Design tokens (`globals.css`)

`--ink` (Recorded) and `--accent`/oxblood (Derived) already exist. Add:
```css
--stamp-blue:      #1f4e6b;  /* Inferred */
--redaction-black: #0d0b08;  /* redaction motif; reused by WP-3.4 */
```

Three texture classes, each pairing color + border-style + an implicit text-label
contract (enforced by the components, not CSS alone — see §5):
```css
.tier-recorded { border: 1px solid var(--ink);        color: var(--ink); }
.tier-derived  { border: 1px dashed var(--accent);     color: var(--accent); }
.tier-inferred { border: 1px dotted var(--stamp-blue); color: var(--stamp-blue); }
```

## 5. Component API

**`tierMeta(tier: Tier): { color: string; borderStyle: "solid"|"dashed"|"dotted"; label: "Recorded"|"Derived"|"Inferred"; className: string }`**
— single source of truth. Every tier-aware component (new and retrofit) imports this
instead of hardcoding colors, closing the "9 components duplicate their palette" gap
specifically for tier rendering.

**`ClaimText`** — inline/prose rendering:
```tsx
<ClaimText claim={claim} />
```
Renders the formatted `claim.value` inside a `tierMeta(claim.tier).className` span,
a small tier-label chip, and an `onClick` that opens `EvidencePanel` for this claim.

**`ClaimStat`** — stat-card form:
```tsx
<ClaimStat claim={claim} label="Skip Rate" />
```
Renders LABEL (small caps) / VALUE (large, tier-colored) / tier badge / `claim.method`
(small, dim). Tapping anywhere opens `EvidencePanel`.

Both are thin and presentational — no new data shape, they consume the existing
`Claim` from `engine/types.ts`.

**`EvidencePanel` extension** — additive, not breaking. Current signature
`{ open, title, claim: string, payload, onClose }` keeps working unchanged for
existing callers. New optional prop `claimObj?: Claim`: when present, the header
shows the tier badge + `claim.method` (in place of the manual `claim` string), and
the body lists `claim.evidence: EvidenceRef[]` (each with its `kind`/`note`/`link`/
`citation`) instead of a single raw JSON payload — since a `Claim` carries an
evidence array, not one blob.

## 6. New panel: Evidence Log

`app/components/ClaimsPanel.tsx` — reads `profile.claims: Claim[]`, groups into
three sections by tier (Recorded / Derived / Inferred), each claim rendered as a
`ClaimStat` in a responsive grid. A header line states per-tier counts (e.g. "14
recorded · 9 derived · 3 inferred"). No search/filter in this pass. Empty-claims
edge case → a plain "no claims in this payload" note (defensive; `buildClaims`
always returns entries in practice).

Wired as an 8th `SidebarItem`/tab ("Evidence Log") in `ForensicDashboard.tsx`,
alongside Overview / Behavioral Signature / Timeline / Network & Influence /
Interests & Keywords / Privacy & Footprint / AI Forensic Analyst.

## 7. Retrofit: `TargetingCard.tsx` / `DemographicPanel.tsx`

Both already emit real `Claim[]` (`TargetingSegment = Claim<TargetingSegmentValue>`;
`DemographicCard.claims: Claim[]`). Replace their inline tier/confidence text
(`{seg.confidence}`, `{c.tier}{confidence}`) with `<ClaimStat claim={...} label={...} />`.
Existing 3-state gating (ok / insufficient_evidence / error) and surrounding layout
are untouched — only the claim-rendering leaves are swapped.

## 8. Error handling / degradation

- `profile.claims` missing/empty → Evidence Log shows the "no claims" note, not a
  crash.
- A `Claim` with `tier` outside the known union → `tierMeta` defaults to a neutral
  "Unknown" styling rather than throwing (defensive; `validateClaims` should prevent
  this upstream, but the component doesn't trust that blindly).
- `EvidencePanel` with `claimObj` but empty `evidence[]` → body states "no evidence
  captured for this claim" (mirrors the existing empty-payload copy).

## 9. Testing

- `tierMeta.test.ts` — exhaustive over all three tiers; each returned color matches
  the contrast-verified hex from §3; unknown tier → safe default, not a throw.
- `ClaimText.test.tsx` / `ClaimStat.test.tsx` — renders tier label + value + method
  per tier; click triggers the evidence-open callback.
- `EvidencePanel.test.tsx` — new `claimObj` path renders the tier badge + evidence
  list; the existing string-based path still passes (regression).
- `ClaimsPanel.test.tsx` — groups by tier correctly; renders per-tier counts;
  empty-state.
- `ClaimsDashboard.test.tsx` — Evidence Log tab renders `ClaimsPanel` from
  `profile.claims`.
- Retrofit regression: existing `TargetingCard.test.ts` / `DemographicPanel` tests
  (if any assert on the old inline text) updated to assert the new `ClaimStat`
  output instead — behaviorally equivalent (tier, value, confidence all still
  visible), not a functional change.

## 10. Out of scope (YAGNI / later WPs)

- `PersonaRadar` / `NicheDriftChart` retrofit → WP-3.4.
- Diagonal-hatch stamp texture, animated/case-file panel treatments → WP-3.4.
- Dossier shell/navigation rebuild → WP-3.1.
- Evidence Log search/filter.
- Full 9-component migration of non-claim chrome to shared design tokens.
- Any Python/backend change (this WP is pure frontend, consuming the payload as-is).

## 11. Open risks

- **Evidence Log could be long** (15–20+ claims in a rich export) with no
  search/filter yet — acceptable for this pass; grouped-by-tier sections keep it
  scannable, and filtering is a natural WP-3.1-shell-era addition.
- **The retrofit changes visible text** on two already-shipped panels (from raw
  "confidence 0.7" to a styled tier badge) — a visual change, not a data change;
  flagged so it isn't mistaken for scope creep during review.
