/**
 * WP-1.1 engine port — transparency gap.
 * Mirror of api.ghost_profile.calculate_transparency_gap: declared ad interests
 * vs behaviorally-inferred interest clusters.
 *
 * Parity note: the gap percent uses Python round() with no digits (round-half-to-
 * even → int), so pyRound(x, 0). The elif short-circuits before dividing, so a
 * zero behavioral_count never divides by zero.
 */

import { pyRound } from "./numeric";

export interface TransparencyGap {
  official_ad_interest_count: number;
  behavioral_interest_count: number;
  gap_interpretation: string;
}

export function calculateTransparencyGap(
  parsed: { ad_interests?: unknown[] },
  profile: { interest_clusters?: unknown[] },
): TransparencyGap {
  const officialCount = (parsed?.ad_interests ?? []).length;
  const behavioralCount = (profile?.interest_clusters ?? []).length;

  let interpretation: string;
  if (officialCount === 0 && behavioralCount > 5) {
    interpretation =
      "Ad interests empty — likely privacy opt-out — but behavioral profile shows strong inferred interests.";
  } else if (officialCount > 0 && officialCount < behavioralCount * 0.5) {
    const pct = pyRound((1 - officialCount / behavioralCount) * 100, 0);
    interpretation = `Significant gap: TikTok's declared interests underrepresent actual behavioral profile by approx ${pct}%.`;
  } else {
    interpretation = "Official interests roughly match behavioral profile.";
  }

  return {
    official_ad_interest_count: officialCount,
    behavioral_interest_count: behavioralCount,
    gap_interpretation: interpretation,
  };
}
