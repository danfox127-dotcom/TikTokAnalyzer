"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import {
  BORDER, MODULE_A, MODULE_B, MODULE_C, MODULE_D, GRAVEYARD_ACCENT, VIBE_ACCENT, INK, INK_DIM, INK_GHOST,
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
  );
}
