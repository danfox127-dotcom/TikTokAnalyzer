/**
 * WP-1.1 engine port — the orchestrator.
 * Mirror of api.ghost_profile.build_ghost_profile: composes every ported module
 * plus the inline logic (social-graph split, is_followed, search rhythm, declared
 * surface, top-hours / vulnerability window) into the full Ghost Profile payload.
 *
 * Non-determinism note: vibe_cluster/graveyard come from countCreators (Python set
 * iteration) and following_usernames is a set→list — so `sample_titles` per creator
 * and `enrichment_targets.following_usernames` have no stable order. The parity test
 * sorts those before comparing; fixtures use distinct counts so all other ordering
 * (which creator ranks where) is fixed by count.
 */

import { runStopwatch, periodKey, PeriodCounts } from "./stopwatch";
import { extractVideoId } from "./videoId";
import { TemporalSeries } from "./types";
import { mineTextFootprint } from "./textFootprint";
import { analyzeShareBehavior, analyzeCommentVoice } from "./engagement";
import { calculateTransparencyGap } from "./transparencyGap";
import { countCreators, resolveVibeCluster, handleFromLink, echoChamberIndex, echoChamberSplit } from "./creators";
import { determinePrimaryArchetype } from "./archetypes";
import {
  algorithmDrift, inferSleepWindow, monthlyCreatorTrends,
  monthlyTopicTrends, sandboxRetests, skipAnomalies,
} from "./temporal";
import { pyRound } from "./numeric";
import { parseDate } from "./parseDate";

/** Mirror of _compute_peak_hour: first (lowest) hour with the max count, zero-padded. */
function computePeakHour(hourlyHeatmap: Record<string, number>): string {
  const vals = Object.values(hourlyHeatmap);
  if (!vals.length || vals.every((v) => v === 0)) return "Unknown";
  let peakKey = "";
  let best = -Infinity;
  for (const [k, v] of Object.entries(hourlyHeatmap)) {
    if (v > best) { // strict > → first (lowest) hour wins
      best = v;
      peakKey = k;
    }
  }
  const hour = parseInt(peakKey, 10);
  const pad = (h: number) => String(h).padStart(2, "0");
  if (hour === 0) return "12:00 AM";
  if (hour < 12) return `${pad(hour)}:00 AM`;
  if (hour === 12) return "12:00 PM";
  return `${pad(hour - 12)}:00 PM`;
}

const lstripAtLower = (h: string) => h.toLowerCase().replace(/^@+/, "");
const byDateDesc = (a: { date: string }, b: { date: string }) =>
  a.date < b.date ? 1 : a.date > b.date ? -1 : 0;

export function buildGhostProfile(
  parsed: any,
  excludeHours: number[] = [],
  linkHandleMap: Record<string, string> | null = null,
): Record<string, any> {
  const activeHistory: any[] = parsed.watch_history_active ?? [];
  // WP-1.3 corroboration: video ids the user engaged with (like/fav/share/comment).
  const engagedVideoIds = new Set<string>();
  for (const [coll, key] of [
    [parsed.likes ?? [], "link"], [parsed.favorites ?? [], "link"],
    [parsed.shares ?? [], "link"], [parsed.comments ?? [], "url"],
  ] as [any[], string][]) {
    for (const item of coll) {
      const evid = extractVideoId(item?.[key] || item?.link || "");
      if (evid) engagedVideoIds.add(evid);
    }
  }
  const sw = runStopwatch(activeHistory, excludeHours, engagedVideoIds) as any;

  const linkToTitle: Record<string, string> = {};
  for (const item of activeHistory) {
    const link = item?.link ?? "";
    if (link) linkToTitle[link] = item?.title ?? "";
  }

  const footprint = mineTextFootprint(parsed);
  const shareBehavior = analyzeShareBehavior(parsed.shares ?? []);
  const commentVoice = analyzeCommentVoice(
    parsed.comments ?? [], sw.total_conscious_videos, shareBehavior.dm_share_count,
  );
  const transparencyGap = calculateTransparencyGap(parsed, { interest_clusters: footprint.interest_clusters });

  const totalConscious = sw.total_conscious_videos;
  const sustainedAndDives = sw.deep_lingers + sw.deep_dives;
  const lingerRatePct = (sustainedAndDives / Math.max(totalConscious, 1)) * 100;
  const nightShiftPct = (sw.night_count / Math.max(totalConscious, 1)) * 100;
  const nightLingerPct = (sw.night_lingers / Math.max(sustainedAndDives, 1)) * 100;

  // WP-1.3: persona-dimension inputs exclude `abandoned` (autoplay-while-away).
  const personaConscious = totalConscious - sw.abandoned;
  const personaLingerRate = (sustainedAndDives / Math.max(personaConscious, 1)) * 100;
  const personaNightShift = ((sw.night_count - sw.abandoned_night) / Math.max(personaConscious, 1)) * 100;

  const vibeCluster = resolveVibeCluster(
    countCreators(sw._linger_links, 20, "linger_count", linkToTitle, linkHandleMap),
  );
  const graveyard = resolveVibeCluster(
    countCreators(sw._graveyard_links, 20, "skip_count", linkToTitle, linkHandleMap),
  );

  const followingUsernames = new Set<string>();
  for (const u of parsed.following ?? []) followingUsernames.add(lstripAtLower(u?.username ?? ""));
  for (const c of [...vibeCluster, ...graveyard]) {
    c.is_followed = followingUsernames.has(lstripAtLower((c.handle as string) ?? ""));
  }

  let followedVideos = 0;
  let algorithmicVideos = 0;
  const allLinks = new Set<string>([...sw._graveyard_links, ...sw._sandbox_links, ...sw._linger_links]);
  for (const link of allLinks) {
    const creator = handleFromLink(link, linkHandleMap);
    if (creator) {
      if (followingUsernames.has(lstripAtLower(creator))) followedVideos++;
      else algorithmicVideos++;
    }
  }
  const totalCreatorsFound = followedVideos + algorithmicVideos;
  const followedPct = totalCreatorsFound > 0 ? pyRound((followedVideos / totalCreatorsFound) * 100, 1) : 0.0;
  const algorithmicPct = totalCreatorsFound > 0 ? pyRound((algorithmicVideos / totalCreatorsFound) * 100, 1) : 0.0;

  const behavioralNodes = {
    peak_hour: computePeakHour(sw.hourly_heatmap),
    inferred_sleep_window: inferSleepWindow(sw.hourly_heatmap),
    skip_rate_percentage: pyRound((sw.graveyard_skips / Math.max(totalConscious, 1)) * 100, 1),
    linger_rate_percentage: pyRound(lingerRatePct, 1),
    night_shift_ratio: pyRound(nightShiftPct, 1),
    night_linger_pct: pyRound(nightLingerPct, 1),
    night_lingers_count: sw.night_lingers,
    social_graph_algorithmic_pct: algorithmicPct,
    social_graph_followed_pct: followedPct,
  };
  const drift = algorithmDrift(sw.monthly_skip_rates ?? {});
  const primaryArchetype = determinePrimaryArchetype(behavioralNodes, parsed, sw, vibeCluster,
    personaConscious, personaLingerRate, personaNightShift);

  const searchesRaw: any[] = parsed.searches ?? [];
  const searchHourHist: Record<number, number> = {};
  const searchTimeline: any[] = [];
  for (const s of searchesRaw) {
    const term = s?.term ?? "";
    const ds = s?.date ?? "";
    const dt = parseDate(ds);
    if (dt) {
      const h = dt.getUTCHours();
      searchHourHist[h] = (searchHourHist[h] ?? 0) + 1;
      searchTimeline.push({ term, date: ds, hour: h, dow: (dt.getUTCDay() + 6) % 7 });
    }
  }
  searchTimeline.sort(byDateDesc);

  const declaredSurface = new Set<string>();
  for (const s of searchesRaw.slice(0, 200)) declaredSurface.add(((s?.term || "") as string).toLowerCase().trim());
  for (const ad of parsed.ad_interests ?? []) declaredSurface.add(((ad || "") as string).toLowerCase().trim());
  for (const si of parsed.settings_interests ?? []) declaredSurface.add(((si || "") as string).toLowerCase().trim());

  const explicitTotal = (parsed.likes?.length ?? 0) + (parsed.comments?.length ?? 0);
  const implicitTotal = sustainedAndDives;
  const echo = echoChamberIndex(sw._linger_links, linkHandleMap);
  const echoSplit = echoChamberSplit(sw.linger_events as any, linkHandleMap);

  // ── WP-1.4: per-period temporal series (month, or week when coverage < 90d) ──
  const gran = sw.temporal_granularity;
  const pdata = sw.period_data as Record<string, PeriodCounts>;
  const mkSeries = <T,>(points: { period: string; value: T }[]): TemporalSeries<T> => ({
    granularity: gran,
    points: [...points].sort((a, b) => (a.period < b.period ? -1 : a.period > b.period ? 1 : 0)),
  });
  const bucketSeries = mkSeries(
    Object.entries(pdata).map(([period, d]) => ({
      period,
      value: { graveyard: d.graveyard, sandbox: d.sandbox, linger: d.linger, deep_dive: d.deep_dive, abandoned: d.abandoned, total: d.total },
    })),
  );
  const nightShiftSeries = mkSeries(
    Object.entries(pdata).map(([period, d]) => ({
      period,
      value: d.total > 0 ? pyRound((d.night / d.total) * 100, 1) : 0.0,
    })),
  );
  const explicitByPeriod: Record<string, number> = {};
  for (const item of [...(parsed.likes ?? []), ...(parsed.comments ?? [])]) {
    const edt = parseDate(item?.date ?? "");
    if (edt) {
      const pk = periodKey(edt, gran);
      explicitByPeriod[pk] = (explicitByPeriod[pk] ?? 0) + 1;
    }
  }
  const eiPeriods = [...new Set([...Object.keys(explicitByPeriod), ...Object.keys(pdata)])].sort();
  const explicitImplicitSeries = mkSeries(
    eiPeriods.map((period) => {
      const implicitP = (pdata[period]?.linger ?? 0) + (pdata[period]?.deep_dive ?? 0);
      const value = implicitP > 0 ? pyRound((explicitByPeriod[period] ?? 0) / implicitP, 3) : 0.0;
      return { period, value };
    }),
  );

  const monthlyCreatorTrends_ = monthlyCreatorTrends(sw.linger_events, linkHandleMap);
  const monthlyTopicTrends_ = monthlyTopicTrends(searchesRaw, parsed.comments ?? []);
  const sandboxRetests_ = sandboxRetests(sw.sandbox_events, linkHandleMap);
  const anomalies = skipAnomalies(sw.monthly_skip_rates ?? {});
  const dataStart = sw.data_start_month;

  const hourlySorted = Object.entries(sw.hourly_heatmap as Record<string, number>)
    .sort((a, b) => b[1] - a[1]);
  const topHours = hourlySorted.slice(0, 3).filter(([, v]) => v > 0).map(([h]) => parseInt(h, 10)).sort((a, b) => a - b);
  const fmtH = (h: number) =>
    h === 0 ? "12 AM" : h < 12 ? `${h} AM` : h === 12 ? "12 PM" : `${h - 12} PM`;

  const loginHistory: any[] = parsed.login_history ?? [];
  const loginStats = parsed.login_history_stats ?? {};

  return {
    status: "success",
    interest_clusters: footprint.interest_clusters,
    interest_phrases: footprint.top_phrases,
    stopwatch_metrics: sw,
    behavioral_nodes: behavioralNodes,
    primary_archetype: primaryArchetype,
    creator_entities: { vibe_cluster: vibeCluster, graveyard },
    academic_insights: {
      explicit_vs_implicit_ratio: implicitTotal > 0 ? pyRound(explicitTotal / implicitTotal, 3) : 0.0,
      explicit_actions_count: explicitTotal,
      implicit_linger_count: implicitTotal,
      echo_chamber_index_pct: echo.pct,
      echo_chamber_basis: echo.basis,
      echo_chamber_distinct_creators: echo.distinct_creators,
      echo_split: echoSplit,
      top_creator_handles: vibeCluster.slice(0, 5).map((c) => c.handle),
    },
    temporal_series: {
      granularity: gran,
      stopwatch_buckets: bucketSeries,
      night_shift_ratio: nightShiftSeries,
      explicit_vs_implicit_ratio: explicitImplicitSeries,
    },
    night_shift: { percentage: pyRound(nightShiftPct, 1), count: sw.night_count, window: "23:00 – 04:00" },
    digital_footprint: {
      login_count: loginHistory.length,
      unique_ips: loginStats.unique_ips ?? 0,
      unique_devices: loginStats.unique_devices ?? [],
      recent_logins: loginHistory
        .filter((l) => l?.date)
        .map((l) => ({
          date: l.date ?? "", ip: l.ip ?? "", device: l.device_model ?? "",
          system: l.device_system ?? "", network: l.network_type ?? "", carrier: l.carrier ?? "",
        }))
        .sort(byDateDesc)
        .slice(0, 25),
    },
    search_rhythm: {
      total_searches: searchTimeline.length,
      hourly_histogram: Object.fromEntries(Array.from({ length: 24 }, (_, h) => [String(h), searchHourHist[h] ?? 0])),
      recent_searches: searchTimeline.slice(0, 30),
    },
    discrepancy_gap: {
      declared_surface_sample: [...declaredSurface].sort().slice(0, 40),
      inferred_creator_handles: vibeCluster.slice(0, 10).map((c) => c.handle),
      declared_count: declaredSurface.size,
      inferred_count: new Set(vibeCluster.map((c) => c.handle ?? "")).size,
    },
    enrichment_targets: {
      lingered: [...sw.linger_events].sort((a: any, b: any) => b.time_spent - a.time_spent).slice(0, 40),
      graveyard: sw.graveyard_events.slice(0, 40),
      sandbox: sw.sandbox_events.slice(0, 40),
      night_lingered: [...sw.night_linger_events].sort((a: any, b: any) => b.time_spent - a.time_spent).slice(0, 30),
      deep_dives: [...sw.deep_dive_events].sort((a: any, b: any) => b.time_spent - a.time_spent).slice(0, 20),
      following_usernames: [...followingUsernames],
    },
    declared_signals: {
      settings_interests: parsed.settings_interests ?? [],
      ad_interests: parsed.ad_interests ?? [],
      recent_searches: searchesRaw.slice(0, 30).filter((s) => s?.term).map((s) => s.term ?? ""),
      following_count: (parsed.following ?? []).length,
      follower_count: (parsed.followers ?? []).length,
    },
    ad_profile: {
      advertiser_categories: parsed.ad_interests ?? [],
      vulnerability_window: topHours.length ? topHours.map(fmtH).join(" / ") : "Unknown",
      peak_ad_hour: behavioralNodes.peak_hour,
      night_targeting: pyRound(nightShiftPct, 1),
      off_platform_tracked: (parsed.off_tiktok_activity ?? []).length > 0,
      off_platform_events: (parsed.off_tiktok_activity ?? []).length,
      shop_order_count: (parsed.shop_orders ?? []).length,
      shop_products: (parsed.shop_orders ?? []).flatMap((o: any) => o.products ?? []).slice(0, 20),
      product_browsing_count: (parsed.product_browsing ?? []).length,
      browsed_products: (parsed.product_browsing ?? []).filter((b: any) => b?.product).map((b: any) => b.product).slice(0, 25),
    },
    comment_voice: commentVoice,
    share_behavior: shareBehavior,
    transparency_gap: transparencyGap,
    algorithm_drift: drift,
    monthly_creator_trends: monthlyCreatorTrends_,
    monthly_topic_trends: monthlyTopicTrends_,
    sandbox_retests: sandboxRetests_,
    skip_anomalies: anomalies,
    data_cliff: { start_month: dataStart, window_days: 180 },
  };
}
