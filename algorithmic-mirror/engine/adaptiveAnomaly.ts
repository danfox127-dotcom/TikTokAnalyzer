/**
 * WP-1.3 stage C — per-user adaptive long-gap anomaly flag.
 * Mirror of api.ghost_profile._adaptive_anomaly.
 *
 * Counts inter-video gaps strictly beyond the user's own p99 delta (integer
 * nearest-rank), floored at 20 min. Additive metadata — does NOT move the fixed
 * 1200s sleep-scrub cutoff. Sample = all non-negative deltas (incl. long gaps),
 * so a heavy-tail user gets a higher personal bar and a sparse-tail user falls
 * back to the 1200s floor.
 */

import { parseDate } from "./parseDate";

const ADAPTIVE_ANOMALY_FLOOR_S = 1200;

export interface AdaptiveAnomaly {
  p99_delta_s: number;
  adaptive_anomaly_threshold_s: number;
  adaptive_anomaly_count: number;
}

export function adaptiveAnomaly(browsingHistory: any[]): AdaptiveAnomaly {
  const dts: number[] = [];
  for (const item of browsingHistory) {
    const dt = parseDate(item?.date ?? "");
    if (dt) dts.push(dt.getTime());
  }
  dts.sort((a, b) => a - b);
  const deltas: number[] = [];
  for (let i = 0; i + 1 < dts.length; i++) {
    const d = (dts[i + 1] - dts[i]) / 1000;
    if (d >= 0) deltas.push(d); // drop clock anomalies (negative)
  }
  if (deltas.length === 0) {
    return { p99_delta_s: 0.0, adaptive_anomaly_threshold_s: ADAPTIVE_ANOMALY_FLOOR_S, adaptive_anomaly_count: 0 };
  }
  const ordered = [...deltas].sort((a, b) => a - b);
  const n = ordered.length;
  let idx = Math.floor((99 * n + 99) / 100) - 1; // ceil(0.99*n) - 1, integer nearest-rank
  idx = Math.max(0, Math.min(idx, n - 1));
  const p99 = ordered[idx];
  const threshold = Math.max(p99, ADAPTIVE_ANOMALY_FLOOR_S);
  const count = deltas.reduce((c, d) => c + (d > threshold ? 1 : 0), 0);
  return { p99_delta_s: p99, adaptive_anomaly_threshold_s: threshold, adaptive_anomaly_count: count };
}
