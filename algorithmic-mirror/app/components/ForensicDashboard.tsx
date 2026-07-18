"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Network,
  Search,
  LayoutDashboard,
  ArrowLeft,
  Lock,
  Zap,
  TrendingUp
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { GhostProfile } from "./GhostProfileHUD";
import { DownloadExportButton } from "./DownloadExportButton";
import { CreatorGraph } from "./CreatorGraph";
import { LLMAnalysisView } from "./LLMAnalysisView";
import { FourPillarsPanel } from "./FourPillarsPanel";
import { LocalModeBanner } from "./LocalModeBanner";

// We'll import existing visualizations or build new ones inside these tabs.
// For now, let's define the tab types.
type Tab = "overview" | "behavior" | "timeline" | "network" | "interests" | "privacy" | "ai";

interface Props {
  profile: GhostProfile;
  onReset: () => void;
  sourceFile?: File;
}

// ---------------------------------------------------------------------------
// Design Tokens (Editorial / Warm-Paper Dossier — matches the landing page)
// ---------------------------------------------------------------------------

const BG = "#f5efe4";          // warm cream (landing background)
const SIDEBAR = "#efe7d8";     // slightly deeper paper
const PANEL = "#efe8da";       // panel paper, subtly off the BG
const BORDER = "rgba(26, 22, 16, 0.16)"; // ink hairline
const ACCENT = "#8b2323";      // oxblood (landing accent)
const INK = "#1a1610";         // near-black brown
const INK_DIM = "rgba(26, 22, 16, 0.62)";
const INK_GHOST = "rgba(26, 22, 16, 0.4)";

// Muted earth accents — readable on cream, no neon. (names kept for stable refs)
const MODULE_A = "#5b4a8a"; // muted aubergine
const MODULE_B = "#8b2323"; // oxblood (concentration / "danger")
const MODULE_C = "#9c6b2e"; // ochre
const MODULE_D = "#3d6b4f"; // forest
const GRAVEYARD_ACCENT = "#a14a5a"; // dusty rose
const VIBE_ACCENT = "#2f6b6e"; // deep teal

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

function DashboardPanel({
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

function SectionTitle({ accent = ACCENT, children }: { accent?: string; children: React.ReactNode }) {
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

function SidebarItem({
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

function StopwatchFunnel({ profile }: { profile: GhostProfile }) {
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

function CreatorLedger({
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

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

export function ForensicDashboard({ profile, onReset, sourceFile }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  const graveyard = (profile.creator_entities?.graveyard ?? []).map(g => ({ 
    handle: g.handle, 
    count: g.skip_count,
    is_followed: g.is_followed 
  }));
  const vibe = (profile.creator_entities?.vibe_cluster ?? []).map(v => ({ 
    handle: v.handle, 
    count: v.linger_count,
    is_followed: v.is_followed
  }));

  return (
    <div style={{
      background: BG,
      minHeight: "100vh",
      display: "flex",
      color: INK,
      fontFamily: "var(--font-body, 'Iowan Old Style', Georgia, serif)"
    }}>
      {/* Sidebar */}
      <aside style={{
        width: 260,
        background: SIDEBAR,
        borderRight: `1px solid ${BORDER}`,
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
        height: "100vh",
        position: "sticky",
        top: 0
      }}>
        <div style={{ padding: "32px 24px", borderBottom: `1px solid ${BORDER}` }}>
          <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 9, letterSpacing: "0.32em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 10 }}>
            The Glass House · Dossier
          </div>
          <h1 style={{ fontFamily: "var(--font-display, 'Fraunces', Georgia, serif)", fontSize: 26, fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1.0, margin: 0, color: INK }}>
            The <span style={{ fontStyle: "italic", color: ACCENT }}>Findings</span>
          </h1>
        </div>

        <nav style={{ flex: 1, padding: "24px 0" }}>
          <SidebarItem 
            icon={LayoutDashboard} 
            label="Overview" 
            active={activeTab === "overview"} 
            onClick={() => setActiveTab("overview")} 
          />
          <SidebarItem
            icon={Activity}
            label="Behavioral Signature"
            active={activeTab === "behavior"}
            onClick={() => setActiveTab("behavior")}
          />
          <SidebarItem
            icon={TrendingUp}
            label="Timeline"
            active={activeTab === "timeline"}
            onClick={() => setActiveTab("timeline")}
          />
          <SidebarItem
            icon={Network}
            label="Network & Influence" 
            active={activeTab === "network"} 
            onClick={() => setActiveTab("network")} 
          />
          <SidebarItem 
            icon={Search} 
            label="Interests & Keywords" 
            active={activeTab === "interests"} 
            onClick={() => setActiveTab("interests")} 
          />
          <SidebarItem 
            icon={Lock} 
            label="Privacy & Footprint" 
            active={activeTab === "privacy"} 
            onClick={() => setActiveTab("privacy")} 
          />
          <SidebarItem 
            icon={Zap} 
            label="AI Forensic Analyst" 
            active={activeTab === "ai"} 
            onClick={() => setActiveTab("ai")} 
          />
        </nav>

        <div style={{ padding: "24px", borderTop: `1px solid ${BORDER}`, display: "flex", flexDirection: "column", gap: 12 }}>
          <button
            onClick={onReset}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px",
              background: "transparent",
              border: `1px solid ${BORDER}`,
              color: INK_DIM,
              fontSize: 11,
              textTransform: "uppercase",
              cursor: "pointer",
              justifyContent: "center"
            }}
          >
            <ArrowLeft size={14} /> New Analysis
          </button>
          {sourceFile && (
            <DownloadExportButton 
              file={sourceFile} 
              apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"} 
            />
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main style={{ flex: 1, overflowY: "auto", padding: "48px" }}>
        <LocalModeBanner profile={profile} />
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === "overview" && (
              <div>
                {profile.data_cliff?.start_month && (
                  <div style={{ marginBottom: 32, padding: "12px 16px", border: `1px solid ${BORDER}`, background: `${MODULE_B}0a`, display: "flex", gap: 12, alignItems: "flex-start" }}>
                    <span style={{ color: MODULE_B, fontFamily: "var(--font-mono, monospace)", fontSize: 11, flexShrink: 0 }}>!</span>
                    <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6 }}>
                      <span style={{ color: INK }}>Your watch history starts in {profile.data_cliff.start_month}.</span>{" "}
                      TikTok automatically deletes your viewing history every 6 months. What you're reading is all that survived — everything before that is gone.
                    </div>
                  </div>
                )}
                <header style={{ marginBottom: 48, borderBottom: `2px solid ${INK}`, paddingBottom: 28 }}>
                  <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.32em", color: ACCENT, textTransform: "uppercase", marginBottom: 16 }}>
                    The Verdict · Who TikTok Thinks You Are
                  </div>
                  <h2 style={{ fontFamily: "var(--font-display, 'Fraunces', Georgia, serif)", fontSize: "clamp(40px, 6vw, 72px)", fontWeight: 800, letterSpacing: "-0.03em", lineHeight: 0.96, margin: 0, color: INK }}>
                    {profile.primary_archetype?.name ?? "The Balanced Viewer"}
                  </h2>
                  <div style={{ marginTop: 18, fontSize: 17, color: INK_DIM, maxWidth: "58ch", lineHeight: 1.6 }}>
                    {profile.primary_archetype?.name === "The Algorithmic Captured" && (
                      "Your attention signature indicates high immersion. The recommendation engine has identified a loop that keeps you engaged for extended periods, suggesting your feed is highly optimized for your current psychological state."
                    )}
                    {profile.primary_archetype?.name === "The Ruthless Curator" && (
                      "You exhibit highly intentional consumption. By skipping rapidly, you are effectively 'training' the algorithm to only surface high-value content, maintaining a high degree of agency over your attention."
                    )}
                    {profile.primary_archetype?.name === "The Nocturnal Seeker" && (
                      "A significant portion of your engagement occurs during late-night windows. The algorithm treats this as 'vulnerability time' and likely surfaces more experimental or emotionally resonant content during these hours."
                    )}
                    {profile.primary_archetype?.name === "The Balanced Viewer" && (
                      "Your behavior suggests a healthy, varied engagement pattern. You neither get trapped in long loops nor skip with aggression, resulting in a diversified algorithmic model."
                    )}
                  </div>
                </header>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                  {/* High level Summary Cards would go here */}
                  <div style={{ background: PANEL, border: `1px solid ${BORDER}`, padding: 24 }}>
                    <div style={{ fontSize: 10, color: INK_DIM, textTransform: "uppercase", marginBottom: 8 }}>Total Conscious Videos</div>
                    <div style={{ fontSize: 32, fontWeight: 700 }}>{profile.stopwatch_metrics.total_conscious_videos.toLocaleString()}</div>
                  </div>
                  <div style={{ background: PANEL, border: `1px solid ${BORDER}`, padding: 24 }}>
                    <div style={{ fontSize: 10, color: INK_DIM, textTransform: "uppercase", marginBottom: 8 }}>Linger Rate</div>
                    <div style={{ fontSize: 32, fontWeight: 700 }}>{profile.behavioral_nodes.linger_rate_percentage}%</div>
                  </div>
                  <div style={{ background: PANEL, border: `1px solid ${BORDER}`, padding: 24 }}>
                    <div style={{ fontSize: 10, color: INK_DIM, textTransform: "uppercase", marginBottom: 8 }}>Night Shift</div>
                    <div style={{ fontSize: 32, fontWeight: 700 }}>{profile.behavioral_nodes.night_shift_ratio}%</div>
                  </div>
                </div>
                
                <div style={{ marginTop: 48 }}>
                  <FourPillarsPanel
                    profile={profile}
                    apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
                  />
                </div>

                <div style={{ marginTop: 32, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 16 }}>
                  {profile.behavioral_nodes.inferred_sleep_window && profile.behavioral_nodes.inferred_sleep_window !== "Unknown" && (
                    <div style={{ background: PANEL, border: `1px solid ${BORDER}`, padding: "20px 24px" }}>
                      <div style={{ fontSize: 10, color: INK_DIM, textTransform: "uppercase", marginBottom: 8 }}>Inferred Sleep Window</div>
                      <div style={{ fontSize: 22, fontWeight: 700, color: MODULE_A }}>{profile.behavioral_nodes.inferred_sleep_window}</div>
                      <div style={{ fontSize: 10, color: INK_GHOST, marginTop: 6, lineHeight: 1.5 }}>Lowest-activity 4h window in your history</div>
                    </div>
                  )}
                  {(() => {
                    const sw = profile.stopwatch_metrics;
                    const est = Math.round((sw.graveyard_skips * 1.5 + sw.sandbox_views * 9 + sw.deep_lingers * 90 + sw.deep_dives * 240) / 3600);
                    if (est < 1) return null;
                    return (
                      <div style={{ background: PANEL, border: `1px solid ${BORDER}`, padding: "20px 24px" }}>
                        <div style={{ fontSize: 10, color: INK_DIM, textTransform: "uppercase", marginBottom: 8 }}>Est. Watch Time</div>
                        <div style={{ fontSize: 22, fontWeight: 700, color: MODULE_B }}>{est.toLocaleString()} hrs</div>
                        <div style={{ fontSize: 10, color: INK_GHOST, marginTop: 6, lineHeight: 1.5 }}>Across your full export history</div>
                      </div>
                    );
                  })()}
                  {profile.algorithm_drift?.detectable && (
                    <div style={{ background: PANEL, border: `1px solid ${BORDER}`, padding: "20px 24px" }}>
                      <div style={{ fontSize: 10, color: INK_DIM, textTransform: "uppercase", marginBottom: 8 }}>Algorithm Capture</div>
                      <div style={{ fontSize: 22, fontWeight: 700, color: profile.algorithm_drift.direction === "tightening" ? MODULE_B : MODULE_D }}>
                        {profile.algorithm_drift.direction === "tightening" ? "Tightening" : profile.algorithm_drift.direction === "loosening" ? "Loosening" : "Stable"}
                      </div>
                      <div style={{ fontSize: 10, color: INK_GHOST, marginTop: 6, lineHeight: 1.5 }}>
                        Skip rate {profile.algorithm_drift.direction === "tightening" ? "↓" : profile.algorithm_drift.direction === "loosening" ? "↑" : "→"} {Math.abs(profile.algorithm_drift.delta_pct ?? 0)}pp early→recent
                      </div>
                    </div>
                  )}
                  <div style={{ background: PANEL, border: `1px solid ${BORDER}`, padding: "20px 24px" }}>
                    <div style={{ fontSize: 10, color: INK_DIM, textTransform: "uppercase", marginBottom: 8 }}>Peak Hour</div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: MODULE_C }}>{profile.behavioral_nodes.peak_hour}</div>
                    <div style={{ fontSize: 10, color: INK_GHOST, marginTop: 6, lineHeight: 1.5 }}>Highest-volume viewing hour</div>
                  </div>
                </div>

                <div style={{ marginTop: 32 }}>
                  <h3 style={{ fontSize: 12, textTransform: "uppercase", color: INK_DIM, marginBottom: 16, fontFamily: "var(--font-mono, monospace)", letterSpacing: "0.1em" }}>// Behavioral Atomic Traits</h3>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                    {profile.primary_archetype?.atomic_traits && Object.entries(profile.primary_archetype.atomic_traits).map(([trait, active]) => (
                      <div key={trait} style={{
                        padding: "7px 14px",
                        background: active ? `${ACCENT}18` : "transparent",
                        border: `1px solid ${active ? ACCENT : BORDER}`,
                        color: active ? ACCENT : INK_GHOST,
                        fontSize: 10,
                        fontFamily: "var(--font-mono, monospace)",
                        letterSpacing: "0.12em",
                        textTransform: "uppercase"
                      }}>
                        {active ? "✓ " : ""}{trait}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === "behavior" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <StopwatchFunnel profile={profile} />
                
                <DashboardPanel label="02 · Engagement Authenticity" accent={MODULE_A}>
                  <SectionTitle accent={MODULE_A}>Explicit vs Implicit Engagement</SectionTitle>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 24 }}>
                    <div style={{ fontSize: 56, fontWeight: 700, color: MODULE_A }}>
                      {(profile.academic_insights?.explicit_vs_implicit_ratio ?? 0).toFixed(2)}
                    </div>
                    <div style={{ fontSize: 11, color: INK_DIM, textTransform: "uppercase" }}>Ratio</div>
                  </div>
                  <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
                    A measure of your active participation (likes/comments) against your passive consumption (lingers).
                    High ratios suggest intentionality; low ratios suggest algorithmic capture.
                  </div>
                </DashboardPanel>

                <DashboardPanel label="03 · Temporal personalizaton" accent={MODULE_C}>
                  <SectionTitle accent={MODULE_C}>Night Shift Ratio</SectionTitle>
                  <div style={{ fontSize: 48, fontWeight: 700, color: MODULE_C, marginBottom: 12 }}>
                    {profile.behavioral_nodes.night_shift_ratio}%
                  </div>
                  <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
                    Percentage of activity occurring in the 'Vulnerability Window' (23:00 - 04:00).
                    Late-night engagement is treated as a high-intent signal for ad targeting.
                  </div>
                </DashboardPanel>

                <DashboardPanel label="04 · Immersion Depth" accent={VIBE_ACCENT}>
                  <SectionTitle accent={VIBE_ACCENT}>Deep Commitments</SectionTitle>
                  <div style={{ fontSize: 42, fontWeight: 700, color: VIBE_ACCENT, marginBottom: 12 }}>
                    {profile.stopwatch_metrics.deep_dives.toLocaleString()} <span style={{ fontSize: 20 }}>videos</span>
                  </div>
                  {(profile.stopwatch_metrics.max_session_duration ?? 0) > 0 && (
                    <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${BORDER}` }}>
                      <div style={{ fontSize: 10, color: INK_GHOST, textTransform: "uppercase", marginBottom: 4 }}>Longest single binge</div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: VIBE_ACCENT }}>
                        {Math.floor(profile.stopwatch_metrics.max_session_duration! / 60)}m{" "}
                        <span style={{ fontSize: 14, color: INK_DIM }}>{profile.stopwatch_metrics.max_session_duration! % 60}s</span>
                      </div>
                    </div>
                  )}
                  <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6, marginTop: 12 }}>
                    Videos you watched for 3 minutes or more. These are the strongest positive
                    signals the recommendation loop receives from you.
                  </div>
                </DashboardPanel>

                <DashboardPanel label="05 · Daily Rhythm" accent={MODULE_C} className="col-span-full">
                  <SectionTitle accent={MODULE_C}>When You Watch · Hour of Day</SectionTitle>
                  <div style={{ display: "flex", height: 72, gap: 3, alignItems: "flex-end", marginBottom: 8 }}>
                    {Array.from({ length: 24 }, (_, h) => {
                      const v = profile.stopwatch_metrics.hourly_heatmap[String(h)] ?? 0;
                      const peak = Math.max(...Object.values(profile.stopwatch_metrics.hourly_heatmap).map(Number), 1);
                      const pct = (v / peak) * 100;
                      const isNight = h >= 23 || h < 4;
                      const isMorning = h >= 6 && h < 12;
                      const color = isNight ? MODULE_B : isMorning ? MODULE_C : VIBE_ACCENT;
                      return (
                        <div key={h} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
                          <div style={{ width: "100%", height: `${Math.max(pct, 2)}%`, background: color, opacity: 0.75 }} title={`${h}:00 — ${v} videos`} />
                        </div>
                      );
                    })}
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: INK_GHOST, fontFamily: "var(--font-mono, monospace)" }}>
                    {["12A","","","","","","6A","","","","","","12P","","","","","","6P","","","","","11P"].map((l, i) => (
                      <span key={i}>{l}</span>
                    ))}
                  </div>
                  <div style={{ marginTop: 10, display: "flex", gap: 16, fontSize: 10, color: INK_GHOST, fontFamily: "var(--font-mono, monospace)" }}>
                    <span style={{ color: MODULE_B }}>■</span> Night (11P–4A)
                    <span style={{ color: MODULE_C }}>■</span> Morning (6A–12P)
                    <span style={{ color: VIBE_ACCENT }}>■</span> Day/Evening
                  </div>
                </DashboardPanel>

                {(profile.algorithm_drift?.detectable && (profile.stopwatch_metrics.monthly_skip_rates != null)) && (() => {
                  const months = Object.entries(profile.stopwatch_metrics.monthly_skip_rates!).sort(([a], [b]) => a.localeCompare(b));
                  const maxRate = Math.max(...months.map(([,v]) => v), 1);
                  const drift = profile.algorithm_drift!;
                  const driftColor = drift.direction === "tightening" ? MODULE_D : drift.direction === "loosening" ? GRAVEYARD_ACCENT : INK_DIM;
                  return (
                    <DashboardPanel label="06 · Algorithm Capture Trajectory" accent={driftColor} className="col-span-full">
                      <SectionTitle accent={driftColor}>Skip Rate Over Time · Filter Bubble Direction</SectionTitle>
                      <div style={{ display: "flex", height: 64, gap: 2, alignItems: "flex-end", marginBottom: 8 }}>
                        {months.map(([month, rate]) => (
                          <div key={month} style={{ flex: 1, height: `${Math.max((rate / maxRate) * 100, 2)}%`, background: driftColor, opacity: 0.65 }} title={`${month}: ${rate}% skip rate`} />
                        ))}
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: INK_GHOST, fontFamily: "var(--font-mono, monospace)", marginBottom: 12 }}>
                        <span>{months[0]?.[0]}</span>
                        <span>{months[months.length - 1]?.[0]}</span>
                      </div>
                      <div style={{ display: "flex", gap: 32, fontSize: 11, color: INK_DIM }}>
                        <div>
                          <div style={{ fontSize: 9, textTransform: "uppercase", color: INK_GHOST, marginBottom: 2 }}>Early avg skip rate</div>
                          <div style={{ fontSize: 20, fontWeight: 700, color: INK }}>{drift.early_avg}%</div>
                        </div>
                        <div style={{ fontSize: 20, color: INK_GHOST, alignSelf: "flex-end", paddingBottom: 2 }}>→</div>
                        <div>
                          <div style={{ fontSize: 9, textTransform: "uppercase", color: INK_GHOST, marginBottom: 2 }}>Recent avg skip rate</div>
                          <div style={{ fontSize: 20, fontWeight: 700, color: driftColor }}>{drift.recent_avg}%</div>
                        </div>
                        <div style={{ marginLeft: "auto", textAlign: "right" }}>
                          <div style={{ fontSize: 9, textTransform: "uppercase", color: INK_GHOST, marginBottom: 2 }}>Verdict</div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: driftColor, textTransform: "uppercase" }}>
                            {drift.direction === "tightening"
                              ? "Filter bubble tightening — you reject less, the algorithm has learned you"
                              : drift.direction === "loosening"
                              ? "You're rejecting more over time — algorithm losing its grip"
                              : "Skip rate stable — no meaningful drift detected"}
                          </div>
                        </div>
                      </div>
                    </DashboardPanel>
                  );
                })()}
              </div>
            )}

            {activeTab === "network" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="md:col-span-2">
                  <DashboardPanel label="04 · Social Connectivity Graph" accent={ACCENT}>
                    <SectionTitle>The Village vs. The Machine</SectionTitle>
                    <div style={{ marginTop: 16 }}>
                      <CreatorGraph data={profile.creator_entities?.vibe_cluster ?? []} />
                    </div>
                    <div style={{ marginTop: 24, fontSize: 13, color: INK_DIM, lineHeight: 1.7 }}>
                      {(() => {
                        const followed = profile.declared_signals?.following_count ?? 0;
                        const followedPct = profile.behavioral_nodes.social_graph_followed_pct;
                        const algoPct = profile.behavioral_nodes.social_graph_algorithmic_pct;
                        if (followed > 0 && algoPct > 0) {
                          return <>You follow <strong style={{ color: INK }}>{followed} accounts</strong>. TikTok chose to show you their content <strong style={{ color: INK }}>{followedPct}%</strong> of the time. The other <strong style={{ color: MODULE_B }}>{algoPct}%</strong> was chosen entirely by the algorithm — creators you never asked to see.</>;
                        }
                        return "Mapping your creator network. Highlighted nodes are accounts you follow; the rest are algorithmic discoveries.";
                      })()}
                    </div>
                    {profile.creator_resolution && profile.creator_resolution.total > 0 && (
                      <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${BORDER}` }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", fontSize: 10, color: INK_GHOST, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 6 }}>
                          <span>Creator Resolution</span>
                          <span style={{ color: ACCENT }}>
                            {profile.creator_resolution.resolved.toLocaleString()} / {profile.creator_resolution.total.toLocaleString()} ({profile.creator_resolution.pct}%)
                          </span>
                        </div>
                        <div style={{ width: "100%", height: 3, background: "rgba(255,255,255,0.06)" }}>
                          <div style={{ height: "100%", width: `${Math.min(profile.creator_resolution.pct, 100)}%`, background: ACCENT }} />
                        </div>
                        <div style={{ marginTop: 8, fontSize: 10, color: INK_GHOST, lineHeight: 1.5 }}>
                          TikTok strips creator handles from your export, so each video must be resolved one
                          by one against a rate-limited endpoint.
                          {profile.creator_resolution.persistent
                            ? ` Results are cached permanently — re-run to resolve more (${profile.creator_resolution.newly_resolved} added this run).`
                            : " Caching is in-memory only (set REDIS_URL to persist coverage across runs)."}
                        </div>
                      </div>
                    )}
                  </DashboardPanel>
                </div>

                <DashboardPanel label="05 · Echo Chamber Index" accent={MODULE_B}>
                  <SectionTitle accent={MODULE_B}>Creator Concentration</SectionTitle>
                  {(profile.academic_insights?.echo_chamber_basis ?? 0) > 0 ? (
                    <>
                      <div style={{ fontSize: 56, fontWeight: 700, color: MODULE_B, marginBottom: 8 }}>
                        {(profile.academic_insights?.echo_chamber_index_pct ?? 0).toFixed(0)}%
                      </div>
                      <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
                        Share of your <em>resolved</em> lingered videos that went to your top 5 creators.
                        High percentages indicate a narrow informational feedback loop.
                      </div>
                      <div style={{ marginTop: 10, fontSize: 10, color: INK_GHOST }}>
                        Based on {profile.academic_insights?.echo_chamber_basis?.toLocaleString()} resolved videos
                        across {profile.academic_insights?.echo_chamber_distinct_creators?.toLocaleString()} creators.
                        Resolve more creators (Network coverage) to sharpen this figure.
                      </div>
                    </>
                  ) : (
                    <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
                      Not measurable yet — no creators have been resolved from your lingered videos.
                      TikTok strips creator handles from the export; once enough are resolved (see the
                      Network coverage bar), this measures how concentrated your attention is.
                    </div>
                  )}
                </DashboardPanel>

                <CreatorLedger
                  label="Vibe Cluster"
                  num="06"
                  accent={VIBE_ACCENT}
                  title="Sustained Attention"
                  entries={vibe}
                  countLabel="lingers"
                />

                <CreatorLedger
                  label="Graveyard"
                  num="06"
                  accent={GRAVEYARD_ACCENT}
                  title="Instant Rejection"
                  entries={graveyard}
                  countLabel="skips"
                />

                {(profile.sandbox_retests ?? []).length > 0 && (
                  <DashboardPanel label="· Hypothesis Re-Tests" accent={MODULE_C}>
                    <SectionTitle accent={MODULE_C}>Creators TikTok Kept Trying On You</SectionTitle>
                    <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 16 }}>
                      These creators were served to you in the 3–15 second window multiple times. You didn't bite — but the algorithm kept re-queuing them, testing whether you'd eventually engage.
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      {(profile.sandbox_retests ?? []).slice(0, 6).map((r, i) => (
                        <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 8, borderBottom: `1px solid ${BORDER}` }}>
                          <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12, color: INK }}>{r.handle}</span>
                          <span style={{ fontSize: 11, color: MODULE_C, fontFamily: "var(--font-mono, monospace)" }}>served {r.times_served}×</span>
                        </div>
                      ))}
                    </div>
                  </DashboardPanel>
                )}

                {(() => {
                  const bridged = (profile.creator_entities?.vibe_cluster ?? []).filter(c => c.youtube);
                  if (bridged.length === 0) return null;
                  return (
                    <div className="md:col-span-2">
                      <DashboardPanel label="07 · Cross-Platform Resolution · YouTube" accent={MODULE_A}>
                        <SectionTitle accent={MODULE_A}>The Same Creators, Tagged By Google</SectionTitle>
                        <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
                          A data broker doesn&rsquo;t re-analyze your videos. They match each TikTok
                          <span style={{ color: INK }}> @handle</span> to the same handle on YouTube and read
                          Google&rsquo;s pre-computed channel tags. Below: creators resolved off your watch
                          history, cross-referenced to YouTube. <span style={{ color: INK_GHOST }}>Prototype — handle match, not identity proof.</span>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                          {bridged.slice(0, 8).map((c, i) => (
                            <div key={i} style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 16, paddingBottom: 12, borderBottom: `1px solid ${BORDER}` }}>
                              <div>
                                <div style={{ fontSize: 12, color: INK }}>{c.handle}</div>
                                <div style={{ fontSize: 10, color: INK_GHOST, marginTop: 2 }}>
                                  → {c.youtube!.channel_title}
                                  {c.youtube!.subscriber_text && ` · ${c.youtube!.subscriber_text}`}
                                </div>
                                <div style={{ fontSize: 8, marginTop: 4, color: c.youtube!.match === "name_verified" ? MODULE_D : INK_GHOST, textTransform: "uppercase", letterSpacing: "0.1em" }}>
                                  {c.youtube!.match === "name_verified" ? "✓ name verified" : "handle match"}
                                </div>
                              </div>
                              <div>
                                {c.youtube!.topics.length > 0 && (
                                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 6 }}>
                                    {c.youtube!.topics.slice(0, 6).map((t, j) => (
                                      <span key={j} style={{ fontSize: 9, padding: "2px 7px", background: "rgba(139,92,246,0.12)", border: `1px solid ${MODULE_A}`, color: MODULE_A }}>{t}</span>
                                    ))}
                                  </div>
                                )}
                                {c.youtube!.description && (
                                  <div style={{ fontSize: 10, color: INK_DIM, lineHeight: 1.5 }}>{c.youtube!.description}</div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </DashboardPanel>
                    </div>
                  );
                })()}
              </div>
            )}

            {activeTab === "timeline" && (
              <div className="grid grid-cols-1 gap-8">
                {/* Algorithm efficiency + anomaly flags */}
                {(() => {
                  const rates = profile.stopwatch_metrics.monthly_skip_rates;
                  const anomalies = profile.skip_anomalies ?? [];
                  if (!rates || Object.keys(rates).length < 2) return null;
                  const months = Object.entries(rates).sort(([a], [b]) => a.localeCompare(b));
                  const maxRate = Math.max(...months.map(([, v]) => v), 1);
                  const anomalyMonths = new Set(anomalies.map(a => a.month));
                  return (
                    <DashboardPanel label="· Algorithm Efficiency Timeline" accent={ACCENT}>
                      <SectionTitle>Skip Rate Over Time</SectionTitle>
                      <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
                        When the skip rate goes down, the algorithm has a better read on you — it's serving content you actually want. When it spikes, something changed: your tastes shifted, the algorithm lost its calibration, or the platform started pushing content you didn't ask for.
                      </div>
                      <div style={{ display: "flex", gap: 4, alignItems: "flex-end", height: 80, marginBottom: 8 }}>
                        {months.map(([month, rate]) => {
                          const isAnomaly = anomalyMonths.has(month);
                          const color = isAnomaly ? MODULE_B : VIBE_ACCENT;
                          return (
                            <div key={month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                              {isAnomaly && <div style={{ width: 6, height: 6, borderRadius: "50%", background: MODULE_B, flexShrink: 0 }} title="Anomaly detected" />}
                              <div style={{ width: "100%", height: `${Math.max((rate / maxRate) * 72, 4)}px`, background: color, opacity: isAnomaly ? 1 : 0.65 }} title={`${month}: ${rate}% skip`} />
                            </div>
                          );
                        })}
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: INK_GHOST, fontFamily: "var(--font-mono, monospace)", marginBottom: 16 }}>
                        <span>{months[0]?.[0]}</span>
                        <span>{months[months.length - 1]?.[0]}</span>
                      </div>
                      {anomalies.length > 0 && (
                        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                          {anomalies.map((a, i) => (
                            <div key={i} style={{ padding: "12px 16px", border: `1px solid ${MODULE_B}40`, background: `${MODULE_B}08` }}>
                              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                                <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: MODULE_B }}>{a.month} · anomaly</span>
                                <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: INK }}>{a.skip_rate}% <span style={{ color: INK_GHOST }}>vs {a.baseline_avg}% baseline</span></span>
                              </div>
                              <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6 }}>
                                Skip rate {a.direction === "spike" ? "spiked" : "dipped"} {Math.abs(a.delta)}pp from your baseline. This could mean the algorithm lost its read on you, your tastes shifted, the platform changed what it was pushing, or a data purge disrupted the recommendation model. The data alone can't say which.
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </DashboardPanel>
                  );
                })()}

                {/* Monthly creator dominance */}
                {(() => {
                  const trends = profile.monthly_creator_trends;
                  if (!trends || Object.keys(trends).length === 0) return null;
                  const months = Object.entries(trends).sort(([a], [b]) => a.localeCompare(b));
                  return (
                    <DashboardPanel label="· Creator Dominance by Month" accent={VIBE_ACCENT}>
                      <SectionTitle accent={VIBE_ACCENT}>Who You Were Watching</SectionTitle>
                      <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
                        The creators you lingered on most, month by month. Shifts here show the algorithm changing what it thinks you want — or you actively seeking something new.
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16 }}>
                        {months.map(([month, creators]) => (
                          <div key={month} style={{ border: `1px solid ${BORDER}`, padding: 16 }}>
                            <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 12 }}>{month}</div>
                            {creators.length === 0 ? (
                              <div style={{ fontSize: 11, color: INK_GHOST }}>No resolved creators</div>
                            ) : (
                              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                                {creators.map((c, i) => (
                                  <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                                    <span style={{ color: i === 0 ? VIBE_ACCENT : INK_DIM, fontFamily: "var(--font-mono, monospace)" }}>{c.handle}</span>
                                    <span style={{ color: INK_GHOST }}>{c.count}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </DashboardPanel>
                  );
                })()}

                {/* Monthly topic trends */}
                {(() => {
                  const trends = profile.monthly_topic_trends;
                  if (!trends || Object.keys(trends).length === 0) return null;
                  const months = Object.entries(trends).sort(([a], [b]) => a.localeCompare(b));
                  return (
                    <DashboardPanel label="· Topic Trends by Month" accent={MODULE_A}>
                      <SectionTitle accent={MODULE_A}>What You Were Into</SectionTitle>
                      <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
                        Top keywords from your searches and comments each month. A snapshot of what was on your mind.
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16 }}>
                        {months.map(([month, topics]) => (
                          <div key={month} style={{ border: `1px solid ${BORDER}`, padding: 16 }}>
                            <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 12 }}>{month}</div>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                              {topics.map((t, i) => (
                                <span key={i} style={{ fontSize: 10, padding: "3px 8px", background: i === 0 ? `${MODULE_A}20` : "transparent", border: `1px solid ${i === 0 ? MODULE_A : BORDER}`, color: i === 0 ? MODULE_A : INK_DIM }}>
                                  {t.term}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </DashboardPanel>
                  );
                })()}
              </div>
            )}

            {activeTab === "interests" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <DashboardPanel label="07 · Topic Mapping" accent={ACCENT}>
                  <SectionTitle>Behavioral Interest Clusters</SectionTitle>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {profile.interest_clusters?.map((c, i) => (
                      <div key={i} style={{ 
                        padding: "6px 12px", 
                        background: "rgba(255,255,255,0.05)",
                        border: `1px solid ${BORDER}`,
                        fontSize: 11,
                        textTransform: "uppercase"
                      }}>
                        {c.term} <span style={{ color: ACCENT, marginLeft: 4 }}>{c.count}</span>
                      </div>
                    ))}
                  </div>
                </DashboardPanel>

                <div className="md:col-span-2">
                  <DashboardPanel label="08 · Audience Labels Sold To Advertisers" accent={MODULE_C}>
                    <SectionTitle accent={MODULE_C}>What Advertisers Were Told About You</SectionTitle>
                    {(profile.ad_profile?.advertiser_categories?.length ?? 0) > 0 ? (
                      <>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
                          {profile.ad_profile!.advertiser_categories.map((cat, i) => (
                            <span key={i} style={{
                              padding: "6px 12px",
                              background: "rgba(249, 115, 22, 0.1)",
                              border: `1px solid ${MODULE_C}`,
                              color: MODULE_C,
                              fontSize: 11,
                            }}>
                              {cat}
                            </span>
                          ))}
                        </div>
                        <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
                          You did not pick these. TikTok inferred them from your behavior and packages
                          them as audience segments advertisers can target. This is the list you cannot
                          see anywhere inside the app.
                        </div>
                      </>
                    ) : (
                      <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
                        No advertiser audience labels were present in this export.
                      </div>
                    )}
                  </DashboardPanel>
                </div>

                <DashboardPanel label="09 · Transparency Gap" accent={MODULE_B}>
                  <SectionTitle accent={MODULE_B}>Declared vs. Inferred</SectionTitle>
                  <div className="flex items-center gap-12 mb-8">
                    <div>
                      <div style={{ fontSize: 10, color: INK_GHOST, textTransform: "uppercase" }}>Declared</div>
                      <div style={{ fontSize: 32, fontWeight: 700 }}>{profile.transparency_gap?.official_ad_interest_count}</div>
                    </div>
                    <div style={{ fontSize: 24, color: INK_GHOST }}>&rarr;</div>
                    <div>
                      <div style={{ fontSize: 10, color: INK_GHOST, textTransform: "uppercase" }}>Inferred</div>
                      <div style={{ fontSize: 32, fontWeight: 700, color: MODULE_B }}>{profile.transparency_gap?.behavioral_interest_count}</div>
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
                    {profile.transparency_gap?.gap_interpretation}
                  </div>
                </DashboardPanel>

                <DashboardPanel label="10 · Search Rhythm" accent={VIBE_ACCENT}>
                  <SectionTitle accent={VIBE_ACCENT}>Active Intent Timeline</SectionTitle>
                  <div style={{ display: "flex", height: 60, gap: 2, alignItems: "flex-end", marginBottom: 12 }}>
                    {profile.search_rhythm?.hourly_histogram && Object.entries(profile.search_rhythm.hourly_histogram).map(([hour, count]) => {
                      const max = Math.max(...Object.values(profile.search_rhythm!.hourly_histogram));
                      const pct = max > 0 ? (count / max) * 100 : 0;
                      return (
                        <div key={hour} style={{ flex: 1, height: `${pct}%`, background: ACCENT, opacity: 0.6 }} title={`${hour}:00 - ${count} searches`} />
                      );
                    })}
                  </div>
                  <div style={{ fontSize: 11, color: INK_DIM }}>
                    Histogram of when you proactively search the platform. Search behavior is a high-confidence indicator of active interest vs. passive scrolling.
                  </div>
                </DashboardPanel>

                <DashboardPanel label="11 · Comment Analysis" accent={MODULE_A}>
                  <SectionTitle accent={MODULE_A}>Recurring Phrases</SectionTitle>
                  <div className="space-y-3">
                    {profile.interest_phrases?.slice(0, 8).map((p, i) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                        <span style={{ color: INK }}>"{p.phrase}"</span>
                        <span style={{ color: INK_GHOST }}>{p.count}x</span>
                      </div>
                    ))}
                  </div>
                </DashboardPanel>
              </div>
            )}

            {activeTab === "privacy" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <DashboardPanel label="09 · Digital Footprint" accent={ACCENT}>
                  <SectionTitle>Geographic & Device Trace</SectionTitle>
                  <div className="space-y-4">
                    <div style={{ borderBottom: `1px solid ${BORDER}`, paddingBottom: 16 }}>
                      <div style={{ fontSize: 10, color: INK_GHOST, textTransform: "uppercase", marginBottom: 4 }}>Unique IPs</div>
                      <div style={{ fontSize: 24, fontWeight: 700 }}>{profile.digital_footprint?.unique_ips}</div>
                    </div>
                    <div style={{ borderBottom: `1px solid ${BORDER}`, paddingBottom: 16 }}>
                      <div style={{ fontSize: 10, color: INK_GHOST, textTransform: "uppercase", marginBottom: 4 }}>Known Devices</div>
                      <div style={{ fontSize: 14 }}>{profile.digital_footprint?.unique_devices.join(" · ")}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 10, color: INK_GHOST, textTransform: "uppercase", marginBottom: 12 }}>Recent Logins</div>
                      <div className="space-y-2">
                        {profile.digital_footprint?.recent_logins.slice(0, 6).map((l, i) => (
                          <div key={i} style={{ fontSize: 11, display: "flex", justifyContent: "space-between", gap: 12, color: INK_DIM }}>
                            <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {l.city ?? "Unknown"}
                              {l.ip && <span style={{ color: INK_GHOST }}> · {l.ip}</span>}
                              {l.carrier && <span style={{ color: INK_GHOST }}> · {l.carrier}</span>}
                            </span>
                            <span style={{ flexShrink: 0 }}>{l.date.split("T")[0]}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </DashboardPanel>

                <DashboardPanel label="10 · Off-Platform Surveillance" accent={GRAVEYARD_ACCENT}>
                  <SectionTitle accent={GRAVEYARD_ACCENT}>Activity Reported From Outside TikTok</SectionTitle>
                  {(profile.ad_profile?.off_platform_events ?? 0) > 0 ? (
                    <>
                      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12 }}>
                        <div style={{ fontSize: 56, fontWeight: 700, color: GRAVEYARD_ACCENT }}>
                          {profile.ad_profile!.off_platform_events.toLocaleString()}
                        </div>
                        <div style={{ fontSize: 11, color: INK_DIM, textTransform: "uppercase" }}>events</div>
                      </div>
                      <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
                        Websites and apps <em>outside</em> TikTok that reported your activity back to
                        ByteDance through its business tools. This is the tracking you cannot see from
                        inside the app — it follows you across the open web.
                      </div>
                    </>
                  ) : (
                    <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
                      No off-platform activity records were found in this export. Either no third-party
                      sites shared your behavior with TikTok, or this section was excluded from your download.
                    </div>
                  )}
                </DashboardPanel>

                {(profile.ad_profile?.shop_order_count ?? 0) > 0 && (
                  <DashboardPanel label="11 · On-Platform Purchases" accent={MODULE_D}>
                    <SectionTitle accent={MODULE_D}>What You Bought On TikTok Shop</SectionTitle>
                    <div style={{ fontSize: 10, color: INK_GHOST, textTransform: "uppercase", marginBottom: 12 }}>
                      {profile.ad_profile!.shop_order_count} orders on file · first-party purchase intent
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {profile.ad_profile!.shop_products.slice(0, 10).map((p, i) => (
                        <div key={i} style={{ fontSize: 11, color: INK_DIM, display: "flex", gap: 8 }}>
                          <span style={{ color: INK_GHOST }}>{String(i + 1).padStart(2, "0")}</span>
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {p.length > 60 ? p.slice(0, 60).trimEnd() + "…" : p}
                          </span>
                        </div>
                      ))}
                    </div>
                  </DashboardPanel>
                )}

                {(profile.ad_profile?.product_browsing_count ?? 0) > 0 && (
                  <DashboardPanel label="12 · Shopping Intent" accent={VIBE_ACCENT}>
                    <SectionTitle accent={VIBE_ACCENT}>Products You Considered</SectionTitle>
                    <div style={{ fontSize: 10, color: INK_GHOST, textTransform: "uppercase", marginBottom: 12 }}>
                      {profile.ad_profile!.product_browsing_count.toLocaleString()} products browsed · intent without purchase
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {profile.ad_profile!.browsed_products.slice(0, 10).map((p, i) => (
                        <div key={i} style={{ fontSize: 11, color: INK_DIM, display: "flex", gap: 8 }}>
                          <span style={{ color: INK_GHOST }}>{String(i + 1).padStart(2, "0")}</span>
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {p.length > 60 ? p.slice(0, 60).trimEnd() + "…" : p}
                          </span>
                        </div>
                      ))}
                    </div>
                  </DashboardPanel>
                )}
              </div>
            )}

            {activeTab === "ai" && (
              <div>
                <LLMAnalysisView 
                  file={sourceFile!} 
                  apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
                  onBack={() => setActiveTab("overview")}
                />
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
