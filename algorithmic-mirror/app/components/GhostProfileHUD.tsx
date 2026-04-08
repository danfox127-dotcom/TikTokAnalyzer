"use client";

import { motion } from "framer-motion";
import { ShieldOff, RotateCcw } from "lucide-react";
import { useDuality } from "../context/DualityContext";

export interface GhostProfile {
  status: "success";
  vibe_vectors: {
    doomscrolling: number;
    escapism: number;
    aspirational: number;
    nostalgic: number;
    outrage_mechanics: number;
  };
  target_lock_inferences: {
    estimated_age: string;
    inferred_income: string;
    vulnerability_state: string;
    political_lean: string;
  };
  raw_metrics: {
    total_videos: number;
    total_watch_time_minutes: number;
  };
  behavioral_nodes?: {
    peak_activity_hour: string;
    skip_rate_percentage: number;
    linger_rate_percentage: number;
    night_shift_ratio: number;
  };
  interest_clusters?: string[];
}

interface Props {
  profile: GhostProfile;
  onReset: () => void;
}

const VIBE_LABELS: Record<keyof GhostProfile["vibe_vectors"], string> = {
  doomscrolling: "DOOMSCROLLING",
  escapism: "ESCAPISM",
  aspirational: "ASPIRATIONAL",
  nostalgic: "NOSTALGIC",
  outrage_mechanics: "OUTRAGE MECHANICS",
};

function getVibeColor(score: number): string {
  if (score >= 70) return "#ff4444";
  if (score >= 40) return "#ffb300";
  return "#39ff14";
}

// Color-code cluster tags by rough category
function getClusterColor(cluster: string): string {
  const c = cluster.toLowerCase();
  if (c.includes("adhd") || c.includes("anxiety") || c.includes("depression") || c.includes("trauma") || c.includes("burnout") || c.includes("sleep"))
    return "#ff4444";
  if (c.includes("debt") || c.includes("budget") || c.includes("hustle") || c.includes("crypto"))
    return "#ffb300";
  if (c.includes("politic") || c.includes("conspir"))
    return "#ff4444";
  if (c.includes("nostalgia") || c.includes("retro"))
    return "#a78bfa";
  if (c.includes("spirituality") || c.includes("manifestation"))
    return "#a78bfa";
  return "#39ff14";
}

export function GhostProfileHUD({ profile, onReset }: Props) {
  const { setMachineView } = useDuality();

  const handleReset = () => {
    setMachineView(false);
    onReset();
  };

  const inferences = profile.target_lock_inferences;
  const metrics = profile.raw_metrics;
  const nodes = profile.behavioral_nodes;
  const clusters = profile.interest_clusters ?? [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full max-w-lg mx-auto font-mono space-y-6"
    >
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs tracking-widest uppercase" style={{ color: "var(--text-secondary)" }}>
            // GHOST PROFILE COMPILED
          </p>
          <h2
            className="text-lg font-bold tracking-tight"
            style={{ color: "var(--accent)", textShadow: "0 0 8px var(--accent-glow)" }}
          >
            ALGORITHMIC DOSSIER
          </h2>
        </div>
        <motion.button
          onClick={handleReset}
          whileTap={{ scale: 0.94 }}
          whileHover={{ scale: 1.04 }}
          className="flex items-center gap-2 px-4 py-2 text-xs uppercase tracking-widest font-bold"
          style={{
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            color: "var(--text-secondary)",
            background: "transparent",
          }}
        >
          <RotateCcw size={12} />
          RESET
        </motion.button>
      </div>

      {/* ── Interest Clusters ── */}
      {clusters.length > 0 && (
        <div
          className="p-4"
          style={{
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            background: "var(--surface)",
          }}
        >
          <p className="text-xs uppercase tracking-widest mb-3" style={{ color: "var(--text-secondary)" }}>
            NICHE_FINGERPRINT //{" "}
            <span style={{ color: "var(--accent)" }}>DETECTED INTEREST CLUSTERS</span>
          </p>
          <div className="flex flex-wrap gap-2">
            {clusters.map((cluster, i) => {
              const color = getClusterColor(cluster);
              return (
                <motion.span
                  key={cluster}
                  initial={{ opacity: 0, scale: 0.85 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.05 }}
                  className="text-xs px-2 py-1 font-bold uppercase tracking-wide"
                  style={{
                    border: `1px solid ${color}`,
                    borderRadius: "2px",
                    color,
                    background: `${color}18`,
                    boxShadow: `0 0 4px ${color}44`,
                  }}
                >
                  {cluster}
                </motion.span>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Vibe Vectors ── */}
      <div
        className="p-4 space-y-4"
        style={{
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          background: "var(--surface)",
        }}
      >
        <p className="text-xs uppercase tracking-widest" style={{ color: "var(--text-secondary)" }}>
          VIBE_VECTORS //{" "}
          <span style={{ color: "var(--accent)" }}>PSYCHOGRAPHIC SCORING</span>
        </p>

        {(Object.keys(VIBE_LABELS) as Array<keyof GhostProfile["vibe_vectors"]>).map(
          (key, i) => {
            const score = profile.vibe_vectors[key];
            const color = getVibeColor(score);
            return (
              <div key={key} className="space-y-1">
                <div className="flex justify-between text-xs" style={{ color: "var(--text-secondary)" }}>
                  <span>{VIBE_LABELS[key]}</span>
                  <span style={{ color }}>{score}/100</span>
                </div>
                <div
                  className="w-full h-1.5 overflow-hidden"
                  style={{ background: "var(--border)", borderRadius: "2px" }}
                >
                  <motion.div
                    className="h-full"
                    style={{ background: color, boxShadow: `0 0 6px ${color}` }}
                    initial={{ width: "0%" }}
                    animate={{ width: `${score}%` }}
                    transition={{ duration: 0.8, delay: i * 0.1, ease: "easeOut" }}
                  />
                </div>
              </div>
            );
          }
        )}
      </div>

      {/* ── Target Lock Inferences ── */}
      <div
        className="p-4 space-y-3"
        style={{
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          background: "var(--surface)",
        }}
      >
        <p className="text-xs uppercase tracking-widest" style={{ color: "var(--text-secondary)" }}>
          TARGET_LOCK //{" "}
          <span style={{ color: "var(--accent)" }}>INFERRED DEMOGRAPHICS</span>
        </p>

        {[
          { label: "AGE_BRACKET", value: inferences.estimated_age },
          { label: "INCOME_TIER", value: inferences.inferred_income },
          { label: "VULNERABILITY", value: inferences.vulnerability_state },
          { label: "POLITICAL_LEAN", value: inferences.political_lean },
        ].map(({ label, value }, i) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4 + i * 0.08 }}
            className="flex items-start justify-between gap-4 text-xs"
          >
            <span style={{ color: "var(--text-secondary)", flexShrink: 0 }}>{label}</span>
            <span
              className="text-right"
              style={{
                color: "var(--accent)",
                textShadow: "0 0 6px var(--accent-glow)",
              }}
            >
              {value}
            </span>
          </motion.div>
        ))}
      </div>

      {/* ── Behavioral Nodes ── */}
      {nodes && (
        <div
          className="p-4 space-y-3"
          style={{
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            background: "var(--surface)",
          }}
        >
          <p className="text-xs uppercase tracking-widest" style={{ color: "var(--text-secondary)" }}>
            BEHAVIORAL_NODES //{" "}
            <span style={{ color: "var(--accent)" }}>ATTENTION PATTERN ANALYSIS</span>
          </p>
          {[
            { label: "PEAK_HOUR", value: nodes.peak_activity_hour },
            { label: "SKIP_RATE", value: `${nodes.skip_rate_percentage}%` },
            { label: "LINGER_RATE", value: `${nodes.linger_rate_percentage}%` },
            { label: "NIGHT_SHIFT", value: `${nodes.night_shift_ratio}%` },
          ].map(({ label, value }, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.6 + i * 0.08 }}
              className="flex items-start justify-between gap-4 text-xs"
            >
              <span style={{ color: "var(--text-secondary)", flexShrink: 0 }}>{label}</span>
              <span style={{ color: "var(--accent)", textShadow: "0 0 6px var(--accent-glow)" }}>
                {value}
              </span>
            </motion.div>
          ))}
        </div>
      )}

      {/* ── Raw Metrics ── */}
      <div
        className="p-4 grid grid-cols-2 gap-4"
        style={{
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          background: "var(--surface)",
        }}
      >
        <div>
          <p className="text-xs uppercase tracking-widest mb-1" style={{ color: "var(--text-secondary)" }}>
            VIDEOS_PROCESSED
          </p>
          <motion.p
            className="text-2xl font-bold"
            style={{ color: "var(--accent)", textShadow: "0 0 8px var(--accent-glow)" }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.7 }}
          >
            {metrics.total_videos.toLocaleString()}
          </motion.p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-widest mb-1" style={{ color: "var(--text-secondary)" }}>
            WATCH_TIME_EST
          </p>
          <motion.p
            className="text-2xl font-bold"
            style={{ color: "var(--accent)", textShadow: "0 0 8px var(--accent-glow)" }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
          >
            {metrics.total_watch_time_minutes.toLocaleString()}
            <span className="text-sm font-normal ml-1" style={{ color: "var(--text-secondary)" }}>
              min
            </span>
          </motion.p>
        </div>
      </div>

      {/* ── Disengage ── */}
      <div className="text-center pb-4">
        <motion.button
          onClick={handleReset}
          whileTap={{ scale: 0.96 }}
          whileHover={{ scale: 1.02 }}
          className="flex items-center gap-2 mx-auto px-6 py-3 text-xs uppercase tracking-widest font-bold"
          style={{
            background: "transparent",
            border: "1px solid rgba(255,68,68,0.4)",
            borderRadius: "var(--radius)",
            color: "#ff4444",
          }}
        >
          <ShieldOff size={13} />
          DISENGAGE — RETURN TO SHELL
        </motion.button>
      </div>
    </motion.div>
  );
}
