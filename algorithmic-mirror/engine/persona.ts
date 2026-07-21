/**
 * WP-2.4 — Persona Engine v2. Pure, browser-safe. Computes a 6-dimension persona
 * vector (0–100) from the already-emitted profile, then maps the 5 "who" dimensions
 * to a named archetype via a config map of centroids (nocturnality is a descriptive
 * prefix, not an archetype axis). Every formula is deterministic and exposed in `method`.
 */

export interface PersonaDimensions {
  intentionality: number;
  capture_susceptibility: number;
  nocturnality: number;
  exploration: number;
  expressiveness: number;
  parasociality: number;
}

export interface PersonaResult {
  status: "ok" | "insufficient_evidence" | "error";
  dimensions: PersonaDimensions;
  base_archetype: string;
  nocturnality_modifier: "Nocturnal" | "Diurnal" | "";
  display_name: string;
  secondary?: string;
  confidence: number;
  requirements?: { needed: string; had: string };
  method: string;
}

const clamp = (n: number): number => Math.max(0, Math.min(100, Number.isFinite(n) ? n : 0));

export function computeDimensions(profile: any): PersonaDimensions {
  const bn = profile?.behavioral_nodes ?? {};
  const ai = profile?.academic_insights ?? {};
  const sw = profile?.stopwatch_metrics ?? {};
  const sr = profile?.search_rhythm ?? {};
  const cv = profile?.comment_voice ?? {};
  const sb = profile?.share_behavior ?? {};

  const followed = Number(bn.social_graph_followed_pct ?? 0);
  const algo = Number(bn.social_graph_algorithmic_pct ?? 0);
  const skip = Number(bn.skip_rate_percentage ?? 0);
  const linger = Number(bn.linger_rate_percentage ?? 0);
  const night = Number(bn.night_shift_ratio ?? 0);
  const explicit = Number(ai.explicit_vs_implicit_ratio ?? 0);
  const echoPct = Number(ai.echo_chamber_index_pct ?? 0);
  const distinct = Number(ai.echo_chamber_distinct_creators ?? 0);
  const sessSecs = Number(sw.max_session_duration ?? 0);
  const searches = Number(sr.total_searches ?? 0);
  const comments = Number(cv.total_comments ?? 0);
  const longPct = Number(cv.long_comment_pct ?? 0);
  const shares = Number(sb.total_shares ?? 0);
  const refs = cv.references_detected ?? {};
  const refCount = Object.values(refs).reduce(
    (s: number, arr: any) => s + (Array.isArray(arr) ? arr.length : 0), 0);

  return {
    intentionality: clamp(0.5 * followed + 0.3 * Math.min(100, explicit * 50) + 0.2 * skip),
    capture_susceptibility: clamp(0.5 * algo + 0.3 * Math.min(100, (sessSecs / 3600) * 100) + 0.2 * linger),
    nocturnality: clamp(Math.min(100, night * 2)),
    exploration: clamp(
      0.4 * (100 - echoPct) + 0.3 * Math.min(100, (distinct / 50) * 100) + 0.3 * Math.min(100, (searches / 50) * 100)),
    expressiveness: comments > 0
      ? clamp(59 + Math.min(41, comments * 2 + longPct * 0.2))   // above the "59.2% never comment" anchor
      : clamp(Math.min(58, shares * 2)),                          // never-commenters stay below 59
    parasociality: clamp(0.5 * echoPct + 0.3 * followed + 0.2 * Math.min(100, refCount * 10)),
  };
}
