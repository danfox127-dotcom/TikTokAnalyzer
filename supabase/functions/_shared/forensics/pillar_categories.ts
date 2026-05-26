/**
 * Pillar Categories (TypeScript Port)
 */

export const KEYWORD_CATEGORY: Record<string, string> = {
  "work": "labor", "job": "labor", "salary": "labor", "career": "labor",
  "love": "relationships", "dating": "relationships", "toxic": "relationships",
  "funny": "humor", "comedy": "humor", "meme": "humor", "joke": "humor",
  "news": "news", "politics": "news", "election": "news",
  "art": "aesthetics", "design": "aesthetics", "aesthetic": "aesthetics",
  "wellness": "wellness", "anxiety": "wellness", "therapy": "wellness",
  "money": "finance", "investing": "finance", "crypto": "finance",
  "gaming": "gaming", "game": "gaming", "minecraft": "gaming",
  "food": "food", "recipe": "food", "cooking": "food",
  "parenting": "parenting", "baby": "parenting", "kids": "parenting",
  "fitness": "fitness", "workout": "fitness", "gym": "fitness",
  "tech": "tech", "coding": "tech", "ai": "tech", "software": "tech",
  "music": "music", "song": "music", "artist": "music",
  "style": "fashion", "outfit": "fashion", "makeup": "fashion",
  "spirituality": "spirituality", "zodiac": "spirituality",
  "sports": "sports", "football": "sports", "basketball": "sports",
};

export const CATEGORY_PHRASES: Record<string, string> = {
  "labor": "the hustle and the grind",
  "relationships": "love, longing, and the people in your life",
  "humor": "comedy and absurdity",
  "news": "the state of the world",
  "aesthetics": "visual worlds and artistic sensibility",
  "wellness": "mental health and self-care",
  "finance": "money and financial independence",
  "gaming": "games and virtual worlds",
  "food": "food, cooking, and culinary culture",
  "parenting": "parenthood and family life",
  "fitness": "body, movement, and physical challenge",
  "tech": "technology and digital tools",
  "music": "sound and musical culture",
  "fashion": "style, beauty, and self-expression",
  "spirituality": "meaning, ritual, and the metaphysical",
  "sports": "competition, teams, and the arena",
  "hobbies": "niche interests and personal craft",
  "local_life": "the physical world and local neighborhoods",
};

export function categorize(keyword: string): string | null {
  const kw = keyword.toLowerCase().trim();
  if (kw in KEYWORD_CATEGORY) {
    return KEYWORD_CATEGORY[kw];
  }
  for (const [key, cat] of Object.entries(KEYWORD_CATEGORY)) {
    if (kw.includes(key)) {
      return cat;
    }
  }
  return null;
}

export function topCategory(keywords: { term: string; count: number }[]): [string, number] {
  const categoryWeight: Record<string, number> = {};
  let totalWeight = 0;

  for (const { term, count } of keywords) {
    totalWeight += count;
    const cat = categorize(term);
    if (cat) {
      categoryWeight[cat] = (categoryWeight[cat] || 0) + count;
    }
  }

  if (Object.keys(categoryWeight).length === 0) {
    return ["humor", 0];
  }

  const bestCat = Object.keys(categoryWeight).reduce((a, b) => categoryWeight[a] > categoryWeight[b] ? a : b);
  const confidence = totalWeight ? categoryWeight[bestCat] / totalWeight : 0;
  return [bestCat, Math.round(confidence * 1000) / 1000];
}
