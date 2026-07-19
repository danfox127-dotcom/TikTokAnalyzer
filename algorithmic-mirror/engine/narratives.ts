/**
 * WP-1.1 engine port — deterministic narrative blocks.
 * Mirror of api/narratives.py build_narrative_blocks (the 9 _build_*_block fns).
 * The LLM path (generate_narrative_blocks_llm) is out of scope (network).
 *
 * Parity traps: Python f-string formats :.Nf use round-half-to-even and always
 * show N decimals → pyFmt(x, N) = pyRound(x, N).toFixed(N). str.title() → pyTitle.
 */

import { pyRound } from "./numeric";

type GP = Record<string, any>;

/** Python f"{x:.Nf}": banker's-rounded to N decimals, always N decimals shown. */
function pyFmt(x: number, d: number): string {
  return pyRound(x, d).toFixed(d);
}

/** Python str.title(): capitalize each alphabetic run, lowercase the rest. */
function pyTitle(s: string): string {
  return s.replace(/[A-Za-z]+/g, (w) => w[0].toUpperCase() + w.slice(1).toLowerCase());
}

const num = (x: any): number => Number(x ?? 0) || 0;

function algorithmicIdentity(gp: GP): any {
  const bn = gp.behavioral_nodes ?? {};
  const followedPct = num(bn.social_graph_followed_pct);
  const algoPct = num(bn.social_graph_algorithmic_pct);
  const vibe: any[] = gp.creator_entities?.vibe_cluster ?? [];
  const topCreator = vibe.length ? vibe[0].handle ?? "Unknown" : "Unknown";

  let prose: string;
  if (followedPct > 60) {
    prose =
      `Your feed is primarily driven by creators you've chosen to follow — ${pyFmt(followedPct, 0)}% ` +
      `of your sustained attention goes to followed accounts, putting you among the most ` +
      `intentional viewers on the platform. Your top creator, ${topCreator}, has earned a ` +
      `disproportionate share of your time. TikTok's algorithm confirms your taste rather ` +
      `than shaping it.`;
  } else if (followedPct < 30) {
    prose =
      `TikTok's algorithm dominates your attention. Only ${pyFmt(followedPct, 0)}% of your sustained ` +
      `viewing goes to accounts you've explicitly followed — the rest is pure machine curation. ` +
      `Your most-watched creator, ${topCreator}, was likely surfaced algorithmically. ` +
      `You are largely a product of the recommendation engine.`;
  } else {
    prose =
      `You split your attention between followed accounts (${pyFmt(followedPct, 0)}%) and ` +
      `algorithmic discovery (${pyFmt(algoPct, 0)}%). ${topCreator} leads your sustained viewing. ` +
      `This balance suggests a measured relationship with the platform — curious but not ` +
      `fully surrendered to the feed.`;
  }

  const top3 = vibe.slice(0, 3);
  const stats: any[] = [
    { label: "Followed %", value: `${pyFmt(followedPct, 0)}%` },
    { label: "Algorithmic %", value: `${pyFmt(algoPct, 0)}%` },
  ];
  top3.forEach((c, i) => stats.push({ label: `#${i + 1} Creator`, value: c.handle ?? "?" }));

  const totalLinger = vibe.reduce((a, c) => a + num(c.linger_count), 0);
  const top5 = vibe.slice(0, 5);
  const top5Linger = top5.reduce((a, c) => a + num(c.linger_count), 0);
  const chartData: any[] = top5
    .filter((c) => num(c.linger_count) > 0)
    .map((c) => ({ name: c.handle ?? "Unknown", value: num(c.linger_count) }));
  if (totalLinger > top5Linger && totalLinger > 0) {
    chartData.push({ name: "Other", value: totalLinger - top5Linger });
  }

  return {
    id: "algorithmic_identity", title: "ALGORITHMIC IDENTITY", icon: "🎭", prose,
    accent: "#4db8ff", stats,
    chart: chartData.length ? { type: "donut", data: chartData } : null,
    provenance: "Derived from watch time deltas (linger count) on identified creator handles vs discovery feed.",
  };
}

function attentionSignature(gp: GP): any {
  const bn = gp.behavioral_nodes ?? {};
  const sw = gp.stopwatch_metrics ?? {};
  const skipRate = num(bn.skip_rate_percentage);
  const lingerRate = num(bn.linger_rate_percentage);
  const total = Math.trunc(num(sw.total_conscious_videos));
  const deepDives = Math.trunc(num(sw.deep_dives));
  const deepDivePct = pyRound((deepDives / Math.max(total, 1)) * 100, 1);

  let prose: string;
  if (lingerRate > 20) {
    prose =
      `You are a deep watcher. ${pyFmt(lingerRate, 0)}% of your views end in extended viewing — ` +
      `far above typical patterns. TikTok's engagement model treats this as a strong positive ` +
      `signal: creators you linger on are amplified in others' feeds. Your attention is a ` +
      `resource the algorithm harvests aggressively.`;
  } else if (skipRate > 50) {
    prose =
      `You are a ruthless curator. You skip ${pyFmt(skipRate, 0)}% of content quickly, training ` +
      `the algorithm through rejection as much as acceptance. The videos that do hold your ` +
      `attention — ${pyFmt(lingerRate, 0)}% of views — send disproportionately strong signals. ` +
      `Scarcity makes your engagement more valuable to the model.`;
  } else {
    prose =
      `Your viewing pattern is balanced — ${pyFmt(skipRate, 0)}% skipped, ${pyFmt(lingerRate, 0)}% ` +
      `lingered. You engage moderately across a range of content rather than sending strong ` +
      `directional signals. The algorithm has a stable, moderate picture of your preferences.`;
  }

  return {
    id: "attention_signature", title: "ATTENTION SIGNATURE", icon: "👁️", prose,
    accent: "#ff8c42",
    stats: [
      { label: "Linger Rate", value: `${pyFmt(lingerRate, 1)}%` },
      { label: "Skip Rate", value: `${pyFmt(skipRate, 1)}%` },
      { label: "Deep Dive Rate", value: `${pyFmt(deepDivePct, 1)}%` },
      { label: "Total Videos", value: String(total) },
    ],
    chart: {
      type: "bar",
      data: [
        { metric: "Linger", value: pyRound(lingerRate, 1) },
        { metric: "Skip", value: pyRound(skipRate, 1) },
        { metric: "Deep Dive", value: deepDivePct },
      ],
    },
    provenance: `Calculated from video interaction events (skip/linger ratios) across ${total} conscious views.`,
  };
}

function dailyRhythm(gp: GP): any {
  const sw = gp.stopwatch_metrics ?? {};
  const bn = gp.behavioral_nodes ?? {};
  const heatmap: Record<string, any> = sw.hourly_heatmap ?? {};
  const totalEvents = Math.trunc(num(sw.total_raw_videos));
  const nightPct = num(bn.night_shift_ratio);
  const peakLabel = bn.peak_hour ?? "Unknown";

  let prose: string;
  if (nightPct > 30) {
    prose =
      `You are a night viewer — ${pyFmt(nightPct, 0)}% of your TikTok activity occurs between ` +
      `11 PM and 4 AM. Your peak engagement hour is ${peakLabel}. Late-night usage is ` +
      `associated with passive consumption and higher ad susceptibility. TikTok's ad ` +
      `targeting systems actively exploit this window.`;
  } else {
    prose =
      `Your peak viewing hour is ${peakLabel}. ${pyFmt(nightPct, 0)}% of your activity occurs in ` +
      `the late-night window (11 PM–4 AM). Your usage pattern follows a typical circadian ` +
      `rhythm — consistent with intentional rather than compulsive consumption.`;
  }

  const chartData = Array.from({ length: 24 }, (_, h) => ({ hour: String(h), count: Math.trunc(num(heatmap[String(h)])) }));
  const activeHours = Object.values(heatmap).filter((v) => Math.trunc(num(v)) > 0).length;

  return {
    id: "dayparting", title: "DAILY RHYTHM", icon: "🕐", prose, accent: "#a8ff78",
    stats: [
      { label: "Peak Hour", value: peakLabel },
      { label: "Night Viewing", value: `${pyFmt(nightPct, 0)}%` },
      { label: "Active Hours", value: String(activeHours) },
    ],
    chart: { type: "bar", data: chartData },
    provenance: `Aggregated from hourly engagement frequency across ${totalEvents} video events.`,
  };
}

function socialGraph(gp: GP): any {
  const bn = gp.behavioral_nodes ?? {};
  const followedPct = num(bn.social_graph_followed_pct);
  const algoPct = num(bn.social_graph_algorithmic_pct);
  const followingCount = Math.trunc(num(gp.declared_signals?.following_count));
  const vibe: any[] = gp.creator_entities?.vibe_cluster ?? [];
  const topCreator = vibe.length ? vibe[0].handle ?? "—" : "—";

  let prose: string;
  if (followedPct > 50) {
    prose =
      `You follow ${followingCount} accounts, and ${pyFmt(followedPct, 0)}% of your sustained ` +
      `viewing goes to them. Your social graph is functioning as intended — you follow ` +
      `creators you actually watch. This is increasingly rare on TikTok, where the FYP ` +
      `often displaces intentional subscriptions entirely.`;
  } else if (followedPct < 20) {
    prose =
      `You follow ${followingCount} accounts, but only ${pyFmt(followedPct, 0)}% of your sustained ` +
      `viewing goes to them. The algorithm has almost entirely displaced your social graph. ` +
      `In effect, your follower list is decorative — the machine decides what you see.`;
  } else {
    prose =
      `You follow ${followingCount} accounts, with ${pyFmt(followedPct, 0)}% of your viewing ` +
      `going to followed creators and ${pyFmt(algoPct, 0)}% to algorithmically-surfaced content. ` +
      `Your top watched creator is ${topCreator}. The social graph still has some influence.`;
  }

  const nodes = vibe.slice(0, 12).map((c) => ({
    name: c.handle ?? "Unknown", size: num(c.linger_count),
    is_followed: c.is_followed ?? false, genre: c.genre ?? "unknown",
  }));

  return {
    id: "social_graph", title: "SOCIAL GRAPH", icon: "🕸️", prose, accent: "#ff4db8",
    stats: [
      { label: "Following", value: String(followingCount) },
      { label: "Watched (Followed)", value: `${pyFmt(followedPct, 0)}%` },
      { label: "Watched (Algorithmic)", value: `${pyFmt(algoPct, 0)}%` },
      { label: "Top Watched", value: topCreator },
    ],
    chart: { type: "creator_graph", data: nodes },
    provenance: "Determined by comparing engagement metrics on followed accounts vs algorithmically-surfaced creators.",
  };
}

function shareBehavior(gp: GP, parsed: GP): any {
  const sb = gp.share_behavior ?? {};
  const totalShares = Math.trunc(num(sb.total_shares));
  const behaviorType = sb.share_behavior_type ?? "Mixed Sharer";
  const primaryMethod = pyTitle(String(sb.primary_share_method || "none"));
  const shareMethods: Record<string, number> = sb.share_methods ?? {};
  const totalLikes = (parsed.likes ?? []).length;
  const shareToLike = pyRound(totalShares / Math.max(totalLikes, 1), 3);

  let prose: string;
  if (totalShares === 0) {
    prose = "You have shared no content from TikTok. You leave no traceable content trail outside the platform.";
  } else if (behaviorType === "Private Curator") {
    prose =
      `You are a Private Curator. The majority of your ${totalShares} shares go through ` +
      `direct message, primarily via ${primaryMethod}. Your shares are high-signal ` +
      `recommendations, not reflexive reposting.`;
  } else {
    prose =
      `Your sharing behavior is ${behaviorType.toLowerCase()} — ${totalShares} shares, ` +
      `with ${primaryMethod} as the primary method. You extend TikTok's reach beyond the platform.`;
  }

  const chartData = Object.entries(shareMethods)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ name: pyTitle(k), value: v }));

  return {
    id: "share_behavior", title: "SHARE BEHAVIOR", icon: "🔗", prose, accent: "#ffd700",
    stats: [
      { label: "Total Shares", value: String(totalShares) },
      { label: "Type", value: behaviorType },
      { label: "Primary Method", value: primaryMethod },
      { label: "Share/Like Ratio", value: pyFmt(shareToLike, 3) },
    ],
    chart: chartData.length ? { type: "donut", data: chartData } : null,
    provenance: "Extracted from share method metadata and correlated with like volume.",
  };
}

function commentVoice(gp: GP): any {
  const cv = gp.comment_voice ?? {};
  const total = Math.trunc(num(cv.total_comments));
  const avgChars = num(cv.avg_length_chars);
  const styleLabel = cv.engagement_style_label ?? "Lurker";

  const prose =
    total === 0
      ? "No comments found. You are a silent viewer, engaging through watch time rather than text."
      : `You are a ${styleLabel}. Your ${total} comments average ${pyFmt(avgChars, 0)} characters. ` +
        `Your textual footprint reflects a ${styleLabel.toLowerCase()} mode of engagement.`;

  return {
    id: "comment_voice", title: "COMMENT VOICE", icon: "💬", prose, accent: "#c8a2c8",
    stats: [
      { label: "Total Comments", value: String(total) },
      { label: "Avg Length", value: `${pyFmt(avgChars, 0)} chars` },
      { label: "Style", value: styleLabel },
    ],
    chart: null,
    provenance: "Analyzed from comment length and frequency relative to viewing volume.",
  };
}

function transparencyGapBlock(gp: GP): any {
  const tg = gp.transparency_gap ?? {};
  const officialCount = Math.trunc(num(tg.official_ad_interest_count));
  const behavioralCount = Math.trunc(num(tg.behavioral_interest_count));
  const interpretation = tg.gap_interpretation ?? "";
  const footprint = gp.digital_footprint ?? {};
  const loginCount = Math.trunc(num(footprint.login_count));
  const uniqueIps = Math.trunc(num(footprint.unique_ips));

  const prose =
    officialCount === 0 && behavioralCount > 5
      ? `Your ad interest profile is empty, yet behavioral analysis shows ${behavioralCount} ` +
        `inferred interest clusters. The algorithm sees far more than what it reports.`
      : `TikTok discloses ${officialCount} declared interests — but behavioral signals ` +
        `reveal ${behavioralCount} clusters. ${interpretation}`;

  return {
    id: "transparency_gap", title: "TRANSPARENCY GAP", icon: "🔍", prose, accent: "#ff4466",
    stats: [
      { label: "Declared Interests", value: String(officialCount) },
      { label: "Behavioral Clusters", value: String(behavioralCount) },
      { label: "Login Events", value: String(loginCount) },
      { label: "Unique IPs", value: String(uniqueIps) },
    ],
    chart: {
      type: "bar",
      data: [
        { category: "Ad Interests", count: officialCount },
        { category: "Behaviors", count: behavioralCount },
        { category: "Logins", count: loginCount },
      ],
    },
    provenance: "Forensic gap between 'Settings Interests' and behavioral categories inferred from video metadata.",
  };
}

function locationTrace(gp: GP): any {
  const logins: any[] = gp.digital_footprint?.recent_logins ?? [];
  const cityCounter = new Map<string, number>();
  for (const login of logins) {
    const city = login.city || "";
    if (city && city !== "Unknown") cityCounter.set(city, (cityCounter.get(city) ?? 0) + 1);
  }
  // most_common(1): stable sort by count desc, first-insertion on ties
  const homeCity = cityCounter.size
    ? [...cityCounter.entries()].sort((a, b) => b[1] - a[1])[0][0]
    : "Unknown";
  const cityCount = cityCounter.size;

  return {
    id: "location_trace", title: "WHERE TIKTOK FOUND YOU", icon: "📍",
    prose:
      `Your login history covers ${cityCount} cities, with ${homeCity} as your home base. ` +
      `Even a single IP can reveal your ISP and approximate neighborhood.`,
    accent: "#00e5ff",
    stats: [
      { label: "Home City", value: homeCity },
      { label: "Cities Seen", value: String(cityCount) },
      { label: "Login Events", value: String(logins.length) },
    ],
    chart: null,
    provenance: `Geolocated from IP addresses recorded in ${logins.length} distinct login events.`,
  };
}

function closingSynthesis(gp: GP): any {
  const archetype = gp.primary_archetype?.name ?? "The Balanced Viewer";
  return {
    id: "closing_synthesis", title: "CLOSING SYNTHESIS", icon: "🧠",
    prose:
      `Across your usage history, you emerge as ${archetype}. ` +
      `The algorithm characterizes you through behavior rather than stated preferences. ` +
      `This dossier is a partial reconstruction — TikTok's actual model is orders of magnitude more granular.`,
    accent: "#e0e0e0", stats: [], chart: null,
    provenance: "Cross-dimensional behavioral synthesis mapped from all forensic blocks.",
  };
}

export function buildNarrativeBlocks(ghostProfile: GP, parsed: GP): any[] {
  const builders: Array<(gp: GP, p: GP) => any> = [
    (gp) => algorithmicIdentity(gp),
    (gp) => attentionSignature(gp),
    (gp) => dailyRhythm(gp),
    (gp) => socialGraph(gp),
    (gp, p) => shareBehavior(gp, p),
    (gp) => commentVoice(gp),
    (gp) => transparencyGapBlock(gp),
    (gp) => locationTrace(gp),
    (gp) => closingSynthesis(gp),
  ];
  const blocks: any[] = [];
  for (const builder of builders) {
    try {
      blocks.push(builder(ghostProfile, parsed));
    } catch {
      /* skip failed block, matching the Python try/except */
    }
  }
  return blocks;
}
