"use client";

import { motion } from "framer-motion";
import { Scan, ShieldOff, Eye } from "lucide-react";
import { useDuality } from "./context/DualityContext";
import { VideoCard } from "./components/VideoCard";

export default function Home() {
  const { isMachineView, toggle } = useDuality();

  return (
    <main
      className="min-h-screen flex flex-col items-center px-4 py-10"
      style={{ background: "var(--bg)" }}
    >
      {/* ── Top nav ── */}
      <header className="w-full max-w-2xl flex items-center justify-between mb-12">
        <div>
          <motion.p
            className="text-xs uppercase tracking-widest mb-0.5"
            style={{ color: "var(--text-secondary)", fontFamily: isMachineView ? "monospace" : "inherit" }}
          >
            {isMachineView ? "// SYSTEM: TARGETING_ACTIVE" : "Algorithmic Forensics"}
          </motion.p>
          <motion.h1
            className="text-xl font-bold tracking-tight"
            style={{
              color: "var(--text-primary)",
              fontFamily: isMachineView ? "monospace" : "inherit",
            }}
            animate={isMachineView ? { textShadow: "0 0 8px #39ff14, 0 0 20px rgba(57,255,20,0.35)" } : { textShadow: "none" }}
            transition={{ duration: 0.4 }}
          >
            {isMachineView ? "[ THE_MACHINE ]" : "The Algorithmic Mirror"}
          </motion.h1>
        </div>

        {/* X-RAY Toggle */}
        <motion.button
          onClick={toggle}
          whileTap={{ scale: 0.94 }}
          whileHover={{ scale: 1.04 }}
          className="flex items-center gap-2 px-5 py-2.5 font-bold text-sm uppercase tracking-widest transition-all"
          style={{
            background: isMachineView ? "var(--accent)" : "var(--text-primary)",
            color: isMachineView ? "#000" : "var(--bg)",
            borderRadius: "var(--radius)",
            border: isMachineView ? "2px solid var(--accent)" : "2px solid transparent",
            boxShadow: isMachineView ? "0 0 16px var(--accent-glow)" : "none",
            fontFamily: isMachineView ? "monospace" : "inherit",
          }}
        >
          {isMachineView ? (
            <>
              <ShieldOff size={15} />
              DISENGAGE
            </>
          ) : (
            <>
              <Scan size={15} />
              X-RAY
            </>
          )}
        </motion.button>
      </header>

      {/* ── Hero blurb ── */}
      <motion.div
        className="w-full max-w-2xl mb-10 text-center"
        animate={{ opacity: 1 }}
        initial={{ opacity: 0 }}
        transition={{ delay: 0.1 }}
      >
        <motion.p
          className="text-sm leading-relaxed"
          style={{
            color: "var(--text-secondary)",
            fontFamily: isMachineView ? "monospace" : "inherit",
          }}
        >
          {isMachineView
            ? "// DOSSIER MODE ACTIVE — WHAT THE ALGORITHM SEES WHEN YOU SCROLL"
            : "You see a friendly video. The algorithm sees a data harvest. Toggle X-RAY to see what's really happening."}
        </motion.p>
      </motion.div>

      {/* ── Mode badge ── */}
      <div className="w-full max-w-sm mb-4 flex items-center justify-between text-xs uppercase tracking-widest">
        <div className="flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
          <Eye size={12} />
          <span style={{ fontFamily: isMachineView ? "monospace" : "inherit" }}>
            {isMachineView ? "MACHINE VIEW — RAW PAYLOAD" : "SHELL VIEW — AS PRESENTED"}
          </span>
        </div>
        <motion.div
          className="w-2 h-2 rounded-full"
          style={{ background: "var(--accent)" }}
          animate={
            isMachineView
              ? { opacity: [1, 0.2, 1], scale: [1, 0.8, 1] }
              : { opacity: 1, scale: 1 }
          }
          transition={isMachineView ? { repeat: Infinity, duration: 1 } : {}}
        />
      </div>

      {/* ── Video Card ── */}
      <div className="w-full max-w-sm">
        <VideoCard />
      </div>

      {/* ── Footer note ── */}
      <motion.p
        className="mt-16 text-xs text-center max-w-sm"
        style={{
          color: "var(--text-secondary)",
          fontFamily: isMachineView ? "monospace" : "inherit",
          opacity: 0.6,
        }}
      >
        {isMachineView
          ? "// All data is simulated for educational purposes. Real payloads are never exposed."
          : "All data shown is simulated. For educational and awareness purposes only."}
      </motion.p>
    </main>
  );
}
