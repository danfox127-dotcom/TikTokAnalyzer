# WP-2.3 · Demographic Inference Module — Design

**Status:** approved design, pre-implementation
**Date:** 2026-07-19
**Depends on:** WP-1.5 (`Claim`/`EvidenceRef`/`Tier` in `engine/types.ts`), WP-2.2 (`targeting_card` — the interests card + spending cluster mix), the TS `parser.ts` (already exposes `birth_date`, `inferred_gender`, full `login_history`), `/api/geo`
**Unblocks:** WP-3.4 (polished demographic panel), WP-2.4 (Persona Engine, independent)
**Refs:** implementation-plan WP-2.3 / §3c; research-integration §5 (PIPEDA #2025-003)

## 1. Purpose

Reconstruct the five demographic categories a government investigation confirmed
TikTok infers about every user — **interests, location, age, gender, spending
power** — from the user's own export, each as a `Claim` anchored to the PIPEDA
#2025-003 finding. The panel's power is the two-layer framing: *TikTok is
documented to infer this category* (government citation) **and** *here is what
your export reconstructs the value to be* (our tiered claim).

Ground rule: deterministic first, honesty always. Speculative values (behavioral
age, spending) ship low-confidence with the formula exposed in the `method`
string; cards that can't meet their coverage gate say so rather than guess.

## 2. Decisions (settled during brainstorming, 2026-07-19)

1. **Architecture: client TS engine layer.** A new pure `engine/demographics.ts`
   (`buildDemographics(input)`) computed as a layer over the parsed export, like
   `targetingCard.ts`. Not Python, not touching parity-locked `buildGhostProfile`.
   The TS `parser.ts` already exposes `birth_date`, `inferred_gender`, and the full
   `login_history`, and `runEngine` returns `parsed` — so **no parser change, no
   Python change, no data-surfacing gap**.
2. **Age card = declared bracket (recorded) + behavioral estimate (inferred).** Both
   output TikTok's exact ad brackets; the behavioral estimate is a low-confidence
   (0.4) documented-signal scorer.
3. **Location card = full geo-enriched login history.** `page.tsx` enriches ALL
   distinct login IPs via `/api/geo` (dedup'd; only IPs leave the device) → an
   `ipGeo` map handed to `buildDemographics`. Home base = modal night-hours city;
   trips = ≥2 consecutive days in a non-home city. The existing 25-cap display panel
   is untouched.
4. **One cohesive spec** (shared module / UI / citation pattern), not decomposed.
   Location is the substantial engine; the other four are thin.
5. **UI: engine data + minimal panel.** Five 3-state cards in the Privacy & Footprint
   tab; the polished redaction-reveal panel is WP-3.4.

## 3. Citation framing (research §5)

PIPEDA #2025-003 (Canadian privacy commissioners, Sept 2025) documented that TikTok
maintains an **advertising age model** classifying users into `13-17 / 18-24 /
25-34 / 35-44 / 45-54 / 55+`, and infers all five categories. So the `citation`
EvidenceRef attests *that TikTok infers the category at all* — separate from our
tier for the reconstructed value. There are no per-category paragraph numbers, so
every card cites the single string `"PIPEDA #2025-003"` with a per-card note
(`"TikTok is documented to infer <category>"`).

## 4. Data flow

```
runEngine(raw) → { parsed, profile, claims, topicCandidates, … }   (sync, offline)
        │   parsed already carries: birth_date, inferred_gender, login_history (full)
page.tsx analyzeLocal (after the WP-2.2 topics step):
        │   • targeting_card = buildTargetingCard(topicResult, profile)   [already built]
        │   • collect ALL distinct IPs from parsed.login_history
        │   • POST /api/geo { ips } → ipGeo: Record<ip,{city,country_name}>  (only IPs leave)
        ▼
buildDemographics({ parsed, profile, targeting_card, ipGeo })   ← NEW pure fn, no network
        ▼
payload.demographics = DemographicModuleResult
        ▼
<DemographicPanel result={profile.demographics} />   ← Privacy & Footprint tab
```

`page.tsx` already geo-enriches the 25 display logins; the only new plumbing is
widening that to all distinct `parsed.login_history` IPs and passing the resulting
`ipGeo` map + `parsed` into the builder.

## 5. Module contract

```ts
interface DemographicCard {
  category: "interests" | "location" | "age" | "gender" | "spending";
  status: "ok" | "insufficient_evidence";
  claims: Claim[];                 // 0 when insufficient; ≥1 when ok (age has 2)
  tiktok_infers: EvidenceRef;      // { kind:"external_source", citation:"PIPEDA #2025-003",
                                   //   note:"TikTok is documented to infer <category>" }
  requirements?: { needed: string; had: string };  // when insufficient
}
interface DemographicModuleResult {
  moduleId: "demographics";
  status: "ok" | "insufficient_evidence" | "error";  // error only on malformed input
  cards: DemographicCard[];        // one per category, in a stable order
  error?: string;
}
```

Every card `claim` is a `Claim` that passes the existing `validateClaims`
(inferred ⇒ confidence in [0,1] + non-empty evidence). Each card's `claim.evidence`
carries the data receipts **plus** the PIPEDA `tiktok_infers` citation ref. Module
`status` is `ok` if ≥1 card is `ok`, `error` only on malformed `parsed`.

## 6. The five cards

### ① Gender — recorded
- Value = `parsed.inferred_gender` **verbatim**. Tier `recorded`.
- `method`: "TikTok's own inferred-gender label, taken verbatim from your export."
- Evidence: `{ kind:"settings", note:"stored inferredGender" }` + citation.
- Gate: `inferred_gender` non-empty, else `insufficient_evidence`.

### ② Age — two claims
- **Declared (recorded):** parse `parsed.birth_date` → age → map to the bracket
  (`13-17/18-24/25-34/35-44/45-54/55+`). `method` names the birthdate. Unparseable/
  absent → this claim omitted.
- **Behavioral (inferred, confidence 0.4):** a deterministic scorer starting neutral
  at `25-34`, nudged by documented signals: `night_shift_ratio > 0.3` → younger;
  youth-coded topic mix in the targeting segments → younger; long account tenure
  (login-history span) → older. Output one bracket; `method` lists each contributing
  signal and its direction. Omitted if no usable signals.
- Gate: at least one of the two claims produced, else `insufficient_evidence`.

### ③ Location — derived (AC unit-tested)
Over `parsed.login_history` (each `{ date, ip }`) joined to `ipGeo` (drop geo-less):
- **Home base** = modal city among **night-hours (23:00–03:59)** logins. Tier `derived`.
- **Work/daytime base** = modal city among **business-hours (09:00–16:59)** logins,
  surfaced only when it differs from home (satisfies the AC's "home/**work**/trip").
- **Trips** = ≥2 **consecutive calendar days** whose per-day modal city is a single
  non-home city. Tier `derived`.
- Evidence: the contributing login records (`kind:"login"`) + citation.
- Gate: **≥5 logins AND ≥5 geo-resolved days**, else `insufficient_evidence`. A
  *geo-resolved day* = a distinct calendar day with ≥1 login whose IP resolved to a
  city via `ipGeo`. Login timestamps parse via the engine's existing `parseDate`.

### ④ Spending power — inferred, conservative (confidence 0.3)
- Inputs: `profile.ad_profile` (`shop_order_count`, `product_browsing_count`) +
  high-value category presence in the targeting segments (finance / luxury /
  real-estate / tech). Output `low | mid | high`.
- Defaults to **mid**; only strong signals push **low** (near-zero commerce
  footprint) or **high** (many orders + high-value categories). `method` lists inputs.
- Gate: some commerce footprint OR a high-value cluster signal; zero of everything →
  `insufficient_evidence` (no default guess).

### ⑤ Interests — inferred, reference
- Thin adapter over the WP-2.2 `targeting_card`: if `ok`, surface its top segments as
  the interests value (tier `inferred`, carrying the targeting confidence); evidence
  references the targeting segments + citation.
- Gate: `targeting_card.status === "ok"`, else `insufficient_evidence`.

## 7. Error handling / degradation

- Missing `inferred_gender` / `birth_date` / commerce data / `targeting_card` →
  that card `insufficient_evidence` (still shows the "TikTok is documented to infer
  this" line — itself a pointed statement).
- `< 5 logins` or `< 5 geo-resolved days` → location `insufficient_evidence`.
- No `parsed` / malformed input → module `status:"error"`, no crash.
- Behavioral-age / spending never fabricate: no usable signal → the speculative
  claim is simply omitted (spending gates; age falls back to declared-only or gates).

## 8. UI

Minimal `app/components/DemographicPanel.tsx`: five cards, each 3-state
(ok / insufficient_evidence / error), warm-paper palette constants, lucide-only,
**no animation**. Each card renders the category name, the "TikTok is documented to
infer this · PIPEDA #2025-003" line, and the reconstructed value with a tier chip
(recorded/derived/inferred) + `method`. Wired into the **Privacy & Footprint tab**;
`page.tsx` attaches `demographics` to the payload and adds `demographics?:
DemographicModuleResult` to the `GhostProfile` interface. WP-3.4 replaces the styling.

## 9. Testing (maps every AC)

### Engine (TS, no network, fixtures)
- `demographics.test.ts`:
  - gender verbatim (+ absent → insufficient).
  - **(AC)** age bracket boundaries (e.g. 17→13-17, 18→18-24, 55→55+) + behavioral
    scorer direction (high night-shift → younger than declared).
  - **(AC)** location engine on **synthetic login fixtures** — home (night modal),
    work (day modal ≠ home), and a ≥2-consecutive-day trip; plus `< 5 logins` and
    `< 5 geo-days` → insufficient.
  - spending low/mid/high thresholds + zero-footprint → insufficient.
  - interests adapter from a fixture `targeting_card` (ok → segments; insufficient → gated).
  - **every produced card `claim` passes `validateClaims`**; every card carries the
    PIPEDA `tiktok_infers` citation ref.
  - malformed `parsed` → module `error`.

### Component (TS, jsdom)
- `DemographicPanel.test.tsx`: renders all five cards across the three states.

## 10. Out of scope (YAGNI / later WPs)

- Polished redaction-reveal panel + stamp states → WP-3.4.
- Any Python / server change (the module is pure client TS over `parsed`).
- Real per-paragraph PIPEDA refs → single `"PIPEDA #2025-003"` string.
- ~3 km² geo precision → we surface city-level from `/api/geo`.
- Multi-user "you vs typical" comparisons.
- Persona Engine (WP-2.4).
- Touching parity-locked `buildGhostProfile` or golden fixtures.

## 11. Open risks

- **Behavioral-age & spending are genuinely speculative.** Mitigated by low fixed
  confidence (0.4 / 0.3), the formula exposed in `method`, and omission-not-fabrication
  when signals are absent. Revisit if they read as over-claiming in practice.
- **Geo coverage.** `/api/geo` may not resolve every IP (VPNs, stale ranges); the
  ≥5-geo-resolved-days gate guards against a thin narrative. Widening geo to all
  logins sends more IPs to the server — still only IPs, consistent with the existing
  thin-endpoint posture.
- **Login timestamp parsing.** `login_history` dates must parse to local hours for the
  night/day windows; reuse the engine's existing `parseDate` helper to stay consistent
  with the rest of the port.
