// algorithmic-mirror/app/components/__tests__/claimStyle.test.ts
import { tierMeta, renderClaimValue } from "../claimStyle";

describe("tierMeta", () => {
  test("recorded: solid ink", () => {
    const m = tierMeta("recorded");
    expect(m).toEqual({ label: "Recorded", color: "#1a1610", borderStyle: "solid", className: "tier-recorded" });
  });
  test("derived: dashed oxblood", () => {
    const m = tierMeta("derived");
    expect(m).toEqual({ label: "Derived", color: "#8b2323", borderStyle: "dashed", className: "tier-derived" });
  });
  test("inferred: dotted stamp-blue", () => {
    const m = tierMeta("inferred");
    expect(m).toEqual({ label: "Inferred", color: "#1f4e6b", borderStyle: "dotted", className: "tier-inferred" });
  });
  test("unknown tier at runtime → safe neutral default, does not throw", () => {
    expect(() => tierMeta("bogus" as any)).not.toThrow();
    const m = tierMeta("bogus" as any);
    expect(m.label).toBe("Unknown");
    expect(m.className).toBe("tier-recorded"); // fall back to the most conservative (solid/ink) styling
  });
});

describe("renderClaimValue", () => {
  test("primitive values stringify plainly", () => {
    expect(renderClaimValue("female")).toBe("female");
    expect(renderClaimValue(42)).toBe("42");
    expect(renderClaimValue(true)).toBe("true");
  });
  test("array of strings joins with comma", () => {
    expect(renderClaimValue(["Education", "Financial Services"])).toBe("Education, Financial Services");
  });
  test("array of trip-shaped objects renders city + days, not [object Object]", () => {
    const v = [{ city: "Miami", start: "2026-01-04", end: "2026-01-05", days: 2 }];
    expect(renderClaimValue(v)).toBe("Miami (2d)");
    expect(renderClaimValue(v)).not.toMatch(/object Object/);
  });
  test("plain object falls back to JSON", () => {
    expect(renderClaimValue({ a: 1 })).toBe('{"a":1}');
  });
  test("null/undefined render as empty string", () => {
    expect(renderClaimValue(null)).toBe("");
    expect(renderClaimValue(undefined)).toBe("");
  });
});
