/**
 * WP-1.5 — confidence/tier plumbing. New functionality; unit-tested against the
 * Claim contract (plan §2). AC: every claim in the payload validates; the full
 * pipeline run produces a schema-valid claim set.
 */
import { buildClaims, validateClaims } from "../claims";
import { Claim } from "../types";
import { runEngine } from "../pipeline";

const richProfile: any = {
  behavioral_nodes: {
    skip_rate_percentage: 40, linger_rate_percentage: 25, peak_hour: "11 PM",
    night_shift_ratio: 40, inferred_sleep_window: "3 AM – 7 AM",
    social_graph_followed_pct: 70, social_graph_algorithmic_pct: 30,
  },
  stopwatch_metrics: { total_conscious_videos: 200, graveyard_skips: 80 },
  declared_signals: { following_count: 120, follower_count: 50, ad_interests: ["Beauty"], settings_interests: ["cooking"] },
  digital_footprint: { login_count: 3, unique_ips: 2 },
  ad_profile: { off_platform_events: 5, shop_order_count: 1 },
  academic_insights: { echo_chamber_index_pct: 60, echo_chamber_distinct_creators: 5, explicit_vs_implicit_ratio: 0.5 },
  primary_archetype: {
    name: "The Intentional Curator",
    sub_archetypes: [
      { name: "The Nocturnal Seeker", confidence: 0.85 },
      { name: "The Algorithmic Captured", confidence: 0.95 },
    ],
    dissonance: { detected: true, label: "Circadian Drift", note: "day curation, night capture" },
  },
  share_behavior: { share_behavior_type: "Private Curator" },
  comment_voice: { engagement_style_label: "Analytical Commenter" },
  transparency_gap: { behavioral_interest_count: 8 },
};

describe("buildClaims", () => {
  const claims = buildClaims(richProfile);
  const by = (id: string) => claims.find((c) => c.id === id);

  test("the whole claim set validates", () => {
    expect(validateClaims(claims)).toEqual([]);
  });

  test("recorded / derived / inferred tiers are assigned correctly", () => {
    expect(by("declared.following_count")).toMatchObject({ tier: "recorded", value: 120 });
    expect(by("attention.skip_rate_pct")).toMatchObject({ tier: "derived", value: 40 });
    expect(by("identity.sub_archetype.the_nocturnal_seeker")).toMatchObject({ tier: "inferred", value: "The Nocturnal Seeker" });
  });

  test("every claim has a method and evidence; inferred ones carry confidence", () => {
    for (const c of claims) {
      expect(typeof c.method).toBe("string");
      expect(Array.isArray(c.evidence)).toBe(true);
      if (c.tier === "inferred") {
        expect(typeof c.confidence).toBe("number");
        expect(c.evidence.length).toBeGreaterThan(0);
      }
    }
    const inferred = claims.filter((c) => c.tier === "inferred");
    expect(inferred.length).toBe(3); // 2 sub-archetypes + dissonance
  });
});

describe("validateClaims catches violations", () => {
  test("inferred without confidence / with empty evidence", () => {
    const bad: Claim[] = [{ id: "x", tier: "inferred", value: 1, evidence: [], method: "m" }];
    const errors = validateClaims(bad);
    expect(errors.some((e) => e.includes("confidence"))).toBe(true);
    expect(errors.some((e) => e.includes("evidence"))).toBe(true);
  });

  test("invalid tier, missing method, duplicate id", () => {
    const bad: any[] = [
      { id: "a", tier: "bogus", value: 1, evidence: [], method: "m" },
      { id: "b", tier: "derived", value: 1, evidence: [] },        // no method
      { id: "a", tier: "recorded", value: 2, evidence: [], method: "m" }, // dup id
    ];
    const errors = validateClaims(bad);
    expect(errors.some((e) => e.includes('invalid tier'))).toBe(true);
    expect(errors.some((e) => e.includes("missing method"))).toBe(true);
    expect(errors.some((e) => e.includes("duplicate id"))).toBe(true);
  });
});

describe("pipeline integration", () => {
  test("runEngine produces a schema-valid claim set", () => {
    const raw = {
      "Your Activity": {
        "Watch History": {
          VideoList: [
            { Date: "2024-01-01 10:00:00", Link: "https://www.tiktok.com/@a/video/1" },
            { Date: "2024-01-01 10:01:00", Link: "https://www.tiktok.com/@a/video/2" },
          ],
        },
      },
    };
    const { claims } = runEngine(raw);
    expect(claims.length).toBeGreaterThan(0);
    expect(validateClaims(claims)).toEqual([]);
  });
});
