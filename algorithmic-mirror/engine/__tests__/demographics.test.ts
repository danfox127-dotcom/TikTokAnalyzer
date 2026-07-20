// algorithmic-mirror/engine/__tests__/demographics.test.ts
import { buildDemographics, buildGenderCard, ageToBracket, PIPEDA_CITATION } from "../demographics";
import { buildAgeCard, ageFromBirthDate } from "../demographics";
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
    expect(validateClaims(card.claims)).toEqual([]);
  });

  test("no birthdate and no behavioral signal → insufficient_evidence", () => {
    const card = buildAgeCard({ parsed: { birth_date: "" }, profile: {}, now: NOW });
    expect(card.status).toBe("insufficient_evidence");
    expect(card.claims).toEqual([]);
  });
});
