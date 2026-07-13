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
