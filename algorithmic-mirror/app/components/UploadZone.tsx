"use client";

import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileJson, AlertTriangle, Loader2 } from "lucide-react";
import { useDuality } from "../context/DualityContext";

interface Props {
  onFile: (file: File) => void;
  isLoading: boolean;
  error: string | null;
}

const LOADING_STEPS = [
  "PARSING BEHAVIORAL NODES...",
  "MAPPING PSYCHOGRAPHIC VECTORS...",
  "INFERRING TARGET DEMOGRAPHICS...",
  "CALCULATING VULNERABILITY INDEX...",
  "COMPILING GHOST PROFILE...",
];

export function UploadZone({ onFile, isLoading, error }: Props) {
  const { isMachineView } = useDuality();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);

  // Cycle through loading steps while loading
  const stepsRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevLoading = useRef(false);
  if (isLoading && !prevLoading.current) {
    prevLoading.current = true;
    setLoadingStep(0);
    stepsRef.current = setInterval(() => {
      setLoadingStep((s) => (s + 1) % LOADING_STEPS.length);
    }, 900);
  } else if (!isLoading && prevLoading.current) {
    prevLoading.current = false;
    if (stepsRef.current) clearInterval(stepsRef.current);
  }

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
        className="w-full max-w-sm mx-auto flex flex-col items-center justify-center gap-6 py-16 font-mono"
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
              transition={{ duration: 0.3 }}
              className="text-sm tracking-widest uppercase"
              style={{
                color: "var(--accent)",
                textShadow: isMachineView
                  ? "0 0 8px var(--accent)"
                  : "none",
              }}
            >
              {LOADING_STEPS[loadingStep]}
            </motion.p>
          </AnimatePresence>
          <p className="text-xs opacity-50" style={{ color: "var(--text-secondary)" }}>
            DO NOT CLOSE THIS TAB
          </p>
        </div>

        {/* Scanning bar */}
        <div
          className="w-full h-1 overflow-hidden"
          style={{ background: "var(--border)", borderRadius: "var(--radius)" }}
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
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="w-full max-w-sm mx-auto"
    >
      <input
        ref={inputRef}
        type="file"
        accept=".json"
        className="hidden"
        onChange={handleChange}
      />

      <motion.div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        className="cursor-pointer flex flex-col items-center justify-center gap-4 p-10 text-center transition-all"
        style={{
          background: isMachineView
            ? isDragging ? "rgba(57,255,20,0.08)" : "var(--surface)"
            : isDragging ? "rgba(24,119,242,0.06)" : "var(--surface)",
          border: isDragging
            ? "2px solid var(--accent)"
            : `2px dashed var(--border)`,
          borderRadius: "var(--radius)",
          boxShadow: isDragging
            ? "0 0 20px var(--accent-glow)"
            : isMachineView
            ? "none"
            : "0 4px 24px rgba(0,0,0,0.06)",
        }}
      >
        <motion.div
          animate={isDragging ? { scale: 1.15 } : { scale: 1 }}
          transition={{ type: "spring", stiffness: 400 }}
        >
          {isDragging ? (
            <FileJson size={40} style={{ color: "var(--accent)" }} />
          ) : (
            <Upload size={36} style={{ color: "var(--text-secondary)" }} />
          )}
        </motion.div>

        <div>
          <p
            className="font-semibold text-base mb-1"
            style={{
              color: "var(--text-primary)",
              fontFamily: isMachineView ? "monospace" : "inherit",
            }}
          >
            {isMachineView
              ? "// UPLOAD TARGET DATA"
              : "Upload your TikTok data export"}
          </p>
          <p
            className="text-sm"
            style={{
              color: "var(--text-secondary)",
              fontFamily: isMachineView ? "monospace" : "inherit",
            }}
          >
            {isMachineView
              ? "DROP user_data_tiktok.json HERE"
              : "Drop your user_data_tiktok.json here, or click to browse"}
          </p>
        </div>

        <span
          className="text-xs px-3 py-1"
          style={{
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            color: "var(--text-secondary)",
            fontFamily: isMachineView ? "monospace" : "inherit",
          }}
        >
          .json only
        </span>
      </motion.div>

      {/* How to get your data */}
      {!isMachineView && (
        <p className="mt-3 text-xs text-center" style={{ color: "var(--text-secondary)" }}>
          Get your export: TikTok → Settings → Privacy → Download Your Data
        </p>
      )}

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-4 flex items-start gap-2 p-3 text-xs"
            style={{
              background: "rgba(255, 68, 68, 0.08)",
              border: "1px solid rgba(255, 68, 68, 0.4)",
              borderRadius: "var(--radius)",
              color: "#ff4444",
              fontFamily: isMachineView ? "monospace" : "inherit",
            }}
          >
            <AlertTriangle size={14} className="flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
