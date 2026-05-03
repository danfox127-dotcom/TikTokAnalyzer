"use client";

import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Loader2 } from "lucide-react";
import { GhostProfileHUD, GhostProfile } from "./components/GhostProfileHUD";
import { TheGlassHouse } from "./components/TheGlassHouse";
import { NarrativeReportView } from "./components/NarrativeReportView";
import { LLMAnalysisView } from "./components/LLMAnalysisView";
import { PhaseTransition } from "./components/PhaseTransition";
import type { NarrativeBlock } from "./types/narrative";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005";

type View = "upload" | "transition" | "narrative" | "hud" | "report" | "llm";

export default function Home() {
  const [profile, setProfile] = useState<GhostProfile | null>(null);
  const [view, setView] = useState<View>("upload");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [narrativeBlocks, setNarrativeBlocks] = useState<NarrativeBlock[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const analyze = async (file: File) => {
    setIsLoading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API_URL}/api/analyze`, { method: "POST", body: fd });
      if (!res.ok) {
        const j = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(j.detail ?? `HTTP ${res.status}`);
      }
      const raw = await res.json();
      setProfile(raw as GhostProfile);
      setNarrativeBlocks((raw as { narrative_blocks?: NarrativeBlock[] }).narrative_blocks ?? []);
      setView("transition");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      const net = /fetch|NetworkError|ECONNREFUSED|Failed to fetch/i.test(msg);
      setError(net ? `Cannot reach forensics engine at ${API_URL}` : msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setProfile(null);
    setView("upload");
    setError(null);
    setUploadedFile(null);
    setNarrativeBlocks([]);
  };

  const handleFile = (file: File | null | undefined) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".json")) {
      setError("Expected a TikTok .json export.");
      return;
    }
    setUploadedFile(file);
    analyze(file);
  };

  if (profile && view === "report") {
    return (
      <NarrativeReportView
        narrativeBlocks={narrativeBlocks}
        onBack={() => setView("narrative")}
      />
    );
  }

  if (view === "transition") {
    return <PhaseTransition onComplete={() => setView("narrative")} />;
  }

  if (profile && view === "llm") {
    return (
      <LLMAnalysisView
        file={uploadedFile!}
        apiUrl={API_URL}
        onBack={() => setView("narrative")}
      />
    );
  }

  if (profile && view === "narrative") {
    return (
      <TheGlassHouse
        profile={profile}
        onReset={handleReset}
        onViewRawForensics={() => setView("hud")}
        sourceFile={uploadedFile ?? undefined}
        onOpenReport={() => setView("report")}
        onAnalyzeWithAI={() => setView("llm")}
      />
    );
  }

  if (profile && view === "hud") {
    return (
      <div style={{ position: "relative" }}>
        {/* Back-to-narrative ribbon */}
        <button
          onClick={() => setView("narrative")}
          style={{
            position: "fixed",
            top: 20,
            left: 20,
            zIndex: 50,
            padding: "10px 16px",
            background: "#f5efe4",
            color: "#1a1610",
            border: "1px solid rgba(26,22,16,0.25)",
            fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
            fontSize: 10,
            letterSpacing: "0.28em",
            textTransform: "uppercase",
            cursor: "pointer",
          }}
        >
          ← Back to the Story
        </button>
        <GhostProfileHUD profile={profile} onReset={handleReset} sourceFile={uploadedFile ?? undefined} />
      </div>
    );
  }

  // ──────────────────────────────────────────────────────────────────────
  // Upload state — editorial cover page
  // ──────────────────────────────────────────────────────────────────────
  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#f5efe4",
        color: "#1a1610",
        fontFamily: "var(--font-body, 'Iowan Old Style', Georgia, serif)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Paper grain */}
      <div
        aria-hidden
        style={{
          position: "fixed",
          inset: 0,
          pointerEvents: "none",
          opacity: 0.5,
          mixBlendMode: "multiply",
          backgroundImage: "radial-gradient(rgba(26,22,16,0.06) 1px, transparent 1px)",
          backgroundSize: "3px 3px",
          zIndex: 1,
        }}
      />

      <div
        style={{
          position: "relative",
          zIndex: 2,
          maxWidth: 1100,
          margin: "0 auto",
          padding: "56px clamp(24px, 5vw, 72px) 120px",
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Masthead */}
        <header
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            borderBottom: "2px solid #1a1610",
            paddingBottom: 18,
            marginBottom: 80,
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 10,
              letterSpacing: "0.38em",
              color: "#6a5e4a",
              textTransform: "uppercase",
            }}
          >
            The Glass House · Vol. I · Dossier Edition
          </div>
          <div
            style={{
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 10,
              letterSpacing: "0.28em",
              color: "#6a5e4a",
              textTransform: "uppercase",
            }}
          >
            An Investigative Piece · About You
          </div>
        </header>

        {/* Hero */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <div
            style={{
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 11,
              letterSpacing: "0.32em",
              color: "#8b2323",
              textTransform: "uppercase",
              marginBottom: 22,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <span style={{ width: 28, height: 1, background: "#8b2323", display: "inline-block" }} />
            Prologue · The Hook
          </div>

          <h1
            style={{
              fontFamily: "var(--font-display, 'Fraunces', 'Playfair Display', Georgia, serif)",
              fontWeight: 800,
              fontSize: "clamp(52px, 8vw, 108px)",
              lineHeight: 0.94,
              letterSpacing: "-0.035em",
              color: "#1a1610",
              margin: 0,
              maxWidth: "14ch",
              marginBottom: 40,
            }}
          >
            The House<br />
            You Didn&rsquo;t<br />
            Know Was{" "}
            <span style={{ fontStyle: "italic", color: "#8b2323" }}>Glass.</span>
          </h1>

          <p
            style={{
              fontFamily: "var(--font-body, 'Iowan Old Style', Georgia, serif)",
              fontSize: "clamp(18px, 2vw, 22px)",
              lineHeight: 1.6,
              color: "#3a3024",
              maxWidth: "56ch",
              margin: "0 0 48px",
            }}
          >
            Upload the TikTok data export ByteDance delivered to you upon request.
            This dossier is reconstructed from what&rsquo;s inside &mdash; every claim
            backed by a raw excerpt you can inspect.
          </p>

          {/* Dropzone */}
          <motion.div
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => {
              e.preventDefault();
              setDragOver(false);
              handleFile(e.dataTransfer.files?.[0]);
            }}
            onClick={() => !isLoading && inputRef.current?.click()}
            animate={{
              borderColor: dragOver ? "#8b2323" : "rgba(26,22,16,0.28)",
              background: dragOver ? "rgba(139, 35, 35, 0.04)" : "#ede5d4",
            }}
            transition={{ duration: 0.2 }}
            style={{
              maxWidth: 560,
              border: "1px dashed",
              padding: "44px 32px",
              cursor: isLoading ? "wait" : "pointer",
              position: "relative",
            }}
          >
            {/* corner ticks */}
            <span style={{ position: "absolute", top: -1, left: -1, width: 10, height: 10, borderTop: "2px solid #8b2323", borderLeft: "2px solid #8b2323" }} />
            <span style={{ position: "absolute", top: -1, right: -1, width: 10, height: 10, borderTop: "2px solid #8b2323", borderRight: "2px solid #8b2323" }} />
            <span style={{ position: "absolute", bottom: -1, left: -1, width: 10, height: 10, borderBottom: "2px solid #8b2323", borderLeft: "2px solid #8b2323" }} />
            <span style={{ position: "absolute", bottom: -1, right: -1, width: 10, height: 10, borderBottom: "2px solid #8b2323", borderRight: "2px solid #8b2323" }} />

            <input
              ref={inputRef}
              type="file"
              accept=".json,application/json"
              style={{ display: "none" }}
              onChange={e => handleFile(e.target.files?.[0])}
            />

            <AnimatePresence mode="wait">
              {isLoading ? (
                <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
                    >
                      <Loader2 size={24} color="#8b2323" />
                    </motion.div>
                    <div>
                      <div
                        style={{
                          fontFamily: "var(--font-display, 'Fraunces', Georgia, serif)",
                          fontSize: 18,
                          fontStyle: "italic",
                          color: "#1a1610",
                          marginBottom: 4,
                        }}
                      >
                        The staff analyst is reading your file&hellip;
                      </div>
                      <div
                        style={{
                          fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                          fontSize: 10,
                          letterSpacing: "0.2em",
                          color: "#6a5e4a",
                          textTransform: "uppercase",
                        }}
                      >
                        Stopwatch · entity resolution · citation audit
                      </div>
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ display: "flex", alignItems: "center", gap: 20 }}>
                  <Upload size={28} color="#1a1610" />
                  <div>
                    <div
                      style={{
                        fontFamily: "var(--font-display, 'Fraunces', Georgia, serif)",
                        fontSize: 22,
                        fontWeight: 600,
                        color: "#1a1610",
                        lineHeight: 1.2,
                      }}
                    >
                      Drop the TikTok export here.
                    </div>
                    <div
                      style={{
                        fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                        fontSize: 10,
                        letterSpacing: "0.22em",
                        color: "#6a5e4a",
                        textTransform: "uppercase",
                        marginTop: 6,
                      }}
                    >
                      or click to select · .json
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                marginTop: 20,
                maxWidth: 560,
                padding: "12px 16px",
                border: "1px solid rgba(139, 35, 35, 0.4)",
                background: "rgba(139, 35, 35, 0.06)",
                color: "#6a1919",
                fontFamily: "var(--font-body, Georgia, serif)",
                fontStyle: "italic",
                fontSize: 14,
              }}
            >
              {error}
            </motion.div>
          )}
        </div>

        {/* Method note */}
        <div
          style={{
            marginTop: 80,
            paddingTop: 20,
            borderTop: "1px solid rgba(26,22,16,0.14)",
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 48,
            fontFamily: "var(--font-body, Georgia, serif)",
            fontSize: 13,
            color: "#6a5e4a",
            lineHeight: 1.7,
          }}
        >
          <div>
            <div
              style={{
                fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                fontSize: 10,
                letterSpacing: "0.25em",
                color: "#6a5e4a",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              Method
            </div>
            Your JSON never leaves this machine. Parsing and stopwatch analysis run against
            a local Python engine at{" "}
            <span style={{ fontFamily: "var(--font-mono, monospace)", color: "#1a1610" }}>
              {API_URL}
            </span>.
          </div>
          <div>
            <div
              style={{
                fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                fontSize: 10,
                letterSpacing: "0.25em",
                color: "#6a5e4a",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              Citation
            </div>
            Every underlined phrase in the dossier is a claim. Click it to reveal the exact
            excerpt of your export that supports it. No synthesis. No paraphrase.
          </div>
        </div>
      </div>
    </main>
  );
}
