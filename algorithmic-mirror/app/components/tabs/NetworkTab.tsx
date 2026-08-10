"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import { CreatorGraph } from "../CreatorGraph";
import {
  BORDER, ACCENT, MODULE_A, MODULE_B, MODULE_C, MODULE_D, GRAVEYARD_ACCENT, VIBE_ACCENT, INK, INK_DIM, INK_GHOST,
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
  );
}
