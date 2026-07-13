/**
 * WP-1.1 engine port — creator resolution + echo-chamber index.
 *
 * Mirrors the deterministic creator cluster in api.ghost_profile:
 *  - _extract_creator_from_url
 *  - _handle_from_link
 *  - _echo_chamber_index
 *
 * NOTE: _count_creators is deliberately NOT ported here — its output ordering
 * depends on Python set iteration and list(set(...)), so it needs an
 * order-insensitive slice of its own. echoChamberIndex is safe because it only
 * SUMS the top-5 counts (identity/order irrelevant).
 */

import { extractVideoId } from "./videoId";
import { pyRound } from "./numeric";
import { URL_NOISE } from "./constants";

/** Mirror of _extract_creator_from_url: `@<name>/` in the URL → "@name", else null.
 *  The trailing slash is REQUIRED (a bare ".../@name" with no slash returns null). */
export function extractCreatorFromUrl(url: string): string | null {
  if (!url) return null;
  const m = url.match(/@([a-zA-Z0-9._-]+)\//);
  return m ? `@${m[1]}` : null;
}

/** Mirror of _keywords_from_url: creator handle (spaced) if present, else the
 *  non-noise, non-numeric URL path parts (length >= 4), lowercased. */
export function keywordsFromUrl(url: string): string[] {
  if (!url) return [];
  const creator = extractCreatorFromUrl(url);
  if (creator) {
    // Python: creator.lstrip("@").replace("_"," ").replace("."," ")
    return [creator.replace(/^@+/, "").replace(/_/g, " ").replace(/\./g, " ")];
  }
  const parts = url.split(/[/:?&=\-_.]/);
  return parts
    .filter((p) => p.length >= 4 && !URL_NOISE.has(p.toLowerCase()) && !/^\d+$/.test(p))
    .map((p) => p.toLowerCase());
}

/** Mirror of _handle_from_link: URL @handle first, then video_id → handle map
 *  (bare map values get a leading "@"). */
export function handleFromLink(
  link: string,
  linkHandleMap?: Record<string, string> | null,
): string | null {
  const creator = extractCreatorFromUrl(link);
  if (creator) return creator;
  if (linkHandleMap) {
    const vid = extractVideoId(link);
    const h = vid ? linkHandleMap[vid] : undefined;
    if (h) return h.startsWith("@") ? h : `@${h}`;
  }
  return null;
}

export interface EchoChamberResult {
  pct: number;
  basis: number;
  distinct_creators: number;
}

/** Mirror of _echo_chamber_index: share of resolved lingered videos on the top-5
 *  creators. Sums the 5 largest per-creator counts, so it is order-independent. */
export function echoChamberIndex(
  lingerLinks: string[],
  linkHandleMap?: Record<string, string> | null,
): EchoChamberResult {
  const freq: Record<string, number> = {};
  for (const link of lingerLinks) {
    const h = handleFromLink(link, linkHandleMap);
    if (h) freq[h] = (freq[h] ?? 0) + 1;
  }
  const values = Object.values(freq);
  const total = values.reduce((a, b) => a + b, 0);
  const top5 = [...values].sort((a, b) => b - a).slice(0, 5).reduce((a, b) => a + b, 0);
  return {
    pct: total > 0 ? pyRound((top5 / total) * 100, 1) : 0.0,
    basis: total,
    distinct_creators: values.length,
  };
}

/**
 * Mirror of _count_creators. HANDLE-FIRST: if any link resolves to a handle, the
 * result is handle-based and unresolved vids are dropped; only if NO handle
 * resolves does it fall back to per-video-id "Unknown" rows.
 *
 * NOTE: Python's sample_titles is `list(set(titles))[:5]` — arbitrary order and,
 * above 5 unique titles, arbitrary selection. Callers/tests compare sample_titles
 * order-insensitively; the parity fixtures keep <=5 unique titles per creator.
 * The input order (a set in Python) is likewise non-deterministic — feed a stable
 * order (e.g. sorted) if reproducible output matters.
 */
export function countCreators(
  linkSet: Iterable<string>,
  limit = 15,
  countKey = "count",
  linkToTitle?: Record<string, string> | null,
  linkHandleMap?: Record<string, string> | null,
): Record<string, unknown>[] {
  const handleFreq = new Map<string, number>();
  const vidFreq = new Map<string, number>();
  const creatorTitles = new Map<string, string[]>();
  const addTitle = (key: string, title: string) => {
    const arr = creatorTitles.get(key);
    if (arr) arr.push(title);
    else creatorTitles.set(key, [title]);
  };
  const hasTitle = (link: string) =>
    !!linkToTitle && Object.prototype.hasOwnProperty.call(linkToTitle, link);

  for (const link of linkSet) {
    const vid = extractVideoId(link);
    if (!vid) continue;
    const creator = handleFromLink(link, linkHandleMap);
    if (creator) {
      handleFreq.set(creator, (handleFreq.get(creator) ?? 0) + 1);
      if (hasTitle(link)) addTitle(creator, linkToTitle![link]);
    } else {
      vidFreq.set(vid, (vidFreq.get(vid) ?? 0) + 1);
      if (hasTitle(link)) addTitle(`vid:${vid}`, linkToTitle![link]);
    }
  }

  const uniq5 = (key: string) => [...new Set(creatorTitles.get(key) ?? [])].slice(0, 5);

  if (handleFreq.size) {
    return [...handleFreq.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, limit)
      .map(([handle, count]) => ({ handle, [countKey]: count, sample_titles: uniq5(handle) }));
  }
  return [...vidFreq.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([vid, count]) => ({ handle: "Unknown", video_id: vid, [countKey]: count, sample_titles: uniq5(`vid:${vid}`) }));
}

// Handle (lowercase, no @) -> [genre, archetype, confidence]. Mirror of CREATOR_REGISTRY.
export const CREATOR_REGISTRY: Record<string, [string, string, number]> = {
  chelseafc: ["sports", "The Dedicated Fan", 1.0],
  premierleague: ["sports", "The Global Spectator", 1.0],
  nba: ["sports", "The Courtside Analyst", 1.0],
  masonmount: ["sports", "The Player Tracker", 0.9],
  reece_james: ["sports", "The Player Tracker", 0.9],
  "brooklyn.beckham": ["fashion", "The Lifestyle Observer", 0.5],
  newyorkcity: ["local_life", "The Urban Resident", 0.8],
  timeoutnewyork: ["local_life", "The City Curator", 0.9],
  uppababy: ["parenting", "The Gear Researcher", 1.0],
  disney: ["parenting", "The Family Entertainer", 0.7],
  cursor_ai: ["tech", "The AI Optimizer", 1.0],
  firebase: ["tech", "The Backend Architect", 1.0],
  marquesbrownlee: ["tech", "The Gadget Guru", 1.0],
  "khaby.lame": ["humor", "The Silent Reactant", 0.9],
};

export interface CreatorMeta {
  handle: string;
  genre: string;
  archetype: string;
  confidence: number;
}

/** Mirror of get_creator_meta: registry lookup by lowercased, @-stripped handle. */
export function getCreatorMeta(handle: string): CreatorMeta | null {
  const clean = handle.toLowerCase().replace(/^@+/, "");
  const entry = CREATOR_REGISTRY[clean];
  if (!entry) return null;
  const [genre, archetype, confidence] = entry;
  return { handle, genre, archetype, confidence };
}

/** Mirror of resolve_vibe_cluster: enrich each entry with registry metadata. */
export function resolveVibeCluster(
  vibeCluster: Record<string, unknown>[],
): Record<string, unknown>[] {
  return vibeCluster.map((entry) => {
    const meta = getCreatorMeta((entry.handle as string) ?? "");
    return meta
      ? { ...entry, ...meta }
      : { ...entry, genre: "unknown", archetype: "unknown", confidence: 0.0 };
  });
}
