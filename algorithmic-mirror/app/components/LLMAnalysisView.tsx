// algorithmic-mirror/app/components/LLMAnalysisView.tsx
"use client";

import React, { useState, useEffect, useRef } from "react";
import { Loader2, Copy, ExternalLink, ArrowLeft } from "lucide-react";

interface Props {
  file: File;
  apiUrl: string;
  onBack: () => void;
}

type Provider = "claude" | "gemini-pro" | "gemini-flash";
type Status = "idle" | "loading" | "streaming" | "done" | "error";

export function LLMAnalysisView({ file, apiUrl, onBack }: Props) {
  const [provider, setProvider] = useState<Provider>("gemini-flash");
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  
  const outputRef = useRef<HTMLDivElement>(null);

  // Load API key from localStorage
  useEffect(() => {
    const savedKey = localStorage.getItem(`llm_api_key_${provider}`);
    setApiKey(savedKey || "");
  }, [provider]);

  // Auto-scroll output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const runAnalysis = async () => {
    if (!apiKey) return;
    
    // Save key
    localStorage.setItem(`llm_api_key_${provider}`, apiKey);
    
    setStatus("loading");
    setOutput("");
    setError(null);

    try {
      const fd = new FormData();
      fd.append("file", file);
      
      const queryParams = new URLSearchParams({
        provider,
        api_key: apiKey
      });

      const res = await fetch(`${apiUrl}/api/analyze/llm?${queryParams}`, {
        method: "POST",
        body: fd,
      });

      if (!res.ok) {
        const j = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(j.detail ?? `HTTP ${res.status}`);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      setStatus("streaming");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");
        
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") {
              setStatus("done");
              break;
            }
            if (data.startsWith("Error: ")) {
               throw new Error(data.slice(7));
            }
            setOutput(prev => prev + data);
          }
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
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${apiUrl}/api/export/llm`, { method: "POST", body: fd });
      if (!res.ok) throw new Error("Failed to export data");
      
      const blob = await res.json();
      await navigator.clipboard.writeText(JSON.stringify(blob, null, 2));
      
      const url = target === "claude" ? "https://claude.ai" : "https://gemini.google.com";
      window.open(url, "_blank");
    } catch (err) {
      alert("Failed to copy data: " + (err instanceof Error ? err.message : "Unknown error"));
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0a0a0a",
        color: "#eee",
        fontFamily: "ui-monospace, Menlo, Monaco, 'Cascadia Mono', monospace",
        padding: "40px 20px 80px",
      }}
    >
      <div style={{ maxWidth: 800, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 40 }}>
          <div style={{ fontSize: 10, letterSpacing: "0.4em", color: "#4db8ff", fontWeight: 700 }}>
            // AI ANALYSIS ENGINE
          </div>
          <button
            onClick={onBack}
            style={{
              background: "none",
              border: "1px solid #333",
              color: "#888",
              padding: "6px 12px",
              fontSize: 11,
              cursor: "pointer",
            }}
          >
            ← BACK
          </button>
        </div>

        {/* Provider Selector */}
        <div style={{ display: "flex", gap: 10, marginBottom: 24 }}>
          {(["claude", "gemini-pro", "gemini-flash"] as const).map(p => {
            let label = p.replace("-", " ").toUpperCase();
            if (p === "claude") label = "CLAUDE 4.5";
            if (p === "gemini-pro") label = "GEMINI 3.1 PRO";
            if (p === "gemini-flash") label = "GEMINI 3.1 FLASH";
            
            return (
              <button
                key={p}
                onClick={() => setProvider(p)}
                style={{
                  flex: 1,
                  padding: "12px",
                  background: provider === p ? "#111" : "transparent",
                  border: `1px solid ${provider === p ? "#4db8ff" : "#222"}`,
                  color: provider === p ? "#4db8ff" : "#666",
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: "0.1em",
                  cursor: "pointer",
                  textTransform: "uppercase",
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* API Key Input */}
        <div style={{ marginBottom: 32 }}>
          <input
            type="password"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder={provider === "claude" ? "sk-ant-..." : "AIza..."}
            style={{
              width: "100%",
              padding: "14px",
              background: "#111",
              border: "1px solid #222",
              color: "#fff",
              fontSize: 13,
              fontFamily: "inherit",
              marginBottom: 16,
            }}
          />
          <button
            onClick={runAnalysis}
            disabled={!apiKey || status === "loading" || status === "streaming"}
            style={{
              width: "100%",
              padding: "14px",
              background: !apiKey ? "#1a1a1a" : "#4db8ff",
              color: !apiKey ? "#444" : "#000",
              border: "none",
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.1em",
              cursor: (!apiKey || status === "loading" || status === "streaming") ? "not-allowed" : "pointer",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              gap: 10,
            }}
          >
            {(status === "loading" || status === "streaming") && <Loader2 size={16} className="animate-spin" />}
            {status === "streaming" ? "STREAMING..." : "RUN ANALYSIS →"}
          </button>
        </div>

        {/* Copy & Open Section */}
        <div style={{ marginBottom: 40, borderTop: "1px solid #1a1a1a", paddingTop: 32 }}>
          <div style={{ fontSize: 10, color: "#555", marginBottom: 16, letterSpacing: "0.1em" }}>
            OR ANALYZE EXTERNALLY (PRIVACY-SAFE EXPORT)
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={() => copyAndOpen("claude")}
              style={{
                flex: 1,
                padding: "10px",
                background: "transparent",
                border: "1px solid #333",
                color: "#aaa",
                fontSize: 10,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
              }}
            >
              <Copy size={12} /> CLAUDE.AI
            </button>
            <button
              onClick={() => copyAndOpen("gemini")}
              style={{
                flex: 1,
                padding: "10px",
                background: "transparent",
                border: "1px solid #333",
                color: "#aaa",
                fontSize: 10,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
              }}
            >
              <Copy size={12} /> GEMINI
            </button>
          </div>
        </div>

        {/* Output Area */}
        <div
          ref={outputRef}
          style={{
            background: "#050505",
            border: "1px solid #1a1a1a",
            padding: "24px",
            minHeight: "400px",
            maxHeight: "600px",
            overflowY: "auto",
            position: "relative",
            fontSize: 14,
            lineHeight: 1.7,
            color: "#ccc",
            whiteSpace: "pre-wrap",
          }}
        >
          {/* Scanline overlay */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              pointerEvents: "none",
              background: "linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06))",
              backgroundSize: "100% 4px, 3px 100%",
              opacity: 0.1,
            }}
          />
          
          {output}
          {status === "streaming" && (
            <span style={{ display: "inline-block", width: "8px", height: "15px", background: "#4db8ff", marginLeft: "4px", verticalAlign: "middle", animation: "blink 1s step-end infinite" }} />
          )}
          {error && (
            <div style={{ color: "#ff4466", marginTop: 20 }}>
              ERROR: {error}
            </div>
          )}
          {status === "idle" && !output && (
            <div style={{ color: "#333", textAlign: "center", marginTop: 160 }}>
              WAITING FOR PARAMETERS...
            </div>
          )}
        </div>

        <style jsx>{`
          @keyframes blink {
            from, to { opacity: 1; }
            50% { opacity: 0; }
          }
          .animate-spin {
            animation: spin 1s linear infinite;
          }
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    </div>
  );
}
