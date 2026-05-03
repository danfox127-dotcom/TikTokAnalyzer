"use client";

import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { DownloadExportButton } from "./DownloadExportButton";

export interface EnrichmentTarget {
  video_id: string;
  link: string;
  time_spent: number;
  hour: number;
}

export interface EnrichedVideo extends EnrichmentTarget {
  title: string;
  author: string;
  author_name: string;
  thumbnail: string;
}

export interface ThemeBundle {
  top_keywords: { term: string; count: number }[];
  top_phrases: { phrase: string; count: number }[];
  top_emojis?: { emoji: string; count: number }[];
}

export interface EnrichmentResult {
  videos: {
    lingered: EnrichedVideo[];
    graveyard: EnrichedVideo[];
    sandbox: EnrichedVideo[];
    night_lingered: EnrichedVideo[];
  };
  video_results?: Record<string, { status: string; error?: string }>;
  cache_metrics?: { hits: number; misses: number; evictions: number };
  top_creators: {
    lingered: { author: string; author_name: string; count: number }[];
    graveyard: { author: string; author_name: string; count: number }[];
  };
  themes: {
    psychographic: ThemeBundle;
    anti_profile: ThemeBundle;
    sandbox: ThemeBundle;
    night: ThemeBundle;
  };
  following_ratio: { followed_pct: number; algorithmic_pct: number; matched_videos: number };
  fetched_count: number;
  requested_count: number;
}

export interface GhostProfile {
  status: "success";
  stopwatch_metrics: {
    total_conscious_videos: number;
    sleep_anomalies_scrubbed: number;
    sleep_scrubbed: number;
    graveyard_skips: number;
    sandbox_views: number;
    deep_lingers: number;
    deep_dives: number;
    total_videos: number;
    hourly_heatmap: Record<string, number>;
    weekly_heatmap?: Record<number, Record<number, number>>;
    monthly_skip_rates?: Record<string, number>;
  };
  behavioral_nodes: {
    peak_hour: string;
    skip_rate_percentage: number;
    linger_rate_percentage: number;
    night_shift_ratio: number;
    night_linger_pct: number;
    night_lingers_count: number;
    social_graph_algorithmic_pct: number;
    social_graph_followed_pct: number;
  };
  creator_entities: {
    vibe_cluster: { handle: string; linger_count: number }[];
    graveyard: { handle: string; skip_count: number }[];
  };
  academic_insights?: {
    explicit_vs_implicit_ratio: number;
    explicit_actions_count: number;
    implicit_linger_count: number;
    echo_chamber_index_pct: number;
    top_creator_handles: string[];
  };
  night_shift?: {
    percentage: number;
    count: number;
    window: string;
  };
  enrichment_targets?: {
    lingered: EnrichmentTarget[];
    graveyard: EnrichmentTarget[];
    sandbox: EnrichmentTarget[];
    night_lingered: EnrichmentTarget[];
    deep_dives?: EnrichmentTarget[];
    following_usernames: string[];
  };
  deep_dives?: { count: number; videos: EnrichmentTarget[] };
  primary_archetype?: { 
    name: string; 
    sub_archetypes: { name: string; confidence: number }[];
    dissonance: { detected: boolean; label: string | null; note: string | null };
    atomic_traits: Record<string, boolean>;
  };
  narrative_blocks?: import("../types/narrative").NarrativeBlock[];
  _evidence?: {

    settings_interests: string[];
    ad_interests: string[];
    recent_searches: string[];
    following_count: number;
    follower_count: number;
  };
  ad_profile?: {
    advertiser_categories: string[];
    vulnerability_window: string;
    peak_ad_hour: string;
    night_targeting: number;
    off_platform_tracked: boolean;
    off_platform_events: number;
    shop_order_count: number;
    shop_products: string[];
  };
  digital_footprint?: {
    login_count: number;
    unique_ips: number;
    unique_devices: string[];
    ip_locations: string[];
    recent_logins: {
      date: string;
      ip: string;
      device: string;
      system: string;
      network: string;
      carrier: string;
    }[];
  };
  search_rhythm?: {
    total_searches: number;
    hourly_histogram: Record<string, number>;
    recent_searches: { term: string; date: string; hour: number; dow: number }[];
  };
  discrepancy_gap?: {
    declared_surface_sample: string[];
    inferred_creator_handles: string[];
    declared_count: number;
    inferred_count: number;
  };
  _evidence?: {
    prologue?: Record<string, unknown>;
    feedback_loop?: Record<string, unknown>;
    discrepancy?: Record<string, unknown>;
    digital_footprint?: Record<string, unknown>;
    psychographic?: Record<string, unknown>;
    search_rhythm?: Record<string, unknown>;
  };
}

interface Props {
  profile: GhostProfile;
  onReset: () => void;
  sourceFile?: File;
  enrichment?: EnrichmentResult | null;
  enrichmentLoading?: boolean;
  sleepWindow?: { start: number; end: number } | null;
  sleepWindowLoading?: boolean;
  onSetSleepWindow?: (w: { start: number; end: number } | null) => void;
}

// ---------------------------------------------------------------------------
// Design tokens (brutalist, monospace, dark navy, per-module accent)
// ---------------------------------------------------------------------------

const BG = "#0f172a";
const PANEL = "#111a2d";
const LINE = "rgba(148, 163, 184, 0.18)";
const LINE_BRIGHT = "rgba(148, 163, 184, 0.35)";
const INK = "#e2e8f0";
const INK_DIM = "#94a3b8";
const INK_GHOST = "#475569";

const MODULE_A = "#8b5cf6"; // Illusion of Choice — purple
const MODULE_B = "#ef4444"; // Echo Chamber — red
const MODULE_C = "#f97316"; // Personalization Trap — orange
const MODULE_D = "#10b981"; // Monolith Adaptation — emerald
const GRAVEYARD_ACCENT = "#ec4899"; // pink
const VIBE_ACCENT = "#06b6d4"; // cyan

// ---------------------------------------------------------------------------
// Primitive — brutalist bordered panel with corner ticks + monospace label
// ---------------------------------------------------------------------------

function Panel({
  label,
  accent,
  children,
  className,
}: {
  label: string;
  accent: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={className}
      style={{
        position: "relative",
        background: PANEL,
        border: `1px solid ${LINE}`,
        padding: "32px 28px 28px",
      }}
    >
      {/* corner ticks */}
      <span style={{ position: "absolute", top: -1, left: -1, width: 10, height: 10, borderTop: `2px solid ${accent}`, borderLeft: `2px solid ${accent}` }} />
      <span style={{ position: "absolute", top: -1, right: -1, width: 10, height: 10, borderTop: `2px solid ${accent}`, borderRight: `2px solid ${accent}` }} />
      <span style={{ position: "absolute", bottom: -1, left: -1, width: 10, height: 10, borderBottom: `2px solid ${accent}`, borderLeft: `2px solid ${accent}` }} />
      <span style={{ position: "absolute", bottom: -1, right: -1, width: 10, height: 10, borderBottom: `2px solid ${accent}`, borderRight: `2px solid ${accent}` }} />

      {/* label ribbon */}
      <div
        style={{
          position: "absolute",
          top: -10,
          left: 24,
          background: BG,
          padding: "0 10px",
          fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
          fontSize: 10,
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

function SectionTitle({ accent, children }: { accent: string; children: React.ReactNode }) {
  return (
    <h3
      style={{
        fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
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

function Copy({ children, dim = false }: { children: React.ReactNode; dim?: boolean }) {
  return (
    <p
      style={{
        fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
        fontSize: 12,
        lineHeight: 1.7,
        color: dim ? INK_DIM : INK,
        margin: 0,
        letterSpacing: "0.02em",
      }}
    >
      {children}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Top Row — True Stopwatch Funnel
// ---------------------------------------------------------------------------

function StopwatchFunnel({ profile }: { profile: GhostProfile }) {
  const sw = profile.stopwatch_metrics ?? { total_conscious_videos: 0, graveyard_skips: 0, sandbox_views: 0, deep_lingers: 0, deep_dives: 0, total_videos: 0, sleep_scrubbed: 0, hourly_heatmap: {} };
  const total = Math.max(sw.total_conscious_videos, 1);
  const buckets = [
    { key: "GRAVEYARD", sub: "<3s skips", value: sw.graveyard_skips, color: GRAVEYARD_ACCENT },
    { key: "SANDBOX", sub: "3–15s probes", value: sw.sandbox_views, color: "#facc15" },
    { key: "LINGER", sub: "15–180s watch", value: sw.deep_lingers, color: VIBE_ACCENT },
    { key: "DEEP DIVE", sub: "180s+ commit", value: sw.deep_dives, color: MODULE_D },
  ];

  return (
    <Panel label="01 · True Stopwatch Funnel" accent={INK_DIM} className="col-span-full">
      <div className="grid grid-cols-5 gap-0" style={{ border: `1px solid ${LINE}` }}>
        <div style={{ padding: "24px 20px", borderRight: `1px solid ${LINE}` }}>
          <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: INK_GHOST }}>
            CONSCIOUS VIDEOS
          </div>
          <div style={{ fontSize: 36, fontWeight: 700, color: INK, marginTop: 8, fontFamily: "var(--font-mono, monospace)" }}>
            {sw.total_conscious_videos.toLocaleString()}
          </div>
          <div style={{ fontSize: 10, color: INK_GHOST, marginTop: 6, fontFamily: "var(--font-mono, monospace)" }}>
            of {sw.total_videos.toLocaleString()} raw · {sw.sleep_scrubbed} AFK scrubbed
          </div>
        </div>
        {buckets.map(b => {
          const pct = (b.value / total) * 100;
          return (
            <div key={b.key} style={{ padding: "24px 20px", borderRight: `1px solid ${LINE}`, position: "relative" }}>
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
                  left: 0,
                  bottom: 0,
                  height: 3,
                  width: "100%",
                  background: b.color,
                  transformOrigin: "left",
                  boxShadow: `0 0 12px ${b.color}`,
                }}
              />
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Module A — Illusion of Choice (explicit vs implicit)
// ---------------------------------------------------------------------------

function IllusionOfChoice({ profile }: { profile: GhostProfile }) {
  const ai = profile.academic_insights;
  const explicit = ai?.explicit_actions_count ?? 0;
  const implicit = ai?.implicit_linger_count ?? 0;
  const ratio = ai?.explicit_vs_implicit_ratio ?? 0;
  const total = Math.max(explicit + implicit, 1);
  const explicitPct = (explicit / total) * 100;
  const implicitPct = (implicit / total) * 100;

  return (
    <Panel label="02 · Module A" accent={MODULE_A}>
      <SectionTitle accent={MODULE_A}>Illusion of Choice</SectionTitle>

      <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 24 }}>
        <div style={{ fontSize: 56, fontWeight: 700, color: MODULE_A, fontFamily: "var(--font-mono, monospace)", letterSpacing: "-0.02em" }}>
          {ratio.toFixed(2)}
        </div>
        <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: INK_DIM, letterSpacing: "0.15em", textTransform: "uppercase" }}>
          explicit : implicit
        </div>
      </div>

      <div style={{ marginBottom: 12, fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.15em", color: INK_GHOST, textTransform: "uppercase" }}>
        <span style={{ color: MODULE_A }}>EXPLICIT</span> {explicit.toLocaleString()} likes + comments
      </div>
      <div style={{ width: "100%", height: 6, background: "rgba(139,92,246,0.12)", marginBottom: 18 }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${explicitPct}%` }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          style={{ height: "100%", background: MODULE_A, boxShadow: `0 0 12px ${MODULE_A}` }}
        />
      </div>

      <div style={{ marginBottom: 12, fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.15em", color: INK_GHOST, textTransform: "uppercase" }}>
        <span style={{ color: INK }}>IMPLICIT</span> {implicit.toLocaleString()} passive lingers
      </div>
      <div style={{ width: "100%", height: 6, background: "rgba(148,163,184,0.12)", marginBottom: 24 }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${implicitPct}%` }}
          transition={{ duration: 0.9, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          style={{ height: "100%", background: INK, boxShadow: `0 0 8px ${INK}` }}
        />
      </div>

      <Copy>
        Subject assumes explicit actions (likes/comments) dictate feed. True neural mapping is derived entirely from passive millisecond retention. Ignore explicit data.
      </Copy>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Module B — Echo Chamber Index
// ---------------------------------------------------------------------------

function EchoChamber({ profile }: { profile: GhostProfile }) {
  const pct = profile.academic_insights?.echo_chamber_index_pct ?? 0;
  const handles = profile.academic_insights?.top_creator_handles ?? [];

  return (
    <Panel label="03 · Module B" accent={MODULE_B}>
      <SectionTitle accent={MODULE_B}>Echo Chamber Index</SectionTitle>

      <div style={{ position: "relative", marginBottom: 24 }}>
        <div style={{ fontSize: 72, fontWeight: 700, color: MODULE_B, fontFamily: "var(--font-mono, monospace)", lineHeight: 1, letterSpacing: "-0.03em" }}>
          {pct.toFixed(0)}
          <span style={{ fontSize: 32, color: INK_DIM }}>%</span>
        </div>
        <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.22em", color: INK_GHOST, textTransform: "uppercase", marginTop: 4 }}>
          top 5 creator concentration
        </div>

        <div style={{ marginTop: 20, height: 28, background: "rgba(239,68,68,0.08)", border: `1px solid rgba(239,68,68,0.25)`, position: "relative" }}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(pct, 100)}%` }}
            transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
            style={{
              height: "100%",
              background: `repeating-linear-gradient(45deg, ${MODULE_B} 0, ${MODULE_B} 4px, rgba(239,68,68,0.7) 4px, rgba(239,68,68,0.7) 8px)`,
            }}
          />
          {[25, 50, 75].map(t => (
            <div key={t} style={{ position: "absolute", top: 0, left: `${t}%`, width: 1, height: "100%", background: "rgba(148,163,184,0.25)" }} />
          ))}
        </div>
      </div>

      {handles.length > 0 && (
        <div style={{ marginBottom: 20, fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: INK_DIM, letterSpacing: "0.05em" }}>
          {handles.slice(0, 5).map((h, i) => (
            <span key={`${h}-${i}`}>
              <span style={{ color: MODULE_B }}>{h}</span>
              {i < Math.min(handles.length, 5) - 1 && <span style={{ color: INK_GHOST }}> · </span>}
            </span>
          ))}
        </div>
      )}

      <Copy>
        High content homogeneity detected via collaborative filtering. Subject is locked in a feedback loop. Vulnerability to targeted messaging is critical.
      </Copy>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Module C — Personalization Trap (night shift)
// ---------------------------------------------------------------------------

function PersonalizationTrap({ profile }: { profile: GhostProfile }) {
  const pct = profile.night_shift?.percentage ?? profile.behavioral_nodes?.night_shift_ratio ?? 0;
  const count = profile.night_shift?.count ?? 0;
  const window = profile.night_shift?.window ?? "23:00 – 04:00";

  return (
    <Panel label="04 · Module C" accent={MODULE_C}>
      <SectionTitle accent={MODULE_C}>Personalization Trap</SectionTitle>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0, border: `1px solid ${LINE}`, marginBottom: 24 }}>
        <div style={{ padding: 20, borderRight: `1px solid ${LINE}` }}>
          <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 8 }}>
            Night Shift Ratio
          </div>
          <div style={{ fontSize: 48, fontWeight: 700, color: MODULE_C, fontFamily: "var(--font-mono, monospace)", lineHeight: 1 }}>
            {pct.toFixed(1)}
            <span style={{ fontSize: 22, color: INK_DIM }}>%</span>
          </div>
        </div>
        <div style={{ padding: 20 }}>
          <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 8 }}>
            Dayparting Window
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: INK, fontFamily: "var(--font-mono, monospace)", lineHeight: 1.2 }}>
            {window}
          </div>
          <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, color: INK_GHOST, marginTop: 8 }}>
            {count.toLocaleString()} sessions
          </div>
        </div>
      </div>

      {/* 24-hour retention bar */}
      <div style={{ display: "flex", height: 40, gap: 2, marginBottom: 10 }}>
        {Array.from({ length: 24 }, (_, h) => {
          const v = profile.stopwatch_metrics.hourly_heatmap[String(h)] ?? 0;
          const maxV = Math.max(...Object.values(profile.stopwatch_metrics.hourly_heatmap));
          const pctH = maxV > 0 ? (v / maxV) * 100 : 0;
          const isNight = h >= 23 || h < 4;
          return (
            <div
              key={h}
              style={{
                flex: 1,
                display: "flex",
                alignItems: "flex-end",
                height: "100%",
              }}
              title={`${h}:00 — ${v} videos`}
            >
              <div
                style={{
                  width: "100%",
                  height: `${pctH}%`,
                  background: isNight ? MODULE_C : INK_GHOST,
                  boxShadow: isNight ? `0 0 6px ${MODULE_C}` : "none",
                }}
              />
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--font-mono, monospace)", fontSize: 9, color: INK_GHOST, marginBottom: 20 }}>
        <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>23:59</span>
      </div>

      <Copy>
        Algorithm overrides biological self-regulation via dayparting. Dense, long-form content served late-night to maximize Information Doomscrolling.
      </Copy>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Module D — Monolith Real-Time Adaptation
// ---------------------------------------------------------------------------

function MonolithAdaptation({ profile }: { profile: GhostProfile }) {
  const total = profile.stopwatch_metrics.total_conscious_videos;
  const embeddings = total * 512; // collisionless hash slots per conscious event

  return (
    <Panel label="05 · Module D" accent={MODULE_D}>
      <SectionTitle accent={MODULE_D}>Monolith Real-Time Adaptation</SectionTitle>

      <div style={{ marginBottom: 20, position: "relative", height: 120, border: `1px solid ${LINE}`, overflow: "hidden" }}>
        {/* pulsing embedding lattice */}
        <div style={{
          position: "absolute", inset: 0,
          backgroundImage: `
            linear-gradient(${LINE} 1px, transparent 1px),
            linear-gradient(90deg, ${LINE} 1px, transparent 1px)
          `,
          backgroundSize: "12px 12px",
        }} />
        {Array.from({ length: 18 }, (_, i) => (
          <motion.div
            key={i}
            animate={{ opacity: [0.2, 1, 0.2] }}
            transition={{ duration: 1.6 + (i % 5) * 0.2, repeat: Infinity, delay: (i * 0.11) % 1.6 }}
            style={{
              position: "absolute",
              left: `${((i * 53) % 92) + 3}%`,
              top: `${((i * 31) % 85) + 5}%`,
              width: 6,
              height: 6,
              background: MODULE_D,
              boxShadow: `0 0 10px ${MODULE_D}`,
            }}
          />
        ))}
        <div style={{
          position: "absolute",
          bottom: 8,
          right: 12,
          fontFamily: "var(--font-mono, monospace)",
          fontSize: 10,
          color: MODULE_D,
          letterSpacing: "0.15em",
        }}>
          {embeddings.toLocaleString()} EMBEDDING SLOTS
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
        <div style={{ padding: "12px 14px", border: `1px solid ${LINE}` }}>
          <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 9, letterSpacing: "0.2em", color: INK_GHOST, textTransform: "uppercase" }}>
            Update latency
          </div>
          <div style={{ fontSize: 20, fontWeight: 700, color: MODULE_D, fontFamily: "var(--font-mono, monospace)", marginTop: 4 }}>
            &lt; 50 ms
          </div>
        </div>
        <div style={{ padding: "12px 14px", border: `1px solid ${LINE}` }}>
          <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 9, letterSpacing: "0.2em", color: INK_GHOST, textTransform: "uppercase" }}>
            Training cadence
          </div>
          <div style={{ fontSize: 20, fontWeight: 700, color: INK, fontFamily: "var(--font-mono, monospace)", marginTop: 4 }}>
            CONTINUOUS
          </div>
        </div>
      </div>

      <Copy>
        Powered by ByteDance Monolith collisionless embedding. Subject&apos;s neural profile is not batch-trained; it is updated at the exact millisecond of video rejection.
      </Copy>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Bottom Row — Creator ledgers (Graveyard + Vibe Cluster)
// ---------------------------------------------------------------------------

function CreatorLedger({
  label,
  num,
  accent,
  title,
  entries,
  countKey,
  countLabel,
}: {
  label: string;
  num: string;
  accent: string;
  title: string;
  entries: { handle: string; count: number }[];
  countKey: string;
  countLabel: string;
}) {
  const max = Math.max(...entries.map(e => e.count), 1);

  return (
    <Panel label={`${num} · ${label}`} accent={accent}>
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
                <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, color: INK_GHOST, letterSpacing: "0.1em" }}>
                  {String(i + 1).padStart(2, "0")}
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12, color: INK, marginBottom: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {e.handle}
                  </div>
                  <div style={{ width: "100%", height: 3, background: "rgba(148,163,184,0.1)" }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.6, delay: i * 0.04, ease: [0.22, 1, 0.36, 1] }}
                      style={{ height: "100%", background: accent, boxShadow: `0 0 6px ${accent}` }}
                    />
                  </div>
                </div>
                <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: accent, whiteSpace: "nowrap" }}>
                  {e.count} <span style={{ color: INK_GHOST, fontSize: 9 }}>{countLabel}</span>
                </div>
              </div>
            );
          })}
          <div style={{ marginTop: 4, fontFamily: "var(--font-mono, monospace)", fontSize: 9, color: INK_GHOST, letterSpacing: "0.15em", textTransform: "uppercase" }}>
            {"//"} top {Math.min(entries.length, 10)} · sorted by {countKey}
          </div>
        </div>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export function GhostProfileHUD({ profile, onReset, sourceFile }: Props) {
  const graveyard = (profile.creator_entities?.graveyard ?? []).map(g => ({ handle: g.handle, count: g.skip_count }));
  const vibe = (profile.creator_entities?.vibe_cluster ?? []).map(v => ({ handle: v.handle, count: v.linger_count }));

  return (
    <div style={{ background: BG, minHeight: "100vh", color: INK, fontFamily: "var(--font-mono, monospace)" }}>
      <div className="w-full max-w-7xl mx-auto px-6 py-12">
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 48 }}>
          <div>
            <div style={{ fontSize: 10, letterSpacing: "0.3em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 12 }}>
              // DOSSIER · ALGORITHMIC FORENSICS · CLASSIFIED
            </div>
            <h1
              style={{
                fontSize: 42,
                fontWeight: 800,
                letterSpacing: "-0.02em",
                lineHeight: 1.05,
                color: INK,
                margin: 0,
              }}
            >
              WHAT <span style={{ color: MODULE_B }}>ELSE</span> TIKTOK
              <br />
              KNOWS ABOUT YOU
            </h1>
            <div style={{ marginTop: 16, fontSize: 11, letterSpacing: "0.15em", color: INK_DIM, textTransform: "uppercase" }}>
              BYTEDANCE MONOLITH · COLLISIONLESS EMBEDDING · REAL-TIME RECOMMENDER
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <motion.button
              onClick={onReset}
              whileTap={{ scale: 0.96 }}
              whileHover={{ scale: 1.02 }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 18px",
                border: `1px solid ${LINE_BRIGHT}`,
                background: "transparent",
                color: INK,
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 11,
                letterSpacing: "0.2em",
                textTransform: "uppercase",
                cursor: "pointer",
              }}
            >
              <ArrowLeft size={14} />
              Reset
            </motion.button>
            {sourceFile && (
              <DownloadExportButton
                file={sourceFile}
                apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
              />
            )}
          </div>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Top row — full width funnel */}
          <div className="md:col-span-2">
            <StopwatchFunnel profile={profile} />
          </div>

          {/* Modules A, B, C, D */}
          <IllusionOfChoice profile={profile} />
          <EchoChamber profile={profile} />
          <PersonalizationTrap profile={profile} />
          <MonolithAdaptation profile={profile} />

          {/* Bottom row — creator ledgers */}
          <CreatorLedger
            label="Module E"
            num="06"
            accent={GRAVEYARD_ACCENT}
            title="Graveyard — Instant Rejection"
            entries={graveyard}
            countKey="skip_count"
            countLabel="skips"
          />
          <CreatorLedger
            label="Module F"
            num="07"
            accent={VIBE_ACCENT}
            title="Vibe Cluster — Sustained Lingers"
            entries={vibe}
            countKey="linger_count"
            countLabel="lingers"
          />
        </div>

        {/* Footer */}
        <div style={{ marginTop: 48, paddingTop: 24, borderTop: `1px solid ${LINE}`, display: "flex", justifyContent: "space-between", fontSize: 10, color: INK_GHOST, letterSpacing: "0.2em", textTransform: "uppercase" }}>
          <span>{"//"} END DOSSIER</span>
          <span>RETENTION-DRIVEN · NOT ACTION-DRIVEN</span>
        </div>
      </div>
    </div>
  );
}
