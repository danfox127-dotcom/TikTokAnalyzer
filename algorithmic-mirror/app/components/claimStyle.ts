// algorithmic-mirror/app/components/claimStyle.ts
/**
 * WP-3.2 — shared confidence-tier visual language. Single source of truth for
 * tier → {color, border texture, label}, so no component hardcodes tier colors.
 * Never encode tier meaning in color alone — every tierMeta() consumer must also
 * show `label` and apply `borderStyle`/`className`.
 */
import type { Tier } from "../../engine/types";

export interface TierMeta {
  label: string;
  color: string;
  borderStyle: "solid" | "dashed" | "dotted";
  className: string;
}

const TIER_META: Record<Tier, TierMeta> = {
  recorded: { label: "Recorded", color: "#1a1610", borderStyle: "solid", className: "tier-recorded" },
  derived: { label: "Derived", color: "#8b2323", borderStyle: "dashed", className: "tier-derived" },
  inferred: { label: "Inferred", color: "#1f4e6b", borderStyle: "dotted", className: "tier-inferred" },
};

/** Safe for a tier value from untrusted/malformed data — never throws. */
export function tierMeta(tier: Tier): TierMeta {
  return TIER_META[tier] ?? { label: "Unknown", color: "#1a1610", borderStyle: "solid", className: "tier-recorded" };
}

/**
 * Formats a Claim's `value` for display. Ported from DemographicPanel's local
 * renderValue (WP-2.3) — handles the trip-object-array shape (city/days) that
 * previously regressed to "[object Object]" before that fix.
 */
export function renderClaimValue(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) {
    return v
      .map((x) => (x && typeof x === "object" && "city" in x
        ? `${(x as any).city} (${(x as any).days}d)`
        : String(x)))
      .join(", ");
  }
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
