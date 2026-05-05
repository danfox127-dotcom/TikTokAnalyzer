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

// ── Design tokens — warm editorial register ────────────────────────────────
const PAPER       = "#f5efe4";
const PAPER_LIGHT = "#fdfbf6";
const PAPER_DEEP  = "#ede5d4";
const INK         = "#1a1610";
const INK_SOFT    = "#3a3024";
const INK_DIM     = "#6a5e4a";
const INK_GHOST   = "#a89a80";
const RULE        = "rgba(26, 22, 16, 0.12)";

// Warm editorial chart palette — no neon
const CHART_PALETTE = [
  "#8b2323", // oxblood
  "#c87941", // amber
  "#5a7a5a", // sage
  "#8b6b3a", // warm brown
  "#3a5a7a", // muted slate
  "#7a3a5a", // dusty rose
  "#2a5a4a", // muted teal
  "#6a7a3a", // ochre-green
];

// ── Decoding text animation ────────────────────────────────────────────────
// Keeps the "data resolving" feel but in the editorial register.
const GLITCH_CHARS = "!<>-_\\/[]{}—=+*^?#________";

function DecodingText({ text, delay = 0 }: { text: string; delay?: number }) {
  const [displayedText, setDisplayedText] = useState("");

  useEffect(() => {
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
              if (index < iteration) return text[index];
              return GLITCH_CHARS[Math.floor(Math.random() * GLITCH_CHARS.length)];
            })
            .join("")
        );
        if (iteration >= text.length) clearInterval(interval);
        iteration += 1 / 3;
      }, 30);
      return () => clearInterval(interval);
    }, delay * 1000);
    return () => clearTimeout(timeout);
  }, [text, delay]);

  return <>{displayedText}</>;
}

// ── Chart components ───────────────────────────────────────────────────────

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
          tick={{ fill: INK_DIM, fontSize: 10, fontFamily: "var(--font-mono, ui-monospace, monospace)" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis hide />
        <Tooltip
          contentStyle={{
            background: PAPER_LIGHT,
            border: `1px solid ${RULE}`,
            color: INK,
            fontSize: 11,
            fontFamily: "var(--font-mono, ui-monospace, monospace)",
            boxShadow: "2px 2px 0 rgba(26,22,16,0.08)",
          }}
          cursor={{ fill: "rgba(26,22,16,0.04)" }}
        />
        <Bar dataKey={yKey} fill="#8b2323" radius={[1, 1, 0, 0]} />
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
            background: PAPER_LIGHT,
            border: `1px solid ${RULE}`,
            color: INK,
            fontSize: 11,
            fontFamily: "var(--font-mono, ui-monospace, monospace)",
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

// ── BlockCard ──────────────────────────────────────────────────────────────

interface BlockCardProps {
  block: NarrativeBlock;
  index?: number;
}

export function BlockCard({ block, index = 0 }: BlockCardProps) {
  const chart = useMemo(() => {
    if (!block.chart || !block.chart.data.length) return null;
    if (block.chart.type === "bar")          return <BlockBarChart data={block.chart.data} />;
    if (block.chart.type === "donut")        return <BlockDonutChart data={block.chart.data} />;
    if (block.chart.type === "creator_graph") return <CreatorGraph data={block.chart.data} />;
    return null;
  }, [block.chart]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-8% 0px" }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1], delay: 0.05 }}
      style={{
        background: PAPER,
        borderTop: `1px solid ${RULE}`,
        borderLeft: `3px solid ${block.accent ?? "#8b2323"}`,
        padding: "32px 28px 28px",
        fontFamily: "var(--font-body, Georgia, serif)",
        marginBottom: 0,
      }}
    >
      {/* Finding number + title */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 14,
          marginBottom: 16,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
            fontSize: 9,
            letterSpacing: "0.2em",
            color: INK_GHOST,
            textTransform: "uppercase",
            flexShrink: 0,
          }}
        >
          {String(index + 1).padStart(2, "0")}
        </span>
        <span style={{ fontSize: 16, lineHeight: 1, flexShrink: 0 }}>{block.icon}</span>
        <span
          style={{
            fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
            fontSize: 10,
            letterSpacing: "0.22em",
            color: block.accent ?? "#8b2323",
            fontWeight: 700,
            textTransform: "uppercase",
          }}
        >
          {block.title}
        </span>
      </div>

      {/* Prose — decoding animation gives a data-reveal feel */}
      <motion.p
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        transition={{ duration: 0.7, delay: 0.15 }}
        style={{
          fontSize: 16,
          lineHeight: 1.75,
          color: INK_SOFT,
          marginBottom: 20,
          maxWidth: "64ch",
          minHeight: "3.6em",
          fontFamily: "var(--font-body, 'Source Serif 4', Georgia, serif)",
        }}
      >
        <DecodingText text={block.prose} delay={0.3} />
      </motion.p>

      {/* Stats */}
      {block.stats.length > 0 && (
        <dl
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
            gap: "8px 12px",
            marginBottom: chart ? 24 : 0,
          }}
        >
          {block.stats.map((stat) => (
            <div
              key={stat.label}
              style={{
                background: PAPER_DEEP,
                padding: "10px 14px",
                borderTop: `1px solid ${RULE}`,
              }}
            >
              <dt
                style={{
                  fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                  fontSize: 9,
                  letterSpacing: "0.18em",
                  color: INK_DIM,
                  textTransform: "uppercase",
                }}
              >
                {stat.label}
              </dt>
              <dd
                style={{
                  fontFamily: "var(--font-display, 'Fraunces', Georgia, serif)",
                  fontSize: 22,
                  fontWeight: 700,
                  color: INK,
                  marginTop: 4,
                  lineHeight: 1.1,
                }}
              >
                {stat.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {/* Chart */}
      {chart && (
        <div style={{ marginTop: 4 }}>
          {chart}
        </div>
      )}

      {/* Provenance footer */}
      <footer
        style={{
          marginTop: 20,
          paddingTop: 12,
          borderTop: `1px solid ${RULE}`,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
            fontSize: 9,
            color: INK_GHOST,
            textTransform: "uppercase",
            letterSpacing: "0.15em",
          }}
        >
          Source
        </span>
        <span
          style={{
            fontFamily: "var(--font-body, Georgia, serif)",
            fontSize: 11,
            color: INK_DIM,
            fontStyle: "italic",
            maxWidth: "80%",
            textAlign: "right",
            lineHeight: 1.5,
          }}
        >
          {block.provenance}
        </span>
      </footer>
    </motion.div>
  );
}
