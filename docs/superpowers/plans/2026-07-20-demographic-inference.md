# Demographic Inference Module (WP-2.3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruct the five demographic categories a government investigation (PIPEDA #2025-003) confirmed TikTok infers — interests, location, age, gender, spending — from the user's own export, each as a `Claim` with the two-layer framing (TikTok-is-documented-to-infer + our-tiered-value).

**Architecture:** A pure client-side TS engine layer (`engine/demographics.ts` + `engine/locationNarrative.ts`) computed over the parsed export, like `targetingCard.ts`. It reads `parsed` (birth_date, inferred_gender, login_history) + `profile` (behavioral_nodes, ad_profile) + the WP-2.2 `targeting_card` + an `ipGeo` map. `page.tsx` widens geo enrichment to all login IPs and calls `buildDemographics`; a minimal `DemographicPanel` renders it. No parser change, no Python change, no touching parity-locked code.

**Tech Stack:** TypeScript (ts-jest, `algorithmic-mirror/engine/`), React 19 / Next 16, `@testing-library/react`.

## Global Constraints

- **Pure client TS**, browser-safe: `demographics.ts` and `locationNarrative.ts` use **no `fs`/`path`/`crypto`/`process`/`require`**.
- `profile.behavioral_nodes.night_shift_ratio` is a **percentage (0–100)**, not a 0–1 ratio — the "heavy late-night" threshold is **`> 30`**.
- Every card is a `DemographicCard` carrying `tiktok_infers = pipedaCitation(category)` — an `EvidenceRef` `{ kind:"external_source", citation:"PIPEDA #2025-003", note:"TikTok is documented to infer <category>" }`. The citation string is exactly **`"PIPEDA #2025-003"`**.
- Value tiers: gender **recorded**; age.declared **recorded**, age.behavioral **inferred** (confidence 0.4); location **derived**; spending **inferred** (confidence 0.3); interests **inferred** (carries the targeting confidence).
- Every produced `claim` must pass the existing `validateClaims` (inferred ⇒ confidence in [0,1] + non-empty evidence). Each card's `claim.evidence` includes the data receipts **plus** the `tiktok_infers` citation ref.
- Location: night window **hours 23,0,1,2,3**; day window **hours 9–16**; home = modal night-hours city; work = modal day-hours city (only if ≠ home); trip = **≥2 consecutive calendar days** whose per-day modal city is a single non-home city; gate **≥5 logins AND ≥5 geo-resolved days**.
- Reads only from `parsed` / `profile` / `targeting_card` / `ipGeo`. Do **not** modify `buildGhostProfile`/`ghostProfile.ts`, `claims.ts`, `types.ts`, the parser, any Python, or golden fixtures.
- Use `getUTCHours()` / `getUTCFullYear()` for TZ-independence; **run TS tests with `TZ=UTC`**.

---

### Task 1: `demographics.ts` — module types, shared helpers, gender card, orchestrator

**Files:**
- Create: `algorithmic-mirror/engine/demographics.ts`
- Test: `algorithmic-mirror/engine/__tests__/demographics.test.ts`

**Interfaces:**
- Consumes: `Claim`, `EvidenceRef` from `./types`; `TargetingCardResult` from `./targetingCard`; `validateClaims` from `./claims` (test only).
- Produces: types `DemographicCard`, `DemographicModuleResult`, `DemographicInput`; consts `PIPEDA_CITATION`, `AGE_BRACKETS`; fns `pipedaCitation(category)`, `ageToBracket(age)`, `buildGenderCard(input)`, `buildDemographics(input)`.

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/engine/__tests__/demographics.test.ts
import { buildDemographics, buildGenderCard, ageToBracket, PIPEDA_CITATION } from "../demographics";
import { validateClaims } from "../claims";

const input = (over: any = {}) => ({ parsed: { inferred_gender: "female" }, profile: {}, ...over });

describe("demographics — module + gender", () => {
  test("ageToBracket maps ages to TikTok's exact brackets", () => {
    expect(ageToBracket(17)).toBe("13-17");
    expect(ageToBracket(18)).toBe("18-24");
    expect(ageToBracket(30)).toBe("25-34");
    expect(ageToBracket(55)).toBe("55+");
  });

  test("gender card: verbatim value, recorded tier, carries the PIPEDA citation", () => {
    const card = buildGenderCard(input());
    expect(card.status).toBe("ok");
    expect(card.claims[0].tier).toBe("recorded");
    expect(card.claims[0].value).toBe("female");
    expect(card.tiktok_infers.citation).toBe(PIPEDA_CITATION);
    expect(card.tiktok_infers.note).toMatch(/documented to infer gender/i);
    // citation ref is also in the claim's evidence
    expect(card.claims[0].evidence.some((e) => e.citation === PIPEDA_CITATION)).toBe(true);
    expect(validateClaims(card.claims)).toEqual([]);
  });

  test("gender card: absent inferred_gender → insufficient_evidence, no claims", () => {
    const card = buildGenderCard(input({ parsed: { inferred_gender: "" } }));
    expect(card.status).toBe("insufficient_evidence");
    expect(card.claims).toEqual([]);
    expect(card.requirements?.needed).toMatch(/inferredGender/i);
  });

  test("buildDemographics: ok when ≥1 card ok; module carries the gender card", () => {
    const res = buildDemographics(input());
    expect(res.moduleId).toBe("demographics");
    expect(res.status).toBe("ok");
    expect(res.cards.find((c) => c.category === "gender")?.status).toBe("ok");
  });

  test("buildDemographics: malformed input → status error, not a crash", () => {
    expect(buildDemographics(null as any).status).toBe("error");
    expect(buildDemographics({ parsed: "nope" } as any).status).toBe("error");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/demographics.test.ts`
Expected: FAIL — `Cannot find module '../demographics'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// algorithmic-mirror/engine/demographics.ts
/**
 * WP-2.3 — Demographic inference module. Pure, browser-safe. Reconstructs the five
 * categories PIPEDA #2025-003 confirmed TikTok infers (interests, location, age,
 * gender, spending), each a Claim with a two-layer framing: the government citation
 * attests TikTok infers the category at all; our tier attests the reconstructed value.
 */
import type { Claim, EvidenceRef } from "./types";
import type { TargetingCardResult } from "./targetingCard";

export const PIPEDA_CITATION = "PIPEDA #2025-003";
export const AGE_BRACKETS = ["13-17", "18-24", "25-34", "35-44", "45-54", "55+"] as const;

export interface DemographicCard {
  category: "interests" | "location" | "age" | "gender" | "spending";
  status: "ok" | "insufficient_evidence";
  claims: Claim[];
  tiktok_infers: EvidenceRef;
  requirements?: { needed: string; had: string };
}
export interface DemographicModuleResult {
  moduleId: "demographics";
  status: "ok" | "insufficient_evidence" | "error";
  cards: DemographicCard[];
  error?: string;
}
export interface DemographicInput {
  parsed: any;
  profile: any;
  targeting_card?: TargetingCardResult;
  ipGeo?: Record<string, { city: string; country_name: string }>;
  now?: Date;
}

export function pipedaCitation(category: string): EvidenceRef {
  return { kind: "external_source", citation: PIPEDA_CITATION, note: `TikTok is documented to infer ${category}` };
}

export function ageToBracket(age: number): string {
  if (age <= 17) return "13-17";
  if (age <= 24) return "18-24";
  if (age <= 34) return "25-34";
  if (age <= 44) return "35-44";
  if (age <= 54) return "45-54";
  return "55+";
}

export function buildGenderCard(input: DemographicInput): DemographicCard {
  const cite = pipedaCitation("gender");
  const g = String(input.parsed?.inferred_gender ?? "").trim();
  if (!g) {
    return {
      category: "gender", status: "insufficient_evidence", claims: [], tiktok_infers: cite,
      requirements: { needed: "TikTok's stored inferredGender", had: "absent from this export" },
    };
  }
  const claim: Claim = {
    id: "demo.gender", tier: "recorded", value: g,
    method: "TikTok's own inferred-gender label, taken verbatim from your export.",
    evidence: [{ kind: "settings", note: "stored inferredGender" }, cite],
  };
  return { category: "gender", status: "ok", claims: [claim], tiktok_infers: cite };
}

export function buildDemographics(input: DemographicInput): DemographicModuleResult {
  if (!input || !input.parsed || typeof input.parsed !== "object") {
    return { moduleId: "demographics", status: "error", error: "malformed input", cards: [] };
  }
  // Cards are added by later tasks in the spec's stable order:
  // [interests, location, age, gender, spending].
  const cards: DemographicCard[] = [buildGenderCard(input)];
  const status: DemographicModuleResult["status"] = cards.some((c) => c.status === "ok")
    ? "ok" : "insufficient_evidence";
  return { moduleId: "demographics", status, cards };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/demographics.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/demographics.ts algorithmic-mirror/engine/__tests__/demographics.test.ts
git commit -m "feat(engine): WP-2.3 demographics module scaffold + gender card"
```

---

### Task 2: Age card — declared bracket (recorded) + behavioral estimate (inferred)

**Files:**
- Modify: `algorithmic-mirror/engine/demographics.ts`
- Test: `algorithmic-mirror/engine/__tests__/demographics.test.ts` (add cases)

**Interfaces:**
- Consumes: `parseDate` from `./parseDate`; `AGE_BRACKETS`, `ageToBracket`, `pipedaCitation`, `DemographicInput`, `DemographicCard` (Task 1).
- Produces: `ageFromBirthDate(birthDate, now)`, `buildAgeCard(input)`; `buildDemographics` now emits `[buildAgeCard(input), buildGenderCard(input)]`.

- [ ] **Step 1: Write the failing test**

```ts
// add to algorithmic-mirror/engine/__tests__/demographics.test.ts
import { buildAgeCard, ageFromBirthDate } from "../demographics";

const NOW = new Date("2026-01-01T00:00:00Z");

describe("demographics — age", () => {
  test("declared age → recorded bracket claim from the birth year", () => {
    const card = buildAgeCard({ parsed: { birth_date: "1998-04-12" }, profile: {}, now: NOW });
    const declared = card.claims.find((c) => c.id === "demo.age.declared")!;
    expect(declared.tier).toBe("recorded");
    expect(declared.value).toBe("25-34"); // 2026 - 1998 = 28
  });

  test("ageFromBirthDate extracts the year; rejects junk", () => {
    expect(ageFromBirthDate("1998-04-12", NOW)).toBe(28);
    expect(ageFromBirthDate("", NOW)).toBeNull();
    expect(ageFromBirthDate("not a date", NOW)).toBeNull();
  });

  test("behavioral estimate: heavy late-night use → skews younger, inferred + low confidence", () => {
    // night_shift_ratio is a PERCENTAGE; 45 > 30 → shift one bracket younger from 25-34 → 18-24
    const card = buildAgeCard({
      parsed: { birth_date: "" }, profile: { behavioral_nodes: { night_shift_ratio: 45 } }, now: NOW,
    });
    const beh = card.claims.find((c) => c.id === "demo.age.behavioral")!;
    expect(beh.tier).toBe("inferred");
    expect(beh.confidence).toBe(0.4);
    expect(beh.value).toBe("18-24");
    expect(beh.method).toMatch(/late-night/i);
  });

  test("no birthdate and no behavioral signal → insufficient_evidence", () => {
    const card = buildAgeCard({ parsed: { birth_date: "" }, profile: {}, now: NOW });
    expect(card.status).toBe("insufficient_evidence");
    expect(card.claims).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/demographics.test.ts`
Expected: FAIL — `buildAgeCard` / `ageFromBirthDate` not exported.

- [ ] **Step 3: Write minimal implementation**

Add the import at the top of `algorithmic-mirror/engine/demographics.ts`:

```ts
import { parseDate } from "./parseDate";
```

Add these before `buildDemographics`:

```ts
// Heuristic, tunable: category substrings that skew a viewer younger.
const YOUTH_TOPICS = ["gaming", "video games", "anime", "students", "education"];

export function ageFromBirthDate(birthDate: string, now: Date): number | null {
  const m = String(birthDate ?? "").match(/(\d{4})/); // first 4-digit run = birth year
  if (!m) return null;
  const year = Number(m[1]);
  if (year < 1900 || year > now.getUTCFullYear()) return null;
  return now.getUTCFullYear() - year;
}

function loginSpanDays(parsed: any): number | null {
  const dates = (parsed?.login_history ?? [])
    .map((l: any) => parseDate(String(l?.date ?? "")))
    .filter((d: Date | null): d is Date => d != null);
  if (dates.length < 2) return null;
  const times = dates.map((d) => d.getTime());
  return (Math.max(...times) - Math.min(...times)) / 86400000;
}

export function buildAgeCard(input: DemographicInput): DemographicCard {
  const cite = pipedaCitation("age");
  const now = input.now ?? new Date();
  const claims: Claim[] = [];

  const age = ageFromBirthDate(input.parsed?.birth_date ?? "", now);
  if (age != null) {
    claims.push({
      id: "demo.age.declared", tier: "recorded", value: ageToBracket(age),
      method: "Age bracket computed from the declared birth year in your export profile.",
      evidence: [{ kind: "settings", note: "declared birthDate" }, cite],
    });
  }

  const bn = input.profile?.behavioral_nodes ?? {};
  const nightShift = Number(bn.night_shift_ratio ?? 0); // percentage 0–100
  const span = loginSpanDays(input.parsed);
  const segCats = (input.targeting_card?.claims ?? [])
    .map((c: any) => String(c?.value?.category ?? "").toLowerCase());
  const youthHit = segCats.some((c: string) => YOUTH_TOPICS.some((y) => c.includes(y)));

  const signals: string[] = [];
  let idx = 2; // start neutral at "25-34"
  if (nightShift > 30) { idx -= 1; signals.push(`heavy late-night use (${nightShift}% of activity)`); }
  if (youthHit) { idx -= 1; signals.push("youth-coded topics in your feed"); }
  if (span != null && span > 1095) { idx += 1; signals.push("long account tenure"); }
  if (signals.length) {
    idx = Math.max(0, Math.min(AGE_BRACKETS.length - 1, idx));
    claims.push({
      id: "demo.age.behavioral", tier: "inferred", value: AGE_BRACKETS[idx], confidence: 0.4,
      method: `Low-confidence behavioral estimate from: ${signals.join("; ")}.`,
      evidence: [{ kind: "video", note: "behavioral age signals" }, cite],
    });
  }

  if (!claims.length) {
    return {
      category: "age", status: "insufficient_evidence", claims: [], tiktok_infers: cite,
      requirements: { needed: "a declared birth year or usable behavioral signals", had: "neither present" },
    };
  }
  return { category: "age", status: "ok", claims, tiktok_infers: cite };
}
```

Update the `cards` array in `buildDemographics`:

```ts
  const cards: DemographicCard[] = [buildAgeCard(input), buildGenderCard(input)];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/demographics.test.ts`
Expected: PASS (all cases).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/demographics.ts algorithmic-mirror/engine/__tests__/demographics.test.ts
git commit -m "feat(engine): WP-2.3 age card — declared bracket + behavioral estimate"
```

---

### Task 3: Location card — movement narrative (`locationNarrative.ts`)

**Files:**
- Create: `algorithmic-mirror/engine/locationNarrative.ts`
- Modify: `algorithmic-mirror/engine/demographics.ts` (import + wire into orchestrator)
- Test: `algorithmic-mirror/engine/__tests__/locationNarrative.test.ts`

**Interfaces:**
- Consumes: `parseDate` from `./parseDate`; `pipedaCitation`, `DemographicCard`, `DemographicInput` from `./demographics` (a runtime-safe circular import — `pipedaCitation` is only *called* inside a function, never at module load).
- Produces: `buildLocationCard(input: DemographicInput): DemographicCard`; `buildDemographics` prepends it → `[buildLocationCard(input), buildAgeCard(input), buildGenderCard(input)]`.

- [ ] **Step 1: Write the failing test**

```ts
// algorithmic-mirror/engine/__tests__/locationNarrative.test.ts
import { buildLocationCard } from "../locationNarrative";

// Build a login at a given datetime + ip. NOTE: no trailing "Z" — the engine's
// parseDate accepts "YYYY-MM-DDTHH:MM:SS" (and space form) but NOT a Z suffix;
// it builds the Date via Date.UTC, so these hours read back via getUTCHours().
const login = (date: string, ip: string) => ({ date, ip });
const geo = (m: Record<string, string>) =>
  Object.fromEntries(Object.entries(m).map(([ip, city]) => [ip, { city, country_name: "US" }]));

describe("buildLocationCard", () => {
  test("home base = modal night-hours city; work = modal day-hours city when it differs", () => {
    // 5 distinct days. Nights (hour 02) in Chicago; days (hour 12) in New York.
    const parsed = {
      login_history: [
        login("2026-01-01T02:00:00", "1"), login("2026-01-01T12:00:00", "2"),
        login("2026-01-02T02:00:00", "1"), login("2026-01-02T12:00:00", "2"),
        login("2026-01-03T02:00:00", "1"), login("2026-01-03T12:00:00", "2"),
        login("2026-01-04T02:00:00", "1"), login("2026-01-04T12:00:00", "2"),
        login("2026-01-05T02:00:00", "1"), login("2026-01-05T12:00:00", "2"),
      ],
    };
    const card = buildLocationCard({ parsed, profile: {}, ipGeo: geo({ "1": "Chicago", "2": "New York" }) });
    expect(card.status).toBe("ok");
    const home = card.claims.find((c) => c.id === "demo.location.home")!;
    const work = card.claims.find((c) => c.id === "demo.location.work")!;
    expect(home.value).toBe("Chicago");
    expect(home.tier).toBe("derived");
    expect(work.value).toBe("New York");
  });

  test("trip = ≥2 consecutive days in a single non-home city", () => {
    const parsed = {
      login_history: [
        login("2026-01-01T02:00:00", "h"), login("2026-01-02T02:00:00", "h"),
        login("2026-01-03T02:00:00", "h"),
        login("2026-01-04T02:00:00", "t"), login("2026-01-05T02:00:00", "t"), // 2 consecutive away
        login("2026-01-06T02:00:00", "h"),
      ],
    };
    const card = buildLocationCard({ parsed, profile: {}, ipGeo: geo({ h: "Denver", t: "Miami" }) });
    const trips = card.claims.find((c) => c.id === "demo.location.trips")!;
    expect(trips.value).toEqual([{ city: "Miami", start: "2026-01-04", end: "2026-01-05", days: 2 }]);
  });

  test("single away-day is NOT a trip", () => {
    const parsed = {
      login_history: [
        login("2026-01-01T02:00:00", "h"), login("2026-01-02T02:00:00", "h"),
        login("2026-01-03T02:00:00", "t"),                              // one day away only
        login("2026-01-04T02:00:00", "h"), login("2026-01-05T02:00:00", "h"),
      ],
    };
    const card = buildLocationCard({ parsed, profile: {}, ipGeo: geo({ h: "Denver", t: "Miami" }) });
    expect(card.claims.find((c) => c.id === "demo.location.trips")).toBeUndefined();
  });

  test("< 5 geo-resolved days → insufficient_evidence", () => {
    const parsed = {
      login_history: [
        login("2026-01-01T02:00:00", "h"), login("2026-01-02T02:00:00", "h"),
        login("2026-01-03T02:00:00", "h"), login("2026-01-04T02:00:00", "x"), // "x" has no geo
        login("2026-01-05T02:00:00", "x"),
      ],
    };
    const card = buildLocationCard({ parsed, profile: {}, ipGeo: geo({ h: "Denver" }) });
    expect(card.status).toBe("insufficient_evidence");
    expect(card.requirements?.needed).toMatch(/geo-resolved days/i);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/locationNarrative.test.ts`
Expected: FAIL — `Cannot find module '../locationNarrative'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// algorithmic-mirror/engine/locationNarrative.ts
/**
 * WP-2.3 — location movement narrative. Pure, browser-safe. Over the full login
 * history joined to an IP→city map: home base (modal night-hours city), work base
 * (modal day-hours city, only if it differs), and trips (≥2 consecutive days in a
 * single non-home city). Emits only IDs/cities/derived facts — no titles, no raw IPs.
 */
import { parseDate } from "./parseDate";
import type { Claim } from "./types";
import { pipedaCitation, type DemographicCard, type DemographicInput } from "./demographics";

const NIGHT_HOURS = new Set([23, 0, 1, 2, 3]);
const DAY_HOURS = new Set([9, 10, 11, 12, 13, 14, 15, 16]);
const MIN_LOGINS = 5;
const MIN_GEO_DAYS = 5;

interface GeoLogin { city: string; day: string; hour: number; }

function modalCity(cities: string[]): string | null {
  if (!cities.length) return null;
  const counts = new Map<string, number>();
  for (const c of cities) counts.set(c, (counts.get(c) ?? 0) + 1);
  // highest count, ties broken by city name ascending (stable/deterministic)
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))[0][0];
}

function isNextDay(a: string, b: string): boolean {
  const da = new Date(a + "T00:00:00Z").getTime();
  const db = new Date(b + "T00:00:00Z").getTime();
  return db - da === 86400000;
}

function detectTrips(geoLogins: GeoLogin[], home: string) {
  const byDay = new Map<string, string[]>();
  for (const g of geoLogins) {
    if (!byDay.has(g.day)) byDay.set(g.day, []);
    byDay.get(g.day)!.push(g.city);
  }
  const dayCity = [...byDay.entries()]
    .map(([day, cities]) => ({ day, city: modalCity(cities)! }))
    .sort((a, b) => (a.day < b.day ? -1 : 1));

  const trips: { city: string; start: string; end: string; days: number }[] = [];
  let i = 0;
  while (i < dayCity.length) {
    const city = dayCity[i].city;
    let j = i;
    while (j + 1 < dayCity.length && dayCity[j + 1].city === city && isNextDay(dayCity[j].day, dayCity[j + 1].day)) j++;
    const runLen = j - i + 1;
    if (city !== home && runLen >= 2) trips.push({ city, start: dayCity[i].day, end: dayCity[j].day, days: runLen });
    i = j + 1;
  }
  return trips;
}

export function buildLocationCard(input: DemographicInput): DemographicCard {
  const cite = pipedaCitation("location");
  const logins: any[] = input.parsed?.login_history ?? [];
  const ipGeo = input.ipGeo ?? {};

  const geoLogins: GeoLogin[] = [];
  for (const l of logins) {
    const d = parseDate(String(l?.date ?? ""));
    const g = ipGeo[String(l?.ip ?? "")];
    if (!d || !g?.city) continue;
    geoLogins.push({ city: g.city, day: d.toISOString().slice(0, 10), hour: d.getUTCHours() });
  }
  const geoDays = new Set(geoLogins.map((g) => g.day));

  if (logins.length < MIN_LOGINS || geoDays.size < MIN_GEO_DAYS) {
    return {
      category: "location", status: "insufficient_evidence", claims: [], tiktok_infers: cite,
      requirements: {
        needed: `≥${MIN_LOGINS} logins and ≥${MIN_GEO_DAYS} geo-resolved days`,
        had: `${logins.length} logins, ${geoDays.size} geo-resolved days`,
      },
    };
  }

  const home =
    modalCity(geoLogins.filter((g) => NIGHT_HOURS.has(g.hour)).map((g) => g.city)) ??
    modalCity(geoLogins.map((g) => g.city))!;
  const work = modalCity(geoLogins.filter((g) => DAY_HOURS.has(g.hour)).map((g) => g.city));

  const claims: Claim[] = [{
    id: "demo.location.home", tier: "derived", value: home,
    method: "Most frequent city among your 11pm–4am logins.",
    evidence: [{ kind: "login", note: "night-hours logins" }, cite],
  }];
  if (work && work !== home) {
    claims.push({
      id: "demo.location.work", tier: "derived", value: work,
      method: "Most frequent city among your 9am–5pm logins.",
      evidence: [{ kind: "login", note: "day-hours logins" }, cite],
    });
  }
  const trips = detectTrips(geoLogins, home);
  if (trips.length) {
    claims.push({
      id: "demo.location.trips", tier: "derived", value: trips,
      method: "Cities where you logged in for ≥2 consecutive days away from home.",
      evidence: [{ kind: "login", note: `${trips.length} trip(s)` }, cite],
    });
  }
  return { category: "location", status: "ok", claims, tiktok_infers: cite };
}
```

Wire it into `algorithmic-mirror/engine/demographics.ts` — add the import at the top:

```ts
import { buildLocationCard } from "./locationNarrative";
```

and update the `cards` array in `buildDemographics`:

```ts
  const cards: DemographicCard[] = [buildLocationCard(input), buildAgeCard(input), buildGenderCard(input)];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/locationNarrative.test.ts engine/__tests__/demographics.test.ts`
Expected: PASS (both suites). Then the full engine suite to confirm no regression:
Run: `cd algorithmic-mirror && TZ=UTC npx jest engine`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/locationNarrative.ts algorithmic-mirror/engine/demographics.ts algorithmic-mirror/engine/__tests__/locationNarrative.test.ts
git commit -m "feat(engine): WP-2.3 location movement narrative — home/work/trips"
```

---

### Task 4: Spending card — conservative low/mid/high proxy

**Files:**
- Modify: `algorithmic-mirror/engine/demographics.ts`
- Test: `algorithmic-mirror/engine/__tests__/demographics.test.ts` (add cases)

**Interfaces:**
- Consumes: `profile.ad_profile` (`shop_order_count`, `product_browsing_count`); `targeting_card.claims[].value.category`; `pipedaCitation`, `DemographicInput`, `DemographicCard`.
- Produces: `buildSpendingCard(input)`; `buildDemographics` cards become `[buildLocationCard, buildAgeCard, buildGenderCard, buildSpendingCard]`.

- [ ] **Step 1: Write the failing test**

```ts
// add to algorithmic-mirror/engine/__tests__/demographics.test.ts
import { buildSpendingCard } from "../demographics";

const seg = (category: string) => ({ id: `targeting.segment.${category}`, tier: "inferred", confidence: 0.7,
  evidence: [{ kind: "video", id: "1" }], method: "m", value: { category } });
const tc = (cats: string[]) => ({ moduleId: "targeting_card", status: "ok", taxonomy_version: "v",
  counts: { declared_ad_interest_count: 0, segment_count: cats.length, confirmed_count: 0 },
  claims: cats.map(seg) });

describe("demographics — spending", () => {
  test("many orders + a high-value interest → high, inferred, conf 0.3", () => {
    const card = buildSpendingCard({
      parsed: {}, profile: { ad_profile: { shop_order_count: 6, product_browsing_count: 10 } },
      targeting_card: tc(["Financial Services"]) as any,
    });
    expect(card.status).toBe("ok");
    expect(card.claims[0].value).toBe("high");
    expect(card.claims[0].tier).toBe("inferred");
    expect(card.claims[0].confidence).toBe(0.3);
  });

  test("near-zero footprint → low", () => {
    const card = buildSpendingCard({
      parsed: {}, profile: { ad_profile: { shop_order_count: 0, product_browsing_count: 1 } },
      targeting_card: tc(["Education"]) as any,
    });
    expect(card.claims[0].value).toBe("low");
  });

  test("no orders, no browsing, no high-value interest → insufficient_evidence", () => {
    const card = buildSpendingCard({ parsed: {}, profile: { ad_profile: {} }, targeting_card: tc(["Education"]) as any });
    expect(card.status).toBe("insufficient_evidence");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/demographics.test.ts`
Expected: FAIL — `buildSpendingCard` not exported.

- [ ] **Step 3: Write minimal implementation**

Add before `buildDemographics` in `algorithmic-mirror/engine/demographics.ts`:

```ts
// Category substrings that signal higher spending power (income proxy).
const HIGH_VALUE_CATEGORIES = ["financial", "finance", "luxury", "real estate", "investment", "wealth"];

export function buildSpendingCard(input: DemographicInput): DemographicCard {
  const cite = pipedaCitation("spending");
  const ad = input.profile?.ad_profile ?? {};
  const orders = Number(ad.shop_order_count ?? 0);
  const browsing = Number(ad.product_browsing_count ?? 0);
  const segCats = (input.targeting_card?.claims ?? [])
    .map((c: any) => String(c?.value?.category ?? "").toLowerCase());
  const highValue = segCats.some((c: string) => HIGH_VALUE_CATEGORIES.some((h) => c.includes(h)));

  if (orders === 0 && browsing === 0 && !highValue) {
    return {
      category: "spending", status: "insufficient_evidence", claims: [], tiktok_infers: cite,
      requirements: { needed: "shop orders, product browsing, or a high-value interest", had: "no commerce footprint" },
    };
  }

  let level = "mid";
  if (orders >= 5 && highValue) level = "high";
  else if (orders === 0 && browsing <= 2 && !highValue) level = "low";

  const claim: Claim = {
    id: "demo.spending", tier: "inferred", value: level, confidence: 0.3,
    method: `Conservative proxy from ${orders} shop orders, ${browsing} products browsed${highValue ? ", high-value interests present" : ""}.`,
    evidence: [{ kind: "order", note: `${orders} orders / ${browsing} browsed` }, cite],
  };
  return { category: "spending", status: "ok", claims: [claim], tiktok_infers: cite };
}
```

Update the `cards` array in `buildDemographics`:

```ts
  const cards: DemographicCard[] = [
    buildLocationCard(input), buildAgeCard(input), buildGenderCard(input), buildSpendingCard(input),
  ];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/demographics.test.ts`
Expected: PASS (all cases).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/demographics.ts algorithmic-mirror/engine/__tests__/demographics.test.ts
git commit -m "feat(engine): WP-2.3 spending card — conservative low/mid/high proxy"
```

---

### Task 5: Interests card — targeting-card adapter (completes the orchestrator)

**Files:**
- Modify: `algorithmic-mirror/engine/demographics.ts`
- Test: `algorithmic-mirror/engine/__tests__/demographics.test.ts` (add cases)

**Interfaces:**
- Consumes: `targeting_card` (`TargetingCardResult`) from the input.
- Produces: `buildInterestsCard(input)`; `buildDemographics` reaches its final spec order `[interests, location, age, gender, spending]`.

- [ ] **Step 1: Write the failing test**

```ts
// add to algorithmic-mirror/engine/__tests__/demographics.test.ts
import { buildInterestsCard } from "../demographics";

describe("demographics — interests + full module order", () => {
  test("ok targeting_card → interests card surfaces its segment categories (inferred)", () => {
    const card = buildInterestsCard({ parsed: {}, profile: {}, targeting_card: tc(["Education", "Financial Services"]) as any });
    expect(card.status).toBe("ok");
    expect(card.claims[0].tier).toBe("inferred");
    expect(card.claims[0].value).toEqual(["Education", "Financial Services"]);
    expect(card.claims[0].confidence).toBe(0.7);
  });

  test("missing / insufficient targeting_card → interests insufficient_evidence", () => {
    expect(buildInterestsCard({ parsed: {}, profile: {} }).status).toBe("insufficient_evidence");
    expect(buildInterestsCard({ parsed: {}, profile: {},
      targeting_card: { moduleId: "targeting_card", status: "insufficient_evidence", taxonomy_version: "v",
        claims: [], counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 } } as any,
    }).status).toBe("insufficient_evidence");
  });

  test("full module: cards are in the stable order interests, location, age, gender, spending", () => {
    const res = buildDemographics({ parsed: { inferred_gender: "male" }, profile: {}, targeting_card: tc(["Education"]) as any });
    expect(res.cards.map((c) => c.category)).toEqual(["interests", "location", "age", "gender", "spending"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/demographics.test.ts`
Expected: FAIL — `buildInterestsCard` not exported / card order wrong.

- [ ] **Step 3: Write minimal implementation**

Add before `buildDemographics` in `algorithmic-mirror/engine/demographics.ts`:

```ts
export function buildInterestsCard(input: DemographicInput): DemographicCard {
  const cite = pipedaCitation("interests");
  const tc = input.targeting_card;
  if (!tc || tc.status !== "ok" || !tc.claims?.length) {
    return {
      category: "interests", status: "insufficient_evidence", claims: [], tiktok_infers: cite,
      requirements: { needed: "the Targeting Card (LLM topic pass)", had: tc ? tc.status : "no targeting card" },
    };
  }
  const categories = tc.claims.slice(0, 5).map((c: any) => String(c?.value?.category ?? "")).filter(Boolean);
  const confidence = Math.max(...tc.claims.map((c: any) => Number(c?.confidence ?? 0)));
  const claim: Claim = {
    id: "demo.interests", tier: "inferred", value: categories, confidence,
    method: "Top advertiser-taxonomy segments from your watched-video topics (see the Targeting Card).",
    evidence: [{ kind: "video", note: `${tc.claims.length} targeting segments` }, cite],
  };
  return { category: "interests", status: "ok", claims: [claim], tiktok_infers: cite };
}
```

Update the `cards` array in `buildDemographics` to its final form:

```ts
  const cards: DemographicCard[] = [
    buildInterestsCard(input), buildLocationCard(input), buildAgeCard(input),
    buildGenderCard(input), buildSpendingCard(input),
  ];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest engine/__tests__/demographics.test.ts`
Expected: PASS (all cases). Then the full engine suite:
Run: `cd algorithmic-mirror && TZ=UTC npx jest engine`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/engine/demographics.ts algorithmic-mirror/engine/__tests__/demographics.test.ts
git commit -m "feat(engine): WP-2.3 interests card + final module order"
```

---

### Task 6: `DemographicPanel.tsx` — minimal five-card render

**Files:**
- Create: `algorithmic-mirror/app/components/DemographicPanel.tsx`
- Test: `algorithmic-mirror/__tests__/DemographicPanel.test.tsx`

**Interfaces:**
- Consumes: `DemographicModuleResult`, `DemographicCard` from `../../engine/demographics`.
- Produces: `export function DemographicPanel({ result }: { result?: DemographicModuleResult })`.

- [ ] **Step 1: Write the failing test**

```tsx
// algorithmic-mirror/__tests__/DemographicPanel.test.tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { DemographicPanel } from "../app/components/DemographicPanel";
import type { DemographicModuleResult } from "../engine/demographics";

const cite = { kind: "external_source" as const, citation: "PIPEDA #2025-003", note: "TikTok is documented to infer gender" };
const ok: DemographicModuleResult = {
  moduleId: "demographics", status: "ok",
  cards: [
    { category: "gender", status: "ok", tiktok_infers: cite,
      claims: [{ id: "demo.gender", tier: "recorded", value: "female", method: "verbatim label.", evidence: [cite] }] },
    { category: "location", status: "insufficient_evidence", tiktok_infers: { ...cite, note: "TikTok is documented to infer location" },
      claims: [], requirements: { needed: "≥5 logins and ≥5 geo-resolved days", had: "2 logins" } },
  ],
};

describe("DemographicPanel", () => {
  test("renders each card with the PIPEDA line and the reconstructed value / gated state", () => {
    render(<DemographicPanel result={ok} />);
    expect(screen.getAllByText(/PIPEDA #2025-003/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("female")).toBeInTheDocument();          // ok card value
    expect(screen.getByText(/recorded/i)).toBeInTheDocument();       // tier chip
    expect(screen.getByText(/geo-resolved days/i)).toBeInTheDocument(); // gated card requirements
  });

  test("module error → a plain error note", () => {
    render(<DemographicPanel result={{ moduleId: "demographics", status: "error", error: "malformed input", cards: [] }} />);
    expect(screen.getByText(/unavailable|error/i)).toBeInTheDocument();
  });

  test("undefined result renders nothing", () => {
    const { container } = render(<DemographicPanel result={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/DemographicPanel.test.tsx`
Expected: FAIL — `Cannot find module '../app/components/DemographicPanel'`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// algorithmic-mirror/app/components/DemographicPanel.tsx
"use client";
/**
 * WP-2.3 — minimal Demographic panel. Renders the five inference cards from payload
 * alone (ok / insufficient_evidence per card; error at the module level). Each card
 * shows the "TikTok is documented to infer this · PIPEDA #2025-003" line plus the
 * reconstructed value + tier. The polished redaction-reveal panel is WP-3.4.
 */
import { ShieldAlert, Lock, AlertTriangle } from "lucide-react";
import type { DemographicModuleResult, DemographicCard } from "../../engine/demographics";

const BORDER = "rgba(26, 22, 16, 0.16)";
const INK = "#1a1610";
const INK_DIM = "rgba(26, 22, 16, 0.62)";
const ACCENT = "#8b2323";

const LABELS: Record<DemographicCard["category"], string> = {
  interests: "Interests", location: "Location", age: "Age range", gender: "Gender", spending: "Spending power",
};

function renderValue(v: unknown): string {
  if (Array.isArray(v)) return v.join(", ");
  if (v && typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function Card({ card }: { card: DemographicCard }) {
  return (
    <div style={{ padding: "12px 14px", border: `1px solid ${BORDER}`, display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ fontWeight: 600, color: INK }}>{LABELS[card.category]}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: INK_DIM }}>
        <ShieldAlert size={13} /> TikTok is documented to infer this · {card.tiktok_infers.citation}
      </div>
      {card.status === "ok" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {card.claims.map((c) => (
            <div key={c.id} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <div>
                <span style={{ color: INK, fontWeight: 500 }}>{renderValue(c.value)}</span>{" "}
                <span style={{ fontSize: 10, textTransform: "uppercase", color: ACCENT, letterSpacing: "0.05em" }}>
                  {c.tier}{c.confidence != null ? ` · ${c.confidence}` : ""}
                </span>
              </div>
              <div style={{ fontSize: 10, color: INK_DIM }}>{c.method}</div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: "flex", gap: 6, alignItems: "flex-start", fontSize: 11, color: INK_DIM }}>
          <Lock size={13} style={{ marginTop: 1, flexShrink: 0 }} />
          <span>Not enough in your export to reconstruct this. Needs {card.requirements?.needed}; have {card.requirements?.had}.</span>
        </div>
      )}
    </div>
  );
}

export function DemographicPanel({ result }: { result?: DemographicModuleResult }) {
  if (!result) return null;
  if (result.status === "error") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: INK_DIM, fontSize: 12 }}>
        <AlertTriangle size={15} /> Demographic analysis unavailable ({result.error ?? "error"}).
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
      {result.cards.map((c) => <Card key={c.category} card={c} />)}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/DemographicPanel.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/DemographicPanel.tsx algorithmic-mirror/__tests__/DemographicPanel.test.tsx
git commit -m "feat(ui): WP-2.3 minimal DemographicPanel — five inference cards"
```

---

### Task 7: Wire demographics into the analyze flow + Privacy tab

**Files:**
- Modify: `algorithmic-mirror/app/page.tsx` (widen geo enrichment; call `buildDemographics`; add to payload)
- Modify: `algorithmic-mirror/app/components/GhostProfileHUD.tsx` (add `demographics?` to `GhostProfile`)
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx` (render in the Privacy tab)
- Test: `algorithmic-mirror/__tests__/DemographicPanelDashboard.test.tsx`

**Interfaces:**
- Consumes: `buildDemographics`, `DemographicModuleResult` from `../engine/demographics`; `DemographicPanel` from `./DemographicPanel`; the existing `analyzeLocal` `out` (`out.parsed`, `out.profile`), `postEnrich`, and the WP-2.2 `targeting_card` variable in `page.tsx`.
- Produces: `payload.demographics`; a rendered `<DemographicPanel>` in the Privacy & Footprint tab.

- [ ] **Step 1: Write the failing test**

```tsx
// algorithmic-mirror/__tests__/DemographicPanelDashboard.test.tsx
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ForensicDashboard } from "../app/components/ForensicDashboard";
import type { GhostProfile } from "../app/components/GhostProfileHUD";

jest.mock("../app/components/CreatorGraph", () => ({ CreatorGraph: () => <div data-testid="creator-graph" /> }));
jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, {
    get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
      const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
      void initial; void animate; void exit; void transition; void whileHover; void whileTap;
      return React.createElement(tag, dom, children as React.ReactNode);
    },
  });
  return { motion, AnimatePresence: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children) };
});

const cite = { kind: "external_source" as const, citation: "PIPEDA #2025-003", note: "TikTok is documented to infer gender" };
const profile = {
  primary_archetype: { name: "The Balanced Viewer" },
  demographics: {
    moduleId: "demographics", status: "ok",
    cards: [{ category: "gender", status: "ok", tiktok_infers: cite,
      claims: [{ id: "demo.gender", tier: "recorded", value: "female", method: "verbatim label.", evidence: [cite] }] }],
  },
} as unknown as GhostProfile;

test("Privacy tab renders the Demographic panel from the payload", () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Privacy & Footprint/i));
  expect(screen.getByText(/What TikTok Infers About You/i)).toBeInTheDocument();
  expect(screen.getByText(/PIPEDA #2025-003/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/DemographicPanelDashboard.test.tsx`
Expected: FAIL — no "What TikTok Infers About You" panel. If the mount throws on a missing profile field, add that field to the minimal `profile` object (keep it minimal).

- [ ] **Step 3a: Add `demographics` to the `GhostProfile` interface**

In `algorithmic-mirror/app/components/GhostProfileHUD.tsx`, add the import and the optional field (mirroring `targeting_card?`):

```ts
import type { DemographicModuleResult } from "../../engine/demographics";
```
```ts
  // WP-2.3 — the five demographic inference cards (present in browser-local payloads).
  demographics?: DemographicModuleResult;
```

- [ ] **Step 3b: Render the panel in the Privacy tab**

In `algorithmic-mirror/app/components/ForensicDashboard.tsx`, add the import near the other component imports:

```tsx
import { DemographicPanel } from "./DemographicPanel";
```

Inside the `{activeTab === "privacy" && ( … )}` block, add a full-width panel (reuse the existing `DashboardPanel`/`SectionTitle`, choosing a panel number that follows the last one already in that tab):

```tsx
                <div className="md:col-span-2">
                  <DashboardPanel label="Demographic Reconstruction" accent={ACCENT}>
                    <SectionTitle>What TikTok Infers About You</SectionTitle>
                    <DemographicPanel result={profile.demographics} />
                  </DashboardPanel>
                </div>
```

- [ ] **Step 3c: Widen geo enrichment + build demographics in `analyzeLocal`**

In `algorithmic-mirror/app/page.tsx`, add imports near the other engine/util imports:

```ts
import { buildDemographics } from "../engine/demographics";
```

Replace the existing geo-enrichment block (the one that collects IPs from `recent_logins` and posts `/api/geo`) with a version that enriches **all** login IPs and keeps the `ipGeo` map:

```ts
  // Geo over ALL login IPs (for the WP-2.3 location card), not just the 25 display
  // logins. Still sends only IPs — strictly less than the export.
  const displayLogins: any[] = out.profile.digital_footprint?.recent_logins ?? [];
  const allLogins: any[] = out.parsed?.login_history ?? [];
  const ips = [...new Set([...allLogins, ...displayLogins]
    .map((l) => l?.ip).filter((ip: string): ip is string => !!ip))];
  let ipGeo: Record<string, { city: string; country_name: string }> = {};
  if (ips.length) {
    const geoResp = await postEnrich<{ geo: Record<string, { city: string; country_name: string }> }>(
      "/api/geo", { ips });
    if (geoResp?.geo) {
      ipGeo = geoResp.geo;
      for (const l of displayLogins) {
        const g = ipGeo[l.ip];
        if (g) { l.city = g.city; l.country_name = g.country_name; }
      }
    }
  }
```

Then, after the WP-2.2 `targeting_card` block (so `targeting_card` and `ipGeo` are both in scope) and before the payload `return`, add (best-effort, never blocks the dossier):

```ts
  let demographics;
  try {
    demographics = buildDemographics({
      parsed: out.parsed, profile: out.profile, targeting_card, ipGeo, now: new Date(),
    });
  } catch {
    demographics = undefined;
  }
```

Add `demographics` to the returned payload object (alongside `targeting_card`):

```ts
    targeting_card,
    demographics,
    _local_mode: true,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/DemographicPanelDashboard.test.tsx`
Expected: PASS. Then the whole frontend + engine suite:
Run: `cd algorithmic-mirror && TZ=UTC npx jest`
Expected: PASS (all suites).

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/page.tsx algorithmic-mirror/app/components/GhostProfileHUD.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx algorithmic-mirror/__tests__/DemographicPanelDashboard.test.tsx
git commit -m "feat(app): WP-2.3 wire demographics into analyze flow + Privacy tab"
```

---

## Self-Review

**Spec coverage:**
- Client-TS engine layer, reads parsed/profile/targeting/ipGeo, no parser/Python change → Tasks 1–5 (`demographics.ts`, `locationNarrative.ts`). ✓
- Two-layer framing (PIPEDA citation on every card + our value tier) → `pipedaCitation` + `tiktok_infers` on every card, asserted in Tasks 1/6. ✓
- Gender recorded verbatim; absent → insufficient → Task 1. ✓
- Age declared (recorded bracket) + behavioral (inferred 0.4, night-shift %>30 / topics / tenure) → Task 2. ✓
- Location home (night modal) + work (day modal ≠ home) + trips (≥2 consecutive non-home days); gate ≥5 logins AND ≥5 geo-days → Task 3 (synthetic fixtures cover home/work/trip/gate — the AC). ✓
- Spending low/mid/high conservative (inferred 0.3); zero footprint → insufficient → Task 4. ✓
- Interests adapter over targeting_card → Task 5. ✓
- Module: ok if ≥1 card ok, error on malformed; stable card order → Tasks 1 & 5. ✓
- Minimal 3-state panel, lucide-only, no animation, Privacy tab → Tasks 6 & 7. ✓
- Every claim passes `validateClaims` → asserted in Task 1 (gender) and implied by construction; the location/age/spending claims all carry non-empty evidence + confidence where inferred.
- Geo widened to all login IPs; `demographics` in payload; `GhostProfile.demographics` field → Task 7. ✓

**Placeholder scan:** none — every code and test step is complete. The "choose a panel number that follows the last one" and "add missing profile field if the mount throws" notes are bounded instructions against existing code, not missing logic.

**Type consistency:** `DemographicCard`/`DemographicModuleResult`/`DemographicInput` defined in Task 1, imported unchanged in Tasks 3/6/7. `buildLocationCard` (Task 3) returns `DemographicCard`. `pipedaCitation` returns `EvidenceRef` (from `types.ts`). `TargetingCardResult`/segment `value.category` consumed in Tasks 2/4/5 match the WP-2.2 shape. `night_shift_ratio` treated as a percentage (`> 30`) consistently. `buildDemographics` input shape matches the Task 7 call site.

**Note for the implementer:** the circular import between `demographics.ts` (imports `buildLocationCard`) and `locationNarrative.ts` (imports `pipedaCitation`/types) is runtime-safe because every cross-module reference is used only *inside* functions, never at module load — do not try to "fix" it by inlining. Run tests with `TZ=UTC` so the night/day hour windows are deterministic.
