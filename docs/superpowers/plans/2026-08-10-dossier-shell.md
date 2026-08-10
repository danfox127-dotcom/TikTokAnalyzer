# Dossier Shell & Navigation (WP-3.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the 1190-line monolithic `ForensicDashboard.tsx` into a thin orchestrator + `DossierShell.tsx` (persistent chrome) + one component per tab, each lazy-loaded via `next/dynamic()`.

**Architecture:** Move the 5 shared local helpers into `dashboardPrimitives.tsx`; extract each of the 8 tabs' inline JSX into its own `tabs/XxxTab.tsx` (pure function of the `profile` prop, verified low-risk — only one `useState` in the whole current file, no cross-tab shared effects); extract the sidebar/header/reset/tab-switch chrome into `DossierShell.tsx`; convert the 8 tab imports to `next/dynamic()` last, in one isolated task, migrating the 5 existing dashboard tests to async queries.

**Tech Stack:** TypeScript (ts-jest, `algorithmic-mirror/`), React 19 / Next 16 (`next/dynamic` — built-in, no new dependency), `@testing-library/react`, existing `framer-motion`/`lucide-react`/`recharts`.

## Global Constraints

- `TheGlassHouse.tsx` is confirmed orphaned (not reachable from any path in `page.tsx`) — **do not touch it** in any task.
- Every extraction must be **verbatim** — copy the exact JSX/logic from the current `ForensicDashboard.tsx`, do not "improve," reformat, or restructure while moving. Byte-for-byte behavior preservation is the whole point of Tasks 1–10.
- Each tab component is a pure function of `{ profile: GhostProfile }`, except `AiTab` (`{ sourceFile: File; apiUrl: string; onBack: () => void }`).
- `dashboardPrimitives.tsx` exports (all moved verbatim, unchanged): the 13 design-token consts (`BG, SIDEBAR, PANEL, BORDER, ACCENT, INK, INK_DIM, INK_GHOST, MODULE_A, MODULE_B, MODULE_C, MODULE_D, GRAVEYARD_ACCENT, VIBE_ACCENT`) + `DashboardPanel`, `SectionTitle`, `SidebarItem`, `StopwatchFunnel`, `CreatorLedger`.
- Tasks 2–9 (the 8 tab extractions) keep `ForensicDashboard.tsx` fully working and all 5 existing dashboard tests passing **unchanged** (still synchronous `getByText`) — imports stay static until Task 11.
- Task 11 is the **only** task that changes observable behavior (real code-splitting) and the **only** task that touches the 5 existing dashboard test files.
- Run TS tests with `TZ=UTC`; run `npx tsc --noEmit` before every commit (ts-jest does not type-check).

---

### Task 1: `dashboardPrimitives.tsx` — shared tokens + helper components

**Files:**
- Create: `algorithmic-mirror/app/components/dashboardPrimitives.tsx`
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx`
- Test: run existing suite only (no new test file — this task is pure relocation, covered by every existing dashboard test still passing)

**Interfaces:**
- Produces: the 13 token consts + `DashboardPanel`, `SectionTitle`, `SidebarItem`, `StopwatchFunnel`, `CreatorLedger` — all named exports, used by every later task.

- [ ] **Step 1: Create `dashboardPrimitives.tsx`** with this exact content:

```tsx
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
```

- [ ] **Step 2: Modify `ForensicDashboard.tsx`** — remove the now-duplicated local definitions and import from `dashboardPrimitives.tsx` instead.

Replace the import block (lines 1–27, everything from `"use client";` through `import { ClaimsPanel } from "./ClaimsPanel";`) with:

```tsx
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
  TrendingUp,
  ScrollText
} from "lucide-react";
import type { GhostProfile } from "./GhostProfileHUD";
import { DownloadExportButton } from "./DownloadExportButton";
import { CreatorGraph } from "./CreatorGraph";
import { LLMAnalysisView } from "./LLMAnalysisView";
import { FourPillarsPanel } from "./FourPillarsPanel";
import { LocalModeBanner } from "./LocalModeBanner";
import { TargetingCard } from "./TargetingCard";
import { DemographicPanel } from "./DemographicPanel";
import { PersonaRadar } from "./PersonaRadar";
import { NicheDriftChart } from "./NicheDriftChart";
import { ClaimsPanel } from "./ClaimsPanel";
import {
  BG, SIDEBAR, PANEL, BORDER, ACCENT, INK, INK_DIM, INK_GHOST,
  MODULE_A, MODULE_B, MODULE_C, MODULE_D, GRAVEYARD_ACCENT, VIBE_ACCENT,
  DashboardPanel, SectionTitle, SidebarItem, StopwatchFunnel, CreatorLedger,
} from "./dashboardPrimitives";
```

(This drops the `LucideIcon` type import — no longer used directly in this file — and removes lines 43–295 of the original file: the token consts, `DashboardPanel`, `SectionTitle`, `SidebarItem`, `StopwatchFunnel`, `CreatorLedger` definitions. Delete that entire block — from the `const BG = "#f5efe4";` line through the closing `}` of `CreatorLedger`, immediately before the `// Main Dashboard` comment.)

- [ ] **Step 3: Run the full existing suite to confirm no regression**

Run: `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2`
Expected: PASS — same counts as before this change (all 5 dashboard tests still use synchronous `getByText` and still pass, since nothing about tab structure or timing changed, only where the helpers live).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 4: Commit**

```bash
git add algorithmic-mirror/app/components/dashboardPrimitives.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx
git commit -m "refactor(ui): WP-3.1 extract dashboardPrimitives — shared tokens + helper components"
```

---

### Task 2: Extract `OverviewTab.tsx`

**Files:**
- Create: `algorithmic-mirror/app/components/tabs/OverviewTab.tsx`
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx`
- Test: `algorithmic-mirror/app/components/tabs/__tests__/OverviewTab.test.tsx`

**Interfaces:**
- Consumes: `dashboardPrimitives.tsx` (Task 1); `PersonaRadar`, `FourPillarsPanel`; `GhostProfile` from `../GhostProfileHUD`.
- Produces: `export function OverviewTab({ profile }: { profile: GhostProfile })`.

- [ ] **Step 1: Create `OverviewTab.tsx`** with this exact content (the current `{activeTab === "overview" && (...)}` block, unwrapped into a component):

```tsx
"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import { PersonaRadar } from "../PersonaRadar";
import { FourPillarsPanel } from "../FourPillarsPanel";
import { BG, PANEL, BORDER, ACCENT, INK, INK_DIM, MODULE_A, MODULE_B, MODULE_C, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

export function OverviewTab({ profile }: { profile: GhostProfile }) {
  return (
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

      {profile.persona && (
        <div className="md:col-span-2">
          <DashboardPanel label="Persona Engine" accent={ACCENT}>
            <SectionTitle>Your Six Dimensions</SectionTitle>
            <PersonaRadar result={profile.persona} />
          </DashboardPanel>
        </div>
      )}

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
            <div style={{ fontSize: 10, color: BORDER === BORDER ? "rgba(26,22,16,0.4)" : undefined, marginTop: 6, lineHeight: 1.5 }}>Lowest-activity 4h window in your history</div>
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
              <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", marginTop: 6, lineHeight: 1.5 }}>Across your full export history</div>
            </div>
          );
        })()}
        {profile.algorithm_drift?.detectable && (
          <div style={{ background: PANEL, border: `1px solid ${BORDER}`, padding: "20px 24px" }}>
            <div style={{ fontSize: 10, color: INK_DIM, textTransform: "uppercase", marginBottom: 8 }}>Algorithm Capture</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: profile.algorithm_drift.direction === "tightening" ? MODULE_B : MODULE_D }}>
              {profile.algorithm_drift.direction === "tightening" ? "Tightening" : profile.algorithm_drift.direction === "loosening" ? "Loosening" : "Stable"}
            </div>
            <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", marginTop: 6, lineHeight: 1.5 }}>
              Skip rate {profile.algorithm_drift.direction === "tightening" ? "↓" : profile.algorithm_drift.direction === "loosening" ? "↑" : "→"} {Math.abs(profile.algorithm_drift.delta_pct ?? 0)}pp early→recent
            </div>
          </div>
        )}
        <div style={{ background: PANEL, border: `1px solid ${BORDER}`, padding: "20px 24px" }}>
          <div style={{ fontSize: 10, color: INK_DIM, textTransform: "uppercase", marginBottom: 8 }}>Peak Hour</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: MODULE_C }}>{profile.behavioral_nodes.peak_hour}</div>
          <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", marginTop: 6, lineHeight: 1.5 }}>Highest-volume viewing hour</div>
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
              color: active ? ACCENT : "rgba(26,22,16,0.4)",
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
  );
}
```

**IMPORTANT — one intentional fix during this extraction:** the original inline block used the bare `INK_GHOST` const in three spots (the "Lowest-activity…", "Across your full export…", and "Highest-volume…" caption lines) and in the atomic-traits inactive-trait color. In the extracted file above, those are written as literal `"rgba(26,22,16,0.4)"` strings (the exact value of `INK_GHOST`) to avoid a needless extra import — this is a **value-identical, zero-behavior-change** substitution (verify: `INK_GHOST = "rgba(26, 22, 16, 0.4)"` in `dashboardPrimitives.tsx`, same string, only whitespace differs in the source literal which does not affect the rendered CSS). Do not "clean up" the odd `BORDER === BORDER ? ... : undefined` ternary on the sleep-window line — that's a copy-paste artifact from this substitution; simplify it directly to `"rgba(26,22,16,0.4)"` (no ternary) since it always evaluates true. If you prefer, import `INK_GHOST` from `dashboardPrimitives` instead of inlining the string — either is acceptable as long as the rendered color is identical; if you do, remove the ternary and use `INK_GHOST` directly in all 4 spots.

- [ ] **Step 2: Write the smoke test**

```tsx
// algorithmic-mirror/app/components/tabs/__tests__/OverviewTab.test.tsx
import React from "react";
import { render } from "@testing-library/react";
import { OverviewTab } from "../OverviewTab";
import type { GhostProfile } from "../../GhostProfileHUD";

jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, RadarChart: Pass, PolarGrid: Pass, PolarAngleAxis: Pass, PolarRadiusAxis: Pass, Radar: Pass };
});
jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const profile = {
  primary_archetype: { name: "The Balanced Viewer" },
  stopwatch_metrics: { total_conscious_videos: 0, graveyard_skips: 0, sandbox_views: 0, deep_lingers: 0, deep_dives: 0 },
  behavioral_nodes: { linger_rate_percentage: 0, night_shift_ratio: 0, peak_hour: "12PM", inferred_sleep_window: "Unknown" },
} as unknown as GhostProfile;

test("OverviewTab renders without throwing", () => {
  const { container } = render(<OverviewTab profile={profile} />);
  expect(container).not.toBeEmptyDOMElement();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/OverviewTab.test.tsx`
Expected: FAIL — `Cannot find module '../OverviewTab'`.

- [ ] **Step 4: Create the file (Step 1's content above), then modify `ForensicDashboard.tsx`**

Add the import near the other component imports:

```tsx
import { OverviewTab } from "./tabs/OverviewTab";
```

Find the block starting with `{activeTab === "overview" && (` and ending at its matching `)}` (immediately before `{activeTab === "behavior" && (`) — this is the entire ~124-line block shown verbatim in Step 1 above, wrapped in `<div>...</div>`. Delete that whole block and replace it with:

```tsx
            {activeTab === "overview" && <OverviewTab profile={profile} />}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/OverviewTab.test.tsx`
Expected: PASS.
Then: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/PersonaRadarDashboard.test.tsx` → PASS (still synchronous — proves the extraction didn't change Overview's behavior).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 6: Commit**

```bash
git add algorithmic-mirror/app/components/tabs/OverviewTab.tsx algorithmic-mirror/app/components/tabs/__tests__/OverviewTab.test.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx
git commit -m "refactor(ui): WP-3.1 extract OverviewTab from ForensicDashboard"
```

---

### Task 3: Extract `BehaviorTab.tsx`

**Files:**
- Create: `algorithmic-mirror/app/components/tabs/BehaviorTab.tsx`
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx`
- Test: `algorithmic-mirror/app/components/tabs/__tests__/BehaviorTab.test.tsx`

**Interfaces:**
- Consumes: `StopwatchFunnel`, `DashboardPanel`, `SectionTitle`, tokens from `dashboardPrimitives.tsx` (Task 1).
- Produces: `export function BehaviorTab({ profile }: { profile: GhostProfile })`.

- [ ] **Step 1: Create `BehaviorTab.tsx`** with this exact content:

```tsx
"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import {
  BORDER, MODULE_A, MODULE_C, MODULE_D, GRAVEYARD_ACCENT, VIBE_ACCENT, INK, INK_DIM, INK_GHOST,
  DashboardPanel, SectionTitle, StopwatchFunnel,
} from "../dashboardPrimitives";

export function BehaviorTab({ profile }: { profile: GhostProfile }) {
  return (
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
            const color = isNight ? MODULE_B_LOCAL : isMorning ? MODULE_C : VIBE_ACCENT;
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
          <span style={{ color: MODULE_B_LOCAL }}>■</span> Night (11P–4A)
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
  );
}
```

**IMPORTANT:** the original inline code referenced `MODULE_B` for the night-hour heatmap bar color (lines 618/632 of the original). This file's import list does NOT include `MODULE_B` — add it. Replace every `MODULE_B_LOCAL` placeholder above with `MODULE_B` and add `MODULE_B` to the import line from `dashboardPrimitives`. (`MODULE_B_LOCAL` is written here only to force you to consciously wire the import — do not leave `MODULE_B_LOCAL` as a literal identifier, it does not exist and will not compile.)

- [ ] **Step 2: Write the smoke test**

```tsx
// algorithmic-mirror/app/components/tabs/__tests__/BehaviorTab.test.tsx
import React from "react";
import { render } from "@testing-library/react";
import { BehaviorTab } from "../BehaviorTab";
import type { GhostProfile } from "../../GhostProfileHUD";

jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const profile = {
  stopwatch_metrics: {
    total_conscious_videos: 10, graveyard_skips: 1, sandbox_views: 2, deep_lingers: 3, deep_dives: 4,
    hourly_heatmap: {}, total_raw_videos: 10,
  },
  behavioral_nodes: { night_shift_ratio: 5 },
  academic_insights: { explicit_vs_implicit_ratio: 0.5 },
} as unknown as GhostProfile;

test("BehaviorTab renders without throwing", () => {
  const { container } = render(<BehaviorTab profile={profile} />);
  expect(container).not.toBeEmptyDOMElement();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/BehaviorTab.test.tsx`
Expected: FAIL — `Cannot find module '../BehaviorTab'`.

- [ ] **Step 4: Create the file, then modify `ForensicDashboard.tsx`**

Add the import: `import { BehaviorTab } from "./tabs/BehaviorTab";`

Find the block starting with `{activeTab === "behavior" && (` and ending at its matching `)}` (immediately before `{activeTab === "network" && (`) and replace it with:

```tsx
            {activeTab === "behavior" && <BehaviorTab profile={profile} />}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/BehaviorTab.test.tsx`
Expected: PASS.
Then `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2` → PASS (all, no regressions).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 6: Commit**

```bash
git add algorithmic-mirror/app/components/tabs/BehaviorTab.tsx algorithmic-mirror/app/components/tabs/__tests__/BehaviorTab.test.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx
git commit -m "refactor(ui): WP-3.1 extract BehaviorTab from ForensicDashboard"
```

---

### Task 4: Extract `NetworkTab.tsx`

**Files:**
- Create: `algorithmic-mirror/app/components/tabs/NetworkTab.tsx`
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx`
- Test: `algorithmic-mirror/app/components/tabs/__tests__/NetworkTab.test.tsx`

**Interfaces:**
- Consumes: `CreatorGraph`; `CreatorLedger`, `DashboardPanel`, `SectionTitle`, tokens from `dashboardPrimitives.tsx`.
- Produces: `export function NetworkTab({ profile }: { profile: GhostProfile })`.

- [ ] **Step 1: Create `NetworkTab.tsx`** with this exact content. This block computes `graveyard`/`vibe` arrays from `profile.creator_entities` — that logic currently lives in `ForensicDashboard`'s function body (lines 304–313 of the original) and is used ONLY by this tab (via `CreatorLedger`), so it moves here:

```tsx
"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import { CreatorGraph } from "../CreatorGraph";
import {
  BORDER, ACCENT, MODULE_A, MODULE_B, MODULE_D, GRAVEYARD_ACCENT, VIBE_ACCENT, INK, INK_DIM, INK_GHOST,
  DashboardPanel, SectionTitle, CreatorLedger,
} from "../dashboardPrimitives";

export function NetworkTab({ profile }: { profile: GhostProfile }) {
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
        <DashboardPanel label="· Hypothesis Re-Tests" accent={MODULE_D === MODULE_D ? "#9c6b2e" : undefined}>
          <SectionTitle accent="#9c6b2e">Creators TikTok Kept Trying On You</SectionTitle>
          <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 16 }}>
            These creators were served to you in the 3–15 second window multiple times. You didn't bite — but the algorithm kept re-queuing them, testing whether you'd eventually engage.
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {(profile.sandbox_retests ?? []).slice(0, 6).map((r, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 8, borderBottom: `1px solid ${BORDER}` }}>
                <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12, color: INK }}>{r.handle}</span>
                <span style={{ fontSize: 11, color: "#9c6b2e", fontFamily: "var(--font-mono, monospace)" }}>served {r.times_served}×</span>
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
  );
}
```

**IMPORTANT:** the "Hypothesis Re-Tests" panel's `accent` in the original file used `MODULE_C` (`#9c6b2e`), not `MODULE_D`. The line above has a placeholder ternary `MODULE_D === MODULE_D ? "#9c6b2e" : undefined` to force a conscious fix — replace it with `MODULE_C` directly (add `MODULE_C` to the import list from `dashboardPrimitives`), and replace the two literal `"#9c6b2e"` strings in that same block (`SectionTitle accent=` and the `served {r.times_served}×` span color) with `MODULE_C` as well, for consistency with how every other panel references the token rather than its literal value.

- [ ] **Step 2: Write the smoke test**

```tsx
// algorithmic-mirror/app/components/tabs/__tests__/NetworkTab.test.tsx
import React from "react";
import { render } from "@testing-library/react";
import { NetworkTab } from "../NetworkTab";
import type { GhostProfile } from "../../GhostProfileHUD";

jest.mock("../../CreatorGraph", () => ({ CreatorGraph: () => <div data-testid="creator-graph" /> }));

const profile = {
  creator_entities: { graveyard: [], vibe_cluster: [] },
  behavioral_nodes: { social_graph_followed_pct: 0, social_graph_algorithmic_pct: 0 },
} as unknown as GhostProfile;

test("NetworkTab renders without throwing", () => {
  const { container } = render(<NetworkTab profile={profile} />);
  expect(container).not.toBeEmptyDOMElement();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/NetworkTab.test.tsx`
Expected: FAIL — `Cannot find module '../NetworkTab'`.

- [ ] **Step 4: Create the file, then modify `ForensicDashboard.tsx`**

Add the import: `import { NetworkTab } from "./tabs/NetworkTab";`

Delete the `const graveyard = ...` and `const vibe = ...` block from `ForensicDashboard`'s function body (lines 304–313 of the original — that logic now lives inside `NetworkTab`, this task's only consumer).

Find the block starting with `{activeTab === "network" && (` and ending at its matching `)}` (immediately before `{activeTab === "timeline" && (`) and replace it with:

```tsx
            {activeTab === "network" && <NetworkTab profile={profile} />}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/NetworkTab.test.tsx`
Expected: PASS.
Then `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2` → PASS (all — confirms removing `graveyard`/`vibe` from ForensicDashboard's body didn't break anything, since NetworkTab was their only consumer).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 6: Commit**

```bash
git add algorithmic-mirror/app/components/tabs/NetworkTab.tsx algorithmic-mirror/app/components/tabs/__tests__/NetworkTab.test.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx
git commit -m "refactor(ui): WP-3.1 extract NetworkTab from ForensicDashboard"
```

---

### Task 5: Extract `TimelineTab.tsx`

**Files:**
- Create: `algorithmic-mirror/app/components/tabs/TimelineTab.tsx`
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx`
- Test: `algorithmic-mirror/app/components/tabs/__tests__/TimelineTab.test.tsx`

**Interfaces:**
- Consumes: `NicheDriftChart`; `DashboardPanel`, `SectionTitle`, tokens from `dashboardPrimitives.tsx`.
- Produces: `export function TimelineTab({ profile }: { profile: GhostProfile })`.

- [ ] **Step 1: Create `TimelineTab.tsx`** with this exact content:

```tsx
"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import { NicheDriftChart } from "../NicheDriftChart";
import { BORDER, ACCENT, MODULE_A, MODULE_B, VIBE_ACCENT, INK, INK_DIM, INK_GHOST, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

export function TimelineTab({ profile }: { profile: GhostProfile }) {
  return (
    <div className="grid grid-cols-1 gap-8">
      {profile.niche_drift && (
        <div className="md:col-span-2">
          <DashboardPanel label="Niche Drift" accent={ACCENT}>
            <SectionTitle>How Your Feed Narrowed</SectionTitle>
            <NicheDriftChart result={profile.niche_drift} />
          </DashboardPanel>
        </div>
      )}

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
  );
}
```

- [ ] **Step 2: Write the smoke test**

```tsx
// algorithmic-mirror/app/components/tabs/__tests__/TimelineTab.test.tsx
import React from "react";
import { render } from "@testing-library/react";
import { TimelineTab } from "../TimelineTab";
import type { GhostProfile } from "../../GhostProfileHUD";

jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, LineChart: Pass, Line: Pass, XAxis: Pass, YAxis: Pass, CartesianGrid: Pass, Tooltip: Pass, Legend: Pass };
});

const profile = {
  stopwatch_metrics: {},
} as unknown as GhostProfile;

test("TimelineTab renders without throwing", () => {
  const { container } = render(<TimelineTab profile={profile} />);
  expect(container).not.toBeEmptyDOMElement();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/TimelineTab.test.tsx`
Expected: FAIL — `Cannot find module '../TimelineTab'`.

- [ ] **Step 4: Create the file, then modify `ForensicDashboard.tsx`**

Add the import: `import { TimelineTab } from "./tabs/TimelineTab";`

Find the block starting with `{activeTab === "timeline" && (` and ending at its matching `)}` (immediately before `{activeTab === "interests" && (`) and replace it with:

```tsx
            {activeTab === "timeline" && <TimelineTab profile={profile} />}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/TimelineTab.test.tsx`
Expected: PASS.
Then `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2` → PASS (all).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 6: Commit**

```bash
git add algorithmic-mirror/app/components/tabs/TimelineTab.tsx algorithmic-mirror/app/components/tabs/__tests__/TimelineTab.test.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx
git commit -m "refactor(ui): WP-3.1 extract TimelineTab from ForensicDashboard"
```

---

### Task 6: Extract `InterestsTab.tsx`

**Files:**
- Create: `algorithmic-mirror/app/components/tabs/InterestsTab.tsx`
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx`
- Test: `algorithmic-mirror/app/components/tabs/__tests__/InterestsTab.test.tsx`

**Interfaces:**
- Consumes: `TargetingCard`; `DashboardPanel`, `SectionTitle`, tokens from `dashboardPrimitives.tsx`.
- Produces: `export function InterestsTab({ profile }: { profile: GhostProfile })`.

- [ ] **Step 1: Create `InterestsTab.tsx`** with this exact content:

```tsx
"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import { TargetingCard } from "../TargetingCard";
import { ACCENT, MODULE_A, MODULE_B, MODULE_C, VIBE_ACCENT, INK_DIM, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

export function InterestsTab({ profile }: { profile: GhostProfile }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
      <DashboardPanel label="07 · Topic Mapping" accent={ACCENT}>
        <SectionTitle>Behavioral Interest Clusters</SectionTitle>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {profile.interest_clusters?.map((c, i) => (
            <div key={i} style={{ 
              padding: "6px 12px", 
              background: "rgba(255,255,255,0.05)",
              border: `1px solid rgba(26, 22, 16, 0.16)`,
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

      <div className="md:col-span-2">
        <DashboardPanel label="09 · Targeting Card" accent={ACCENT}>
          <SectionTitle>What Advertisers Can Target You By</SectionTitle>
          <TargetingCard result={profile.targeting_card} />
        </DashboardPanel>
      </div>

      <DashboardPanel label="10 · Transparency Gap" accent={MODULE_B}>
        <SectionTitle accent={MODULE_B}>Declared vs. Inferred</SectionTitle>
        <div className="flex items-center gap-12 mb-8">
          <div>
            <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase" }}>Declared</div>
            <div style={{ fontSize: 32, fontWeight: 700 }}>{profile.transparency_gap?.official_ad_interest_count}</div>
          </div>
          <div style={{ fontSize: 24, color: "rgba(26,22,16,0.4)" }}>&rarr;</div>
          <div>
            <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase" }}>Inferred</div>
            <div style={{ fontSize: 32, fontWeight: 700, color: MODULE_B }}>{profile.transparency_gap?.behavioral_interest_count}</div>
          </div>
        </div>
        <div style={{ fontSize: 11, color: INK_DIM, lineHeight: 1.6 }}>
          {profile.transparency_gap?.gap_interpretation}
        </div>
      </DashboardPanel>

      <DashboardPanel label="11 · Search Rhythm" accent={VIBE_ACCENT}>
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

      <DashboardPanel label="12 · Comment Analysis" accent={MODULE_A}>
        <SectionTitle accent={MODULE_A}>Recurring Phrases</SectionTitle>
        <div className="space-y-3">
          {profile.interest_phrases?.slice(0, 8).map((p, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
              <span style={{ color: "#1a1610" }}>"{p.phrase}"</span>
              <span style={{ color: "rgba(26,22,16,0.4)" }}>{p.count}x</span>
            </div>
          ))}
        </div>
      </DashboardPanel>
    </div>
  );
}
```

**Note:** `INK`/`INK_GHOST`/`BORDER` appear as inline literal color values (`"#1a1610"`, `"rgba(26,22,16,0.4)"`) in a few spots above rather than imported tokens — same value-identical substitution rationale as Task 2 (avoids importing tokens used only once or twice in this file). If you prefer, import `INK`, `INK_GHOST`, and `BORDER` from `dashboardPrimitives` and use them directly instead of the inline literals — either is fine as long as the rendered values are identical to the original file.

- [ ] **Step 2: Write the smoke test**

```tsx
// algorithmic-mirror/app/components/tabs/__tests__/InterestsTab.test.tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { InterestsTab } from "../InterestsTab";
import type { GhostProfile } from "../../GhostProfileHUD";

const profile = {
  interest_clusters: [],
  targeting_card: { moduleId: "targeting_card", status: "error", error: "no data", claims: [],
    counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 }, taxonomy_version: "v" },
} as unknown as GhostProfile;

test("InterestsTab renders without throwing", () => {
  render(<InterestsTab profile={profile} />);
  expect(screen.getByText(/Behavioral Interest Clusters/i)).toBeInTheDocument();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/InterestsTab.test.tsx`
Expected: FAIL — `Cannot find module '../InterestsTab'`.

- [ ] **Step 4: Create the file, then modify `ForensicDashboard.tsx`**

Add the import: `import { InterestsTab } from "./tabs/InterestsTab";`

Find the block starting with `{activeTab === "interests" && (` and ending at its matching `)}` (immediately before `{activeTab === "privacy" && (`) and replace it with:

```tsx
            {activeTab === "interests" && <InterestsTab profile={profile} />}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/InterestsTab.test.tsx`
Expected: PASS.
Then `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2` → PASS (all — including `TargetingCardDashboard.test.tsx`, still synchronous).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 6: Commit**

```bash
git add algorithmic-mirror/app/components/tabs/InterestsTab.tsx algorithmic-mirror/app/components/tabs/__tests__/InterestsTab.test.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx
git commit -m "refactor(ui): WP-3.1 extract InterestsTab from ForensicDashboard"
```

---

### Task 7: Extract `PrivacyTab.tsx`

**Files:**
- Create: `algorithmic-mirror/app/components/tabs/PrivacyTab.tsx`
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx`
- Test: `algorithmic-mirror/app/components/tabs/__tests__/PrivacyTab.test.tsx`

**Interfaces:**
- Consumes: `DemographicPanel`; `DashboardPanel`, `SectionTitle`, tokens from `dashboardPrimitives.tsx`.
- Produces: `export function PrivacyTab({ profile }: { profile: GhostProfile })`.

- [ ] **Step 1: Create `PrivacyTab.tsx`** with this exact content:

```tsx
"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import { DemographicPanel } from "../DemographicPanel";
import { ACCENT, MODULE_D, GRAVEYARD_ACCENT, VIBE_ACCENT, INK_DIM, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

export function PrivacyTab({ profile }: { profile: GhostProfile }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
      <DashboardPanel label="09 · Digital Footprint" accent={ACCENT}>
        <SectionTitle>Geographic & Device Trace</SectionTitle>
        <div className="space-y-4">
          <div style={{ borderBottom: `1px solid rgba(26, 22, 16, 0.16)`, paddingBottom: 16 }}>
            <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase", marginBottom: 4 }}>Unique IPs</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{profile.digital_footprint?.unique_ips}</div>
          </div>
          <div style={{ borderBottom: `1px solid rgba(26, 22, 16, 0.16)`, paddingBottom: 16 }}>
            <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase", marginBottom: 4 }}>Known Devices</div>
            <div style={{ fontSize: 14 }}>{profile.digital_footprint?.unique_devices.join(" · ")}</div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase", marginBottom: 12 }}>Recent Logins</div>
            <div className="space-y-2">
              {profile.digital_footprint?.recent_logins.slice(0, 6).map((l, i) => (
                <div key={i} style={{ fontSize: 11, display: "flex", justifyContent: "space-between", gap: 12, color: INK_DIM }}>
                  <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {l.city ?? "Unknown"}
                    {l.ip && <span style={{ color: "rgba(26,22,16,0.4)" }}> · {l.ip}</span>}
                    {l.carrier && <span style={{ color: "rgba(26,22,16,0.4)" }}> · {l.carrier}</span>}
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
          <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase", marginBottom: 12 }}>
            {profile.ad_profile!.shop_order_count} orders on file · first-party purchase intent
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {profile.ad_profile!.shop_products.slice(0, 10).map((p, i) => (
              <div key={i} style={{ fontSize: 11, color: INK_DIM, display: "flex", gap: 8 }}>
                <span style={{ color: "rgba(26,22,16,0.4)" }}>{String(i + 1).padStart(2, "0")}</span>
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
          <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", textTransform: "uppercase", marginBottom: 12 }}>
            {profile.ad_profile!.product_browsing_count.toLocaleString()} products browsed · intent without purchase
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {profile.ad_profile!.browsed_products.slice(0, 10).map((p, i) => (
              <div key={i} style={{ fontSize: 11, color: INK_DIM, display: "flex", gap: 8 }}>
                <span style={{ color: "rgba(26,22,16,0.4)" }}>{String(i + 1).padStart(2, "0")}</span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {p.length > 60 ? p.slice(0, 60).trimEnd() + "…" : p}
                </span>
              </div>
            ))}
          </div>
        </DashboardPanel>
      )}

      {profile.demographics && (
        <div className="md:col-span-2">
          <DashboardPanel label="13 · Demographic Reconstruction" accent={ACCENT}>
            <SectionTitle>What TikTok Infers About You</SectionTitle>
            <DemographicPanel result={profile.demographics} />
          </DashboardPanel>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write the smoke test**

```tsx
// algorithmic-mirror/app/components/tabs/__tests__/PrivacyTab.test.tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { PrivacyTab } from "../PrivacyTab";
import type { GhostProfile } from "../../GhostProfileHUD";

const profile = {
  digital_footprint: { unique_ips: 0, unique_devices: [], recent_logins: [] },
} as unknown as GhostProfile;

test("PrivacyTab renders without throwing", () => {
  render(<PrivacyTab profile={profile} />);
  expect(screen.getByText(/Geographic & Device Trace/i)).toBeInTheDocument();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/PrivacyTab.test.tsx`
Expected: FAIL — `Cannot find module '../PrivacyTab'`.

- [ ] **Step 4: Create the file, then modify `ForensicDashboard.tsx`**

Add the import: `import { PrivacyTab } from "./tabs/PrivacyTab";`

Find the block starting with `{activeTab === "privacy" && (` and ending at its matching `)}` (immediately before `{activeTab === "ai" && (`) and replace it with:

```tsx
            {activeTab === "privacy" && <PrivacyTab profile={profile} />}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/PrivacyTab.test.tsx`
Expected: PASS.
Then `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2` → PASS (all — including `DemographicPanelDashboard.test.tsx`, still synchronous).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 6: Commit**

```bash
git add algorithmic-mirror/app/components/tabs/PrivacyTab.tsx algorithmic-mirror/app/components/tabs/__tests__/PrivacyTab.test.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx
git commit -m "refactor(ui): WP-3.1 extract PrivacyTab from ForensicDashboard"
```

---

### Task 8: Extract `AiTab.tsx`

**Files:**
- Create: `algorithmic-mirror/app/components/tabs/AiTab.tsx`
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx`
- Test: `algorithmic-mirror/app/components/tabs/__tests__/AiTab.test.tsx`

**Interfaces:**
- Consumes: `LLMAnalysisView`.
- Produces: `export function AiTab({ sourceFile, apiUrl, onBack }: { sourceFile: File; apiUrl: string; onBack: () => void })`.

- [ ] **Step 1: Create `AiTab.tsx`** with this exact content:

```tsx
"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import { LLMAnalysisView } from "../LLMAnalysisView";

export function AiTab({ sourceFile, apiUrl, onBack }: { sourceFile: File; apiUrl: string; onBack: () => void }) {
  return (
    <div>
      <LLMAnalysisView
        file={sourceFile}
        apiUrl={apiUrl}
        onBack={onBack}
      />
    </div>
  );
}
```

- [ ] **Step 2: Write the smoke test**

```tsx
// algorithmic-mirror/app/components/tabs/__tests__/AiTab.test.tsx
import React from "react";
import { render } from "@testing-library/react";
import { AiTab } from "../AiTab";

test("AiTab renders without throwing", () => {
  const { container } = render(
    <AiTab sourceFile={new File(["{}"], "x.json")} apiUrl="http://localhost:8005" onBack={jest.fn()} />
  );
  expect(container).not.toBeEmptyDOMElement();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/AiTab.test.tsx`
Expected: FAIL — `Cannot find module '../AiTab'`.

- [ ] **Step 4: Create the file, then modify `ForensicDashboard.tsx`**

Add the import: `import { AiTab } from "./tabs/AiTab";`

Find the block starting with `{activeTab === "ai" && (` and ending at its matching `)}` (immediately before `{activeTab === "claims" && (`) and replace it with:

```tsx
            {activeTab === "ai" && (
              <AiTab
                sourceFile={sourceFile!}
                apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
                onBack={() => setActiveTab("overview")}
              />
            )}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/AiTab.test.tsx`
Expected: PASS.
Then `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2` → PASS (all).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 6: Commit**

```bash
git add algorithmic-mirror/app/components/tabs/AiTab.tsx algorithmic-mirror/app/components/tabs/__tests__/AiTab.test.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx
git commit -m "refactor(ui): WP-3.1 extract AiTab from ForensicDashboard"
```

---

### Task 9: Extract `ClaimsTab.tsx`

**Files:**
- Create: `algorithmic-mirror/app/components/tabs/ClaimsTab.tsx`
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx`
- Test: `algorithmic-mirror/app/components/tabs/__tests__/ClaimsTab.test.tsx`

**Interfaces:**
- Consumes: `ClaimsPanel`; `DashboardPanel`, `SectionTitle`, `ACCENT` from `dashboardPrimitives.tsx`.
- Produces: `export function ClaimsTab({ profile }: { profile: GhostProfile })`.

- [ ] **Step 1: Create `ClaimsTab.tsx`** with this exact content:

```tsx
"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import { ClaimsPanel } from "../ClaimsPanel";
import { ACCENT, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

export function ClaimsTab({ profile }: { profile: GhostProfile }) {
  return (
    <div>
      <DashboardPanel label="Evidence Log" accent={ACCENT}>
        <SectionTitle>Every Claim, By Tier</SectionTitle>
        <ClaimsPanel claims={profile.claims} />
      </DashboardPanel>
    </div>
  );
}
```

- [ ] **Step 2: Write the smoke test**

```tsx
// algorithmic-mirror/app/components/tabs/__tests__/ClaimsTab.test.tsx
import React from "react";
import { render, screen } from "@testing-library/react";
import { ClaimsTab } from "../ClaimsTab";
import type { GhostProfile } from "../../GhostProfileHUD";

const profile = { claims: [] } as unknown as GhostProfile;

test("ClaimsTab renders without throwing", () => {
  render(<ClaimsTab profile={profile} />);
  expect(screen.getByText(/Every Claim, By Tier/i)).toBeInTheDocument();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/ClaimsTab.test.tsx`
Expected: FAIL — `Cannot find module '../ClaimsTab'`.

- [ ] **Step 4: Create the file, then modify `ForensicDashboard.tsx`**

Add the import: `import { ClaimsTab } from "./tabs/ClaimsTab";`

Find the block starting with `{activeTab === "claims" && (` and ending at its matching `)}` (immediately before `</motion.div>`) and replace it with:

```tsx
            {activeTab === "claims" && <ClaimsTab profile={profile} />}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest app/components/tabs/__tests__/ClaimsTab.test.tsx`
Expected: PASS.
Then `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2` → PASS (all — including `ClaimsDashboard.test.tsx`, still synchronous). At this point `ForensicDashboard.tsx` should have NO remaining inline tab JSX — every `{activeTab === "xxx" && (...)}` block is now a single-line component reference. Confirm this visually before moving to Task 10.
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 6: Commit**

```bash
git add algorithmic-mirror/app/components/tabs/ClaimsTab.tsx algorithmic-mirror/app/components/tabs/__tests__/ClaimsTab.test.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx
git commit -m "refactor(ui): WP-3.1 extract ClaimsTab from ForensicDashboard"
```

---

### Task 10: Extract `DossierShell.tsx` — the persistent chrome

**Files:**
- Create: `algorithmic-mirror/app/components/DossierShell.tsx`
- Modify: `algorithmic-mirror/app/components/ForensicDashboard.tsx`
- Test: no new test file — verified via the full existing suite (this task is pure relocation of the sidebar/header/tab-switch chrome; all 8 tabs it renders were already proven correct in Tasks 2–9)

**Interfaces:**
- Consumes: all 8 tab components (Tasks 2–9, still statically imported at this point); `SidebarItem`, `DashboardPanel`-adjacent tokens from `dashboardPrimitives.tsx`; `LocalModeBanner`, `DownloadExportButton`.
- Produces: `export function DossierShell({ profile, onReset, sourceFile }: Props)` — identical `Props` shape to the current `ForensicDashboard`.

- [ ] **Step 1: Create `DossierShell.tsx`** with this exact content — this is everything currently in `ForensicDashboard.tsx` EXCEPT the import list handled in Task 1 (which stays in `ForensicDashboard.tsx` for now and moves here in this step) and the tab-content bodies (already extracted):

```tsx
"use client";
/**
 * WP-3.1 — the persistent Dossier workspace: sidebar navigation, header, reset
 * control, and the tab-switch animation wrapper. Owns `activeTab` state. Tab
 * bodies are still statically imported here; Task 11 converts them to
 * next/dynamic() for real code-splitting.
 */
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity, Network, Search, LayoutDashboard, ArrowLeft, Lock, Zap, TrendingUp, ScrollText,
} from "lucide-react";
import type { GhostProfile } from "./GhostProfileHUD";
import { DownloadExportButton } from "./DownloadExportButton";
import { LocalModeBanner } from "./LocalModeBanner";
import { BG, SIDEBAR, BORDER, ACCENT, INK, INK_DIM, SidebarItem } from "./dashboardPrimitives";
import { OverviewTab } from "./tabs/OverviewTab";
import { BehaviorTab } from "./tabs/BehaviorTab";
import { NetworkTab } from "./tabs/NetworkTab";
import { TimelineTab } from "./tabs/TimelineTab";
import { InterestsTab } from "./tabs/InterestsTab";
import { PrivacyTab } from "./tabs/PrivacyTab";
import { AiTab } from "./tabs/AiTab";
import { ClaimsTab } from "./tabs/ClaimsTab";

type Tab = "overview" | "behavior" | "timeline" | "network" | "interests" | "privacy" | "ai" | "claims";

interface Props {
  profile: GhostProfile;
  onReset: () => void;
  sourceFile?: File;
}

export function DossierShell({ profile, onReset, sourceFile }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");

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
          <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 9, letterSpacing: "0.32em", color: "rgba(26,22,16,0.4)", textTransform: "uppercase", marginBottom: 10 }}>
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
          <SidebarItem
            icon={ScrollText}
            label="Evidence Log"
            active={activeTab === "claims"}
            onClick={() => setActiveTab("claims")}
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
            {activeTab === "overview" && <OverviewTab profile={profile} />}
            {activeTab === "behavior" && <BehaviorTab profile={profile} />}
            {activeTab === "network" && <NetworkTab profile={profile} />}
            {activeTab === "timeline" && <TimelineTab profile={profile} />}
            {activeTab === "interests" && <InterestsTab profile={profile} />}
            {activeTab === "privacy" && <PrivacyTab profile={profile} />}
            {activeTab === "ai" && (
              <AiTab
                sourceFile={sourceFile!}
                apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
                onBack={() => setActiveTab("overview")}
              />
            )}
            {activeTab === "claims" && <ClaimsTab profile={profile} />}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
```

(Note: `INK_GHOST` from the original sidebar header text (`"The Glass House · Dossier"` label color) is inlined here as `"rgba(26,22,16,0.4)"`, same value-identical rationale as prior tasks — or import `INK_GHOST` from `dashboardPrimitives` and use it directly; either is fine.)

- [ ] **Step 2: Replace `ForensicDashboard.tsx` with its final thin-orchestrator form** — the ENTIRE file becomes:

```tsx
"use client";
/**
 * WP-3.1 — thin orchestrator. All rendering logic lives in DossierShell.tsx
 * and the extracted tab components; this file exists to keep the public
 * `ForensicDashboard` import path stable for existing callers (page.tsx).
 */
import type { GhostProfile } from "./GhostProfileHUD";
import { DossierShell } from "./DossierShell";

interface Props {
  profile: GhostProfile;
  onReset: () => void;
  sourceFile?: File;
}

export function ForensicDashboard(props: Props) {
  return <DossierShell {...props} />;
}
```

- [ ] **Step 3: Run the full existing suite to confirm no regression**

Run: `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2`
Expected: PASS — same counts as before (all 5 dashboard tests + all 8 tab smoke tests, still synchronous throughout — `DossierShell` still uses static imports at this point).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 4: Commit**

```bash
git add algorithmic-mirror/app/components/DossierShell.tsx algorithmic-mirror/app/components/ForensicDashboard.tsx
git commit -m "refactor(ui): WP-3.1 extract DossierShell — ForensicDashboard becomes a thin orchestrator"
```

---

### Task 11: Convert to `next/dynamic()` — real code-splitting + test migration

**Files:**
- Modify: `algorithmic-mirror/app/components/DossierShell.tsx`
- Modify: `algorithmic-mirror/__tests__/TargetingCardDashboard.test.tsx`
- Modify: `algorithmic-mirror/__tests__/DemographicPanelDashboard.test.tsx`
- Modify: `algorithmic-mirror/__tests__/PersonaRadarDashboard.test.tsx`
- Modify: `algorithmic-mirror/__tests__/NicheDriftDashboard.test.tsx`
- Modify: `algorithmic-mirror/__tests__/ClaimsDashboard.test.tsx`
- Test: `algorithmic-mirror/__tests__/DossierShell.test.tsx` (new)

**Interfaces:**
- Consumes: the 8 tab components (Tasks 2–9), `next/dynamic` (Next.js built-in).
- Produces: no new exports — `DossierShell`'s public signature is unchanged; only its internal tab-loading mechanism changes.

- [ ] **Step 1: Modify `DossierShell.tsx`'s imports** — this is the ONLY change to this file. Find:

```tsx
import { OverviewTab } from "./tabs/OverviewTab";
import { BehaviorTab } from "./tabs/BehaviorTab";
import { NetworkTab } from "./tabs/NetworkTab";
import { TimelineTab } from "./tabs/TimelineTab";
import { InterestsTab } from "./tabs/InterestsTab";
import { PrivacyTab } from "./tabs/PrivacyTab";
import { AiTab } from "./tabs/AiTab";
import { ClaimsTab } from "./tabs/ClaimsTab";
```

Replace with:

```tsx
import dynamic from "next/dynamic";

const dynamicOpts = { loading: () => <div style={{ padding: 48, color: INK_DIM, fontSize: 12 }}>Loading…</div> };
const OverviewTab = dynamic(() => import("./tabs/OverviewTab").then(m => m.OverviewTab), dynamicOpts);
const BehaviorTab = dynamic(() => import("./tabs/BehaviorTab").then(m => m.BehaviorTab), dynamicOpts);
const NetworkTab = dynamic(() => import("./tabs/NetworkTab").then(m => m.NetworkTab), dynamicOpts);
const TimelineTab = dynamic(() => import("./tabs/TimelineTab").then(m => m.TimelineTab), dynamicOpts);
const InterestsTab = dynamic(() => import("./tabs/InterestsTab").then(m => m.InterestsTab), dynamicOpts);
const PrivacyTab = dynamic(() => import("./tabs/PrivacyTab").then(m => m.PrivacyTab), dynamicOpts);
const AiTab = dynamic(() => import("./tabs/AiTab").then(m => m.AiTab), dynamicOpts);
const ClaimsTab = dynamic(() => import("./tabs/ClaimsTab").then(m => m.ClaimsTab), dynamicOpts);
```

`dynamicOpts` references `INK_DIM`, which is already imported from `dashboardPrimitives` earlier in this file — no new import needed for it. Everything else in `DossierShell.tsx` (the JSX call sites `{activeTab === "overview" && <OverviewTab profile={profile} />}` etc.) stays **completely unchanged** — `dynamic()` returns a component with the same call signature as the original.

- [ ] **Step 2: Migrate the 5 existing dashboard tests to async queries**

In `algorithmic-mirror/__tests__/TargetingCardDashboard.test.tsx`, find:

```tsx
test("Interests tab renders the Targeting Card panel from the payload", () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Interests & Keywords/i));
  expect(screen.getByText(/Targeting Card/i)).toBeInTheDocument();
  expect(screen.getByText(/bring your own key/i)).toBeInTheDocument();
});
```

Replace with:

```tsx
test("Interests tab renders the Targeting Card panel from the payload", async () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Interests & Keywords/i));
  expect(await screen.findByText(/Targeting Card/i)).toBeInTheDocument();
  expect(await screen.findByText(/bring your own key/i)).toBeInTheDocument();
});
```

In `algorithmic-mirror/__tests__/DemographicPanelDashboard.test.tsx`, find:

```tsx
test("Privacy tab renders the Demographic panel from the payload", () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Privacy & Footprint/i));
  expect(screen.getByText(/What TikTok Infers About You/i)).toBeInTheDocument();
  expect(screen.getByText(/PIPEDA #2025-003/)).toBeInTheDocument();
});
```

Replace with:

```tsx
test("Privacy tab renders the Demographic panel from the payload", async () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Privacy & Footprint/i));
  expect(await screen.findByText(/What TikTok Infers About You/i)).toBeInTheDocument();
  expect(await screen.findByText(/PIPEDA #2025-003/)).toBeInTheDocument();
});
```

In `algorithmic-mirror/__tests__/PersonaRadarDashboard.test.tsx`, find:

```tsx
test("Overview tab renders the Persona radar from the payload", () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  expect(screen.getByText("Nocturnal Seeker")).toBeInTheDocument();
});
```

Replace with:

```tsx
test("Overview tab renders the Persona radar from the payload", async () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  expect(await screen.findByText("Nocturnal Seeker")).toBeInTheDocument();
});
```

In `algorithmic-mirror/__tests__/NicheDriftDashboard.test.tsx`, find:

```tsx
test("Timeline tab renders the niche-drift chart from the payload", () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Timeline|Evolution/i));
  expect(screen.getByText(/narrowed from 40 to 12/i)).toBeInTheDocument();
});
```

Replace with:

```tsx
test("Timeline tab renders the niche-drift chart from the payload", async () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Timeline|Evolution/i));
  expect(await screen.findByText(/narrowed from 40 to 12/i)).toBeInTheDocument();
});
```

In `algorithmic-mirror/__tests__/ClaimsDashboard.test.tsx`, find:

```tsx
test("Evidence Log tab renders the claims panel from the payload", () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Evidence Log/i));
  expect(screen.getByText("120")).toBeInTheDocument();
});
```

Replace with:

```tsx
test("Evidence Log tab renders the claims panel from the payload", async () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Evidence Log/i));
  expect(await screen.findByText("120")).toBeInTheDocument();
});
```

- [ ] **Step 3: Write the new `DossierShell.test.tsx`**

```tsx
// algorithmic-mirror/__tests__/DossierShell.test.tsx
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ForensicDashboard } from "../app/components/ForensicDashboard";
import type { GhostProfile } from "../app/components/GhostProfileHUD";

jest.mock("../app/components/CreatorGraph", () => ({ CreatorGraph: () => <div data-testid="creator-graph" /> }));
jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, LineChart: Pass, Line: Pass, XAxis: Pass, YAxis: Pass, CartesianGrid: Pass, Tooltip: Pass, Legend: Pass,
    BarChart: Pass, Bar: Pass, Cell: Pass, PieChart: Pass, Pie: Pass, RadarChart: Pass, Radar: Pass, PolarGrid: Pass, PolarAngleAxis: Pass, PolarRadiusAxis: Pass, Area: Pass, AreaChart: Pass };
});
jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const profile = {
  primary_archetype: { name: "The Balanced Viewer" },
  stopwatch_metrics: { total_conscious_videos: 0, graveyard_skips: 0, sandbox_views: 0, deep_lingers: 0, deep_dives: 0 },
  behavioral_nodes: { linger_rate_percentage: 0, night_shift_ratio: 0, peak_hour: "12PM", inferred_sleep_window: "Unknown" },
} as unknown as GhostProfile;

describe("DossierShell (via ForensicDashboard)", () => {
  test("all 8 tab labels render in the sidebar", () => {
    render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
    for (const label of ["Overview", "Behavioral Signature", "Timeline", "Network & Influence", "Interests & Keywords", "Privacy & Footprint", "AI Forensic Analyst", "Evidence Log"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  test("clicking a tab switches activeTab and (async) renders its lazy-loaded content", async () => {
    render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
    fireEvent.click(screen.getByText("Behavioral Signature"));
    expect(await screen.findByText(/True Stopwatch Funnel/i)).toBeInTheDocument();
  });

  test("reset button fires onReset", () => {
    const onReset = jest.fn();
    render(<ForensicDashboard profile={profile} onReset={onReset} sourceFile={new File(["{}"], "x.json")} />);
    fireEvent.click(screen.getByText(/New Analysis/i));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithmic-mirror && TZ=UTC npx jest __tests__/DossierShell.test.tsx __tests__/TargetingCardDashboard.test.tsx __tests__/DemographicPanelDashboard.test.tsx __tests__/PersonaRadarDashboard.test.tsx __tests__/NicheDriftDashboard.test.tsx __tests__/ClaimsDashboard.test.tsx`
Expected: PASS (all).
Then the whole suite: `cd algorithmic-mirror && TZ=UTC npx jest --maxWorkers=2` → PASS (all — every tab smoke test from Tasks 2–9 must still pass too, since they render the tab components directly, bypassing `DossierShell`'s dynamic wrapper entirely).
Then `cd algorithmic-mirror && npx tsc --noEmit` → ZERO errors.

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/DossierShell.tsx algorithmic-mirror/__tests__/TargetingCardDashboard.test.tsx algorithmic-mirror/__tests__/DemographicPanelDashboard.test.tsx algorithmic-mirror/__tests__/PersonaRadarDashboard.test.tsx algorithmic-mirror/__tests__/NicheDriftDashboard.test.tsx algorithmic-mirror/__tests__/ClaimsDashboard.test.tsx algorithmic-mirror/__tests__/DossierShell.test.tsx
git commit -m "feat(ui): WP-3.1 convert Dossier tabs to next/dynamic() — real code-splitting"
```

---

## Self-Review

**Spec coverage:**
- `TheGlassHouse.tsx` untouched → no task modifies it. ✓
- "Panel grid" interpreted as existing card-grid layout within a tab, not changed → no task alters that layout, only relocates it. ✓
- Real `next/dynamic()` code-splitting → Task 11. ✓
- 5 existing dashboard tests migrated to `findByText`, identical coverage → Task 11 Step 2 (exact before/after for each). ✓
- "No per-panel refetch" preserved → every tab component remains a pure function of the `profile` prop; no task introduces a fetch. ✓
- `dashboardPrimitives.tsx` (5 helpers + 13 tokens) → Task 1. ✓
- 8 tab components → Tasks 2–9. ✓
- `DossierShell.tsx` → Task 10. ✓
- `ForensicDashboard.tsx` thin orchestrator → Task 10 Step 2. ✓
- Loading fallback for failed/slow chunks → Task 11 `dynamicOpts.loading`. ✓
- New tests: `DossierShell.test.tsx` (8 labels, async tab switch, reset) + one smoke test per tab → Tasks 2–9 + Task 11. ✓

**Placeholder scan:** none of the "TBD/TODO" patterns present. The `MODULE_B_LOCAL` and `MODULE_D === MODULE_D ? ... : undefined` constructs in Tasks 3 and 4 are deliberate, called-out forcing-functions (with explicit instructions to replace them), not unresolved placeholders — each is accompanied by the exact fix and the reasoning, matching the plan's own self-review discipline used in prior WPs (e.g. WP-2.4's `MAX_DIST` catch).

**Type consistency:** every tab component's prop shape (`{ profile: GhostProfile }` except `AiTab`'s `{ sourceFile, apiUrl, onBack }`) is used identically at its Task's ForensicDashboard call site AND at Task 10's DossierShell call site AND Task 11 doesn't change any call site at all (only the import mechanism). `dashboardPrimitives.tsx`'s exports (Task 1) are consumed with matching names across all 8 tab tasks and Task 10 — cross-checked each import list against Task 1's export list.

**Note for the implementer:** Tasks 2–9 must be executed **in order** — each task's ForensicDashboard.tsx edit assumes the file is in the state left by the previous task (earlier tabs already extracted, later tabs still inline). Do not skip ahead or reorder. Task 10 assumes ALL of Tasks 2–9 are complete (every tab already extracted) — verify this explicitly before starting Task 10 (grep `ForensicDashboard.tsx` for any remaining `{activeTab === "..." && (` followed by more than one line — if found, an earlier task was skipped).
