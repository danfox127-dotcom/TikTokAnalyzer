/**
 * WP-1.2 — coverage detection & gating.
 *
 * NEW functionality (not a port): the export can span 30 days or 2 years, and
 * short windows produce confidently-wrong insights. computeCoverage measures the
 * date span per section; the gate registry declares each insight module's minimum
 * data requirements, so a thin export yields `insufficient_evidence` instead of a
 * bad guess. Layered in the pipeline on top of the parity-locked engine — NOT
 * inside buildGhostProfile (which must stay byte-identical to the Python oracle).
 */

import { parseDate } from "./parseDate";

const MS_PER_DAY = 86_400_000;

export interface Coverage {
  overall: { start: string; end: string; days: number };
  perSection: Record<string, { start: string; end: string; count: number }>;
}

// Coverage section id → the parsed key that holds its dated records.
const SECTION_KEYS: Record<string, string> = {
  watch_history: "browsing_history",
  searches: "searches",
  likes: "likes",
  shares: "shares",
  comments: "comments",
  logins: "login_history",
  follows: "following",
  orders: "shop_orders",
  off_platform: "off_tiktok_activity",
  favorites: "favorites",
};

function iso(ms: number): string {
  return new Date(ms).toISOString();
}

export function computeCoverage(parsed: any): Coverage {
  const perSection: Coverage["perSection"] = {};
  let overallMin = Infinity;
  let overallMax = -Infinity;

  for (const [section, key] of Object.entries(SECTION_KEYS)) {
    const items: any[] = parsed?.[key] ?? [];
    let minMs = Infinity;
    let maxMs = -Infinity;
    for (const item of items) {
      const dt = parseDate(item?.date ?? "");
      if (!dt) continue;
      const t = dt.getTime();
      if (t < minMs) minMs = t;
      if (t > maxMs) maxMs = t;
    }
    const hasDates = minMs !== Infinity;
    perSection[section] = {
      start: hasDates ? iso(minMs) : "",
      end: hasDates ? iso(maxMs) : "",
      count: items.length,
    };
    if (hasDates) {
      if (minMs < overallMin) overallMin = minMs;
      if (maxMs > overallMax) overallMax = maxMs;
    }
  }

  const overall = overallMin !== Infinity
    ? { start: iso(overallMin), end: iso(overallMax), days: Math.floor((overallMax - overallMin) / MS_PER_DAY) }
    : { start: "", end: "", days: 0 };

  return { overall, perSection };
}

// ── Gating ─────────────────────────────────────────────────────────────────
export interface GateRequirement {
  minDays?: number;
  minConsciousViews?: number;
  minLogins?: number;
}

// Per-module minimums (addendum §5). "stopwatch" has no requirement → always ok.
export const COVERAGE_REQUIREMENTS: Record<string, GateRequirement> = {
  stopwatch: {},
  persona: { minDays: 30, minConsciousViews: 500 },
  rabbit_hole: { minDays: 60 },
  movement: { minLogins: 5 },
  attribution: { minDays: 90 },
  forecast: { minDays: 90 },
};

export interface GateResult {
  moduleId: string;
  status: "ok" | "insufficient_evidence";
  requirements?: { needed: string; had: string };
}

export interface GateMetrics {
  consciousViews: number;
}

/** Guard a single module against the coverage + computed metrics. */
export function requireCoverage(
  moduleId: string,
  coverage: Coverage,
  metrics: GateMetrics,
): GateResult {
  const req = COVERAGE_REQUIREMENTS[moduleId];
  if (!req) return { moduleId, status: "ok" };

  const days = coverage.overall.days;
  const logins = coverage.perSection.logins?.count ?? 0;
  const views = metrics.consciousViews;

  const needed: string[] = [];
  const had: string[] = [];
  let ok = true;

  if (req.minDays != null) {
    needed.push(`≥${req.minDays} days`);
    had.push(`${days} days`);
    if (days < req.minDays) ok = false;
  }
  if (req.minConsciousViews != null) {
    needed.push(`≥${req.minConsciousViews} conscious views`);
    had.push(`${views} conscious views`);
    if (views < req.minConsciousViews) ok = false;
  }
  if (req.minLogins != null) {
    needed.push(`≥${req.minLogins} logins`);
    had.push(`${logins} logins`);
    if (logins < req.minLogins) ok = false;
  }

  if (ok) return { moduleId, status: "ok" };
  return { moduleId, status: "insufficient_evidence", requirements: { needed: needed.join(" and "), had: had.join(", ") } };
}

/** Evaluate every registered module's gate. */
export function evaluateGates(coverage: Coverage, metrics: GateMetrics): Record<string, GateResult> {
  const out: Record<string, GateResult> = {};
  for (const moduleId of Object.keys(COVERAGE_REQUIREMENTS)) {
    out[moduleId] = requireCoverage(moduleId, coverage, metrics);
  }
  return out;
}
