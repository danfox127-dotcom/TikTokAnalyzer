/**
 * WP-1.1 engine port — persona / archetype layer.
 * Mirrors api.ghost_profile._detect_atomic_traits, _synthesize_sub_archetypes,
 * _detect_cognitive_dissonance, _determine_primary_archetype.
 *
 * All pure boolean/arithmetic (no rounding). Parity is about exact thresholds,
 * sub-archetype APPEND order, dissonance FIRST-MATCH order, and verbatim notes.
 * A missing trait key reads as falsy in both Python (dict.get -> None) and JS.
 */

interface Sw {
  max_session_duration: number;
  max_consecutive_skips: number;
  night_count: number;
  night_lingers: number;
  total_conscious_videos?: number;
}
interface Parsed {
  shares?: unknown[];
  likes?: unknown[];
  comments?: unknown[];
  following?: unknown[];
}
interface VibeEntry {
  genre?: string;
  linger_count?: number;
}
type Traits = Record<string, boolean>;
// behavioral_nodes is a mixed bag (peak_hour/sleep_window are strings); the
// archetype logic only reads the numeric fields.
type Nodes = Record<string, any>;

const len = (a?: unknown[]): number => a?.length ?? 0;
const sumLinger = (v: VibeEntry[]): number => v.reduce((a, c) => a + (c.linger_count ?? 0), 0);

export function detectAtomicTraits(
  sw: Sw,
  totalConscious: number,
  parsed: Parsed,
  lingerRatePct: number,
  nightShiftPct: number,
  vibeCluster: VibeEntry[],
): Traits {
  const totalLinger = sumLinger(vibeCluster);
  const techLinger = sumLinger(vibeCluster.filter((c) => c.genre === "tech"));
  const actions = len(parsed.likes) + len(parsed.shares) + len(parsed.comments);
  return {
    trapped: sw.max_session_duration > 3600 || lingerRatePct > 30,
    ruthless: sw.max_consecutive_skips >= 10,
    nocturnal: nightShiftPct > 35,
    curator: len(parsed.shares) / Math.max(len(parsed.likes), 1) > 0.5,
    ghost: actions / Math.max(totalConscious, 1) < 0.01,
    optimizer: techLinger / Math.max(totalLinger, 1) > 0.2,
  };
}

export interface SubArchetype {
  name: string;
  confidence: number;
}

export function synthesizeSubArchetypes(traits: Traits, nodes: Nodes): SubArchetype[] {
  const subs: SubArchetype[] = [];
  if (traits.curator && (nodes.social_graph_followed_pct ?? 0) > 60)
    subs.push({ name: "The Intentional Curator", confidence: 0.9 });
  if (traits.nocturnal && (nodes.linger_rate_percentage ?? 0) > 25)
    subs.push({ name: "The Nocturnal Seeker", confidence: 0.85 });
  if (traits.trapped && (nodes.social_graph_algorithmic_pct ?? 0) > 75)
    subs.push({ name: "The Algorithmic Captured", confidence: 0.95 });
  if (traits.ghost && (nodes.linger_rate_percentage ?? 0) < 10)
    subs.push({ name: "The Passive Observer", confidence: 0.8 });
  return subs;
}

export interface Dissonance {
  detected: boolean;
  label: string | null;
  note: string | null;
}

export function detectCognitiveDissonance(
  traits: Traits,
  sw: Sw,
  nodes: Nodes,
  parsed: Parsed,
  vibeCluster: VibeEntry[],
): Dissonance {
  const nightTotal = sw.night_count;
  const nightTrapped = nightTotal > 0 && sw.night_lingers / nightTotal > 0.3;
  if (traits.ruthless && nightTrapped) {
    return {
      detected: true,
      label: "Circadian Drift",
      note: "Your daytime curation is ruthless, but you lose control to the algorithm after midnight.",
    };
  }
  if (len(parsed.following) > 100 && (nodes.social_graph_algorithmic_pct ?? 0) > 90) {
    return {
      detected: true,
      label: "Social Paradox",
      note: "You follow a village of creators but let the algorithm choose 90% of what you actually see.",
    };
  }
  const totalLinger = sumLinger(vibeCluster);
  const techLingerPct = sumLinger(vibeCluster.filter((c) => c.genre === "tech")) / Math.max(totalLinger, 1);
  if (techLingerPct > 0.2 && traits.ghost) {
    return {
      detected: true,
      label: "Silent Expert",
      note: "You consume high-fidelity knowledge at scale while leaving zero digital trace.",
    };
  }
  return { detected: false, label: null, note: null };
}

export interface PrimaryArchetype {
  name: string;
  sub_archetypes: SubArchetype[];
  dissonance: Dissonance;
  atomic_traits: Traits;
}

export function determinePrimaryArchetype(
  nodes: Nodes,
  parsed: Parsed,
  sw: Sw,
  vibeCluster: VibeEntry[],
): PrimaryArchetype {
  const traits = detectAtomicTraits(
    sw,
    sw.total_conscious_videos ?? 0,
    parsed,
    nodes.linger_rate_percentage ?? 0,
    nodes.night_shift_ratio ?? 0,
    vibeCluster,
  );
  const subArchetypes = synthesizeSubArchetypes(traits, nodes);
  const dissonance = detectCognitiveDissonance(traits, sw, nodes, parsed, vibeCluster);
  const name = subArchetypes.length ? subArchetypes[0].name : "The Balanced Viewer";
  return { name, sub_archetypes: subArchetypes, dissonance, atomic_traits: traits };
}
