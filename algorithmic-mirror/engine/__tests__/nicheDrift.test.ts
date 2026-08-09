import { buildNicheDrift } from "../nicheDrift";

// Each linger event: a creator link + its _month. Links already embed the @handle
// so handleFromLink resolves them WITHOUT a map (extractCreatorFromUrl path).
const ev = (handle: string, month: string) => ({ link: `https://www.tiktok.com/@${handle}/video/1`, _month: month });
const prof = (linger: any[]) => ({ stopwatch_metrics: { linger_events: linger } });

// n events for a given handle+month
const many = (handle: string, month: string, n: number) => Array.from({ length: n }, () => ev(handle, month));

describe("buildNicheDrift", () => {
  test("per-month distinct creators + top-5 concentration", () => {
    // Jan: 6 distinct creators (a..f), each 2 events → 12 events; top-5 = 10/12 = 83.3%
    const jan = ["a", "b", "c", "d", "e", "f"].flatMap((h) => many(h, "2026-01", 2));
    // Feb: 6 distinct creators, same shape
    const feb = ["a", "b", "c", "d", "e", "f"].flatMap((h) => many(h, "2026-02", 2));
    const res = buildNicheDrift(prof([...jan, ...feb]));
    expect(res.status).toBe("ok");
    expect(res.series.granularity).toBe("month");
    const p0 = res.series.points[0];
    expect(p0.period).toBe("2026-01");
    expect(p0.value.distinct_creators).toBe(6);
    expect(p0.value.top5_concentration_pct).toBe(83.3);
  });

  test("narrowing: distinct creators fall month-over-month → direction 'narrowing', negative slope", () => {
    // 3 months, ≥10 resolved each (no widening): distinct 6 → 4 → 2
    const m1 = ["a", "b", "c", "d", "e", "f"].flatMap((h) => many(h, "2026-01", 2)); // 12 ev, 6 distinct
    const m2 = ["a", "b", "c", "d"].flatMap((h) => many(h, "2026-02", 3));            // 12 ev, 4 distinct
    const m3 = ["a", "b"].flatMap((h) => many(h, "2026-03", 6));                       // 12 ev, 2 distinct
    const res = buildNicheDrift(prof([...m1, ...m2, ...m3]));
    expect(res.series.points.map((p) => p.value.distinct_creators)).toEqual([6, 4, 2]);
    expect(res.distinct_creators_trend.slope).toBeLessThan(0);
    expect(res.distinct_creators_trend.direction).toBe("narrowing");
    // concentration rises (fewer creators) → also "narrowing"
    expect(res.top5_concentration_trend.direction).toBe("narrowing");
  });

  test("< 3 buckets → slope null, direction insufficient_trend (series still emits)", () => {
    const m1 = ["a", "b", "c"].flatMap((h) => many(h, "2026-01", 4));  // 12 ev
    const m2 = ["a", "b", "c"].flatMap((h) => many(h, "2026-02", 4));  // 12 ev
    const res = buildNicheDrift(prof([...m1, ...m2]));
    expect(res.status).toBe("ok");
    expect(res.series.points).toHaveLength(2);
    expect(res.distinct_creators_trend.slope).toBeNull();
    expect(res.distinct_creators_trend.direction).toBe("insufficient_trend");
  });

  test("a sub-10-resolved month widens the WHOLE series to quarters", () => {
    // Jan: 12 resolved (fine). Feb: 4 resolved (sparse) → widen all to quarters.
    const jan = ["a", "b", "c"].flatMap((h) => many(h, "2026-01", 4)); // 12
    const feb = many("a", "2026-02", 4);                                // 4 → sparse
    const res = buildNicheDrift(prof([...jan, ...feb]));
    expect(res.series.granularity).toBe("quarter");
    expect(res.series.points[0].period).toBe("2026-Q1"); // Jan+Feb collapse into Q1
    expect(res.series.points).toHaveLength(1);
  });

  test("< 40% resolved → insufficient_evidence with requirements", () => {
    // 2 resolvable events + 8 unresolvable (bare links, no map) → 20% coverage
    const resolvable = many("a", "2026-01", 2);
    const bare = Array.from({ length: 8 }, () => ({ link: "https://www.tiktokv.com/share/video/999/", _month: "2026-01" }));
    const res = buildNicheDrift(prof([...resolvable, ...bare])); // no linkHandleMap → bare links unresolved
    expect(res.status).toBe("insufficient_evidence");
    expect(res.resolved_coverage_pct).toBe(20);
    expect(res.requirements?.needed).toMatch(/40%/);
  });

  test("malformed profile → error", () => {
    expect(buildNicheDrift(null as any).status).toBe("error");
    expect(buildNicheDrift({ stopwatch_metrics: { linger_events: "nope" } } as any).status).toBe("error");
  });

  test("deterministic", () => {
    const m = ["a", "b", "c"].flatMap((h) => many(h, "2026-01", 4));
    expect(buildNicheDrift(prof(m))).toEqual(buildNicheDrift(prof(m)));
  });
});
