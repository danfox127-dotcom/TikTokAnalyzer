/**
 * WP-1.1 engine port — pillar categories.
 * Mirrors utils.pillar_categories.{categorize, top_category}.
 *
 * Parity note: the substring fallback in categorize() and the max() in
 * top_category() are BOTH order-dependent on KEYWORD_CATEGORY insertion order,
 * so the entries below are kept in the EXACT order of the Python dict.
 */

import { pyRound } from "./numeric";

// Insertion order is load-bearing — do not reorder. (Mirror of the Python dict.)
export const KEYWORD_CATEGORY = new Map<string, string>([
  ["work", "labor"], ["job", "labor"], ["salary", "labor"], ["career", "labor"],
  ["love", "relationships"], ["dating", "relationships"], ["toxic", "relationships"],
  ["funny", "humor"], ["comedy", "humor"], ["meme", "humor"], ["joke", "humor"],
  ["news", "news"], ["politics", "news"], ["election", "news"],
  ["art", "aesthetics"], ["design", "aesthetics"], ["aesthetic", "aesthetics"],
  ["wellness", "wellness"], ["anxiety", "wellness"], ["therapy", "wellness"],
  ["money", "finance"], ["investing", "finance"], ["crypto", "finance"],
  ["gaming", "gaming"], ["game", "gaming"], ["minecraft", "gaming"],
  ["food", "food"], ["recipe", "food"], ["cooking", "food"],
  ["parenting", "parenting"], ["baby", "parenting"], ["kids", "parenting"],
  ["fitness", "fitness"], ["workout", "fitness"], ["gym", "fitness"],
  ["tech", "tech"], ["coding", "tech"], ["ai", "tech"], ["software", "tech"],
  ["music", "music"], ["song", "music"], ["artist", "music"],
  ["style", "fashion"], ["outfit", "fashion"], ["makeup", "fashion"],
  ["spirituality", "spirituality"], ["zodiac", "spirituality"],
  ["sports", "sports"], ["football", "sports"], ["basketball", "sports"],
]);

export const CATEGORY_PHRASES: Record<string, string> = {
  labor: "the hustle and the grind",
  relationships: "love, longing, and the people in your life",
  humor: "comedy and absurdity",
  news: "the state of the world",
  aesthetics: "visual worlds and artistic sensibility",
  wellness: "mental health and self-care",
  finance: "money and financial independence",
  gaming: "games and virtual worlds",
  food: "food, cooking, and culinary culture",
  parenting: "parenthood and family life",
  fitness: "body, movement, and physical challenge",
  tech: "technology and digital tools",
  music: "sound and musical culture",
  fashion: "style, beauty, and self-expression",
  spirituality: "meaning, ritual, and the metaphysical",
  sports: "competition, teams, and the arena",
  hobbies: "niche interests and personal craft",
  local_life: "the physical world and local neighborhoods",
};

/** Category for a keyword: exact match, then first ordered substring match, else null. */
export function categorize(keyword: string): string | null {
  const kw = keyword.toLowerCase().trim();
  const exact = KEYWORD_CATEGORY.get(kw);
  if (exact !== undefined) return exact;
  for (const [key, cat] of KEYWORD_CATEGORY) {
    if (kw.includes(key)) return cat;
  }
  return null;
}

export interface WeightedKeyword {
  term?: string;
  count?: number;
}

/** Dominant category from a weighted keyword list. Ties break to first-inserted. */
export function topCategory(keywords: WeightedKeyword[]): [string, number] {
  const categoryWeight = new Map<string, number>();
  let totalWeight = 0;

  for (const kw of keywords) {
    const term = kw?.term ?? "";
    const count = Number(kw?.count ?? 1); // Python float(kw.get("count", 1)); present-but-0 stays 0
    totalWeight += count;
    const cat = categorize(term);
    if (cat) categoryWeight.set(cat, (categoryWeight.get(cat) ?? 0) + count);
  }

  if (categoryWeight.size === 0) return ["humor", 0.0];

  let bestCat = "";
  let bestW = -Infinity;
  for (const [cat, w] of categoryWeight) {
    if (w > bestW) { // strict > → first max in insertion order wins
      bestW = w;
      bestCat = cat;
    }
  }
  const confidence = totalWeight ? pyRound(bestW / totalWeight, 3) : 0.0;
  return [bestCat, confidence];
}
