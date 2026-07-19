// algorithmic-mirror/app/components/LLMAnalysisView.tsx
"use client";

import React, { useState, useEffect, useRef } from "react";
import { Loader2, Copy, Cpu } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// ── Design tokens ──────────────────────────────────────────────────────────
const PAPER       = "#f5efe4";
const PAPER_DEEP  = "#ede5d4";
const PAPER_LIGHT = "#fdfbf6";
const INK         = "#1a1610";
const INK_SOFT    = "#3a3024";
const INK_DIM     = "#6a5e4a";
const INK_GHOST   = "#a89a80";
const RULE        = "rgba(26, 22, 16, 0.14)";
const ACCENT      = "#8b2323";

interface Props {
  file: File;
  apiUrl: string;
  onBack: () => void;
}

type Provider = "claude" | "gemini-pro" | "gemini-flash";
type Status = "idle" | "loading" | "streaming" | "done" | "error";

const PROVIDERS: { id: Provider; label: string; sub: string }[] = [
  { id: "gemini-flash", label: "Gemini Flash",   sub: "Fast · 3.1" },
  { id: "gemini-pro",  label: "Gemini Pro",     sub: "Thorough · 3.1" },
  { id: "claude",      label: "Claude",         sub: "Deep · 4.5" },
];

export function LLMAnalysisView({ file, apiUrl, onBack }: Props) {
  const [provider, setProvider] = useState<Provider>("gemini-flash");
  const [apiKey, setApiKey]   = useState("");
  const [status, setStatus]   = useState<Status>("idle");
  const [output, setOutput]   = useState("");
  const [error, setError]     = useState<string | null>(null);

  const outputRef = useRef<HTMLDivElement>(null);

  // Persist key per provider
  useEffect(() => {
    setApiKey(localStorage.getItem(`llm_api_key_${provider}`) ?? "");
  }, [provider]);

  // Auto-scroll output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const runAnalysis = async () => {
    if (!apiKey) return;
    localStorage.setItem(`llm_api_key_${provider}`, apiKey);
    setStatus("loading");
    setOutput("");
    setError(null);

    try {
      const fd = new FormData();
      fd.append("file", file);
      const params = new URLSearchParams({ provider });
      const res = await fetch(`${apiUrl}/api/analyze/llm?${params}`, {
        method: "POST", body: fd, headers: { "X-API-Key": apiKey },
      });

      if (!res.ok) {
        const j = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(j.detail ?? `HTTP ${res.status}`);
      }

      const reader  = res.body!.getReader();
      const decoder = new TextDecoder();
      setStatus("streaming");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6);
          if (data === "[DONE]") { setStatus("done"); break; }
          if (data.startsWith("Error: ")) throw new Error(data.slice(7));
          setOutput(prev => prev + data);
        }
      }
      if (status !== "done") setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setStatus("error");
    }
  };

  const copyAndOpen = async (target: "claude" | "gemini") => {
    try {
      const fd  = new FormData();
      fd.append("file", file);
      const res = await fetch(`${apiUrl}/api/export/llm`, { method: "POST", body: fd });
      if (!res.ok) throw new Error("Failed to export data");
      const blob = await res.json();
      await navigator.clipboard.writeText(JSON.stringify(blob, null, 2));
      window.open(target === "claude" ? "https://claude.ai" : "https://gemini.google.com", "_blank");
    } catch (err) {
      alert("Failed to copy data: " + (err instanceof Error ? err.message : "Unknown error"));
    }
  };

  const busy = status === "loading" || status === "streaming";

  return (
    <div
      style={{
        minHeight: "100vh",
        background: PAPER,
        color: INK,
        fontFamily: "var(--font-body, 'Source Serif 4', Georgia, serif)",
        position: "relative",
        overflowX: "hidden",
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
          maxWidth: 860,
          margin: "0 auto",
          padding: "56px clamp(24px, 5vw, 72px) 120px",
        }}
      >
        {/* Masthead */}
        <header
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            borderBottom: `2px solid ${INK}`,
            paddingBottom: 18,
            marginBottom: 72,
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div>
            <div
              style={{
                fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                fontSize: 10,
                letterSpacing: "0.38em",
                color: INK_DIM,
                textTransform: "uppercase",
                marginBottom: 6,
              }}
            >
              The Glass House · Vol. I · Dossier Edition
            </div>
            <h1
              style={{
                fontFamily: "var(--font-display, 'Fraunces', Georgia, serif)",
                fontSize: "clamp(32px, 4.5vw, 52px)",
                fontWeight: 800,
                lineHeight: 0.96,
                letterSpacing: "-0.02em",
                color: INK,
                margin: 0,
              }}
            >
              AI Analysis
            </h1>
          </div>
          <button
            onClick={onBack}
            style={{
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 10,
              letterSpacing: "0.28em",
              textTransform: "uppercase",
              color: INK_DIM,
              background: PAPER_DEEP,
              border: `1px solid rgba(26,22,16,0.25)`,
              padding: "10px 16px",
              cursor: "pointer",
              alignSelf: "flex-end",
            }}
          >
            ← Back to the Story
          </button>
        </header>

        {/* Provider selector */}
        <div style={{ marginBottom: 36 }}>
          <div
            style={{
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 10,
              letterSpacing: "0.25em",
              color: INK_DIM,
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            Model
          </div>
          <div style={{ display: "flex", gap: 0, borderTop: `1px solid ${RULE}` }}>
            {PROVIDERS.map(p => (
              <button
                key={p.id}
                onClick={() => setProvider(p.id)}
                style={{
                  flex: 1,
                  padding: "14px 12px",
                  background: provider === p.id ? PAPER_DEEP : PAPER,
                  border: `1px solid ${RULE}`,
                  borderTop: provider === p.id ? `2px solid ${ACCENT}` : `1px solid ${RULE}`,
                  borderLeft: "none",
                  color: provider === p.id ? INK : INK_DIM,
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "background 0.15s ease",
                }}
              >
                <div
                  style={{
                    fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    color: provider === p.id ? ACCENT : INK_GHOST,
                  }}
                >
                  {p.label}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-body, Georgia, serif)",
                    fontSize: 12,
                    color: provider === p.id ? INK_DIM : INK_GHOST,
                    marginTop: 2,
                    fontStyle: "italic",
                  }}
                >
                  {p.sub}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* API key */}
        <div style={{ marginBottom: 32 }}>
          <div
            style={{
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 10,
              letterSpacing: "0.25em",
              color: INK_DIM,
              textTransform: "uppercase",
              marginBottom: 10,
            }}
          >
            API Key
          </div>
          <input
            type="password"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !busy && apiKey && runAnalysis()}
            placeholder={provider === "claude" ? "sk-ant-…" : "AIza…"}
            style={{
              width: "100%",
              padding: "12px 14px",
              background: PAPER_LIGHT,
              border: `1px solid rgba(26,22,16,0.22)`,
              color: INK,
              fontSize: 13,
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              letterSpacing: "0.05em",
              outline: "none",
              marginBottom: 12,
            }}
          />
          <button
            onClick={runAnalysis}
            disabled={!apiKey || busy}
            style={{
              width: "100%",
              padding: "14px",
              background: !apiKey || busy ? PAPER_DEEP : ACCENT,
              color: !apiKey || busy ? INK_GHOST : "#fff",
              border: `1px solid ${!apiKey || busy ? RULE : ACCENT}`,
              fontSize: 11,
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontWeight: 700,
              letterSpacing: "0.22em",
              textTransform: "uppercase",
              cursor: !apiKey || busy ? "not-allowed" : "pointer",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              gap: 10,
              transition: "background 0.15s ease",
            }}
          >
            {busy && (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1.1, ease: "linear" }}
              >
                <Loader2 size={14} />
              </motion.div>
            )}
            {status === "streaming" ? "Streaming…" : "Run Analysis →"}
          </button>
        </div>

        {/* Privacy-safe external export */}
        <div
          style={{
            marginBottom: 48,
            paddingTop: 24,
            borderTop: `1px solid ${RULE}`,
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 10,
              letterSpacing: "0.22em",
              color: INK_GHOST,
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            Or analyze externally — privacy-safe export
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            {(["claude", "gemini"] as const).map(t => (
              <button
                key={t}
                onClick={() => copyAndOpen(t)}
                style={{
                  flex: 1,
                  padding: "10px",
                  background: PAPER,
                  border: `1px solid rgba(26,22,16,0.2)`,
                  color: INK_DIM,
                  fontSize: 10,
                  fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 8,
                  transition: "background 0.12s ease",
                }}
              >
                <Copy size={11} />
                {t === "claude" ? "Claude.ai" : "Gemini"}
              </button>
            ))}
          </div>
          <p
            style={{
              fontFamily: "var(--font-body, Georgia, serif)",
              fontSize: 12,
              color: INK_GHOST,
              fontStyle: "italic",
              marginTop: 10,
              lineHeight: 1.6,
            }}
          >
            Copies a sanitized JSON snapshot to your clipboard and opens the AI in a new tab.
            Your raw export file never leaves this machine.
          </p>
        </div>

        {/* Output area */}
        <AnimatePresence>
          {(output || status === "idle" || status === "error") && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <div
                style={{
                  fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                  fontSize: 10,
                  letterSpacing: "0.25em",
                  color: INK_DIM,
                  textTransform: "uppercase",
                  marginBottom: 10,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <Cpu size={11} />
                Output
              </div>
              <div
                ref={outputRef}
                style={{
                  background: PAPER_LIGHT,
                  border: `1px solid rgba(26,22,16,0.14)`,
                  borderLeft: `3px solid ${ACCENT}`,
                  padding: "24px 28px",
                  minHeight: 320,
                  maxHeight: 560,
                  overflowY: "auto",
                  position: "relative",
                  fontSize: 15,
                  lineHeight: 1.75,
                  color: INK_SOFT,
                  whiteSpace: "pre-wrap",
                  fontFamily: "var(--font-body, 'Source Serif 4', Georgia, serif)",
                }}
              >
                {output}
                {status === "streaming" && (
                  <motion.span
                    animate={{ opacity: [1, 0, 1] }}
                    transition={{ repeat: Infinity, duration: 0.9 }}
                    style={{
                      display: "inline-block",
                      width: 7,
                      height: 16,
                      background: ACCENT,
                      marginLeft: 3,
                      verticalAlign: "middle",
                    }}
                  />
                )}
                {status === "error" && error && (
                  <div
                    style={{
                      color: ACCENT,
                      fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                      fontSize: 12,
                      marginTop: 16,
                    }}
                  >
                    Error: {error}
                  </div>
                )}
                {status === "idle" && !output && (
                  <div
                    style={{
                      color: INK_GHOST,
                      textAlign: "center",
                      paddingTop: 100,
                      fontFamily: "var(--font-body, Georgia, serif)",
                      fontStyle: "italic",
                      fontSize: 15,
                    }}
                  >
                    Enter an API key and run the analysis to see results here.
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
