"use client";

import { useRef, useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileJson, AlertTriangle, Loader2 } from "lucide-react";
import { useDuality } from "../context/DualityContext";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Props {
  onFile: (file: File) => void;
  isLoading: boolean;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOADING_STEPS = [
  "PARSING BEHAVIORAL NODES...",
  "MAPPING PSYCHOGRAPHIC VECTORS...",
  "INFERRING TARGET DEMOGRAPHICS...",
  "CALCULATING VULNERABILITY INDEX...",
  "COMPILING GHOST PROFILE...",
];

// Spring presets — tuned for tactile, "juicy" feel
const SPRING_HOVER = { type: "spring", stiffness: 320, damping: 18 } as const;
const SPRING_TAP   = { type: "spring", stiffness: 500, damping: 22 } as const;
const SPRING_ICON  = { type: "spring", stiffness: 420, damping: 14 } as const;

// ---------------------------------------------------------------------------
// FileDropzone
// ---------------------------------------------------------------------------

export function FileDropzone({ onFile, isLoading, error }: Props) {
  const { isMachineView } = useDuality();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);

  // Cycle loading copy while parsing
  useEffect(() => {
    if (!isLoading) return;
    setLoadingStep(0);
    const id = setInterval(() => {
      setLoadingStep((s) => (s + 1) % LOADING_STEPS.length);
    }, 900);
    return () => clearInterval(id);
  }, [isLoading]);
  // ── Handlers ──────────────────────────────────────────────────────────

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file?.name.endsWith(".json")) onFile(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFile(file);
    e.target.value = "";
  };

  // ── Loading state ──────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="w-full max-w-sm mx-auto flex flex-col items-center justify-center gap-6 py-16"
        style={{ color: "var(--accent)" }}
      >
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
        >
          <Loader2 size={40} style={{ color: "var(--accent)" }} />
        </motion.div>

        <div className="text-center space-y-2">
          <AnimatePresence mode="wait">
            <motion.p
              key={loadingStep}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.28 }}
              className="text-sm tracking-widest uppercase"
              style={{
                fontFamily: "var(--font-mono)",
                color: "var(--accent)",
                textShadow: isMachineView ? "0 0 8px var(--accent)" : "none",
              }}
            >
              {LOADING_STEPS[loadingStep]}
            </motion.p>
          </AnimatePresence>
          <p
            className="text-xs opacity-50"
            style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}
          >
            DO NOT CLOSE THIS TAB
          </p>
        </div>

        {/* Scanning bar */}
        <div
          className="w-full h-px overflow-hidden"
          style={{ background: "var(--border)" }}
        >
          <motion.div
            className="h-full"
            style={{ background: "var(--accent)" }}
            animate={{ x: ["-100%", "200%"] }}
            transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
          />
        </div>
      </motion.div>
    );
  }

  // ── Drop zone ──────────────────────────────────────────────────────────

  return (
    <div className="w-full max-w-sm mx-auto">
      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        accept=".json"
        className="hidden"
        onChange={handleChange}
      />

      {/*
        Outer motion wrapper handles the spring lift on hover and
        the compression on tap. The border glow is a separate layer
        so it can animate independently without affecting layout.
      */}
      <motion.div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        // ── Spring physics ──────────────────────────────────────────
        whileHover={{ y: -8, scale: 1.025 }}
        whileTap={{ y: 3, scale: 0.965 }}
        animate={isDragging ? { y: -10, scale: 1.03 } : { y: 0, scale: 1 }}
        transition={isDragging ? SPRING_HOVER : SPRING_TAP}
        className="cursor-pointer relative flex flex-col items-center justify-center gap-5 p-10 text-center"
        style={{
          background: isDragging
            ? "rgba(0, 255, 157, 0.05)"
            : "var(--surface)",
          border: isDragging
            ? "1px solid var(--accent)"
            : "1px dashed var(--border-bright)",
          // Shadow lifts with the card, deepens on hover via CSS transition
          boxShadow: isDragging
            ? "0 32px 64px rgba(0,0,0,0.45), 0 0 48px var(--accent-glow)"
            : "0 4px 20px rgba(0,0,0,0.2)",
          transition: "background 0.2s, border-color 0.2s, box-shadow 0.2s",
        }}
      >
        {/* Icon — springs separately for extra bounce */}
        <motion.div
          animate={isDragging ? { scale: 1.2, rotate: -4 } : { scale: 1, rotate: 0 }}
          transition={SPRING_ICON}
        >
          {isDragging ? (
            <FileJson size={44} style={{ color: "var(--accent)" }} />
          ) : (
            <Upload
              size={38}
              style={{
                color: "var(--text-secondary)",
                transition: "color 0.2s",
              }}
            />
          )}
        </motion.div>

        {/* Copy */}
        <div>
          <p
            className="text-base font-semibold mb-1.5"
            style={{
              fontFamily: isMachineView ? "var(--font-mono)" : "var(--font-serif)",
              color: "var(--text-primary)",
              letterSpacing: isMachineView ? "0.06em" : undefined,
            }}
          >
            {isMachineView ? "// UPLOAD TARGET DATA" : "Upload your TikTok data export"}
          </p>
          <p
            className="text-sm"
            style={{
              fontFamily: isMachineView ? "var(--font-mono)" : "var(--font-serif)",
              color: "var(--text-secondary)",
            }}
          >
            {isMachineView
              ? "DROP user_data_tiktok.json HERE"
              : "Drop your user_data_tiktok.json here, or click to browse"}
          </p>
        </div>

        {/* Badge */}
        <span
          className="text-xs px-3 py-1"
          style={{
            border: "1px solid var(--border)",
            fontFamily: "var(--font-mono)",
            color: "var(--text-secondary)",
            letterSpacing: "0.1em",
          }}
        >
          .json only
        </span>
      </motion.div>

      {/* How to get your data */}
      {!isMachineView && (
        <p
          className="mt-3 text-xs text-center"
          style={{ fontFamily: "var(--font-serif)", color: "var(--text-secondary)" }}
        >
          TikTok → Settings → Privacy → Download Your Data
        </p>
      )}

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="mt-4 flex items-start gap-2 p-3 text-xs"
            style={{
              background: "rgba(255, 51, 102, 0.07)",
              border: "1px solid rgba(255, 51, 102, 0.35)",
              fontFamily: "var(--font-mono)",
              color: "var(--danger)",
            }}
          >
            <AlertTriangle size={13} className="flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
