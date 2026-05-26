/**
 * Ghost Profile Scoring Engine (TypeScript Port)
 * Calculates behavioral forensics and archetypes.
 */

import { parseDate, VideoEntry, ParseResult } from "./tiktok_parser.ts";
import { resolveVibeCluster } from "./creators.ts";
import { extractThemes, buildPillarNarrative } from "./psychographic.ts";

const DM_METHODS = new Set([
  "chat_head", "dm", "message", "whatsapp", "instagram",
  "line", "kakaotalk", "telegram",
]);

const SIGNAL_WEIGHTS: Record<string, number> = {
  "comment":      10,
  "favorite":      7,
  "share_dm":      8,
  "share_public":  4,
  "follow":        6,
  "search":        5,
  "like":          3,
};

// ---------------------------------------------------------------------------
// Stopwatch logic
// ---------------------------------------------------------------------------

function runStopwatch(browsingHistory: VideoEntry[], excludeHours: number[] = []) {
  const entries = browsingHistory
    .map(item => ({ dt: parseDate(item.date), link: item.link }))
    .filter(item => item.dt !== null)
    .sort((a, b) => a.dt!.getTime() - b.dt!.getTime());

  const SLEEP_THRESHOLD_S = 1200;
  const metrics = {
    total_raw_videos: entries.length,
    clock_anomalies: 0,
    sleep_scrubbed: 0,
    graveyard_skips: 0,
    sandbox_views: 0,
    deep_lingers: 0,
    deep_dives: 0,
    night_count: 0,
    night_lingers: 0,
    max_consecutive_skips: 0,
    max_session_duration: 0,
  };

  let consecutiveSkips = 0;
  let currentSessionDuration = 0;

  const graveyardLinks = new Set<string>();
  const sandboxLinks = new Set<string>();
  const lingerLinks = new Set<string>();
  const deepDiveLinks = new Set<string>();
  
  const hourlyHeatmap: Record<string, number> = {};
  for (let h = 0; h < 24; h++) hourlyHeatmap[String(h)] = 0;

  for (let i = 0; i < entries.length - 1; i++) {
    const cur = entries[i];
    const nxt = entries[i + 1];
    const delta = (nxt.dt!.getTime() - cur.dt!.getTime()) / 1000;

    if (delta < 0) {
      metrics.clock_anomalies++;
      continue;
    }

    if (delta >= SLEEP_THRESHOLD_S) {
      metrics.sleep_scrubbed++;
      currentSessionDuration = 0;
      continue;
    }

    if (delta > 300) {
      currentSessionDuration = 0;
    } else {
      currentSessionDuration += delta;
      metrics.max_session_duration = Math.max(metrics.max_session_duration, currentSessionDuration);
    }

    const hour = cur.dt!.getUTCHours(); // Use UTC or local? Python used local but in Edge Functions we should be consistent.
    if (excludeHours.includes(hour)) continue;

    hourlyHeatmap[String(hour)]++;

    if (hour >= 23 || hour < 4) {
      metrics.night_count++;
    }

    const link = cur.link;
    
    if (delta < 3) {
      metrics.graveyard_skips++;
      consecutiveSkips++;
      metrics.max_consecutive_skips = Math.max(metrics.max_consecutive_skips, consecutiveSkips);
      if (link) graveyardLinks.add(link);
    } else if (delta <= 15) {
      consecutiveSkips = 0;
      metrics.sandbox_views++;
      if (link) sandboxLinks.add(link);
    } else if (delta <= 180) {
      consecutiveSkips = 0;
      metrics.deep_lingers++;
      if (hour >= 23 || hour < 4) metrics.night_lingers++;
      if (link) lingerLinks.add(link);
    } else {
      consecutiveSkips = 0;
      metrics.deep_dives++;
      if (hour >= 23 || hour < 4) metrics.night_lingers++;
      if (link) {
        deepDiveLinks.add(link);
        lingerLinks.add(link);
      }
    }
  }

  const totalConscious = metrics.graveyard_skips + metrics.sandbox_views + metrics.deep_lingers + metrics.deep_dives;

  return {
    ...metrics,
    total_conscious_videos: totalConscious,
    _graveyard_links: Array.from(graveyardLinks),
    _sandbox_links: Array.from(sandboxLinks),
    _linger_links: Array.from(lingerLinks),
    _deep_dive_links: Array.from(deepDiveLinks),
    hourly_heatmap: hourlyHeatmap,
  };
}

// ---------------------------------------------------------------------------
// Archetype engine
// ---------------------------------------------------------------------------

function detectAtomicTraits(sw: any, lingerRatePct: number, nightShiftPct: number) {
  const traits: Record<string, boolean> = {};
  traits["trapped"] = (sw.max_session_duration > 3600) || (lingerRatePct > 30);
  traits["ruthless"] = sw.max_consecutive_skips >= 10;
  traits["nocturnal"] = nightShiftPct > 35;
  // ... other traits
  return traits;
}

function determinePrimaryArchetype(behavioralNodes: any, sw: any) {
  const traits = detectAtomicTraits(
    sw, 
    behavioralNodes.linger_rate_percentage, 
    behavioralNodes.night_shift_ratio
  );
  
  // Simplified synthesis for now
  let name = "The Balanced Viewer";
  if (traits.trapped) name = "The Algorithmic Captured";
  else if (traits.ruthless) name = "The Ruthless Curator";
  else if (traits.nocturnal) name = "The Nocturnal Seeker";

  return { name, atomic_traits: traits };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function buildGhostProfile(parsed: ParseResult, excludeHours: number[] = []) {
  const sw = runStopwatch(parsed.watch_history_active, excludeHours);
  
  const totalConscious = Math.max(sw.total_conscious_videos, 1);
  const lingerRatePct = ((sw.deep_lingers + sw.deep_dives) / totalConscious) * 100;
  const nightShiftPct = (sw.night_count / totalConscious) * 100;

  const behavioral_nodes = {
    peak_hour: "Unknown", // need helper
    skip_rate_percentage: Math.round((sw.graveyard_skips / totalConscious) * 1000) / 10,
    linger_rate_percentage: Math.round(lingerRatePct * 10) / 10,
    night_shift_ratio: Math.round(nightShiftPct * 10) / 10,
    social_graph_algorithmic_pct: 0, // placeholder
    social_graph_followed_pct: 0, // placeholder
  };

  const primary_archetype = determinePrimaryArchetype(behavioral_nodes, sw);

  // Extract themes from watch history titles if available
  // In the real port, we'd need to carry the titles through or resolve them
  const themes = extractThemes([]); 

  return {
    status: "success",
    stopwatch_metrics: sw,
    behavioral_nodes,
    primary_archetype,
    interest_clusters: themes.top_keywords,
    interest_phrases: themes.top_phrases,
    // ... add other sections
  };
}
