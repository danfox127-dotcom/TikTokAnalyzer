/**
 * explanations.ts — newsroom-voice captions for every datum we render.
 *
 * Voice: dossier register. We are reporters reading a file the subject
 * received from ByteDance. No second-person hectoring, no academic hedging.
 * Short sentences. Specific verbs. The data is the lede; the caption is the
 * subhed that tells the reader what they're looking at.
 *
 * Keys are kebab-case slugs of the form `<scope>.<field>`.
 * - `surface.*`  — the bright pre-transition Surface phase
 * - `dossier.*`  — the dark Glass House sections (reserved; not yet used)
 *
 * Each value is a 1-2 sentence string. Keep them under ~140 chars.
 *
 * If you add a render that needs an explanation, add the key here first and
 * import `caption('surface.foo')` from the component. Missing keys throw in
 * development to keep us honest; in production they degrade to an empty
 * string so a typo can't blank a page.
 */

const EXPLANATIONS: Record<string, string> = {
  // ── Surface · Hero ─────────────────────────────────────────────────────────
  "surface.hero.kicker":
    "Vol. I · Edition One · The Surface",
  "surface.hero.lede":
    "ByteDance handed over your file. This is the side of it you knew about.",

  // ── Surface · Stats row ────────────────────────────────────────────────────
  "surface.following_count":
    "Accounts you chose to follow. The deliberate edge of the social graph.",
  "surface.follower_count":
    "Accounts that chose to follow you. The other half of the contract.",

  // ── Surface · Declared interests grid ──────────────────────────────────────
  "surface.settings_interests.heading":
    "What You Said You Wanted",
  "surface.settings_interests.caption":
    "The categories you ticked during onboarding. TikTok treats these as your opening bid.",

  // ── Surface · Ad categories ────────────────────────────────────────────────
  "surface.ad_interests.heading":
    "What Advertisers Were Told About You",
  "surface.ad_interests.caption":
    "The audience labels TikTok sells to advertisers on your behalf. You did not pick these — TikTok did.",

  // ── Surface · Recent searches ──────────────────────────────────────────────
  "surface.recent_searches.heading":
    "What You Asked It About",
  "surface.recent_searches.caption":
    "The last things you typed into the search bar. Each query is a pin in the map of your interest.",

  // ── Surface · TikTok Shop orders ───────────────────────────────────────────
  "surface.shop_orders.heading":
    "What You Bought On Platform",
  "surface.shop_orders.caption":
    "TikTok Shop purchases on file. First-party purchase intent — the strongest signal in the building.",

  // ── Surface · Algorithm Note (anchor explanation) ──────────────────────────
  "surface.algorithm_note.heading":
    "How To Read This Page",
  "surface.algorithm_note.body_a":
    "This is what you handed over at the door. Your age, your location, the boxes you ticked, the things you searched. The deliberate part.",
  "surface.algorithm_note.body_b":
    "The algorithm builds the rest from how you behaved once inside. That part — the ghost profile, the inferred preferences, the patterns you never typed — is on the next page.",
  "surface.algorithm_note.weighting":
    "Weighting · high impact at signup, decays as behavior accumulates.",

  // ── Surface · Apple ATT permission card ────────────────────────────────────
  "surface.permissions.heading":
    "TikTok would also like permission to track you.",
  "surface.permissions.body":
    "You agreed to this when you created the account. The four lines below are what the agreement actually covers.",

  "surface.permissions.watch_history":
    "Every video you watched. How long, whether you replayed it, whether you skipped.",
  "surface.permissions.social_graph":
    "Who you follow versus who TikTok served you. The split between your taste and the algorithm's.",
  "surface.permissions.active_hours":
    "What time of day you open the app. Including the 2 a.m. opens.",
  "surface.permissions.skip_signal":
    "Every video you rejected in under three seconds. Negative signal is fed back into your profile too.",

  // ── Surface · Sentinel / scroll cue ────────────────────────────────────────
  "surface.scroll_cue.line_1":
    "That was the surface layer.",
  "surface.scroll_cue.line_2":
    "Keep scrolling to see what the algorithm built underneath.",
};

/**
 * Look up a caption by key. Throws in development if the key is missing —
 * that's a bug we want to surface immediately. Returns "" in production so a
 * typo in a one-off render never blanks a page.
 */
export function caption(key: string): string {
  const value = EXPLANATIONS[key];
  if (value === undefined) {
    if (process.env.NODE_ENV !== "production") {
      throw new Error(`[explanations] missing key: "${key}"`);
    }
    return "";
  }
  return value;
}

export default EXPLANATIONS;
