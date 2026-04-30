"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X, FileJson } from "lucide-react";

interface Props {
  open: boolean;
  title: string | null;
  claim: string | null;
  payload: unknown;
  onClose: () => void;
}

export function EvidencePanel({ open, title, claim, payload, onClose }: Props) {
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Scrim */}
          <motion.div
            key="scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(12, 10, 8, 0.55)",
              backdropFilter: "blur(2px)",
              zIndex: 90,
            }}
          />

          {/* Drawer */}
          <motion.aside
            key="panel"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            style={{
              position: "fixed",
              top: 0,
              right: 0,
              bottom: 0,
              width: "min(560px, 92vw)",
              background: "#f8f5ef",
              borderLeft: "1px solid rgba(30, 27, 24, 0.18)",
              zIndex: 100,
              display: "flex",
              flexDirection: "column",
              fontFamily: "var(--font-body, Georgia, 'Iowan Old Style', serif)",
              boxShadow: "-30px 0 60px rgba(0,0,0,0.25)",
            }}
          >
            {/* Top strip */}
            <div
              style={{
                padding: "20px 28px 16px",
                borderBottom: "1px solid rgba(30, 27, 24, 0.12)",
                display: "flex",
                alignItems: "flex-start",
                justifyContent: "space-between",
                gap: 16,
                background: "#f3ede2",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 10,
                    letterSpacing: "0.28em",
                    color: "#8a7c64",
                    textTransform: "uppercase",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 8,
                  }}
                >
                  <FileJson size={12} />
                  Notes · Source Evidence
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-display, 'Fraunces', 'Playfair Display', serif)",
                    fontSize: 22,
                    lineHeight: 1.15,
                    fontWeight: 600,
                    color: "#1a1610",
                    letterSpacing: "-0.01em",
                  }}
                >
                  {title ?? "Evidence"}
                </div>
                {claim && (
                  <div
                    style={{
                      marginTop: 10,
                      padding: "8px 12px",
                      borderLeft: "3px solid #8b6b3a",
                      background: "rgba(139, 107, 58, 0.08)",
                      fontStyle: "italic",
                      fontSize: 13,
                      lineHeight: 1.5,
                      color: "#3a3024",
                    }}
                  >
                    &ldquo;{claim}&rdquo;
                  </div>
                )}
              </div>
              <button
                onClick={onClose}
                aria-label="Close evidence panel"
                style={{
                  background: "transparent",
                  border: "1px solid rgba(30, 27, 24, 0.25)",
                  width: 36,
                  height: 36,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  color: "#1a1610",
                  flexShrink: 0,
                }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Body */}
            <div
              style={{
                flex: 1,
                overflow: "auto",
                padding: "24px 28px 40px",
              }}
            >
              <div
                style={{
                  fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                  fontSize: 10,
                  letterSpacing: "0.2em",
                  color: "#8a7c64",
                  textTransform: "uppercase",
                  marginBottom: 10,
                }}
              >
                // raw excerpt · parsed from your export
              </div>
              <pre
                style={{
                  fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                  fontSize: 11.5,
                  lineHeight: 1.7,
                  color: "#2a241b",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  background: "#fdfbf6",
                  border: "1px solid rgba(30, 27, 24, 0.12)",
                  padding: "18px 20px",
                  margin: 0,
                }}
              >
                {payload === null || payload === undefined
                  ? "// no evidence captured for this claim"
                  : JSON.stringify(payload, null, 2)}
              </pre>

              <div
                style={{
                  marginTop: 20,
                  fontFamily: "var(--font-body, Georgia, serif)",
                  fontSize: 12,
                  lineHeight: 1.7,
                  color: "#6a5e4a",
                  fontStyle: "italic",
                }}
              >
                This excerpt is taken directly from your TikTok data export. We have not
                re-synthesised or paraphrased it. The claim above rests entirely on the
                numbers you see here.
              </div>
            </div>

            {/* Foot */}
            <div
              style={{
                padding: "14px 28px",
                borderTop: "1px solid rgba(30, 27, 24, 0.12)",
                fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                fontSize: 10,
                letterSpacing: "0.22em",
                color: "#8a7c64",
                textTransform: "uppercase",
                display: "flex",
                justifyContent: "space-between",
                background: "#f3ede2",
              }}
            >
              <span>// evidence panel</span>
              <span>press esc to close</span>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
