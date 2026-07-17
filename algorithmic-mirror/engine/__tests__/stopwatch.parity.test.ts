/**
 * WP-1.1 stopwatch parity: TS `runStopwatch` vs the frozen Python oracle.
 *
 * The fixture is generated from `api.ghost_profile._run_stopwatch` by
 * `scripts/gen_stopwatch_parity_fixture.py` and COMMITTED. Regenerate only on
 * an intentional Python change (review the resulting JSON diff). If this test
 * goes red, the port drifted from the oracle — fix the port, not the fixture.
 *
 * We assert an explicit per-field surface (not a whole-object deep-equal) with
 * the right comparator per type: exact for counts/heatmaps/rates, set-equal for
 * link collections (Python sets have no order), float-tolerant for durations.
 */
import * as fs from "fs";
import * as path from "path";
import { runStopwatch, StopwatchResult, StopwatchEvent } from "../stopwatch";

interface FixtureCase {
  name: string;
  input: { history: { date: string; link: string }[]; exclude_hours: number[]; engaged_video_ids?: string[] };
  expected: Record<string, any>;
}

const fixture = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "__fixtures__", "stopwatch_parity.json"), "utf8"),
);
const cases: FixtureCase[] = fixture.cases;

const SCALAR_FIELDS: (keyof StopwatchResult)[] = [
  "total_raw_videos", "total_conscious_videos", "sleep_anomalies_scrubbed",
  "sleep_scrubbed", "graveyard_skips", "sandbox_views", "deep_lingers",
  "deep_dives", "abandoned", "abandoned_night", "night_count", "night_lingers",
  "max_consecutive_skips",
];
const LINK_FIELDS: (keyof StopwatchResult)[] = [
  "_graveyard_links", "_sandbox_links", "_linger_links", "_deep_dive_links", "_abandoned_links",
];
const EVENT_FIELDS: (keyof StopwatchResult)[] = [
  "linger_events", "graveyard_events", "sandbox_events",
  "night_linger_events", "deep_dive_events",
];

/** Round event time_spent to kill float-repr noise (deltas are whole-second anyway). */
function normEvents(events: StopwatchEvent[]): any[] {
  return events.map((e) => ({ ...e, time_spent: Math.round(e.time_spent * 1e6) / 1e6 }));
}

describe("stopwatch parity vs Python oracle", () => {
  test.each(cases.map((c) => [c.name, c] as const))("%s", (_name, c) => {
    const engaged = c.input.engaged_video_ids ? new Set<string>(c.input.engaged_video_ids) : undefined;
    const got = runStopwatch(c.input.history, c.input.exclude_hours, engaged) as any;
    const exp = c.expected;

    for (const f of SCALAR_FIELDS) {
      expect(`${f}=${got[f]}`).toBe(`${f}=${exp[f as string]}`);
    }

    expect(got.max_session_duration).toBeCloseTo(exp.max_session_duration, 6);
    expect(got.data_start_month).toBe(exp.data_start_month);

    for (const f of LINK_FIELDS) {
      expect([...(got[f] as string[])].sort()).toEqual([...(exp[f as string] as string[])].sort());
    }

    expect(got.hourly_heatmap).toEqual(exp.hourly_heatmap);
    expect(got.weekly_heatmap).toEqual(exp.weekly_heatmap);
    expect(got.monthly_skip_rates).toEqual(exp.monthly_skip_rates);

    for (const f of EVENT_FIELDS) {
      expect(normEvents(got[f])).toEqual(normEvents(exp[f as string]));
    }

    // WP-1.4 temporal bucketing: granularity + per-period bucket/night counts.
    expect(got.temporal_granularity).toBe(exp.temporal_granularity);
    expect(got.period_data).toEqual(exp.period_data);
  });

  test("fixture actually loaded", () => {
    expect(cases.length).toBeGreaterThan(5);
  });
});
