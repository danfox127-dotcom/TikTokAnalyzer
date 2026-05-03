"use client";

/**
 * PhaseTransition — holographic bridge between Phase 1 (light/Bespin) and Phase 3 (dark/Ghost).
 *
 * Rendered as a full-screen overlay that plays once then unmounts.
 * The sequence: warm → scan line wipe → cold dark.
 */

import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";

const DATA_FRAGMENTS = [
  "PARSING BEHAVIORAL NODES",
  "RESOLVING VIDEO GRAPH",
  "MAPPING TEMPORAL SIGNATURES",
  "IDENTIFYING VIBE CLUSTER",
  "BUILDING GHOST PROFILE",
  "DOSSIER READY",
];

interface Props {
  onComplete: () => void;
}

export function PhaseTransition({ onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    // Advance text fragments
    const interval = setInterval(() => {
      setStep(s => {
        if (s >= DATA_FRAGMENTS.length - 1) {
          clearInterval(interval);
          return s;
        }
        return s + 1;
      });
    }, 260);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Exit after full sequence
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(onComplete, 600);
    }, DATA_FRAGMENTS.length * 260 + 400);
    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="phase-transition"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
          }}
        >
          {/* Flash Bulb Effect */}
          <motion.div
            initial={{ opacity: 1 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 1, ease: "easeOut" }}
            style={{
              position: "absolute",
              inset: 0,
              background: "white",
              zIndex: 10000,
              pointerEvents: "none",
            }}
          />
          <motion.div
            initial={{ opacity: 0.8 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 1.5, ease: "easeOut", delay: 0.1 }}
            style={{
              position: "absolute",
              inset: 0,
              background: "radial-gradient(circle, #f5d57a 0%, transparent 70%)",
              zIndex: 9999,
              pointerEvents: "none",
            }}
          />

          {/* Background — gradient wipe warm → cold */}
          <motion.div
            initial={{ background: "linear-gradient(160deg, #faf8f5 0%, #f2ede6 100%)" }}
            animate={{ background: "linear-gradient(160deg, #05080f 0%, #0a0f1a 100%)" }}
            transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1], delay: 0.3 }}
            style={{ position: "absolute", inset: 0 }}
          />

          {/* Holographic scan wipe — horizontal line sweeping down */}
          <motion.div
            initial={{ top: "-2px" }}
            animate={{ top: "102%" }}
            transition={{ duration: 1.1, ease: [0.4, 0, 0.2, 1], delay: 0.2 }}
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              height: 2,
              background: "linear-gradient(to right, transparent 0%, #4db8ff 20%, #4db8ff 80%, transparent 100%)",
              boxShadow: "0 0 24px rgba(77,184,255,0.8), 0 0 60px rgba(77,184,255,0.3)",
              zIndex: 2,
            }}
          />

          {/* Glassmorphic data panel */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            style={{
              position: "relative",
              zIndex: 3,
              padding: "40px 48px",
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(77,184,255,0.2)",
              backdropFilter: "blur(20px)",
              minWidth: 360,
              textAlign: "center",
            }}
          >
            {/* Corner chips */}
            {["tl","tr","bl","br"].map(corner => (
              <div key={corner} style={{
                position: "absolute",
                width: 8, height: 8,
                border: "1px solid rgba(77,184,255,0.5)",
                ...(corner === "tl" ? { top: -1, left: -1, borderRight: "none", borderBottom: "none" } : {}),
                ...(corner === "tr" ? { top: -1, right: -1, borderLeft: "none", borderBottom: "none" } : {}),
                ...(corner === "bl" ? { bottom: -1, left: -1, borderRight: "none", borderTop: "none" } : {}),
                ...(corner === "br" ? { bottom: -1, right: -1, borderLeft: "none", borderTop: "none" } : {}),
              }} />
            ))}

            <motion.div
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
              style={{
                width: 8, height: 8, borderRadius: "50%",
                background: "#4db8ff",
                boxShadow: "0 0 12px #4db8ff",
                margin: "0 auto 24px",
              }}
            />

            <div style={{
              fontFamily: "monospace",
              fontSize: 11,
              letterSpacing: "0.18em",
              color: "rgba(77,184,255,0.6)",
              marginBottom: 20,
              textTransform: "uppercase",
            }}>
              BEHAVIORAL ANALYSIS
            </div>

            <div style={{ minHeight: 28, marginBottom: 8 }}>
              <AnimatePresence mode="wait">
                <motion.div
                  key={step}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                  style={{
                    fontFamily: "monospace",
                    fontSize: 13,
                    letterSpacing: "0.12em",
                    color: step === DATA_FRAGMENTS.length - 1 ? "#4db8ff" : "#dde8f8",
                    textTransform: "uppercase",
                  }}
                >
                  {DATA_FRAGMENTS[step]}
                  {step < DATA_FRAGMENTS.length - 1 && (
                    <motion.span
                      animate={{ opacity: [1, 0, 1] }}
                      transition={{ repeat: Infinity, duration: 0.8 }}
                    >
                      _
                    </motion.span>
                  )}
                </motion.div>
              </AnimatePresence>
            </div>

            {/* Progress bar */}
            <div style={{ width: "100%", height: 1, background: "rgba(77,184,255,0.15)", marginTop: 20 }}>
              <motion.div
                initial={{ width: "0%" }}
                animate={{ width: `${((step + 1) / DATA_FRAGMENTS.length) * 100}%` }}
                transition={{ duration: 0.26, ease: "easeOut" }}
                style={{ height: "100%", background: "#4db8ff", boxShadow: "0 0 8px rgba(77,184,255,0.6)" }}
              />
            </div>
          </motion.div>

          {/* Scanlines overlay */}
          <div className="scanlines" style={{ opacity: 0.2, zIndex: 4 }} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
