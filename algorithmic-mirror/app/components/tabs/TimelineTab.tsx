"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
/** WP-3.3 — month-range scrubber narrows the panels below to a sub-window of history. */
import { useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import type { GhostProfile } from "../GhostProfileHUD";
import { NicheDriftChart } from "../NicheDriftChart";
import { MonthRangeScrubber } from "../MonthRangeScrubber";
import { unionMonths, isMonthInRange, filterEntriesByRange } from "../../utils/monthRange";
import { BORDER, ACCENT, MODULE_A, MODULE_B, VIBE_ACCENT, INK, INK_DIM, INK_GHOST, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

const SPRING = { type: "spring", stiffness: 320, damping: 18 } as const;

export function TimelineTab({ profile }: { profile: GhostProfile }) {
  const prefersReducedMotion = useReducedMotion();
  const transition = prefersReducedMotion ? { duration: 0 } : SPRING;

  const skipRates = profile.stopwatch_metrics.monthly_skip_rates ?? {};
  const creatorTrends = profile.monthly_creator_trends ?? {};
  const topicTrends = profile.monthly_topic_trends ?? {};
  const months = unionMonths(Object.keys(skipRates), Object.keys(creatorTrends), Object.keys(topicTrends));
  const showScrubber = months.length >= 2;

  const [range, setRange] = useState<[string, string]>(
    showScrubber ? [months[0], months[months.length - 1]] : ["", ""]
  );
  const activeRange: [string, string] | null = showScrubber ? range : null;

  const visibleSkipEntries = (activeRange ? filterEntriesByRange(Object.entries(skipRates), activeRange) : Object.entries(skipRates))
    .sort(([a], [b]) => a.localeCompare(b));
  const visibleAnomalies = activeRange
    ? (profile.skip_anomalies ?? []).filter((a) => isMonthInRange(a.month, activeRange))
    : (profile.skip_anomalies ?? []);
  const visibleCreatorEntries = (activeRange ? filterEntriesByRange(Object.entries(creatorTrends), activeRange) : Object.entries(creatorTrends))
    .sort(([a], [b]) => a.localeCompare(b));
  const visibleTopicEntries = (activeRange ? filterEntriesByRange(Object.entries(topicTrends), activeRange) : Object.entries(topicTrends))
    .sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="grid grid-cols-1 gap-8">
      {showScrubber && (
        <MonthRangeScrubber months={months} value={range} onChange={setRange} />
      )}

      {profile.niche_drift && (
        <div className="md:col-span-2">
          <DashboardPanel label="Niche Drift" accent={ACCENT}>
            <SectionTitle>How Your Feed Narrowed</SectionTitle>
            <NicheDriftChart result={profile.niche_drift} visibleRange={activeRange ?? undefined} />
          </DashboardPanel>
        </div>
      )}

      {/* Algorithm efficiency + anomaly flags */}
      {(() => {
        if (!skipRates || Object.keys(skipRates).length < 2) return null;
        const maxRate = Math.max(...visibleSkipEntries.map(([, v]) => v), 1);
        const anomalyMonths = new Set(visibleAnomalies.map(a => a.month));
        return (
          <DashboardPanel label="· Algorithm Efficiency Timeline" accent={ACCENT}>
            <SectionTitle>Skip Rate Over Time</SectionTitle>
            <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
              When the skip rate goes down, the algorithm has a better read on you — it's serving content you actually want. When it spikes, something changed: your tastes shifted, the algorithm lost its calibration, or the platform started pushing content you didn't ask for.
            </div>
            <div style={{ display: "flex", gap: 4, alignItems: "flex-end", height: 80, marginBottom: 8 }}>
              <AnimatePresence>
                {visibleSkipEntries.map(([month, rate]) => {
                  const isAnomaly = anomalyMonths.has(month);
                  const color = isAnomaly ? MODULE_B : VIBE_ACCENT;
                  return (
                    <motion.div
                      key={month}
                      layout={!prefersReducedMotion}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={transition}
                      style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}
                    >
                      {isAnomaly && <div style={{ width: 6, height: 6, borderRadius: "50%", background: MODULE_B, flexShrink: 0 }} title="Anomaly detected" />}
                      <div style={{ width: "100%", height: `${Math.max((rate / maxRate) * 72, 4)}px`, background: color, opacity: isAnomaly ? 1 : 0.65 }} title={`${month}: ${rate}% skip`} />
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: INK_GHOST, fontFamily: "var(--font-mono, monospace)", marginBottom: 16 }}>
              <span>{visibleSkipEntries[0]?.[0]}</span>
              <span>{visibleSkipEntries[visibleSkipEntries.length - 1]?.[0]}</span>
            </div>
            {visibleAnomalies.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <AnimatePresence>
                  {visibleAnomalies.map((a) => (
                    <motion.div
                      key={a.month}
                      layout={!prefersReducedMotion}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={transition}
                      style={{ padding: "12px 16px", border: `1px solid ${MODULE_B}40`, background: `${MODULE_B}08` }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                        <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: MODULE_B }}>{a.month} · anomaly</span>
                        <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: INK }}>{a.skip_rate}% <span style={{ color: INK_GHOST }}>vs {a.baseline_avg}% baseline</span></span>
                      </div>
                      <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6 }}>
                        Skip rate {a.direction === "spike" ? "spiked" : "dipped"} {Math.abs(a.delta)}pp from your baseline. This could mean the algorithm lost its read on you, your tastes shifted, the platform changed what it was pushing, or a data purge disrupted the recommendation model. The data alone can't say which.
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </DashboardPanel>
        );
      })()}

      {/* Monthly creator dominance */}
      {(() => {
        if (!creatorTrends || Object.keys(creatorTrends).length === 0) return null;
        return (
          <DashboardPanel label="· Creator Dominance by Month" accent={VIBE_ACCENT}>
            <SectionTitle accent={VIBE_ACCENT}>Who You Were Watching</SectionTitle>
            <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
              The creators you lingered on most, month by month. Shifts here show the algorithm changing what it thinks you want — or you actively seeking something new.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16 }}>
              <AnimatePresence>
                {visibleCreatorEntries.map(([month, creators]) => (
                  <motion.div
                    key={month}
                    layout={!prefersReducedMotion}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={transition}
                    style={{ border: `1px solid ${BORDER}`, padding: 16 }}
                  >
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
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </DashboardPanel>
        );
      })()}

      {/* Monthly topic trends */}
      {(() => {
        if (!topicTrends || Object.keys(topicTrends).length === 0) return null;
        return (
          <DashboardPanel label="· Topic Trends by Month" accent={MODULE_A}>
            <SectionTitle accent={MODULE_A}>What You Were Into</SectionTitle>
            <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, marginBottom: 20 }}>
              Top keywords from your searches and comments each month. A snapshot of what was on your mind.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16 }}>
              <AnimatePresence>
                {visibleTopicEntries.map(([month, topics]) => (
                  <motion.div
                    key={month}
                    layout={!prefersReducedMotion}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={transition}
                    style={{ border: `1px solid ${BORDER}`, padding: 16 }}
                  >
                    <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 10, letterSpacing: "0.2em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 12 }}>{month}</div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                      {topics.map((t, i) => (
                        <span key={i} style={{ fontSize: 10, padding: "3px 8px", background: i === 0 ? `${MODULE_A}20` : "transparent", border: `1px solid ${i === 0 ? MODULE_A : BORDER}`, color: i === 0 ? MODULE_A : INK_DIM }}>
                          {t.term}
                        </span>
                      ))}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </DashboardPanel>
        );
      })()}
    </div>
  );
}
