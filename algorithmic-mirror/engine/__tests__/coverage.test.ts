/**
 * WP-1.2 — coverage detection & gating (new functionality; unit-tested, not a
 * parity port). Covers the AC: a 20-day window → insufficient_evidence for
 * persona/attribution and ok for stopwatch basics; coverage present in payload.
 */
import { computeCoverage, requireCoverage, evaluateGates, Coverage } from "../coverage";
import { runEngine } from "../pipeline";

function mkCoverage(days: number, loginCount: number): Coverage {
  return {
    overall: { start: "2024-01-01T00:00:00.000Z", end: "2024-01-01T00:00:00.000Z", days },
    perSection: { logins: { start: "", end: "", count: loginCount } },
  };
}

describe("computeCoverage", () => {
  const parsed = {
    browsing_history: [
      { date: "2024-01-01 00:00:00", link: "x" },
      { date: "2024-01-21 00:00:00", link: "y" }, // 20-day span
    ],
    searches: [{ date: "2024-01-05 10:00:00", term: "t" }],
    login_history: [
      { date: "2024-01-02 08:00:00" }, { date: "2024-01-10 08:00:00" }, { date: "2024-01-15 08:00:00" },
    ],
    off_tiktok_activity: [{ x: 1 }, { y: 2 }], // no dates
  };
  const cov = computeCoverage(parsed);

  test("overall span is 20 days", () => {
    expect(cov.overall.days).toBe(20);
    expect(cov.overall.start).toBe("2024-01-01T00:00:00.000Z");
    expect(cov.overall.end).toBe("2024-01-21T00:00:00.000Z");
  });

  test("per-section counts and windows", () => {
    expect(cov.perSection.watch_history).toEqual({
      start: "2024-01-01T00:00:00.000Z", end: "2024-01-21T00:00:00.000Z", count: 2,
    });
    expect(cov.perSection.logins.count).toBe(3);
    expect(cov.perSection.searches.count).toBe(1);
    // dateless section: counted but no window
    expect(cov.perSection.off_platform).toEqual({ start: "", end: "", count: 2 });
    // absent section: zero count
    expect(cov.perSection.orders).toEqual({ start: "", end: "", count: 0 });
  });

  test("empty parsed → zero coverage", () => {
    const c = computeCoverage({});
    expect(c.overall).toEqual({ start: "", end: "", days: 0 });
    expect(c.perSection.watch_history.count).toBe(0);
  });
});

describe("gating — the 20-day AC", () => {
  const cov = mkCoverage(20, 3);
  const gates = evaluateGates(cov, { consciousViews: 100 });

  test("stopwatch basics are ok", () => {
    expect(gates.stopwatch.status).toBe("ok");
  });

  test("persona and attribution are insufficient", () => {
    expect(gates.persona.status).toBe("insufficient_evidence");
    expect(gates.attribution.status).toBe("insufficient_evidence");
    expect(gates.rabbit_hole.status).toBe("insufficient_evidence");
    expect(gates.movement.status).toBe("insufficient_evidence"); // 3 < 5 logins
  });

  test("insufficient result explains what was needed vs had", () => {
    expect(gates.persona.requirements).toEqual({
      needed: "≥30 days and ≥500 conscious views",
      had: "20 days, 100 conscious views",
    });
  });
});

describe("gating — sufficiency", () => {
  test("wide window + enough views/logins → all ok", () => {
    const gates = evaluateGates(mkCoverage(100, 6), { consciousViews: 600 });
    for (const id of ["stopwatch", "persona", "rabbit_hole", "movement", "attribution", "forecast"]) {
      expect(gates[id].status).toBe("ok");
    }
  });

  test("days sufficient but views short → persona still gated", () => {
    const g = requireCoverage("persona", mkCoverage(100, 6), { consciousViews: 400 });
    expect(g.status).toBe("insufficient_evidence");
    expect(g.requirements?.had).toContain("400 conscious views");
  });
});

describe("pipeline integration", () => {
  test("runEngine surfaces coverage + gates in the payload", () => {
    const raw = {
      "Your Activity": {
        "Watch History": {
          VideoList: [
            { Date: "2024-01-01 10:00:00", Link: "https://www.tiktok.com/@a/video/1" },
            { Date: "2024-01-05 10:00:00", Link: "https://www.tiktok.com/@a/video/2" },
          ],
        },
      },
    };
    const { coverage, gates } = runEngine(raw);
    expect(coverage.overall.days).toBe(4);
    expect(coverage.perSection.watch_history.count).toBe(2);
    expect(gates.stopwatch.status).toBe("ok");
    expect(gates.persona.status).toBe("insufficient_evidence"); // 4 days, few views
  });
});
