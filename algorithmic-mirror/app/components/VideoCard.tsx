"use client";

import { motion, AnimatePresence, Variants } from "framer-motion";
import { Heart, MessageCircle, Share2, Music2, Eye, Clock, Tag, Users } from "lucide-react";
import { useDuality } from "../context/DualityContext";

const MOCK_PAYLOAD = {
  content_id: "vid_0x3F9A1C",
  dwell_time_ms: 18420,
  loop_count: 3,
  scroll_velocity: "0.12rem/ms",
  psychographic_tags: ["anxiety_loop", "fomo_trigger", "social_validation", "dopamine_cycle"],
  inferred_demographics: {
    age_bracket: "18–24",
    gender_confidence: "F:0.73",
    income_tier: "lower_mid",
    political_lean: "progressive_lean_0.61",
  },
  engagement_score: 0.847,
  retention_bucket: "HOOKED",
  next_injection: "vid_0x3F9A1D",
  ad_profile_delta: "+3 segments",
};

const glitchVariants: Variants = {
  idle: { x: 0, opacity: 1, filter: "none" },
  glitch: {
    x: [0, -4, 4, -2, 2, 0],
    opacity: [1, 0.8, 1, 0.9, 1],
    filter: [
      "none",
      "hue-rotate(90deg) saturate(3)",
      "none",
      "hue-rotate(-90deg)",
      "none",
    ],
    transition: { duration: 0.35, ease: "easeInOut" },
  },
};

const dataRevealVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.06, duration: 0.2 },
  }),
};

export function VideoCard() {
  const { isMachineView } = useDuality();

  return (
    <div className="relative w-full max-w-sm mx-auto" style={{ minHeight: 560 }}>
      <AnimatePresence mode="wait" initial={false}>
        {!isMachineView ? (
          <motion.div
            key="shell"
            initial={{ opacity: 1, scale: 1 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.3 }}
            variants={glitchVariants}
            className="absolute inset-0 flex flex-col overflow-hidden"
            style={{
              background: "var(--surface)",
              borderRadius: "var(--radius)",
              border: "1px solid var(--border)",
              boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
            }}
          >
            {/* Thumbnail */}
            <div className="relative h-72 bg-gradient-to-br from-rose-400 via-fuchsia-500 to-indigo-500 flex items-center justify-center overflow-hidden">
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-20 h-20 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
                  <div className="w-0 h-0 border-t-[14px] border-t-transparent border-l-[24px] border-l-white border-b-[14px] border-b-transparent ml-1" />
                </div>
              </div>
              {/* Simulated music ticker */}
              <div className="absolute bottom-3 left-3 right-3 flex items-center gap-2 text-white text-xs">
                <Music2 size={12} />
                <span className="truncate opacity-90">original sound · @creator_xyz</span>
              </div>
              {/* View count badge */}
              <div className="absolute top-3 right-3 bg-black/50 backdrop-blur-sm text-white text-xs px-2 py-1 rounded-full flex items-center gap-1">
                <Eye size={10} />
                2.4M
              </div>
            </div>

            {/* Author row */}
            <div className="px-4 pt-3 pb-1 flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-orange-400 to-pink-500 flex-shrink-0" />
              <div>
                <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  @creator_xyz
                </p>
                <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  Just your everyday content ✨
                </p>
              </div>
              <button
                className="ml-auto text-xs font-bold px-3 py-1 rounded-full text-white"
                style={{ background: "var(--accent)" }}
              >
                Follow
              </button>
            </div>

            {/* Caption */}
            <p className="px-4 py-2 text-sm" style={{ color: "var(--text-primary)" }}>
              This totally relatable moment when you can't stop scrolling 😂{" "}
              <span style={{ color: "var(--accent)" }}>#fyp #relatable #trending</span>
            </p>

            {/* Actions */}
            <div className="px-4 pb-4 flex items-center gap-5 mt-auto">
              {[
                { Icon: Heart, label: "48.2K" },
                { Icon: MessageCircle, label: "1.3K" },
                { Icon: Share2, label: "891" },
              ].map(({ Icon, label }) => (
                <button
                  key={label}
                  className="flex items-center gap-1.5 text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Icon size={18} />
                  {label}
                </button>
              ))}
            </div>
          </motion.div>
        ) : (
          /* ── MACHINE VIEW ── */
          <motion.div
            key="machine"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="absolute inset-0 flex flex-col overflow-hidden font-mono"
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
            }}
          >
            {/* Header bar */}
            <motion.div
              variants={glitchVariants}
              initial="idle"
              animate="glitch"
              className="px-3 py-2 flex items-center justify-between text-xs neon-border"
              style={{
                borderBottom: "1px solid var(--border)",
                color: "var(--text-secondary)",
              }}
            >
              <span className="neon-glow" style={{ color: "var(--accent)", fontSize: 10 }}>
                ▶ TARGETING_LOCK ACQUIRED
              </span>
              <span style={{ color: "var(--text-secondary)", fontSize: 10 }}>
                {new Date().toISOString()}
              </span>
            </motion.div>

            {/* Content ID */}
            <motion.div
              custom={0}
              variants={dataRevealVariants}
              initial="hidden"
              animate="visible"
              className="px-3 pt-3 pb-1"
            >
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                CONTENT_ID:{" "}
              </span>
              <span className="neon-glow text-sm font-bold" style={{ color: "var(--accent)" }}>
                {MOCK_PAYLOAD.content_id}
              </span>
            </motion.div>

            {/* Dwell / loops */}
            <motion.div
              custom={1}
              variants={dataRevealVariants}
              initial="hidden"
              animate="visible"
              className="px-3 py-1 grid grid-cols-2 gap-2"
            >
              <div
                className="p-2"
                style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)" }}
              >
                <div className="flex items-center gap-1 mb-1" style={{ color: "var(--text-secondary)" }}>
                  <Clock size={10} />
                  <span className="text-xs uppercase">Dwell</span>
                </div>
                <p className="text-lg font-bold neon-glow" style={{ color: "var(--accent)" }}>
                  {(MOCK_PAYLOAD.dwell_time_ms / 1000).toFixed(2)}s
                </p>
              </div>
              <div
                className="p-2"
                style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)" }}
              >
                <div className="flex items-center gap-1 mb-1" style={{ color: "var(--text-secondary)" }}>
                  <Eye size={10} />
                  <span className="text-xs uppercase">Loops</span>
                </div>
                <p className="text-lg font-bold neon-glow" style={{ color: "var(--text-secondary)" }}>
                  ×{MOCK_PAYLOAD.loop_count}
                </p>
              </div>
            </motion.div>

            {/* Psychographic tags */}
            <motion.div
              custom={2}
              variants={dataRevealVariants}
              initial="hidden"
              animate="visible"
              className="px-3 py-2"
            >
              <div className="flex items-center gap-1 mb-1.5" style={{ color: "var(--text-secondary)" }}>
                <Tag size={10} />
                <span className="text-xs uppercase">Psychographic Tags</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {MOCK_PAYLOAD.psychographic_tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs px-2 py-0.5 font-mono"
                    style={{
                      border: "1px solid var(--accent)",
                      color: "var(--accent)",
                      borderRadius: "var(--radius)",
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </motion.div>

            {/* Inferred Demographics */}
            <motion.div
              custom={3}
              variants={dataRevealVariants}
              initial="hidden"
              animate="visible"
              className="px-3 py-2"
            >
              <div className="flex items-center gap-1 mb-1.5" style={{ color: "var(--text-secondary)" }}>
                <Users size={10} />
                <span className="text-xs uppercase">Inferred Demographics</span>
              </div>
              <div
                className="p-2 text-xs space-y-1"
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  background: "rgba(57,255,20,0.03)",
                }}
              >
                {Object.entries(MOCK_PAYLOAD.inferred_demographics).map(([k, v], i) => (
                  <motion.div
                    key={k}
                    custom={3 + i * 0.5}
                    variants={dataRevealVariants}
                    initial="hidden"
                    animate="visible"
                    className="flex justify-between"
                  >
                    <span style={{ color: "var(--text-secondary)" }}>{k}:</span>
                    <span className="font-bold" style={{ color: "var(--accent)" }}>{String(v)}</span>
                  </motion.div>
                ))}
              </div>
            </motion.div>

            {/* Engagement score + retention */}
            <motion.div
              custom={5}
              variants={dataRevealVariants}
              initial="hidden"
              animate="visible"
              className="px-3 py-2 mt-auto"
            >
              <div className="flex items-center justify-between text-xs">
                <span style={{ color: "var(--text-secondary)" }}>ENGAGEMENT_SCORE:</span>
                <span className="neon-glow font-bold" style={{ color: "var(--accent)" }}>
                  {MOCK_PAYLOAD.engagement_score}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs mt-1">
                <span style={{ color: "var(--text-secondary)" }}>RETENTION_BUCKET:</span>
                <span
                  className="font-bold px-2 py-0.5"
                  style={{
                    background: "var(--accent)",
                    color: "#000",
                    borderRadius: "var(--radius)",
                    fontSize: 10,
                  }}
                >
                  {MOCK_PAYLOAD.retention_bucket}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs mt-1">
                <span style={{ color: "var(--text-secondary)" }}>NEXT_INJECTION:</span>
                <span style={{ color: "var(--text-secondary)" }}>{MOCK_PAYLOAD.next_injection}</span>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
