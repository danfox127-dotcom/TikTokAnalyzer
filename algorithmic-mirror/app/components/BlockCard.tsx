// algorithmic-mirror/app/components/BlockCard.tsx
"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import type { NarrativeBlock } from "../types/narrative";

const CHART_PALETTE = [
  "#4db8ff",
  "#ff8c42",
  "#a8ff78",
  "#ff4db8",
  "#ffd700",
  "#c8a2c8",
  "#ff4466",
  "#00e5ff",
];

function BlockBarChart({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return null;
  const keys = Object.keys(data[0]);
  const xKey = keys[0] ?? "name";
  const yKey = keys[1] ?? "value";
  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
        <XAxis
          dataKey={xKey}
          tick={{ fill: "#888", fontSize: 10, fontFamily: "ui-monospace, monospace" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis hide />
        <Tooltip
          contentStyle={{
            background: "#111",
            border: "1px solid #333",
            color: "#eee",
            fontSize: 11,
            fontFamily: "ui-monospace, monospace",
          }}
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
        />
        <Bar dataKey={yKey} fill="#4db8ff" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function BlockDonutChart({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return null;
  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={45}
          outerRadius={75}
          paddingAngle={2}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={CHART_PALETTE[i % CHART_PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "#111",
            border: "1px solid #333",
            color: "#eee",
            fontSize: 11,
            fontFamily: "ui-monospace, monospace",
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

interface BlockCardProps {
  block: NarrativeBlock;
}

export function BlockCard({ block }: BlockCardProps) {
  const chart = useMemo(() => {
    if (!block.chart || !block.chart.data.length) return null;
    if (block.chart.type === "bar") return <BlockBarChart data={block.chart.data} />;
    if (block.chart.type === "donut") return <BlockDonutChart data={block.chart.data} />;
    return null;
  }, [block.chart]);

  return (
    <div
      style={{
        background: "#111",
        border: "1px solid #1e1e1e",
        borderLeft: `4px solid ${block.accent}`,
        padding: "20px 24px",
        fontFamily: "ui-monospace, Menlo, Monaco, 'Cascadia Mono', monospace",
      }}
    >
      {/* Icon + Title */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 14,
        }}
      >
        <span style={{ fontSize: 18, lineHeight: 1 }}>{block.icon}</span>
        <span
          style={{
            fontSize: 10,
            letterSpacing: "0.25em",
            color: block.accent,
            fontWeight: 700,
            textTransform: "uppercase",
          }}
        >
          {block.title}
        </span>
      </div>

      {/* Prose */}
      <p
        style={{
          fontSize: 13,
          lineHeight: 1.8,
          color: "#bbb",
          marginBottom: 16,
          maxWidth: 640,
        }}
      >
        {block.prose}
      </p>

      {/* Stats */}
      {block.stats.length > 0 && (
        <dl
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
            gap: "8px 12px",
            marginBottom: chart ? 20 : 0,
          }}
        >
          {block.stats.map((stat) => (
            <div
              key={stat.label}
              style={{ background: "#1a1a1a", padding: "8px 12px" }}
            >
              <dt
                style={{
                  fontSize: 9,
                  letterSpacing: "0.15em",
                  color: "#555",
                  textTransform: "uppercase",
                }}
              >
                {stat.label}
              </dt>
              <dd
                style={{
                  fontSize: 14,
                  color: "#eee",
                  marginTop: 3,
                  fontWeight: 600,
                }}
              >
                {stat.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {/* Chart */}
      {chart}

      {/* Provenance */}
      <footer
        style={{
          marginTop: 20,
          paddingTop: 12,
          borderTop: "1px solid rgba(255,255,255,0.05)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span
          style={{
            fontSize: 9,
            color: "#444",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}
        >
          // PROVENANCE
        </span>
        <span
          style={{
            fontSize: 9,
            color: "#666",
            fontStyle: "italic",
            maxWidth: "80%",
            textAlign: "right",
          }}
        >
          {block.provenance}
        </span>
      </footer>
    </div>
  );
}
