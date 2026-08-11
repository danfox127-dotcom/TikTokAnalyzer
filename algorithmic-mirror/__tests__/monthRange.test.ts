import { unionMonths, isMonthInRange, filterEntriesByRange, quarterOverlapsRange } from "../app/utils/monthRange";

describe("unionMonths", () => {
  test("dedupes and sorts across multiple lists", () => {
    expect(unionMonths(["2025-03", "2025-01"], ["2025-02", "2025-01"], []))
      .toEqual(["2025-01", "2025-02", "2025-03"]);
  });
  test("empty input returns empty array", () => {
    expect(unionMonths([], [])).toEqual([]);
  });
});

describe("isMonthInRange", () => {
  test("inclusive at both boundaries", () => {
    expect(isMonthInRange("2025-01", ["2025-01", "2025-03"])).toBe(true);
    expect(isMonthInRange("2025-03", ["2025-01", "2025-03"])).toBe(true);
  });
  test("inside the range", () => {
    expect(isMonthInRange("2025-02", ["2025-01", "2025-03"])).toBe(true);
  });
  test("outside the range", () => {
    expect(isMonthInRange("2024-12", ["2025-01", "2025-03"])).toBe(false);
    expect(isMonthInRange("2025-04", ["2025-01", "2025-03"])).toBe(false);
  });
});

describe("filterEntriesByRange", () => {
  const entries: [string, number][] = [["2025-01", 1], ["2025-02", 2], ["2025-03", 3]];
  test("full range is a no-op", () => {
    expect(filterEntriesByRange(entries, ["2025-01", "2025-03"])).toEqual(entries);
  });
  test("narrowed range drops entries outside it", () => {
    expect(filterEntriesByRange(entries, ["2025-02", "2025-02"])).toEqual([["2025-02", 2]]);
  });
  test("range outside all entries returns empty", () => {
    expect(filterEntriesByRange(entries, ["2026-01", "2026-06"])).toEqual([]);
  });
});

describe("quarterOverlapsRange", () => {
  test("range fully inside the quarter overlaps", () => {
    expect(quarterOverlapsRange("2025-Q1", ["2025-02", "2025-02"])).toBe(true);
  });
  test("range partially overlapping the quarter's end overlaps", () => {
    // Q2 = Apr-Jun; range ends in April, inside Q2
    expect(quarterOverlapsRange("2025-Q2", ["2025-01", "2025-04"])).toBe(true);
  });
  test("range entirely after the quarter does not overlap", () => {
    // Q1 = Jan-Mar
    expect(quarterOverlapsRange("2025-Q1", ["2025-04", "2025-05"])).toBe(false);
  });
  test("range entirely before the quarter does not overlap", () => {
    // Q3 = Jul-Sep
    expect(quarterOverlapsRange("2025-Q3", ["2025-01", "2025-03"])).toBe(false);
  });
});
