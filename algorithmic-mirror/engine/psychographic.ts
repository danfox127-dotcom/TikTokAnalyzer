/**
 * WP-1.1 engine port — theme extraction.
 * Mirror of utils.psychographic.extract_themes.
 *
 * Parity choices, each of which a naive port gets wrong:
 *  - word cleanup uses Unicode letter/number classes (`\p{L}\p{N}_`) to match
 *    Python's Unicode `\w`; JS `\w` is ASCII-only and would mangle accented/CJK
 *    text ("café" -> "caf").
 *  - per title, hashtag words are appended BEFORE token words — this insertion
 *    order is what breaks ties in most_common (stable sort by count desc).
 *  - emojis are matched on the ORIGINAL (non-lowercased) title over the exact
 *    Python code-point ranges, one code point per match.
 *  - most_common(n) == stable sort by count desc, ties by first-insertion.
 */

const STOP_WORDS = new Set<string>([
  "the", "and", "to", "of", "a", "in", "is", "for", "on", "you", "that",
  "this", "it", "with", "as", "at", "are", "be", "your", "my", "from",
  "so", "but", "not", "have", "we", "all", "can", "by", "if", "or",
  "an", "do", "what", "just", "about", "like", "how", "out", "up",
  "when", "was", "will", "they", "me", "get", "no", "one", "there",
  "more", "who", "has",
]);

// Same code-point ranges as psychographic.EMOJI_PATTERN, one code point per match.
const EMOJI_RE =
  /[\u{1F300}-\u{1F5FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{1FA70}-\u{1FAFF}]/gu;

export interface Themes {
  top_keywords: { term: string; count: number }[];
  top_phrases: { phrase: string; count: number }[];
  top_emojis: { emoji: string; count: number }[];
}

/** Counter.most_common(n): stable sort by count desc; ties keep first-insertion order. */
function mostCommon(items: string[], n: number): [string, number][] {
  const freq = new Map<string, number>();
  for (const x of items) freq.set(x, (freq.get(x) ?? 0) + 1);
  return [...freq.entries()].sort((a, b) => b[1] - a[1]).slice(0, n);
}

export function extractThemes(titles: string[], topK = 18, topP = 12): Themes {
  const words: string[] = [];
  const phrases: string[] = [];
  const emojis: string[] = [];

  for (const title of titles) {
    if (!title || title === "Title Hidden" || title === "No Caption (Just Hashtags)") continue;

    const lower = title.toLowerCase();

    // Hashtags (from the lowercased title, kept without '#'), appended first.
    for (const m of lower.matchAll(/#([^\s#]+)/gu)) {
      const h = m[1];
      if (h && !STOP_WORDS.has(h)) words.push(h);
    }

    // Emoji tokens from the ORIGINAL title, one code point per match.
    const em = title.match(EMOJI_RE);
    if (em) for (const e of em) emojis.push(e);

    // Word tokens: strip non-word punctuation (Unicode \w), keep spaces.
    const clean = lower.replace(/[^\p{L}\p{N}_\s]/gu, "");
    const tokens = clean.split(/\s+/).filter((t) => t.length > 0);

    for (let i = 0; i < tokens.length - 1; i++) {
      if (!STOP_WORDS.has(tokens[i]) && !STOP_WORDS.has(tokens[i + 1])) {
        phrases.push(`${tokens[i]} ${tokens[i + 1]}`);
      }
    }
    for (const t of tokens) {
      if (t.length > 2 && !STOP_WORDS.has(t)) words.push(t);
    }
  }

  return {
    top_keywords: mostCommon(words, topK).map(([term, count]) => ({ term, count })),
    top_phrases: mostCommon(phrases, topP).map(([phrase, count]) => ({ phrase, count })),
    top_emojis: mostCommon(emojis, topK).map(([emoji, count]) => ({ emoji, count })),
  };
}
