// algorithmic-mirror/engine/__tests__/persona.test.ts
import { computeDimensions } from "../persona";

// a profile with the dimension inputs; omitted fields default to 0
const prof = (over: any = {}) => ({
  behavioral_nodes: { social_graph_followed_pct: 0, social_graph_algorithmic_pct: 0,
    skip_rate_percentage: 0, linger_rate_percentage: 0, night_shift_ratio: 0, ...(over.bn ?? {}) },
  academic_insights: { explicit_vs_implicit_ratio: 0, echo_chamber_index_pct: 0,
    echo_chamber_distinct_creators: 0, ...(over.ai ?? {}) },
  stopwatch_metrics: { max_session_duration: 0, total_conscious_videos: 0, ...(over.sw ?? {}) },
  search_rhythm: { total_searches: 0, ...(over.sr ?? {}) },
  comment_voice: { total_comments: 0, long_comment_pct: 0, references_detected: {}, ...(over.cv ?? {}) },
  share_behavior: { total_shares: 0, ...(over.sb ?? {}) },
});

describe("computeDimensions", () => {
  test("all-zero profile → dimensions finite & clamped; exploration has an echo-inverse base", () => {
    const d = computeDimensions(prof());
    for (const v of Object.values(d)) {
      expect(Number.isFinite(v)).toBe(true);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
    expect(d.intentionality).toBe(0);
    expect(d.capture_susceptibility).toBe(0);
    expect(d.nocturnality).toBe(0);
    expect(d.expressiveness).toBe(0);
    expect(d.parasociality).toBe(0);
    expect(d.exploration).toBe(40); // low echo-concentration reads as exploratory; gated upstream
  });

  test("intentionality blends followed% + explicit ratio + skip%", () => {
    // 0.5*80 + 0.3*min(100, 1*50) + 0.2*50 = 40 + 15 + 10 = 65
    const d = computeDimensions(prof({ bn: { social_graph_followed_pct: 80, skip_rate_percentage: 50 }, ai: { explicit_vs_implicit_ratio: 1 } }));
    expect(d.intentionality).toBe(65);
  });

  test("capture blends algorithmic% + session length + linger%", () => {
    // 0.5*100 + 0.3*min(100, 3600/3600*100) + 0.2*0 = 50 + 30 = 80
    const d = computeDimensions(prof({ bn: { social_graph_algorithmic_pct: 100 }, sw: { max_session_duration: 3600 } }));
    expect(d.capture_susceptibility).toBe(80);
  });

  test("nocturnality doubles night_shift_ratio, clamped", () => {
    expect(computeDimensions(prof({ bn: { night_shift_ratio: 25 } })).nocturnality).toBe(50);
    expect(computeDimensions(prof({ bn: { night_shift_ratio: 80 } })).nocturnality).toBe(100); // 160→100
  });

  test("exploration folds in search intensity (heavy search > no search)", () => {
    const base = { ai: { echo_chamber_index_pct: 40, echo_chamber_distinct_creators: 25 } };
    const noSearch = computeDimensions(prof({ ...base, sr: { total_searches: 0 } })).exploration;
    const heavy = computeDimensions(prof({ ...base, sr: { total_searches: 50 } })).exploration;
    expect(heavy).toBeGreaterThan(noSearch);
    // 0.4*60 + 0.3*50 + 0.3*100 = 24 + 15 + 30 = 69
    expect(heavy).toBe(69);
  });

  test("expressiveness: any comment lifts above the 59th-percentile anchor; none caps below it", () => {
    expect(computeDimensions(prof({ cv: { total_comments: 0 }, sb: { total_shares: 0 } })).expressiveness).toBe(0);
    expect(computeDimensions(prof({ cv: { total_comments: 1 } })).expressiveness).toBeGreaterThanOrEqual(59);
    expect(computeDimensions(prof({ cv: { total_comments: 0 }, sb: { total_shares: 5 } })).expressiveness).toBeLessThan(59);
  });

  test("parasociality blends echo concentration + followed% + comment references", () => {
    // 0.5*80 + 0.3*50 + 0.2*min(100, 2*10) = 40 + 15 + 4 = 59
    const d = computeDimensions(prof({ ai: { echo_chamber_index_pct: 80 }, bn: { social_graph_followed_pct: 50 },
      cv: { references_detected: { song: ["a"], creator: ["b"] } } }));
    expect(d.parasociality).toBe(59);
  });
});
