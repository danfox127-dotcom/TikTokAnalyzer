/**
 * WP-1.1 engine port — temporal / monthly features.
 * Mirrors the six functions extracted (behavior-preserving) from
 * api.ghost_profile: algorithm drift, sleep window, monthly creator trends,
 * monthly topic trends, sandbox re-tests, skip anomalies.
 *
 * NOTE: monthlyTopicTrends tokenizes comments with plain /[a-z]{3,}/ (NO word
 * boundary), unlike textFootprint's Unicode-\b emulation — so "café" -> "caf".
 */

import { parseDate } from "./parseDate";
import { handleFromLink } from "./creators";
import { FOOTPRINT_STOP } from "./constants";
import { pyRound } from "./numeric";

type SkipRates = Record<string, number>;

function monthKey(dt: Date): string {
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, "0")}`;
}

/** most_common(n): stable sort by count desc, ties by first-insertion order. */
function mostCommon(m: Map<string, number>, n: number): [string, number][] {
  return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, n);
}

// ── Algorithm drift ────────────────────────────────────────────────────────
export interface AlgorithmDrift {
  detectable: boolean;
  direction: string | null;
  delta_pct: number | null;
  early_avg?: number;
  recent_avg?: number;
}

export function algorithmDrift(monthlySkipRates: SkipRates): AlgorithmDrift {
  const months = Object.keys(monthlySkipRates).sort();
  if (months.length < 4) return { detectable: false, direction: null, delta_pct: null };
  const mid = Math.floor(months.length / 2);
  const early = months.slice(0, mid).map((m) => monthlySkipRates[m]);
  const recent = months.slice(mid).map((m) => monthlySkipRates[m]);
  const avgEarly = early.reduce((a, b) => a + b, 0) / early.length;
  const avgRecent = recent.reduce((a, b) => a + b, 0) / recent.length;
  const delta = pyRound(avgRecent - avgEarly, 1);
  const direction = delta < -4 ? "tightening" : delta > 4 ? "loosening" : "stable";
  return {
    detectable: true,
    direction,
    delta_pct: delta,
    early_avg: pyRound(avgEarly, 1),
    recent_avg: pyRound(avgRecent, 1),
  };
}

// ── Sleep window ───────────────────────────────────────────────────────────
function fmtHour(h: number): string {
  h = ((h % 24) + 24) % 24;
  if (h === 0) return "12 AM";
  if (h < 12) return `${h} AM`;
  if (h === 12) return "12 PM";
  return `${h - 12} PM`;
}

export function inferSleepWindow(hourlyHeatmap: Record<string, number>): string {
  const hours: number[] = [];
  for (let h = 0; h < 24; h++) hours.push(hourlyHeatmap[String(h)] ?? hourlyHeatmap[h as any] ?? 0);
  if (!hours.some((v) => v)) return "Unknown";
  const doubled = hours.concat(hours);
  const WINDOW = 4;
  let bestStart = 0;
  let bestSum = Infinity;
  for (let s = 0; s < 24; s++) {
    const w = doubled.slice(s, s + WINDOW).reduce((a, b) => a + b, 0);
    if (w < bestSum) { // strict < → first (lowest) start wins, matches Python
      bestSum = w;
      bestStart = s;
    }
  }
  return `${fmtHour(bestStart)} – ${fmtHour(bestStart + WINDOW)}`;
}

// ── Monthly creator trends ─────────────────────────────────────────────────
interface Event {
  link?: string;
  _month?: string;
  [k: string]: unknown;
}

export function monthlyCreatorTrends(
  lingerEvents: Event[],
  linkHandleMap?: Record<string, string> | null,
): Record<string, { handle: string; count: number }[]> {
  const monthly = new Map<string, Map<string, number>>();
  for (const ev of lingerEvents) {
    const handle = handleFromLink(ev.link ?? "", linkHandleMap);
    const mk = ev._month;
    if (handle && mk) {
      let inner = monthly.get(mk);
      if (!inner) { inner = new Map(); monthly.set(mk, inner); }
      inner.set(handle, (inner.get(handle) ?? 0) + 1);
    }
  }
  const out: Record<string, { handle: string; count: number }[]> = {};
  for (const mk of [...monthly.keys()].sort()) {
    out[mk] = [...monthly.get(mk)!.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([handle, count]) => ({ handle, count }));
  }
  return out;
}

// ── Monthly topic trends ───────────────────────────────────────────────────
export function monthlyTopicTrends(
  searches: { term?: string; date?: string }[],
  comments: { comment?: string; date?: string }[],
): Record<string, { term: string; count: number }[]> {
  const monthly = new Map<string, Map<string, number>>();
  const bump = (mk: string, term: string, by: number) => {
    let inner = monthly.get(mk);
    if (!inner) { inner = new Map(); monthly.set(mk, inner); }
    inner.set(term, (inner.get(term) ?? 0) + by);
  };

  for (const s of searches) {
    const term = (s?.term ?? "").toLowerCase().trim();
    const dt = parseDate(s?.date ?? "");
    if (term && dt && !FOOTPRINT_STOP.has(term) && term.length > 2) {
      bump(monthKey(dt), term, 3); // searches weighted higher
    }
  }
  for (const c of comments) {
    const text = (c?.comment ?? "").toLowerCase();
    const dt = parseDate(c?.date ?? "");
    if (text && dt) {
      const mk = monthKey(dt);
      for (const word of text.match(/[a-z]{3,}/g) ?? []) {
        if (!FOOTPRINT_STOP.has(word)) bump(mk, word, 1);
      }
    }
  }

  const out: Record<string, { term: string; count: number }[]> = {};
  for (const mk of [...monthly.keys()].sort()) {
    out[mk] = mostCommon(monthly.get(mk)!, 8).map(([term, count]) => ({ term, count }));
  }
  return out;
}

// ── Sandbox re-tests ───────────────────────────────────────────────────────
export function sandboxRetests(
  sandboxEvents: Event[],
  linkHandleMap?: Record<string, string> | null,
): { handle: string; times_served: number }[] {
  const counts = new Map<string, number>();
  for (const ev of sandboxEvents) {
    const h = handleFromLink(ev.link ?? "", linkHandleMap);
    if (h) counts.set(h, (counts.get(h) ?? 0) + 1);
  }
  return mostCommon(counts, 8)
    .filter(([, c]) => c >= 2)
    .map(([handle, c]) => ({ handle, times_served: c }));
}

// ── Skip anomalies ─────────────────────────────────────────────────────────
export interface SkipAnomaly {
  month: string;
  skip_rate: number;
  baseline_avg: number;
  delta: number;
  direction: string;
}

export function skipAnomalies(monthlySkipRates: SkipRates): SkipAnomaly[] {
  const months = Object.keys(monthlySkipRates).sort();
  const anomalies: SkipAnomaly[] = [];
  if (months.length >= 3) {
    const baselineMonths = months.slice(0, -1);
    const baselineAvg =
      baselineMonths.reduce((a, m) => a + monthlySkipRates[m], 0) / baselineMonths.length;
    for (const mk of months) {
      const delta = monthlySkipRates[mk] - baselineAvg;
      if (Math.abs(delta) >= 3.0) {
        anomalies.push({
          month: mk,
          skip_rate: monthlySkipRates[mk],
          baseline_avg: pyRound(baselineAvg, 1),
          delta: pyRound(delta, 1),
          direction: delta > 0 ? "spike" : "dip",
        });
      }
    }
  }
  return anomalies;
}
