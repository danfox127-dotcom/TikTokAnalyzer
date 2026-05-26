/**
 * Psychographic Analysis (TypeScript Port)
 */

import { topCategory, CATEGORY_PHRASES } from "./pillar_categories.ts";

const STOP_WORDS = new Set([
  "the", "and", "to", "of", "a", "in", "is", "for", "on", "you", "that",
  "this", "it", "with", "as", "at", "are", "be", "your", "my", "from",
  "so", "but", "not", "have", "we", "all", "can", "by", "if", "or",
  "an", "do", "what", "just", "about", "like", "how", "out", "up",
  "when", "was", "will", "they", "me", "get", "no", "one", "there",
  "more", "who", "has",
]);

const EMOJI_PATTERN = /[\u{1F300}-\u{1F5FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{1FA70}-\u{1FAFF}]/gu;

export function extractThemes(titles: string[], topK = 18, topP = 12) {
  const words: string[] = [];
  const phrases: string[] = [];
  const emojisList: string[] = [];

  for (const title of titles) {
    if (!title || title === "Title Hidden" || title === "No Caption (Just Hashtags)") {
      continue;
    }

    // Extract hashtags
    const hashtags = title.toLowerCase().match(/#([^\s#]+)/g);
    if (hashtags) {
      hashtags.forEach(h => {
        const tag = h.slice(1);
        if (tag && !STOP_WORDS.has(tag)) words.push(tag);
      });
    }

    // Extract emojis
    const extractedEmojis = title.match(EMOJI_PATTERN);
    if (extractedEmojis) {
      extractedEmojis.forEach(e => emojisList.push(e));
    }

    // Word tokens
    const cleanTitle = title.toLowerCase().replace(/[^\w\s]/g, "");
    const tokens = cleanTitle.split(/\s+/).filter(Boolean);

    // Bigrams
    for (let i = 0; i < tokens.length - 1; i++) {
      if (!STOP_WORDS.has(tokens[i]) && !STOP_WORDS.has(tokens[i + 1])) {
        phrases.push(`${tokens[i]} ${tokens[i + 1]}`);
      }
    }

    // Single words
    tokens.forEach(token => {
      if (token.length > 2 && !STOP_WORDS.has(token)) {
        words.push(token);
      }
    });
  }

  const countFreq = (arr: string[]) => {
    const freq: Record<string, number> = {};
    arr.forEach(x => freq[x] = (freq[x] || 0) + 1);
    return Object.entries(freq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, topK);
  };

  const wordCounts = countFreq(words);
  const phraseCounts = countFreq(phrases).slice(0, topP);
  const emojiCounts = countFreq(emojisList);

  return {
    top_keywords: wordCounts.map(([term, count]) => ({ term, count })),
    top_phrases: phraseCounts.map(([phrase, count]) => ({ phrase, count })),
    top_emojis: emojiCounts.map(([emoji, count]) => ({ emoji, count })),
  };
}

const HEADLINE_TEMPLATES: Record<string, string> = {
  "psychographic": "The algorithm believes you are drawn to {category_phrase}.",
  "anti_profile":  "The algorithm tested {category_phrase} on you. You refused.",
  "sandbox":       "Currently under evaluation: {category_phrase}.",
  "night":         "After midnight, you become someone who watches {category_phrase}.",
};

// ... (skipping the full INTERPRETATIONS dictionary for brevity in the first pass, 
// can be added or loaded from a JSON file in a real migration)

export function buildPillarNarrative(
  pillar: string,
  keywords: any[],
  phrases: any[],
  emojis: any[],
  sampleTitles: string[]
) {
  const effectivePillar = pillar in HEADLINE_TEMPLATES ? pillar : "psychographic";
  const [category] = topCategory(keywords);
  const categoryPhrase = CATEGORY_PHRASES[category] || "content the algorithm has catalogued";

  const headline = HEADLINE_TEMPLATES[effectivePillar].replace("{category_phrase}", categoryPhrase);

  return {
    headline,
    interpretation: "Forensic analysis of your attention signature in this vertical.",
    evidence: sampleTitles.slice(0, 3).filter(t => t && t !== "Title Hidden"),
  };
}
