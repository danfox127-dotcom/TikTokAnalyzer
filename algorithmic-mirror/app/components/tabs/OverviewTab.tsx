"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import { PersonaRadar } from "../PersonaRadar";
import { FourPillarsPanel } from "../FourPillarsPanel";
import { PANEL, BORDER, ACCENT, INK, INK_DIM, MODULE_A, MODULE_B, MODULE_C, MODULE_D, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

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
            <div style={{ fontSize: 10, color: "rgba(26,22,16,0.4)", marginTop: 6, lineHeight: 1.5 }}>Lowest-activity 4h window in your history</div>
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
