// algorithmic-mirror/app/components/BlockCard.tsx
"use client";

import { useMemo, useState, useEffect } from "react";
import { motion } from "framer-motion";
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
import { CreatorGraph } from "./CreatorGraph";

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

function DecodingText({ text, delay = 0 }: { text: string; delay?: number }) {
  const [displayedText, setDisplayedText] = useState("");
  const chars = "!<>-_\\/[]{}—=+*^?#________";

  useEffect(() => {
    // Skip animation in tests
    if (process.env.NODE_ENV === "test") {
      setDisplayedText(text);
      return;
    }

    let iteration = 0;
    const timeout = setTimeout(() => {
      const interval = setInterval(() => {
        setDisplayedText(
          text
            .split("")
            .map((char, index) => {
              if (index < iteration) {
                return text[index];
              }
              return chars[Math.floor(Math.random() * chars.length)];
            })
            .join("")
        );

        if (iteration >= text.length) {
          clearInterval(interval);
        }

        iteration += 1 / 3;
      }, 30);
      return () => clearInterval(interval);
    }, delay * 1000);
    return () => clearTimeout(timeout);
  }, [text, delay]);

  return <>{displayedText}</>;
}

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
    if (block.chart.type === "creator_graph") return <CreatorGraph data={block.chart.data} />;
    return null;
  }, [block.chart]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-10% 0px" }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
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

      {/* Prose with subtle fade-in and decoding effect */}
      <motion.p
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.2 }}
        style={{
          fontSize: 13,
          lineHeight: 1.8,
          color: "#bbb",
          marginBottom: 16,
          maxWidth: 640,
          minHeight: "3.6em", // Prevent layout shift during decoding
        }}
      >
        <DecodingText text={block.prose} delay={0.4} />
      </motion.p>

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
    </motion.div>
  );
}
