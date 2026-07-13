/**
 * WP-1.1 engine port — the Stopwatch.
 *
 * Faithful TypeScript mirror of `api.ghost_profile._run_stopwatch` (the frozen
 * Python oracle). Reconstructs per-video watch time from timestamp deltas and
 * buckets views into graveyard / sandbox / linger / deep-dive tiers.
 *
 * Parity is enforced by `__tests__/stopwatch.parity.test.ts` against a golden
 * fixture generated from the oracle. Deliberate parity choices, each of which
 * would silently diverge if "translated" naively:
 *  - field name `sleep_anomalies_scrubbed` is Python's name for the negative-
 *    delta (clock-anomaly) count — NOT `clock_anomalies`.
 *  - weekday is Python's `datetime.weekday()` (Monday=0). JS `getUTCDay()` is
 *    Sunday=0, so we remap `(getUTCDay() + 6) % 7`.
 *  - hour uses `getUTCHours()` to match `Date.UTC` construction in parseDate.
 *  - graveyard/sandbox events carry no `_month`; linger/deep-dive events do.
 *  - `monthly_skip_rates` uses Python's round-half-to-even.
 */

import { parseDate } from "./parseDate";
import { extractVideoId } from "./videoId";
import { pyRound } from "./numeric";

export interface HistoryEntry {
  date: string;
  link: string;
}

export interface StopwatchEvent {
  video_id: string;
  link: string;
  time_spent: number;
  hour: number;
  _month?: string;
}

export interface StopwatchResult {
  total_raw_videos: number;
  total_conscious_videos: number;
  sleep_anomalies_scrubbed: number;
  sleep_scrubbed: number;
  graveyard_skips: number;
  sandbox_views: number;
  deep_lingers: number;
  deep_dives: number;
  night_count: number;
  night_lingers: number;
  max_consecutive_skips: number;
  max_session_duration: number;
  _graveyard_links: string[];
  _sandbox_links: string[];
  _linger_links: string[];
  _deep_dive_links: string[];
  hourly_heatmap: Record<string, number>;
  weekly_heatmap: Record<string, Record<string, number>>;
  monthly_skip_rates: Record<string, number>;
  linger_events: StopwatchEvent[];
  graveyard_events: StopwatchEvent[];
  sandbox_events: StopwatchEvent[];
  night_linger_events: StopwatchEvent[];
  deep_dive_events: StopwatchEvent[];
  data_start_month: string | null;
}

const SLEEP_THRESHOLD_S = 1200;

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function ym(dt: Date): string {
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function runStopwatch(
  browsingHistory: HistoryEntry[],
  excludeHours: number[] = [],
): StopwatchResult {
  const exclude = new Set(excludeHours);

  const entries: { dt: Date; link: string }[] = [];
  for (const item of browsingHistory) {
    const dt = parseDate(item?.date ?? "");
    if (dt) entries.push({ dt, link: item?.link ?? "" });
  }
  entries.sort((a, b) => a.dt.getTime() - b.dt.getTime());

  let clockAnomalies = 0;
  let sleepScrubbed = 0;
  let graveyard = 0;
  let sandbox = 0;
  let linger = 0;
  let deepDive = 0;
  let nightCount = 0;
  let nightLingers = 0;
  let consecutiveSkips = 0;
  let maxConsecutiveSkips = 0;
  let currentSessionDuration = 0;
  let maxSessionDuration = 0;

  const hourly: Record<number, number> = {};
  const weekly: Record<number, Record<number, number>> = {};
  const monthly: Record<string, { skip: number; total: number }> = {};

  const graveyardLinks = new Set<string>();
  const sandboxLinks = new Set<string>();
  const lingerLinks = new Set<string>();
  const deepDiveLinks = new Set<string>();

  const lingerEvents: StopwatchEvent[] = [];
  const graveyardEvents: StopwatchEvent[] = [];
  const sandboxEvents: StopwatchEvent[] = [];
  const nightLingerEvents: StopwatchEvent[] = [];
  const deepDiveEvents: StopwatchEvent[] = [];

  for (let i = 0; i < entries.length - 1; i++) {
    const cur = entries[i];
    const nxt = entries[i + 1];
    const delta = (nxt.dt.getTime() - cur.dt.getTime()) / 1000;

    if (delta < 0) {
      clockAnomalies++;
      continue;
    }
    if (delta >= SLEEP_THRESHOLD_S) {
      sleepScrubbed++;
      currentSessionDuration = 0;
      continue;
    }
    if (delta > 300) {
      currentSessionDuration = 0;
    } else {
      currentSessionDuration += delta;
      maxSessionDuration = Math.max(maxSessionDuration, currentSessionDuration);
    }

    const hour = cur.dt.getUTCHours();
    if (exclude.has(hour)) continue;

    const dow = (cur.dt.getUTCDay() + 6) % 7; // JS Sun=0 → Python Mon=0
    hourly[hour] = (hourly[hour] ?? 0) + 1;
    (weekly[dow] ??= {})[hour] = (weekly[dow][hour] ?? 0) + 1;

    const monthKey = ym(cur.dt);
    (monthly[monthKey] ??= { skip: 0, total: 0 }).total += 1;

    const isNight = hour >= 23 || hour < 4;
    if (isNight) nightCount++;

    const link = cur.link;
    const vid = link ? extractVideoId(link) : null;
    const timeSpent = Math.min(delta, 270.0);

    if (delta < 3) {
      graveyard++;
      consecutiveSkips++;
      maxConsecutiveSkips = Math.max(maxConsecutiveSkips, consecutiveSkips);
      monthly[monthKey].skip += 1;
      if (link) graveyardLinks.add(link);
      if (vid) graveyardEvents.push({ video_id: vid, link, time_spent: timeSpent, hour });
    } else if (delta <= 15) {
      consecutiveSkips = 0;
      sandbox++;
      if (link) sandboxLinks.add(link);
      if (vid) sandboxEvents.push({ video_id: vid, link, time_spent: timeSpent, hour });
    } else if (delta <= 180) {
      consecutiveSkips = 0;
      linger++;
      if (isNight) nightLingers++;
      if (link) lingerLinks.add(link);
      if (vid) {
        const ev: StopwatchEvent = { video_id: vid, link, time_spent: timeSpent, hour, _month: monthKey };
        lingerEvents.push(ev);
        if (isNight) nightLingerEvents.push(ev);
      }
    } else {
      consecutiveSkips = 0;
      deepDive++;
      if (isNight) nightLingers++;
      if (link) {
        deepDiveLinks.add(link);
        lingerLinks.add(link);
      }
      if (vid) {
        const ev: StopwatchEvent = { video_id: vid, link, time_spent: timeSpent, hour, _month: monthKey };
        deepDiveEvents.push(ev);
        lingerEvents.push(ev);
        if (isNight) nightLingerEvents.push(ev);
      }
    }
  }

  const totalConscious = graveyard + sandbox + linger + deepDive;

  const hourlyHeatmap: Record<string, number> = {};
  for (let h = 0; h < 24; h++) hourlyHeatmap[String(h)] = hourly[h] ?? 0;

  const weeklyHeatmap: Record<string, Record<string, number>> = {};
  for (let d = 0; d < 7; d++) {
    const row: Record<string, number> = {};
    for (let h = 0; h < 24; h++) row[String(h)] = weekly[d]?.[h] ?? 0;
    weeklyHeatmap[String(d)] = row;
  }

  const monthlySkipRates: Record<string, number> = {};
  for (const mk of Object.keys(monthly).sort()) {
    const m = monthly[mk];
    monthlySkipRates[mk] = m.total > 0 ? pyRound((m.skip / m.total) * 100, 1) : 0.0;
  }

  const dataStartMonth = entries.length
    ? `${MONTH_NAMES[entries[0].dt.getUTCMonth()]} ${entries[0].dt.getUTCFullYear()}`
    : null;

  return {
    total_raw_videos: entries.length,
    total_conscious_videos: totalConscious,
    sleep_anomalies_scrubbed: clockAnomalies,
    sleep_scrubbed: sleepScrubbed,
    graveyard_skips: graveyard,
    sandbox_views: sandbox,
    deep_lingers: linger,
    deep_dives: deepDive,
    night_count: nightCount,
    night_lingers: nightLingers,
    max_consecutive_skips: maxConsecutiveSkips,
    max_session_duration: maxSessionDuration,
    _graveyard_links: Array.from(graveyardLinks),
    _sandbox_links: Array.from(sandboxLinks),
    _linger_links: Array.from(lingerLinks),
    _deep_dive_links: Array.from(deepDiveLinks),
    hourly_heatmap: hourlyHeatmap,
    weekly_heatmap: weeklyHeatmap,
    monthly_skip_rates: monthlySkipRates,
    linger_events: lingerEvents,
    graveyard_events: graveyardEvents,
    sandbox_events: sandboxEvents,
    night_linger_events: nightLingerEvents,
    deep_dive_events: deepDiveEvents,
    data_start_month: dataStartMonth,
  };
}
