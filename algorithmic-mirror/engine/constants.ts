/**
 * WP-1.1 engine port — shared constants (mirror of api.ghost_profile module globals).
 */

export const DM_METHODS = new Set<string>([
  "chat_head", "dm", "message", "whatsapp", "instagram",
  "line", "kakaotalk", "telegram",
]);

export const SIGNAL_WEIGHTS: Record<string, number> = {
  comment: 10,
  favorite: 7,
  share_dm: 8,
  share_public: 4,
  follow: 6,
  search: 5,
  like: 3,
};

// Larger stopword set used by the text-footprint / temporal features
// (distinct from psychographic.STOP_WORDS).
export const FOOTPRINT_STOP = new Set<string>([
  "the", "and", "to", "of", "a", "in", "is", "for", "on", "you", "that",
  "this", "it", "with", "as", "at", "are", "be", "your", "my", "from",
  "so", "but", "not", "have", "we", "all", "can", "by", "if", "or",
  "an", "do", "what", "just", "about", "like", "how", "out", "up",
  "when", "was", "will", "they", "me", "get", "no", "one", "there",
  "its", "also", "more", "than", "then", "now", "has", "had", "him",
  "her", "she", "he", "who", "which", "been", "would", "could", "should",
]);

export const URL_NOISE = new Set<string>([
  "www", "com", "tiktok", "http", "https", "video", "tag", "discover",
]);
