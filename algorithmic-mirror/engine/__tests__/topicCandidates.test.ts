import { selectTopicCandidates } from "../topicCandidates";

// Build a profile from explicit events. linger_events includes deep dives.
function profile(linger: any[], deep: any[]) {
  return { stopwatch_metrics: { linger_events: linger, deep_dive_events: deep } };
}
const ev = (video_id: string, time_spent: number, _month = "2024-01") => ({ video_id, time_spent, _month });

describe("selectTopicCandidates", () => {
  test("deep dives weight 1.0x, pure lingers 0.5x; graveyard/sandbox absent are excluded", () => {
    // v1 is a deep dive (in deep_dive_events) → 1.0 * 100 = 100
    // v2 is a pure linger → 0.5 * 100 = 50
    const linger = [ev("v1", 100), ev("v2", 100)];
    const deep = [ev("v1", 100)];
    const out = selectTopicCandidates(profile(linger, deep));
    expect(out).toEqual([
      { video_id: "v1", weight: 100 },
      { video_id: "v2", weight: 50 },
    ]);
  });

  test("weights for a recurring video accumulate; stable tie-break by video_id", () => {
    const linger = [ev("b", 20), ev("a", 10), ev("a", 10)];
    const deep: any[] = [];
    // a: 0.5*(10+10)=10 ; b: 0.5*20=10 → tie, a before b
    const out = selectTopicCandidates(profile(linger, deep));
    expect(out).toEqual([
      { video_id: "a", weight: 10 },
      { video_id: "b", weight: 10 },
    ]);
  });

  test("month-proportional cap keeps each month represented", () => {
    // Jan: 4 videos, Feb: 2 videos, limit 3 → Jan quota 2, Feb quota 1
    const jan = ["j1", "j2", "j3", "j4"].map((v, i) => ev(v, 40 - i, "2024-01"));
    const feb = ["f1", "f2"].map((v, i) => ev(v, 40 - i, "2024-02"));
    const out = selectTopicCandidates(profile([...jan, ...feb], []), { limit: 3 });
    const ids = out.map((c) => c.video_id).sort();
    expect(out.length).toBe(3);
    expect(ids).toContain("f1");            // Feb still represented, not crowded out
    expect(ids).toContain("j1");            // Jan's top survives
  });

  test("returns all when under the limit", () => {
    const out = selectTopicCandidates(profile([ev("a", 10)], []), { limit: 800 });
    expect(out).toEqual([{ video_id: "a", weight: 5 }]);
  });
});
