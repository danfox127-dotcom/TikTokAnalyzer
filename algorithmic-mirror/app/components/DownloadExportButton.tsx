"use client";
import { useState, useRef } from "react";

interface Props {
  file: File;
  apiUrl: string;
}

type State = "idle" | "loading" | "error";

export function DownloadExportButton({ file, apiUrl }: Props) {
  const [state, setState] = useState<State>("idle");
  const errorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleClick = async () => {
    if (state === "loading") return;
    if (errorTimer.current) clearTimeout(errorTimer.current);
    setState("loading");

    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${apiUrl}/api/export/llm`, { method: "POST", body: fd });

      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail ?? `HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tiktok_analysis_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setState("idle");
    } catch {
      setState("error");
      errorTimer.current = setTimeout(() => setState("idle"), 3000);
    }
  };

  const label =
    state === "loading" ? "Downloading…" :
    state === "error"   ? "Export failed" :
    "Download for LLM →";

  return (
    <button
      onClick={handleClick}
      disabled={state === "loading"}
      style={{
        fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
        fontSize: 10,
        letterSpacing: "0.2em",
        textTransform: "uppercase",
        color: state === "error" ? "#f87171" : "rgba(148, 163, 184, 0.6)",
        background: "transparent",
        border: "none",
        cursor: state === "loading" ? "default" : "pointer",
        padding: 0,
        opacity: state === "loading" ? 0.5 : 1,
        transition: "opacity 0.2s, color 0.2s",
      }}
    >
      {label}
    </button>
  );
}
