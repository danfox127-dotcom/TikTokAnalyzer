"use client";

import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Loader2 } from "lucide-react";
import { GhostProfile } from "./components/GhostProfileHUD";
import { ForensicDashboard } from "./components/ForensicDashboard";
import { NarrativeReportView } from "./components/NarrativeReportView";
import { LLMAnalysisView } from "./components/LLMAnalysisView";
import { runEngineOffThread } from "./utils/engineWorker";
import { extractVideoId } from "../engine/videoId";
import type { NarrativeBlock } from "./types/narrative";
import { resolveTopicResult, readSavedKey } from "./utils/topicStep";
import { buildTargetingCard } from "../engine/targetingCard";
import { buildDemographics } from "../engine/demographics";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005";
// Browser-local mode (Gate 0) is the DEFAULT: the whole deterministic engine runs
// client-side and the raw export NEVER leaves the device. Two thin, best-effort
// lookups still hit the server — lingered video ids → creator @handles, and login
// IPs → city labels — each strictly less disclosure than uploading the export.
// Set NEXT_PUBLIC_SERVER_ENGINE=1 to force the legacy server upload path (debug/parity).
const SERVER_ENGINE = process.env.NEXT_PUBLIC_SERVER_ENGINE === "1";

/** POST JSON to a thin enrichment endpoint. Distinguishes an offline / transport
 *  failure (expected in local mode — returns null quietly) from a reachable-but-
 *  broken endpoint (surfaced via console.warn so a real outage isn't silently
 *  swallowed by the graceful degradation). */
async function postEnrich<T>(
  path: string, body: unknown, headers?: Record<string, string>,
): Promise<T | null> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(headers ?? {}) },
      body: JSON.stringify(body),
    });
  } catch {
    return null; // offline / unreachable — expected; degrade silently
  }
  if (!res.ok) {
    // eslint-disable-next-line no-console
    console.warn(`[local-mode] ${path} → HTTP ${res.status}; degrading without this enrichment`);
    return null;
  }
  try { return (await res.json()) as T; } catch { return null; }
}

/** Run the parity-locked TS engine on the file, entirely in the browser. Returns
 *  the same top-level shape as POST /api/analyze: the ghost profile spread with
 *  `narrative_blocks`, plus the engine's coverage/gates/claims/schema layers.
 *
 *  Two passes: (1) run locally with unresolved creators; (2) if the resolve
 *  endpoint is reachable, re-run with the cache-backed handle map so creators /
 *  echo-chamber / vibe-cluster come back real. The raw export never leaves the
 *  device — only opaque video ids for lingered/graveyard creators are sent. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function analyzeLocal(file: File): Promise<any> {
  const rawExport = JSON.parse(await file.text());
  let out = await runEngineOffThread(rawExport);

  const sw = out.profile.stopwatch_metrics ?? {};
  const links: string[] = [...(sw._linger_links ?? []), ...(sw._graveyard_links ?? [])];
  const videoIds = [...new Set(links.map((l) => extractVideoId(l)).filter((v): v is string => !!v))];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const resolution = videoIds.length ? await postEnrich<any>("/api/resolve", { video_ids: videoIds }) : null;

  if (resolution?.handles && Object.keys(resolution.handles).length) {
    out = await runEngineOffThread(rawExport, { linkHandleMap: resolution.handles });
    // Attach display name / thumbnail to the ledgers (mirrors /api/analyze).
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const metaByHandle: Record<string, any> = {};
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    for (const m of Object.values(resolution.meta ?? {}) as any[]) {
      if (m?.handle) metaByHandle[String(m.handle).replace(/^@/, "").toLowerCase()] = m;
    }
    const ce = out.profile.creator_entities ?? {};
    for (const c of [...(ce.vibe_cluster ?? []), ...(ce.graveyard ?? [])]) {
      const m = metaByHandle[String(c.handle ?? "").replace(/^@/, "").toLowerCase()];
      if (m) {
        if (m.display_name && c.display_name == null) c.display_name = m.display_name;
        if (m.thumbnail && c.thumbnail == null) c.thumbnail = m.thumbnail;
      }
    }
    out.profile.creator_resolution = {
      resolved: resolution.resolved, total: resolution.total, pct: resolution.pct,
      newly_resolved: resolution.newly_resolved, persistent: resolution.persistent,
    };
  }

  // Geo over ALL login IPs (for the WP-2.3 location card), not just the 25 display
  // logins. Still sends only IPs — strictly less than the export.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const displayLogins: any[] = out.profile.digital_footprint?.recent_logins ?? [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const allLogins: any[] = out.parsed?.login_history ?? [];
  const ips = [...new Set([...allLogins, ...displayLogins]
    .map((l) => l?.ip).filter((ip: string): ip is string => !!ip))];
  let ipGeo: Record<string, { city: string; country_name: string }> = {};
  if (ips.length) {
    const geoResp = await postEnrich<{ geo: Record<string, { city: string; country_name: string }> }>(
      "/api/geo", { ips });
    if (geoResp?.geo) {
      ipGeo = geoResp.geo;
      for (const l of displayLogins) {
        const g = ipGeo[l.ip];
        if (g) { l.city = g.city; l.country_name = g.country_name; }
      }
    }
  }

  // WP-2.2 — topics step + Targeting Card. BYOK → /api/topics; else keyword
  // fallback (which gates the card to insufficient_evidence). Best-effort: any
  // failure leaves the card gated, never blocks the dossier.
  let targeting_card;
  try {
    const topicResult = await resolveTopicResult({
      topicCandidates: out.topicCandidates ?? [],
      profile: out.profile,
      getKey: () => readSavedKey((k) => localStorage.getItem(k)),
      post: postEnrich,
    });
    targeting_card = buildTargetingCard(topicResult, out.profile);
  } catch {
    targeting_card = undefined;
  }

  // WP-2.3 — demographic reconstruction (gender/age/location/spending/interests).
  // Best-effort: any failure leaves demographics undefined, never blocks the dossier.
  let demographics;
  try {
    demographics = buildDemographics({
      parsed: out.parsed, profile: out.profile, targeting_card, ipGeo, now: new Date(),
    });
  } catch {
    demographics = undefined;
  }

  return {
    ...out.profile, narrative_blocks: out.narratives,
    coverage: out.coverage, gates: out.gates, claims: out.claims, schema: out.schema,
    targeting_card,
    demographics,
    persona: out.persona,
    _local_mode: true,
  };
}

// Direct tool-based view flow: upload → dashboard
type View = "upload" | "dashboard" | "report" | "llm" | "hud";

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
      let raw;

      // DEFAULT: browser-local engine — the raw export never leaves the device.
      if (!SERVER_ENGINE) {
        raw = await analyzeLocal(file);
      } else {
        // Legacy server upload path (opt-out via NEXT_PUBLIC_SERVER_ENGINE=1) —
        // the live Python FastAPI backend.
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch(`${API_URL}/api/analyze`, { method: "POST", body: fd });
        if (!res.ok) {
          const j = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
          throw new Error(j.detail ?? `HTTP ${res.status}`);
        }
        raw = await res.json();
      }

      setProfile(raw as GhostProfile);
      setNarrativeBlocks((raw as { narrative_blocks?: NarrativeBlock[] }).narrative_blocks ?? []);
      
      // Pivot: Bypass cinematic surface/transition, go straight to tools.
      setView("dashboard");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      const net = /fetch|NetworkError|ECONNREFUSED|Failed to fetch/i.test(msg);
      // No server-file-upload fallback by design: local mode is the default and
      // its own enrichment lookups already degrade gracefully offline. Uploading
      // the raw export on failure would silently break "nothing leaves the device".
      setError(net && SERVER_ENGINE ? `Cannot reach forensics engine at ${API_URL}` : msg);
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

  if (profile && view === "dashboard") {
    return (
      <ForensicDashboard 
        profile={profile} 
        onReset={handleReset} 
        sourceFile={uploadedFile!} 
      />
    );
  }

  if (profile && view === "report") {
    return (
      <NarrativeReportView
        narrativeBlocks={narrativeBlocks}
        onBack={() => setView("dashboard")}
      />
    );
  }

  if (profile && view === "llm") {
    return (
      <LLMAnalysisView
        file={uploadedFile!}
        apiUrl={API_URL}
        onBack={() => setView("dashboard")}
      />
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
            How Much<br />
            Does TikTok{" "}
            <span style={{ fontStyle: "italic", color: "#8b2323" }}>Really</span><br />
            Know About You?
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
