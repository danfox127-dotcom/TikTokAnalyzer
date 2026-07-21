/**
 * WP-2.4 — Persona Engine v2. Pure, browser-safe. Computes a 6-dimension persona
 * vector (0–100) from the already-emitted profile, then maps the 5 "who" dimensions
 * to a named archetype via a config map of centroids (nocturnality is a descriptive
 * prefix, not an archetype axis). Every formula is deterministic and exposed in `method`.
 */

import { requireCoverage, type Coverage } from "./coverage";

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

// The 5 "who" dimensions the archetype centroids live in (nocturnality is a prefix,
// not an axis). Tunable config — retuning archetypes is data, not code branches.
const WHO_DIMS = [
  "intentionality", "capture_susceptibility", "exploration", "expressiveness", "parasociality",
] as const;

interface Centroid { name: string; v: Record<(typeof WHO_DIMS)[number], number>; }

export const ARCHETYPE_CENTROIDS: Centroid[] = [
  { name: "The Intentional Curator", v: { intentionality: 85, capture_susceptibility: 20, exploration: 60, expressiveness: 70, parasociality: 50 } },
  { name: "The Seeker",              v: { intentionality: 70, capture_susceptibility: 25, exploration: 90, expressiveness: 55, parasociality: 40 } },
  { name: "The Algorithmic Captured",v: { intentionality: 20, capture_susceptibility: 90, exploration: 25, expressiveness: 25, parasociality: 65 } },
  { name: "The Passive Observer",    v: { intentionality: 30, capture_susceptibility: 55, exploration: 40, expressiveness: 10, parasociality: 30 } },
  { name: "The Balanced Viewer",     v: { intentionality: 50, capture_susceptibility: 50, exploration: 50, expressiveness: 50, parasociality: 50 } },
];

const SECONDARY_GAP = 25;
const MAX_DIST = Math.sqrt(WHO_DIMS.length) * 100; // max Euclidean over 5 dims of range 100

const METHOD =
  "6 dimensions (0–100) from your behavioral metrics; archetype = nearest centroid over the 5 identity " +
  "dimensions (nocturnality is a descriptive prefix, not an axis). Expressiveness is anchored on platform " +
  "benchmarks (59.2% never comment / 73.5% never post).";

function distance(dims: PersonaDimensions, c: Centroid): number {
  let s = 0;
  for (const k of WHO_DIMS) { const d = (dims as any)[k] - c.v[k]; s += d * d; }
  return Math.sqrt(s);
}

export function nocturnalityModifier(nocturnality: number): "Nocturnal" | "Diurnal" | "" {
  if (nocturnality >= 66) return "Nocturnal";
  if (nocturnality <= 33) return "Diurnal";
  return "";
}

function zeroDims(): PersonaDimensions {
  return { intentionality: 0, capture_susceptibility: 0, nocturnality: 0, exploration: 0, expressiveness: 0, parasociality: 0 };
}

export function buildPersona(profile: any, coverage: Coverage): PersonaResult {
  if (!profile || typeof profile !== "object") {
    return { status: "error", dimensions: zeroDims(), base_archetype: "", nocturnality_modifier: "", display_name: "", confidence: 0, method: "malformed profile" };
  }
  const dimensions = computeDimensions(profile);
  const gate = requireCoverage("persona", coverage ?? { overall: { start: "", end: "", days: 0 }, perSection: {} },
    { consciousViews: Number(profile?.stopwatch_metrics?.total_conscious_videos ?? 0) });
  if (gate.status !== "ok") {
    return { status: "insufficient_evidence", dimensions, base_archetype: "", nocturnality_modifier: "", display_name: "", confidence: 0, requirements: gate.requirements, method: METHOD };
  }

  const ranked = ARCHETYPE_CENTROIDS
    .map((c) => ({ name: c.name, d: distance(dimensions, c) }))
    .sort((a, b) => a.d - b.d || (a.name < b.name ? -1 : 1));
  const primary = ranked[0];
  const secondary = ranked[1] && ranked[1].d <= primary.d + SECONDARY_GAP ? ranked[1].name : undefined;
  const modifier = nocturnalityModifier(dimensions.nocturnality);
  const bare = primary.name.replace(/^The /, "");
  const display_name = modifier ? `${modifier} ${bare}` : primary.name;
  const confidence = Math.round(Math.max(0, Math.min(1, 1 - primary.d / MAX_DIST)) * 100) / 100;

  return { status: "ok", dimensions, base_archetype: primary.name, nocturnality_modifier: modifier, display_name, secondary, confidence, method: METHOD };
}
