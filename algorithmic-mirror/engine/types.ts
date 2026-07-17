/**
 * WP-1.5 — shared Claim contract (plan §2).
 *
 * Every user-facing insight is a Claim carrying a confidence TIER and a receipt:
 *  - recorded: TikTok's own stored/declared data, straight from the export
 *  - derived:  computed by our deterministic math over recorded data
 *  - inferred: a probabilistic label (requires `confidence` + non-empty `evidence`)
 */

export type Tier = "recorded" | "derived" | "inferred";

export interface EvidenceRef {
  kind:
    | "video" | "search" | "login" | "like" | "share" | "comment"
    | "follow" | "order" | "settings" | "external_source";
  id?: string;
  link?: string;
  timestamp?: string;
  note?: string;
  citation?: string;
}

/**
 * WP-1.4 — a metric bucketed over time. `granularity` is "month" (coverage ≥ 90d)
 * or "week" (Monday-anchored period keys, < 90d). Points are sorted by period.
 */
export interface TemporalSeries<T = unknown> {
  granularity: "month" | "week";
  points: { period: string; value: T }[];
}

export interface Claim<T = unknown> {
  id: string; // stable key, e.g. "attention.skip_rate_pct"
  tier: Tier;
  value: T;
  confidence?: number; // required when tier === "inferred"
  evidence: EvidenceRef[];
  method: string; // one-line plain-language description of the formula
}
