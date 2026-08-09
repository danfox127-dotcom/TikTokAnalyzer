/**
 * WP-2.5 — Niche-drift metric. Pure, browser-safe. Charts how a feed narrows over
 * time via per-month distinct creators + top-5 creator concentration, each with a
 * fitted least-squares trend. Redefines the un-obtainable like-count curve onto a
 * signal we own (creator resolution). See docs/superpowers/specs/2026-07-27-niche-drift-design.md.
 */
import { handleFromLink } from "./creators";
import { pyRound } from "./numeric";
import type { TemporalSeries } from "./types";

const MIN_COVERAGE_PCT = 40;
const SPARSE_MONTH_MIN = 10;
const MIN_TREND_BUCKETS = 3;
const EPS = 0.01;

export interface NicheDriftPoint {
  period: string;
  distinct_creators: number;
  top5_concentration_pct: number;
}
export interface DriftTrend {
  slope: number | null;
  direction: string; // "narrowing" | "widening" | "flat" | "insufficient_trend"
}
export interface NicheDriftResult {
  status: "ok" | "insufficient_evidence" | "error";
  series: TemporalSeries<NicheDriftPoint>;
  distinct_creators_trend: DriftTrend;
  top5_concentration_trend: DriftTrend;
  resolved_coverage_pct: number;
  requirements?: { needed: string; had: string };
  method: string;
}

const METHOD =
  "Per-period distinct creators + top-5 creator concentration from your watched-video " +
  "creators, with a least-squares trend. Excluded when <40% of watched videos resolve to " +
  "a creator; months with <10 resolved videos widen the whole series to quarters.";

function quarterOf(month: string): string {
  const [y, m] = month.split("-");
  const q = Math.floor((Number(m) - 1) / 3) + 1;
  return `${y}-Q${q}`;
}

function linearSlope(ys: number[]): number | null {
  const n = ys.length;
  if (n < MIN_TREND_BUCKETS) return null;
  const xbar = (n - 1) / 2;
  const ybar = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) { num += (i - xbar) * (ys[i] - ybar); den += (i - xbar) ** 2; }
  if (den === 0) return null;
  return pyRound(num / den, 3);
}

function driftDirection(slope: number | null, invert: boolean): string {
  if (slope === null) return "insufficient_trend";
  const s = invert ? -slope : slope; // concentration rising = narrowing → invert
  if (s < -EPS) return "narrowing";
  if (s > EPS) return "widening";
  return "flat";
}

// distinct creators + top-5 concentration for one bucket's resolved handles.
function bucketMetrics(handles: string[]): { distinct_creators: number; top5_concentration_pct: number } {
  const counts = new Map<string, number>();
  for (const h of handles) counts.set(h, (counts.get(h) ?? 0) + 1);
  const total = handles.length;
  const top5 = [...counts.values()].sort((a, b) => b - a).slice(0, 5).reduce((a, b) => a + b, 0);
  return {
    distinct_creators: counts.size,
    top5_concentration_pct: total > 0 ? pyRound((top5 / total) * 100, 1) : 0,
  };
}

const err = (): NicheDriftResult => ({
  status: "error",
  series: { granularity: "month", points: [] },
  distinct_creators_trend: { slope: null, direction: "insufficient_trend" },
  top5_concentration_trend: { slope: null, direction: "insufficient_trend" },
  resolved_coverage_pct: 0,
  method: METHOD,
});

export function buildNicheDrift(profile: any, linkHandleMap?: Record<string, string> | null): NicheDriftResult {
  const lingerEvents = profile?.stopwatch_metrics?.linger_events;
  if (!profile || typeof profile !== "object" || !Array.isArray(lingerEvents)) return err();

  // Resolve every event; keep {month, handle} for resolved ones.
  const resolved: { month: string; handle: string }[] = [];
  for (const e of lingerEvents) {
    const handle = handleFromLink(String(e?.link ?? ""), linkHandleMap);
    const month = String(e?._month ?? "");
    if (handle && month) resolved.push({ month, handle });
  }

  const coverage = lingerEvents.length > 0 ? (resolved.length / lingerEvents.length) * 100 : 0;
  const resolved_coverage_pct = pyRound(coverage, 1);
  const emptySeries: TemporalSeries<NicheDriftPoint> = { granularity: "month", points: [] };
  const noTrend = { slope: null, direction: "insufficient_trend" };
  if (coverage < MIN_COVERAGE_PCT) {
    return {
      status: "insufficient_evidence", series: emptySeries,
      distinct_creators_trend: { ...noTrend }, top5_concentration_trend: { ...noTrend },
      resolved_coverage_pct,
      requirements: { needed: "≥40% of watched videos resolved to a creator", had: `${resolved_coverage_pct}%` },
      method: METHOD,
    };
  }

  // Decide granularity: widen the whole series to quarters if any month is sparse.
  const perMonth = new Map<string, string[]>();
  for (const r of resolved) { if (!perMonth.has(r.month)) perMonth.set(r.month, []); perMonth.get(r.month)!.push(r.handle); }
  const sparse = [...perMonth.values()].some((hs) => hs.length < SPARSE_MONTH_MIN);
  const granularity: "month" | "quarter" = sparse ? "quarter" : "month";

  const perBucket = new Map<string, string[]>();
  for (const r of resolved) {
    const key = granularity === "quarter" ? quarterOf(r.month) : r.month;
    if (!perBucket.has(key)) perBucket.set(key, []);
    perBucket.get(key)!.push(r.handle);
  }

  const periods = [...perBucket.keys()].sort();
  const points = periods.map((period) => ({ period, value: { period, ...bucketMetrics(perBucket.get(period)!) } }));

  const distinctYs = points.map((p) => p.value.distinct_creators);
  const concYs = points.map((p) => p.value.top5_concentration_pct);
  const distinctSlope = linearSlope(distinctYs);
  const concSlope = linearSlope(concYs);

  return {
    status: "ok",
    series: { granularity, points },
    distinct_creators_trend: { slope: distinctSlope, direction: driftDirection(distinctSlope, false) },
    top5_concentration_trend: { slope: concSlope, direction: driftDirection(concSlope, true) },
    resolved_coverage_pct,
    method: METHOD,
  };
}
