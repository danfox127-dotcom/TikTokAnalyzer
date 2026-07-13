/**
 * WP-1.1 engine port — comment-voice + share-behavior analysis.
 * Mirrors api.ghost_profile.analyze_comment_voice and _analyze_share_behavior.
 *
 * Parity trap: Python len() counts CODE POINTS; JS .length counts UTF-16 units.
 * Any comment with an astral emoji would diverge on avg length, the >150
 * long-comment boundary, and the top-20 sort — so all string lengths here use
 * cpLen() ([...s].length), never .length.
 */

import { DM_METHODS } from "./constants";
import { pyRound } from "./numeric";

/** Code-point length, matching Python len(). */
function cpLen(s: string): number {
  return [...s].length;
}

/** most_common(n): stable sort by count desc, ties by first-insertion order. */
function mostCommon(m: Map<string, number>, n: number): [string, number][] {
  return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, n);
}

// Mirror of _ENTITY_KEYWORDS (order preserved for references output).
const ENTITY_KEYWORDS: Record<string, string[]> = {
  sports_teams: ["lakers", "warriors", "celtics", "bulls", "knicks", "nets", "heat", "patriots", "cowboys", "chiefs", "packers", "49ers", "yankees", "dodgers", "cubs", "nba", "nfl", "mlb", "nhl"],
  tv_shows: ["stranger things", "the office", "breaking bad", "game of thrones", "friends", "seinfeld", "succession", "ozark", "sopranos", "wire"],
  musicians: ["taylor swift", "drake", "beyonce", "kendrick", "billie eilish", "eminem", "rihanna", "travis scott", "bad bunny", "sza"],
  political_figures: ["trump", "biden", "obama", "aoc", "bernie", "pelosi", "desantis", "harris", "musk"],
  films: ["avengers", "oppenheimer", "barbie", "inception", "interstellar", "joker", "parasite", "dune", "titanic", "matrix"],
};

// Same ranges/flags as _EMOJI_RE (runs of emoji, broad ranges).
const EMOJI_RE =
  /[\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F300}-\u{1F5FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F9FF}\u{1FA00}-\u{1FA9F}]+/gu;

export interface CommentVoice {
  total_comments: number;
  avg_length_chars: number;
  long_comments_count: number;
  long_comment_pct: number;
  top_20_longest: string[];
  references_detected: Record<string, string[]>;
  emoji_density: number;
  engagement_style_label: string;
}

export function analyzeCommentVoice(
  comments: { comment?: string }[],
  activeVideoCount: number,
  dmShareCount = 0,
): CommentVoice {
  const texts = comments.filter((c) => c?.comment).map((c) => c.comment as string);
  const total = texts.length;

  if (total === 0) {
    return {
      total_comments: 0, avg_length_chars: 0.0, long_comments_count: 0,
      long_comment_pct: 0.0, top_20_longest: [], references_detected: {},
      emoji_density: 0.0, engagement_style_label: "Lurker",
    };
  }

  const lengths = texts.map(cpLen);
  const avgLength = lengths.reduce((a, b) => a + b, 0) / total;
  const longComments = texts.filter((t) => cpLen(t) > 150);
  const top20 = [...texts].sort((a, b) => cpLen(b) - cpLen(a)).slice(0, 20);

  const totalChars = lengths.reduce((a, b) => a + b, 0);
  const emojiChars = texts.reduce((acc, t) => acc + cpLen((t.match(EMOJI_RE) ?? []).join("")), 0);
  const emojiDensity = totalChars > 0 ? emojiChars / totalChars : 0.0;

  const allText = texts.join(" ").toLowerCase();
  const references: Record<string, string[]> = {};
  for (const [category, keywords] of Object.entries(ENTITY_KEYWORDS)) {
    const found = keywords.filter((kw) => allText.includes(kw));
    if (found.length) references[category] = found;
  }

  const commentRate = activeVideoCount > 0 ? total / activeVideoCount : 0.0;
  let label: string;
  if (commentRate < 0.005) label = "Lurker";
  else if (avgLength > 100 && emojiDensity < 0.05) label = "Analytical Commenter";
  else if (avgLength < 40 && commentRate > 0.05) label = "Reactive Commenter";
  else if (total < 20 && dmShareCount > total * 3) label = "Curator";
  else label = "Community Participant";

  return {
    total_comments: total,
    avg_length_chars: pyRound(avgLength, 1),
    long_comments_count: longComments.length,
    long_comment_pct: pyRound((longComments.length / total) * 100, 1),
    top_20_longest: top20,
    references_detected: references,
    emoji_density: pyRound(emojiDensity, 4),
    engagement_style_label: label,
  };
}

export interface ShareBehavior {
  total_shares: number;
  share_methods: Record<string, number>;
  primary_share_method: string | null;
  share_behavior_type: string;
  dm_share_count: number;
}

export function analyzeShareBehavior(shares: { method?: string | null }[]): ShareBehavior {
  if (!shares.length) {
    return {
      total_shares: 0, share_methods: {}, primary_share_method: null,
      share_behavior_type: "Mixed Sharer", dm_share_count: 0,
    };
  }

  const methodCounts = new Map<string, number>();
  let dmCount = 0;
  let publicCount = 0;
  for (const item of shares) {
    const method = (item?.method || "unknown").toLowerCase();
    methodCounts.set(method, (methodCounts.get(method) ?? 0) + 1);
    if (DM_METHODS.has(method)) dmCount++;
    else publicCount++;
  }

  const total = shares.length;
  const primary = mostCommon(methodCounts, 1)[0][0];
  const dmPct = dmCount / total;
  const publicPct = publicCount / total;

  const behaviorType =
    dmPct >= 0.7 ? "Private Curator" : publicPct > 0.5 ? "Public Broadcaster" : "Mixed Sharer";

  return {
    total_shares: total,
    share_methods: Object.fromEntries(methodCounts),
    primary_share_method: primary,
    share_behavior_type: behaviorType,
    dm_share_count: dmCount,
  };
}
