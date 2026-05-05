"use client";

/**
 * PhaseTransition — the cinematic pivot between Phase 1 (bright Surface) and
 * Phase 2 (warm editorial Glass House).
 *
 * Visual language: editorial warm paper → brief ink-dark reveal moment → fades
 * back to warm paper as the dossier renders beneath it.
 * Colors are the same oxblood/ink register as TheGlassHouse, not the old
 * surveillance neon-blue palette.
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

const ACCENT  = "#8b2323"; // oxblood — matches TheGlassHouse
const INK     = "#1a1610";
const PAPER   = "#f5efe4";

interface Props {
  onComplete: () => void;
}

export function PhaseTransition({ onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
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
          {/* Flash Bulb — white to transparent */}
          <motion.div
            initial={{ opacity: 1 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 0.9, ease: "easeOut" }}
            style={{
              position: "absolute",
              inset: 0,
              background: "white",
              zIndex: 10,
              pointerEvents: "none",
            }}
          />

          {/* Background — warm paper → deep ink (cinematic reveal) */}
          <motion.div
            initial={{ background: `linear-gradient(160deg, ${PAPER} 0%, #ede5d4 100%)` }}
            animate={{ background: `linear-gradient(160deg, ${INK} 0%, #2a221a 100%)` }}
            transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1], delay: 0.25 }}
            style={{ position: "absolute", inset: 0 }}
          />

          {/* Oxblood scan wipe — editorial, not surveillance */}
          <motion.div
            initial={{ top: "-2px" }}
            animate={{ top: "102%" }}
            transition={{ duration: 1.0, ease: [0.4, 0, 0.2, 1], delay: 0.15 }}
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              height: 1,
              background: `linear-gradient(to right, transparent 0%, ${ACCENT} 20%, ${ACCENT} 80%, transparent 100%)`,
              boxShadow: `0 0 16px rgba(139,35,35,0.6), 0 0 40px rgba(139,35,35,0.2)`,
              zIndex: 2,
            }}
          />

          {/* Data panel — ink-on-paper, editorial register */}
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            style={{
              position: "relative",
              zIndex: 3,
              padding: "40px 48px",
              background: "rgba(253,251,246,0.06)",
              border: `1px solid rgba(139,35,35,0.28)`,
              backdropFilter: "blur(20px)",
              minWidth: 360,
              textAlign: "center",
            }}
          >
            {/* Corner chips — oxblood */}
            {(["tl","tr","bl","br"] as const).map(corner => (
              <div key={corner} style={{
                position: "absolute",
                width: 8, height: 8,
                border: `1px solid rgba(139,35,35,0.55)`,
                ...(corner === "tl" ? { top: -1, left: -1, borderRight: "none", borderBottom: "none" } : {}),
                ...(corner === "tr" ? { top: -1, right: -1, borderLeft: "none", borderBottom: "none" } : {}),
                ...(corner === "bl" ? { bottom: -1, left: -1, borderRight: "none", borderTop: "none" } : {}),
                ...(corner === "br" ? { bottom: -1, right: -1, borderLeft: "none", borderTop: "none" } : {}),
              }} />
            ))}

            {/* Pulsing dot */}
            <motion.div
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
              style={{
                width: 7, height: 7, borderRadius: "50%",
                background: ACCENT,
                boxShadow: `0 0 10px ${ACCENT}`,
                margin: "0 auto 24px",
              }}
            />

            <div style={{
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 10,
              letterSpacing: "0.22em",
              color: `rgba(139,35,35,0.7)`,
              marginBottom: 20,
              textTransform: "uppercase",
            }}>
              BEHAVIORAL ANALYSIS
            </div>

            <div style={{ minHeight: 28, marginBottom: 8 }}>
              <AnimatePresence mode="wait">
                <motion.div
                  key={step}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.18 }}
                  style={{
                    fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 12,
                    letterSpacing: "0.14em",
                    color: step === DATA_FRAGMENTS.length - 1 ? ACCENT : "rgba(253,251,246,0.85)",
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

            {/* Progress bar — oxblood */}
            <div style={{ width: "100%", height: 1, background: "rgba(139,35,35,0.18)", marginTop: 20 }}>
              <motion.div
                initial={{ width: "0%" }}
                animate={{ width: `${((step + 1) / DATA_FRAGMENTS.length) * 100}%` }}
                transition={{ duration: 0.26, ease: "easeOut" }}
                style={{
                  height: "100%",
                  background: ACCENT,
                  boxShadow: `0 0 6px rgba(139,35,35,0.5)`,
                }}
              />
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
