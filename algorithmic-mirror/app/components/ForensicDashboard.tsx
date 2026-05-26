"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Activity, 
  Network, 
  Search, 
  ShieldAlert, 
  LayoutDashboard,
  ArrowLeft,
  Share2,
  Lock,
  Zap
} from "lucide-react";
import type { GhostProfile } from "./GhostProfileHUD";
import { DownloadExportButton } from "./DownloadExportButton";
import { CreatorGraph } from "./CreatorGraph";
import { LLMAnalysisView } from "./LLMAnalysisView";

// We'll import existing visualizations or build new ones inside these tabs.
// For now, let's define the tab types.
type Tab = "overview" | "behavior" | "network" | "interests" | "privacy" | "ai";

interface Props {
  profile: GhostProfile;
  onReset: () => void;
  sourceFile?: File;
}

// ---------------------------------------------------------------------------
// Design Tokens (Dark Deco / Dashboard Noir)
// ---------------------------------------------------------------------------

const BG = "#050505";
const SIDEBAR = "#0a0a0a";
const PANEL = "#0f0f0f";
const BORDER = "rgba(255, 255, 255, 0.08)";
const ACCENT = "#00e5ff"; // Forensic Cyan
const INK = "#ffffff";
const INK_DIM = "rgba(255, 255, 255, 0.6)";
const INK_GHOST = "rgba(255, 255, 255, 0.25)";

const MODULE_A = "#8b5cf6"; // Illusion of Choice — purple
const MODULE_B = "#ef4444"; // Echo Chamber — red
const MODULE_C = "#f97316"; // Personalization Trap — orange
const MODULE_D = "#10b981"; // Monolith Adaptation — emerald
const GRAVEYARD_ACCENT = "#ec4899"; // pink
const VIBE_ACCENT = "#06b6d4"; // cyan

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
            of {sw.total_raw_videos.toLocaleString()} raw
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
    <div style={{ 
      background: BG, 
      minHeight: "100vh", 
      display: "flex", 
      color: INK, 
      fontFamily: "var(--font-mono, monospace)" 
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
          <div style={{ fontSize: 10, letterSpacing: "0.3em", color: ACCENT, marginBottom: 8 }}>
            // SYS.TEARDOWN
          </div>
          <h1 style={{ fontSize: 18, fontWeight: 900, letterSpacing: "-0.02em", margin: 0 }}>
            FORENSIC <span style={{ color: ACCENT }}>DASHBOARD</span>
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
                <header style={{ marginBottom: 48 }}>
                  <div style={{ fontSize: 11, letterSpacing: "0.2em", color: ACCENT, marginBottom: 12 }}>
                    // USER_ARCHETYPE_IDENTIFIED
                  </div>
                  <h2 style={{ fontSize: 48, fontWeight: 900, margin: 0 }}>
                    {profile.primary_archetype?.name ?? "The Balanced Viewer"}
                  </h2>
                  <div style={{ marginTop: 12, fontSize: 14, color: INK_DIM, maxWidth: 600, lineHeight: 1.6 }}>
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
                  <h3 style={{ fontSize: 12, textTransform: "uppercase", color: INK_DIM, marginBottom: 24 }}>// Behavioral Atomic Traits</h3>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
                    {profile.primary_archetype?.atomic_traits && Object.entries(profile.primary_archetype.atomic_traits).map(([trait, active]) => (
                      <div key={trait} style={{ 
                        padding: "8px 16px", 
                        background: active ? "rgba(0, 229, 255, 0.15)" : "rgba(255,255,255,0.05)",
                        border: `1px solid ${active ? ACCENT : BORDER}`,
                        color: active ? ACCENT : INK_DIM,
                        fontSize: 11,
                        textTransform: "uppercase"
                      }}>
                        {trait}
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
                      {profile.academic_insights?.explicit_vs_implicit_ratio.toFixed(2)}
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

                <DashboardPanel label="04 · Session Intensity" accent={VIBE_ACCENT}>
                  <SectionTitle accent={VIBE_ACCENT}>Maximum Flow State</SectionTitle>
                  <div style={{ fontSize: 42, fontWeight: 700, color: VIBE_ACCENT, marginBottom: 12 }}>
                    {(profile.stopwatch_metrics.max_session_duration / 60).toFixed(1)} <span style={{ fontSize: 20 }}>min</span>
                  </div>
                  <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
                    Longest continuous engagement session scrubbed of AFK anomalies.
                    Represents your maximum immersion depth in the recommendation loop.
                  </div>
                </DashboardPanel>
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
                    <div style={{ marginTop: 24, fontSize: 11, color: INK_DIM }}>
                      Mapping your creator network. Cyan nodes are followed accounts; 
                      Magenta nodes are purely algorithmic discoveries that captured your attention.
                    </div>
                  </DashboardPanel>
                </div>

                <DashboardPanel label="05 · Echo Chamber Index" accent={MODULE_B}>
                  <SectionTitle accent={MODULE_B}>Creator Concentration</SectionTitle>
                  <div style={{ fontSize: 56, fontWeight: 700, color: MODULE_B, marginBottom: 8 }}>
                    {profile.academic_insights?.echo_chamber_index_pct.toFixed(0)}%
                  </div>
                  <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
                    Concentration of attention on your top 5 creators. 
                    High percentages indicate a narrow informational feedback loop.
                  </div>
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

                <DashboardPanel label="08 · Transparency Gap" accent={MODULE_B}>
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

                <DashboardPanel label="09 · Search Rhythm" accent={VIBE_ACCENT}>
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

                <DashboardPanel label="10 · Comment Analysis" accent={MODULE_A}>
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
                        {profile.digital_footprint?.recent_logins.slice(0, 5).map((l, i) => (
                          <div key={i} style={{ fontSize: 11, display: "flex", justifyContent: "space-between", color: INK_DIM }}>
                            <span>{l.city ?? "Unknown City"}</span>
                            <span>{l.date.split("T")[0]}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </DashboardPanel>

                <DashboardPanel label="10 · Data Harvesting" accent={GRAVEYARD_ACCENT}>
                  <SectionTitle accent={GRAVEYARD_ACCENT}>Silent Permissions</SectionTitle>
                  <div className="space-y-4">
                    {[
                      { label: "Watch History", sub: "Retention time per frame" },
                      { label: "Social Graph", sub: "Followed vs Surfaced ratio" },
                      { label: "Search Rhythm", sub: "Keyword intent timeline" },
                      { label: "Ad susceptibility", sub: "Peak vulnerability window" }
                    ].map((p, i) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 8, borderBottom: `1px solid ${BORDER}` }}>
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 600 }}>{p.label}</div>
                          <div style={{ fontSize: 10, color: INK_GHOST }}>{p.sub}</div>
                        </div>
                        <div style={{ fontSize: 9, color: GRAVEYARD_ACCENT, fontWeight: 900 }}>COLLECTED</div>
                      </div>
                    ))}
                  </div>
                </DashboardPanel>
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
