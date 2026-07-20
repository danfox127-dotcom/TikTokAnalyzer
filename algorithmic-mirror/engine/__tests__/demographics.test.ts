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
