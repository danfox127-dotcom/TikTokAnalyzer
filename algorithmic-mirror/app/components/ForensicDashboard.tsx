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
import { LLMAnalysisView } from "./LLMAnalysisView";
import { LocalModeBanner } from "./LocalModeBanner";
import { TargetingCard } from "./TargetingCard";
import { DemographicPanel } from "./DemographicPanel";
import { NicheDriftChart } from "./NicheDriftChart";
import { ClaimsPanel } from "./ClaimsPanel";
import { OverviewTab } from "./tabs/OverviewTab";
import { BehaviorTab } from "./tabs/BehaviorTab";
import { NetworkTab } from "./tabs/NetworkTab";
import {
  BG, SIDEBAR, BORDER, ACCENT, INK, INK_DIM, INK_GHOST,
  MODULE_A, MODULE_B, MODULE_C, MODULE_D, GRAVEYARD_ACCENT, VIBE_ACCENT,
  DashboardPanel, SectionTitle, SidebarItem, CreatorLedger,
} from "./dashboardPrimitives";

// We'll import existing visualizations or build new ones inside these tabs.
// For now, let's define the tab types.
type Tab = "overview" | "behavior" | "timeline" | "network" | "interests" | "privacy" | "ai" | "claims";

interface Props {
  profile: GhostProfile;
  onReset: () => void;
  sourceFile?: File;
}

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

export function ForensicDashboard({ profile, onReset, sourceFile }: Props) {
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

            {activeTab === "timeline" && (
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

                {profile.demographics && (
                  <div className="md:col-span-2">
                    <DashboardPanel label="13 · Demographic Reconstruction" accent={ACCENT}>
                      <SectionTitle>What TikTok Infers About You</SectionTitle>
                      <DemographicPanel result={profile.demographics} />
                    </DashboardPanel>
                  </div>
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
            {activeTab === "claims" && (
              <div>
                <DashboardPanel label="Evidence Log" accent={ACCENT}>
                  <SectionTitle>Every Claim, By Tier</SectionTitle>
                  <ClaimsPanel claims={profile.claims} />
                </DashboardPanel>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
