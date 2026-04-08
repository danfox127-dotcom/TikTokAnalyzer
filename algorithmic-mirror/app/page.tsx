"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Scan, ShieldOff, Eye } from "lucide-react";
import { useDuality } from "./context/DualityContext";
import { VideoCard } from "./components/VideoCard";
import { UploadZone } from "./components/UploadZone";
import { GhostProfileHUD, GhostProfile } from "./components/GhostProfileHUD";

export default function Home() {
  const { isMachineView, toggle, setMachineView } = useDuality();
  const [ghostProfile, setGhostProfile] = useState<GhostProfile | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleUpload = async (file: File) => {
    setIsLoading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8001/api/analyze", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(detail.detail ?? `HTTP ${res.status}`);
      }

      const data: GhostProfile = await res.json();
      setGhostProfile(data);
      setMachineView(true);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      const isNetworkError =
        message.includes("fetch") ||
        message.includes("Failed to fetch") ||
        message.includes("NetworkError") ||
        message.includes("ECONNREFUSED");
      setUploadError(
        isNetworkError
          ? "UPLINK FAILURE: Cannot reach forensics engine at localhost:8000"
          : `PARSE ERROR: ${message}`
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setGhostProfile(null);
    setUploadError(null);
  };

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
        initial={{ opacity: 1 }}
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
            : "You see a friendly video. The algorithm sees a data harvest. Upload your TikTok export to see what it knows about you."}
        </motion.p>
      </motion.div>

      {/* ── Mode badge ── */}
      <div className="w-full max-w-lg mb-4 flex items-center justify-between text-xs uppercase tracking-widest">
        <div className="flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
          <Eye size={12} />
          <span style={{ fontFamily: isMachineView ? "monospace" : "inherit" }}>
            {ghostProfile
              ? isMachineView
                ? "GHOST PROFILE — LIVE DATA"
                : "SHELL VIEW — PROFILE LOADED"
              : isMachineView
              ? "MACHINE VIEW — RAW PAYLOAD"
              : "SHELL VIEW — AS PRESENTED"}
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

      {/* ── Main content ── */}
      <div className="w-full max-w-lg">
        <AnimatePresence mode="wait" initial={false}>
          {ghostProfile ? (
            <motion.div
              key="hud"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              <GhostProfileHUD profile={ghostProfile} onReset={handleReset} />
            </motion.div>
          ) : (
            <motion.div
              key="upload"
              initial={{ opacity: 1 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="space-y-8"
            >
              <UploadZone
                onFile={handleUpload}
                isLoading={isLoading}
                error={uploadError}
              />

              {/* Demo VideoCard below upload zone */}
              {!isLoading && (
                <div>
                  <p
                    className="text-xs uppercase tracking-widest mb-3 text-center"
                    style={{
                      color: "var(--text-secondary)",
                      fontFamily: isMachineView ? "monospace" : "inherit",
                    }}
                  >
                    {isMachineView ? "// SAMPLE_PAYLOAD" : "Example — what the algorithm sees"}
                  </p>
                  <VideoCard />
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Footer note ── */}
      {!ghostProfile && (
        <motion.p
          className="mt-16 text-xs text-center max-w-sm"
          style={{
            color: "var(--text-secondary)",
            fontFamily: isMachineView ? "monospace" : "inherit",
            opacity: 0.6,
          }}
        >
          {isMachineView
            ? "// All analysis runs locally. Your data never leaves your browser."
            : "Your data is never uploaded to any server. All analysis runs locally."}
        </motion.p>
      )}
    </main>
  );
}
