"use client";
/**
 * WP-2.5 — minimal niche-drift chart. Two lines (distinct creators + top-5
 * concentration %) over the month/quarter x-axis, from payload alone (ok /
 * insufficient_evidence / error). The polished Timeline panel is WP-3.4.
 */
import { Lock, AlertTriangle } from "lucide-react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import type { NicheDriftResult } from "../../engine/nicheDrift";

const BORDER = "rgba(26, 22, 16, 0.16)";
const INK = "#1a1610";
const INK_DIM = "rgba(26, 22, 16, 0.62)";
const ACCENT = "#8b2323";
const ACCENT2 = "#2e5b7a";

function headline(result: NicheDriftResult): string {
  const pts = result.series.points;
  if (pts.length < 2) return "Not enough history yet to read a trend in your feed.";
  const first = pts[0].value.distinct_creators;
  const last = pts[pts.length - 1].value.distinct_creators;
  if (result.distinct_creators_trend.direction === "narrowing")
    return `Your feed narrowed from ${first} to ${last} creators.`;
  if (result.distinct_creators_trend.direction === "widening")
    return `Your feed widened from ${first} to ${last} creators.`;
  if (result.distinct_creators_trend.direction === "insufficient_trend")
    return `Too few periods yet to read a trend — ${last} creators most recently.`;
  return `Your feed held steady around ${last} creators.`;
}

export function NicheDriftChart({ result }: { result?: NicheDriftResult }) {
  if (!result) return null;

  if (result.status === "error") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: INK_DIM, fontSize: 12 }}>
        <AlertTriangle size={15} /> Niche-drift unavailable.
      </div>
    );
  }
  if (result.status === "insufficient_evidence") {
    return (
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start", color: INK_DIM, fontSize: 12 }}>
        <Lock size={15} style={{ marginTop: 1, flexShrink: 0 }} />
        <span>Not enough of your watched videos resolved to a creator to chart drift. Needs {result.requirements?.needed}; have {result.requirements?.had}.</span>
      </div>
    );
  }

  const data = result.series.points.map((p) => ({
    period: p.value.period,
    creators: p.value.distinct_creators,
    concentration: p.value.top5_concentration_pct,
  }));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontWeight: 600, color: INK, fontSize: 16 }}>{headline(result)}</div>
      <div style={{ width: "100%", height: 260, border: `1px solid ${BORDER}` }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid stroke={BORDER} />
            <XAxis dataKey="period" tick={{ fontSize: 10, fill: INK_DIM }} />
            <YAxis tick={{ fontSize: 10, fill: INK_DIM }} />
            <Tooltip />
            <Legend />
            <Line name="Distinct creators" dataKey="creators" stroke={ACCENT} dot={false} />
            <Line name="Top-5 concentration %" dataKey="concentration" stroke={ACCENT2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div style={{ fontSize: 10, color: INK_DIM }}>
        Creators: {result.distinct_creators_trend.direction} · Concentration: {result.top5_concentration_trend.direction} · {result.series.granularity} buckets
      </div>
    </div>
  );
}
