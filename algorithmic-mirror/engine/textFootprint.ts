/**
 * WP-1.1 engine port — text-footprint mining.
 * Mirror of api.ghost_profile._mine_text_footprint.
 *
 * Builds an engagement-weighted interest corpus: each (text, source) is repeated
 * SIGNAL_WEIGHTS[source] times, re-tokenized, and counted — so term counts are
 * weighted and most_common / dominant_source ties break by corpus insertion order
 * (comments → searches → following → shares → favorites → likes).
 *
 * Tokenizer parity: Python uses r"\b[a-zA-Z]{3,}\b" where \b is UNICODE-aware.
 * JS \b is ASCII, so we emulate the Unicode boundary with \p{L}\p{N}_ lookarounds;
 * otherwise "café" would wrongly yield "caf" (Python yields nothing there).
 */

import { keywordsFromUrl } from "./creators";
import { DM_METHODS, SIGNAL_WEIGHTS, FOOTPRINT_STOP } from "./constants";

export interface InterestCluster {
  term: string;
  count: number;
  dominant_source: string;
}
export interface FootprintResult {
  interest_clusters: InterestCluster[];
  top_phrases: { phrase: string; count: number }[];
}

/** Mirror of re.findall(r"\b[a-zA-Z]{3,}\b", text.lower()) with Python's Unicode \b. */
function words3(text: string): string[] {
  return text.toLowerCase().match(/(?<![\p{L}\p{N}_])[a-z]{3,}(?![\p{L}\p{N}_])/gu) ?? [];
}

/** most_common(n): stable sort by count desc, ties by first-insertion order. */
function mostCommon<T>(m: Map<T, number>, n: number): [T, number][] {
  return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, n);
}

export function mineTextFootprint(parsed: any): FootprintResult {
  const corpus: [string, string][] = []; // (text, source)
  const rawComments: string[] = [];

  const push = (text: string, source: string) => {
    const w = SIGNAL_WEIGHTS[source];
    for (let i = 0; i < w; i++) corpus.push([text, source]);
  };

  for (const item of parsed.comments ?? []) {
    const text = item?.comment ?? "";
    if (text) {
      push(text, "comment");
      rawComments.push(text);
    }
  }
  for (const item of parsed.searches ?? []) {
    const text = item?.term ?? "";
    if (text) push(text, "search");
  }
  for (const item of parsed.following ?? []) {
    const username = item?.username ?? "";
    if (username) {
      const text = username.toLowerCase().split(/[._@]/).filter((w: string) => w.length > 2).join(" ");
      if (text) push(text, "follow");
    }
  }
  for (const item of parsed.shares ?? []) {
    const method = (item?.method ?? "").toLowerCase();
    const keywords = keywordsFromUrl(item?.link ?? "");
    if (keywords.length) {
      const source = DM_METHODS.has(method) ? "share_dm" : "share_public";
      for (const kw of keywords) push(kw, source);
    }
  }
  for (const item of parsed.favorites ?? []) {
    for (const kw of keywordsFromUrl(item?.link ?? "")) push(kw, "favorite");
  }
  for (const item of parsed.likes ?? []) {
    for (const kw of keywordsFromUrl(item?.link ?? "")) push(kw, "like");
  }

  if (corpus.length === 0) return { interest_clusters: [], top_phrases: [] };

  const termCounts = new Map<string, number>();
  const termSources = new Map<string, Map<string, number>>();
  for (const [text, source] of corpus) {
    for (const word of words3(text)) {
      if (FOOTPRINT_STOP.has(word)) continue;
      termCounts.set(word, (termCounts.get(word) ?? 0) + 1);
      let sm = termSources.get(word);
      if (!sm) {
        sm = new Map();
        termSources.set(word, sm);
      }
      sm.set(source, (sm.get(source) ?? 0) + 1);
    }
  }

  const interest_clusters: InterestCluster[] = mostCommon(termCounts, 20).map(([term, count]) => ({
    term,
    count,
    dominant_source: mostCommon(termSources.get(term)!, 1)[0][0],
  }));

  const phraseCounts = new Map<string, number>();
  for (const text of rawComments) {
    const words = words3(text);
    for (let i = 0; i < words.length - 1; i++) {
      if (!FOOTPRINT_STOP.has(words[i]) && !FOOTPRINT_STOP.has(words[i + 1])) {
        const p = `${words[i]} ${words[i + 1]}`;
        phraseCounts.set(p, (phraseCounts.get(p) ?? 0) + 1);
      }
    }
  }
  const top_phrases = mostCommon(phraseCounts, 10).map(([phrase, count]) => ({ phrase, count }));

  return { interest_clusters, top_phrases };
}
