"use client";
/**
 * WP-2.4 — minimal Persona radar. Renders the 6-dimension vector + composed archetype
 * from payload alone (ok / insufficient_evidence / error). The polished animated radar
 * is WP-3.4. recharts (already a dep) draws the axes; the text summary carries the label.
 */
import { Lock, AlertTriangle } from "lucide-react";
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from "recharts";
import type { PersonaResult } from "../../engine/persona";

const BORDER = "rgba(26, 22, 16, 0.16)";
const INK = "#1a1610";
const INK_DIM = "rgba(26, 22, 16, 0.62)";
const ACCENT = "#8b2323";

const AXES: { key: keyof PersonaResult["dimensions"]; label: string }[] = [
  { key: "intentionality", label: "Intentionality" },
  { key: "capture_susceptibility", label: "Capture" },
  { key: "nocturnality", label: "Nocturnality" },
  { key: "exploration", label: "Exploration" },
  { key: "expressiveness", label: "Expressiveness" },
  { key: "parasociality", label: "Parasociality" },
];

export function PersonaRadar({ result }: { result?: PersonaResult }) {
  if (!result) return null;

  if (result.status === "error") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: INK_DIM, fontSize: 12 }}>
        <AlertTriangle size={15} /> Persona unavailable.
      </div>
    );
  }
  if (result.status === "insufficient_evidence") {
    return (
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start", color: INK_DIM, fontSize: 12 }}>
        <Lock size={15} style={{ marginTop: 1, flexShrink: 0 }} />
        <span>Not enough watched history to read a persona yet. Needs {result.requirements?.needed}; have {result.requirements?.had}.</span>
      </div>
    );
  }

  const data = AXES.map((a) => ({ axis: a.label, value: result.dimensions[a.key] }));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div>
        <span style={{ fontWeight: 600, color: INK, fontSize: 18 }}>{result.display_name}</span>{" "}
        <span style={{ fontSize: 11, color: ACCENT }}>{Math.round(result.confidence * 100)}% confidence</span>
      </div>
      {result.secondary && (
        <div style={{ fontSize: 11, color: INK_DIM }}>Secondary reading: {result.secondary}</div>
      )}
      <div style={{ width: "100%", height: 280, border: `1px solid ${BORDER}` }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="70%">
            <PolarGrid />
            <PolarAngleAxis dataKey="axis" tick={{ fontSize: 10, fill: INK_DIM }} />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
            <Radar dataKey="value" stroke={ACCENT} fill={ACCENT} fillOpacity={0.35} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 10, color: INK_DIM }}>
        {AXES.map((a) => (
          <span key={a.key}>{a.label} <strong style={{ color: INK }}>{result.dimensions[a.key]}</strong></span>
        ))}
      </div>
    </div>
  );
}
