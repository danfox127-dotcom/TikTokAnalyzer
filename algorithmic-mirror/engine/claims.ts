/**
 * WP-1.5 — confidence/tier plumbing.
 *
 * Transforms the raw (parity-locked) Ghost Profile into a flat list of Claims,
 * each tagged recorded / derived / inferred with a plain-language method and
 * evidence. This is a layer OVER buildGhostProfile — the orchestrator payload
 * stays byte-identical to the oracle; claims are assembled in the pipeline.
 *
 * Ground rule 2: inferred claims must carry confidence (0–1) + non-empty evidence.
 */

import { Claim, Tier, EvidenceRef } from "./types";

function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

export function buildClaims(profile: any): Claim[] {
  const claims: Claim[] = [];
  const bn = profile?.behavioral_nodes ?? {};
  const sw = profile?.stopwatch_metrics ?? {};
  const decl = profile?.declared_signals ?? {};
  const foot = profile?.digital_footprint ?? {};
  const ad = profile?.ad_profile ?? {};
  const ai = profile?.academic_insights ?? {};
  const arch = profile?.primary_archetype ?? {};

  const add = (
    id: string, tier: Tier, value: unknown, method: string,
    evidence: EvidenceRef[], confidence?: number,
  ) => {
    const c: Claim = { id, tier, value, evidence, method };
    if (confidence != null) c.confidence = confidence;
    claims.push(c);
  };

  const total = Number(sw.total_conscious_videos ?? 0);

  // ── Recorded: TikTok's own stored/declared data ──────────────────────────
  add("declared.following_count", "recorded", decl.following_count ?? 0,
    "Count of accounts you follow, from the export's Following list.",
    [{ kind: "follow", note: "Following list" }]);
  add("declared.follower_count", "recorded", decl.follower_count ?? 0,
    "Count of your followers, from the export.",
    [{ kind: "follow", note: "Follower list" }]);
  add("declared.ad_interests", "recorded", decl.ad_interests ?? [],
    "Advertiser interest categories TikTok stores about you.",
    [{ kind: "settings", note: "Ad Interests" }]);
  add("declared.settings_interests", "recorded", decl.settings_interests ?? [],
    "Interests you declared in Settings.",
    [{ kind: "settings", note: "Settings Interests" }]);
  add("footprint.login_count", "recorded", foot.login_count ?? 0,
    "Number of recorded login events.",
    [{ kind: "login", note: "Login history" }]);
  add("footprint.unique_ips", "recorded", foot.unique_ips ?? 0,
    "Distinct IP addresses in your login history.",
    [{ kind: "login", note: "Login history" }]);
  add("ads.off_platform_events", "recorded", ad.off_platform_events ?? 0,
    "Off-TikTok activity events reported to TikTok by third parties.",
    [{ kind: "external_source", note: "Off TikTok Activity" }]);
  add("ads.shop_order_count", "recorded", ad.shop_order_count ?? 0,
    "TikTok Shop orders in the export.",
    [{ kind: "order", note: "Shop orders" }]);

  // ── Derived: our deterministic math ──────────────────────────────────────
  add("attention.skip_rate_pct", "derived", bn.skip_rate_percentage ?? 0,
    "Share of conscious views skipped in under 3 seconds.",
    [{ kind: "video", note: `${sw.graveyard_skips ?? 0} skips / ${total} conscious views` }]);
  add("attention.linger_rate_pct", "derived", bn.linger_rate_percentage ?? 0,
    "Share of views held 15s+ (sustained + deep dives).",
    [{ kind: "video", note: `over ${total} conscious views` }]);
  add("rhythm.peak_hour", "derived", bn.peak_hour ?? "Unknown",
    "Modal hour of watch activity from the hourly heatmap.",
    [{ kind: "video", note: "hourly heatmap" }]);
  add("rhythm.night_shift_pct", "derived", bn.night_shift_ratio ?? 0,
    "Share of activity in the 11pm–4am window.",
    [{ kind: "video", note: "night-hour views" }]);
  add("rhythm.inferred_sleep_window", "derived", bn.inferred_sleep_window ?? "Unknown",
    "Quietest consecutive 4-hour block in your heatmap.",
    [{ kind: "video", note: "hourly heatmap dead zone" }]);
  add("social.followed_pct", "derived", bn.social_graph_followed_pct ?? 0,
    "Share of watched creators you actually follow.",
    [{ kind: "follow", note: "followed vs algorithmic creators" }]);
  add("social.algorithmic_pct", "derived", bn.social_graph_algorithmic_pct ?? 0,
    "Share of watched creators surfaced algorithmically.",
    [{ kind: "video", note: "algorithmic vs followed creators" }]);
  add("echo.concentration_pct", "derived", ai.echo_chamber_index_pct ?? 0,
    "Share of lingered videos on your top-5 creators.",
    [{ kind: "video", note: `${ai.echo_chamber_distinct_creators ?? 0} distinct creators` }]);
  add("engagement.explicit_vs_implicit_ratio", "derived", ai.explicit_vs_implicit_ratio ?? 0,
    "Ratio of explicit actions (likes + comments) to silent lingers.",
    [{ kind: "like", note: "explicit vs implicit engagement" }]);
  add("identity.archetype", "derived", arch.name ?? "The Balanced Viewer",
    "Deterministic primary archetype from behavioral thresholds.",
    [{ kind: "video", note: "atomic trait synthesis" }]);
  add("share.behavior_type", "derived", profile?.share_behavior?.share_behavior_type ?? "Mixed Sharer",
    "Sharing style from the DM-vs-public method mix.",
    [{ kind: "share", note: "share method distribution" }]);
  add("comment.style_label", "derived", profile?.comment_voice?.engagement_style_label ?? "Lurker",
    "Commenting style from comment length and frequency.",
    [{ kind: "comment", note: "comment length / frequency" }]);
  add("transparency.behavioral_clusters", "derived", profile?.transparency_gap?.behavioral_interest_count ?? 0,
    "Behavioral interest clusters inferred from watch history vs declared interests.",
    [{ kind: "video", note: "interest clustering" }]);

  // ── Inferred: probabilistic labels (confidence + evidence required) ───────
  for (const sub of arch.sub_archetypes ?? []) {
    add(`identity.sub_archetype.${slug(sub.name)}`, "inferred", sub.name,
      "Probabilistic secondary persona from a trait combination.",
      [{ kind: "video", note: "trait synthesis" }], sub.confidence);
  }
  const diss = arch.dissonance ?? {};
  if (diss.detected) {
    add("identity.dissonance", "inferred", diss.label,
      `Contradictory behavioral identity: ${diss.note}`,
      [{ kind: "video", note: "cross-trait contradiction" }], 0.7);
  }

  return claims;
}

// ── Schema validation (WP-1.5 AC) ────────────────────────────────────────────
const TIERS = new Set<Tier>(["recorded", "derived", "inferred"]);

/** Returns a list of schema violations; empty means the claim set is valid. */
export function validateClaims(claims: Claim[]): string[] {
  const errors: string[] = [];
  const seen = new Set<string>();
  claims.forEach((c, i) => {
    const where = c?.id || `#${i}`;
    if (!c || typeof c !== "object") { errors.push(`${where}: not an object`); return; }
    if (typeof c.id !== "string" || !c.id) errors.push(`${where}: missing id`);
    else if (seen.has(c.id)) errors.push(`${c.id}: duplicate id`);
    else seen.add(c.id);
    if (!TIERS.has(c.tier)) errors.push(`${where}: invalid tier "${c.tier}"`);
    if (c.value === undefined) errors.push(`${where}: missing value`);
    if (typeof c.method !== "string" || !c.method) errors.push(`${where}: missing method`);
    if (!Array.isArray(c.evidence)) errors.push(`${where}: evidence must be an array`);
    if (c.tier === "inferred") {
      if (typeof c.confidence !== "number" || c.confidence < 0 || c.confidence > 1) {
        errors.push(`${where}: inferred claim needs confidence in [0,1]`);
      }
      if (!Array.isArray(c.evidence) || c.evidence.length === 0) {
        errors.push(`${where}: inferred claim needs non-empty evidence`);
      }
    }
  });
  return errors;
}
