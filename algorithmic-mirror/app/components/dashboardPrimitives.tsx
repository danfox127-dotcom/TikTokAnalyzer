"use client";
/**
 * WP-3.1 — shared design tokens + presentational helpers used across every
 * Dossier tab. Moved verbatim out of the former monolithic ForensicDashboard.tsx.
 */
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import type { GhostProfile } from "./GhostProfileHUD";

// ---------------------------------------------------------------------------
// Design Tokens (Editorial / Warm-Paper Dossier — matches the landing page)
// ---------------------------------------------------------------------------

export const BG = "#f5efe4";          // warm cream (landing background)
export const SIDEBAR = "#efe7d8";     // slightly deeper paper
export const PANEL = "#efe8da";       // panel paper, subtly off the BG
export const BORDER = "rgba(26, 22, 16, 0.16)"; // ink hairline
export const ACCENT = "#8b2323";      // oxblood (landing accent)
export const INK = "#1a1610";         // near-black brown
export const INK_DIM = "rgba(26, 22, 16, 0.62)";
export const INK_GHOST = "rgba(26, 22, 16, 0.4)";

// Muted earth accents — readable on cream, no neon. (names kept for stable refs)
export const MODULE_A = "#5b4a8a"; // muted aubergine
export const MODULE_B = "#8b2323"; // oxblood (concentration / "danger")
export const MODULE_C = "#9c6b2e"; // ochre
export const MODULE_D = "#3d6b4f"; // forest
export const GRAVEYARD_ACCENT = "#a14a5a"; // dusty rose
export const VIBE_ACCENT = "#2f6b6e"; // deep teal

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

export function DashboardPanel({
  label,
  accent = ACCENT,
  children,
  className,
}: {
  label: string;
  accent?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={className}
      style={{
        position: "relative",
        background: PANEL,
        border: `1px solid ${BORDER}`,
        padding: "32px 28px 28px",
      }}
    >
      {/* corner ticks */}
      <span style={{ position: "absolute", top: -1, left: -1, width: 8, height: 8, borderTop: `2px solid ${accent}`, borderLeft: `2px solid ${accent}` }} />
      <span style={{ position: "absolute", top: -1, right: -1, width: 8, height: 8, borderTop: `2px solid ${accent}`, borderRight: `2px solid ${accent}` }} />
      <span style={{ position: "absolute", bottom: -1, left: -1, width: 8, height: 8, borderBottom: `2px solid ${accent}`, borderLeft: `2px solid ${accent}` }} />
      <span style={{ position: "absolute", bottom: -1, right: -1, width: 8, height: 8, borderBottom: `2px solid ${accent}`, borderRight: `2px solid ${accent}` }} />

      {/* label ribbon */}
      <div
        style={{
          position: "absolute",
          top: -10,
          left: 24,
          background: BG,
          padding: "0 10px",
          fontFamily: "var(--font-mono, monospace)",
          fontSize: 9,
          letterSpacing: "0.22em",
          color: accent,
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>

      {children}
    </section>
  );
}

export function SectionTitle({ accent = ACCENT, children }: { accent?: string; children: React.ReactNode }) {
  return (
    <h3
      style={{
        fontFamily: "var(--font-mono, monospace)",
        fontSize: 13,
        letterSpacing: "0.18em",
        color: accent,
        textTransform: "uppercase",
        margin: 0,
        marginBottom: 20,
      }}
    >
      <span style={{ color: INK_GHOST, marginRight: 8 }}>{"//"}</span>
      {children}
    </h3>
  );
}

export function SidebarItem({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        width: "100%",
        padding: "12px 24px",
        background: active ? "rgba(0, 229, 255, 0.08)" : "transparent",
        border: "none",
        borderLeft: `2px solid ${active ? ACCENT : "transparent"}`,
        color: active ? ACCENT : INK_DIM,
        fontFamily: "var(--font-mono, monospace)",
        fontSize: 12,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        textAlign: "left",
        cursor: "pointer",
        transition: "color 0.15s, background 0.15s",
      }}
    >
      <Icon size={16} color={active ? ACCENT : INK_GHOST} />
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Migrated Visualization Components
// ---------------------------------------------------------------------------

export function StopwatchFunnel({ profile }: { profile: GhostProfile }) {
  const sw = profile.stopwatch_metrics;
  const total = Math.max(sw.total_conscious_videos, 1);
  const buckets = [
    { key: "GRAVEYARD", sub: "<3s skips", value: sw.graveyard_skips, color: GRAVEYARD_ACCENT },
    { key: "SANDBOX", sub: "3–15s probes", value: sw.sandbox_views, color: "#facc15" },
    { key: "LINGER", sub: "15–180s watch", value: sw.deep_lingers, color: VIBE_ACCENT },
    { key: "DEEP DIVE", sub: "180s+ commit", value: sw.deep_dives, color: MODULE_D },
  ];

  return (
    <DashboardPanel label="01 · True Stopwatch Funnel" accent={INK_DIM} className="col-span-full">
      <div className="grid grid-cols-1 md:grid-cols-5 gap-0" style={{ border: `1px solid ${BORDER}` }}>
        <div style={{ padding: "24px 20px", borderRight: `1px solid ${BORDER}` }}>
          <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: INK_GHOST }}>
            CONSCIOUS VIDEOS
          </div>
          <div style={{ fontSize: 36, fontWeight: 700, color: INK, marginTop: 8, fontFamily: "var(--font-mono, monospace)" }}>
            {sw.total_conscious_videos.toLocaleString()}
          </div>
          <div style={{ fontSize: 10, color: INK_GHOST, marginTop: 6, fontFamily: "var(--font-mono, monospace)" }}>
            of {(sw.total_raw_videos ?? sw.total_videos ?? 0).toLocaleString()} raw
          </div>
        </div>
        {buckets.map(b => {
          const pct = (b.value / total) * 100;
          return (
            <div key={b.key} style={{ padding: "24px 20px", borderRight: `1px solid ${BORDER}`, position: "relative" }}>
              <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: b.color }}>
                {b.key}
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: INK, marginTop: 8, fontFamily: "var(--font-mono, monospace)" }}>
                {b.value.toLocaleString()}
              </div>
              <div style={{ fontSize: 10, color: INK_GHOST, marginTop: 6, fontFamily: "var(--font-mono, monospace)" }}>
                {b.sub} · {pct.toFixed(1)}%
              </div>
              <motion.div
                initial={{ scaleX: 0 }}
                animate={{ scaleX: pct / 100 }}
                transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
                style={{
                  position: "absolute",
                  left: 0, bottom: 0, height: 3, width: "100%",
                  background: b.color,
                  transformOrigin: "left",
                  boxShadow: `0 0 12px ${b.color}`,
                }}
              />
            </div>
          );
        })}
      </div>
    </DashboardPanel>
  );
}

export function CreatorLedger({
  label,
  num,
  accent,
  title,
  entries,
  countLabel,
}: {
  label: string;
  num: string;
  accent: string;
  title: string;
  entries: { handle: string; count: number; is_followed?: boolean }[];
  countLabel: string;
}) {
  const max = Math.max(...entries.map(e => e.count), 1);

  return (
    <DashboardPanel label={`${num} · ${label}`} accent={accent}>
      <SectionTitle accent={accent}>{title}</SectionTitle>

      {entries.length === 0 ? (
        <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: INK_GHOST }}>
          {"//"} NO SIGNAL
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {entries.slice(0, 10).map((e, i) => {
            const pct = (e.count / max) * 100;
            return (
              <div key={`${e.handle}-${i}`} style={{ display: "grid", gridTemplateColumns: "32px 1fr auto", alignItems: "center", gap: 12 }}>
                <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, color: INK_GHOST }}>
                  {String(i + 1).padStart(2, "0")}
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12, color: INK, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {e.handle}
                    </div>
                    {e.is_followed && (
                      <div style={{ fontSize: 7, background: accent, color: "black", padding: "0px 3px", fontWeight: 900 }}>FOLLOWED</div>
                    )}
                  </div>
                  <div style={{ width: "100%", height: 3, background: "rgba(255,255,255,0.05)" }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.6, delay: i * 0.04 }}
                      style={{ height: "100%", background: accent, boxShadow: `0 0 6px ${accent}` }}
                    />
                  </div>
                </div>
                <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: accent }}>
                  {e.count} <span style={{ color: INK_GHOST, fontSize: 9 }}>{countLabel}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </DashboardPanel>
  );
}
