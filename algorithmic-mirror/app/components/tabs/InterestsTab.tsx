"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import { TargetingCard } from "../TargetingCard";
import { ACCENT, MODULE_A, MODULE_B, MODULE_C, VIBE_ACCENT, INK_DIM, INK_GHOST, INK, BORDER, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

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
              <span style={{ color: INK }}>"{p.phrase}"</span>
              <span style={{ color: INK_GHOST }}>{p.count}x</span>
            </div>
          ))}
        </div>
      </DashboardPanel>
    </div>
  );
}
