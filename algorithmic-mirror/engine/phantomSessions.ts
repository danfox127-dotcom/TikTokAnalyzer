/**
 * WP-1.3 stage B — phantom-session (asleep-autoplay) detection.
 * Mirror of api.ghost_profile._detect_phantom_sessions.
 *
 * A run of ≥10 consecutive night-hour videos at a steady 30–180s autoplay
 * cadence with ZERO engagement in the window is almost certainly the app playing
 * to an empty room. Retained as an artifact; the videos stay in raw buckets but
 * are pulled from persona scoring. Every phantom video has a qualifying onward
 * delta (so it's a night linger) — this keeps the persona subtraction exact.
 */

import { parseDate } from "./parseDate";

const PHANTOM_MIN_RUN = 10;
const PHANTOM_DELTA_MIN = 30.0;
const PHANTOM_DELTA_MAX = 180.0;

function isNight(hour: number): boolean {
  return hour >= 23 || hour < 4;
}

export interface PhantomSession {
  start: string;
  end: string;
  night: string;
  video_count: number;
  hours: number;
}

export interface PhantomResult {
  phantom_sessions: PhantomSession[];
  phantom_video_count: number;
  phantom_nights: number;
  excluded_hours: number;
  _phantom_links: string[];
}

/** Mirror of Python's date.strftime("%Y-%m-%d %H:%M:%S") on a UTC-constructed Date. */
function fmtDateTime(dt: Date): string {
  const p = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${dt.getUTCFullYear()}-${p(dt.getUTCMonth() + 1)}-${p(dt.getUTCDate())} ` +
    `${p(dt.getUTCHours())}:${p(dt.getUTCMinutes())}:${p(dt.getUTCSeconds())}`;
}

function fmtDate(dt: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${dt.getUTCFullYear()}-${p(dt.getUTCMonth() + 1)}-${p(dt.getUTCDate())}`;
}

/** pyRound-free 2dp round matching Python round(x, 2) closely enough for hours;
 *  values here are exact multiples of small fractions so half-even isn't hit. */
function round2(x: number): number {
  return Math.round(x * 100) / 100;
}

export function detectPhantomSessions(
  browsingHistory: any[],
  engagementTimes: Date[],
): PhantomResult {
  const entries: { dt: Date; link: string }[] = [];
  for (const item of browsingHistory) {
    const dt = parseDate(item?.date ?? "");
    if (dt) entries.push({ dt, link: item?.link ?? "" });
  }
  entries.sort((a, b) => a.dt.getTime() - b.dt.getTime());
  const eng = [...engagementTimes].map((d) => d.getTime()).sort((a, b) => a - b);

  const sessions: PhantomSession[] = [];
  const phantomLinks = new Set<string>();
  const n = entries.length;
  let i = 0;
  while (i < n) {
    let j = i;
    while (
      j + 1 < n &&
      isNight(entries[j].dt.getUTCHours()) &&
      (() => {
        const d = (entries[j + 1].dt.getTime() - entries[j].dt.getTime()) / 1000;
        return d >= PHANTOM_DELTA_MIN && d <= PHANTOM_DELTA_MAX;
      })()
    ) {
      j += 1;
    }
    const runLen = j - i;
    if (runLen >= PHANTOM_MIN_RUN) {
      const start = entries[i].dt;
      const end = entries[j].dt;
      const startMs = start.getTime();
      const endMs = end.getTime();
      const hasEngagement = eng.some((t) => t >= startMs && t <= endMs);
      if (!hasEngagement) {
        const hours = (endMs - startMs) / 1000 / 3600.0;
        sessions.push({
          start: fmtDateTime(start),
          end: fmtDateTime(end),
          night: fmtDate(start),
          video_count: runLen,
          hours: round2(hours),
        });
        for (let k = i; k < j; k++) {
          if (entries[k].link) phantomLinks.add(entries[k].link);
        }
      }
    }
    i = Math.max(j, i + 1);
  }

  const phantomVideoCount = sessions.reduce((s, x) => s + x.video_count, 0);
  return {
    phantom_sessions: sessions,
    phantom_video_count: phantomVideoCount,
    phantom_nights: new Set(sessions.map((s) => s.night)).size,
    excluded_hours: round2(sessions.reduce((s, x) => s + x.hours, 0)),
    _phantom_links: Array.from(phantomLinks),
  };
}
