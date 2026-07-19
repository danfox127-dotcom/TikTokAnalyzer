"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import type { GhostProfile } from "./GhostProfileHUD";

const BG = "#f5efe4";
const PANEL = "#efe8da";
const BORDER = "rgba(26, 22, 16, 0.16)";
const ACCENT = "#8b2323";
const INK = "#1a1610";
const INK_DIM = "rgba(26, 22, 16, 0.62)";
const INK_GHOST = "rgba(26, 22, 16, 0.4)";

const PILLAR_COLORS = ["#5b4a8a", "#8b2323", "#9c6b2e", "#3d6b4f"];

interface Pillar {
  label: string;
  description: string;
  contributing_creators: string[];
  contributing_topics: string[];
  ad_tier: string;
  misfire: string;
}

interface Props {
  profile: GhostProfile;
  apiUrl: string;
}

export function FourPillarsPanel({ profile, apiUrl }: Props) {
  const [pillars, setPillars] = useState<Pillar[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState(() =>
    typeof window !== "undefined" ? localStorage.getItem("llm_api_key_claude") ?? "" : ""
  );

  const generate = async () => {
    if (!apiKey) return;
    setLoading(true);
    setError(null);
    try {
      localStorage.setItem("llm_api_key_claude", apiKey);
      const res = await fetch(`${apiUrl}/api/pillars?provider=claude`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
        body: JSON.stringify({
          vibe_cluster: profile.creator_entities.vibe_cluster,
          graveyard: profile.creator_entities.graveyard,
          interest_clusters: profile.interest_clusters ?? [],
        }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail ?? `HTTP ${res.status}`);
      }
      const data = await res.json();
      setPillars(data.pillars);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  if (!pillars) {
    return (
      <div style={{ border: `1px solid ${BORDER}`, background: PANEL, padding: "32px 28px" }}>
        <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 9, letterSpacing: "0.22em", color: ACCENT, textTransform: "uppercase", marginBottom: 16 }}>
          · The Four Pillars · LLM Analysis
        </div>
        <h3 style={{ fontFamily: "var(--font-display, 'Fraunces', Georgia, serif)", fontSize: 24, fontWeight: 800, margin: "0 0 12px", color: INK }}>
          How TikTok Has <span style={{ fontStyle: "italic", color: ACCENT }}>Categorized</span> You
        </h3>
        <p style={{ fontSize: 13, color: INK_DIM, lineHeight: 1.7, maxWidth: "56ch", marginBottom: 24 }}>
          This reads your top creators and topics and identifies the 2–4 buckets TikTok has placed you in — what each one signals to advertisers, and where the algorithm gets it wrong.
        </p>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="password"
            placeholder="Anthropic API key (stays local)"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !loading && apiKey && generate()}
            style={{
              padding: "10px 14px",
              background: BG,
              border: `1px solid ${BORDER}`,
              color: INK,
              fontSize: 12,
              fontFamily: "var(--font-mono, monospace)",
              width: 300,
              outline: "none",
            }}
          />
          <button
            onClick={generate}
            disabled={!apiKey || loading}
            style={{
              padding: "10px 20px",
              background: apiKey && !loading ? ACCENT : "transparent",
              border: `1px solid ${apiKey && !loading ? ACCENT : BORDER}`,
              color: apiKey && !loading ? "#fff" : INK_GHOST,
              fontSize: 11,
              fontFamily: "var(--font-mono, monospace)",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              cursor: apiKey && !loading ? "pointer" : "not-allowed",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            {loading ? <><Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} /> Analyzing…</> : "Generate Pillars"}
          </button>
        </div>
        {error && (
          <div style={{ marginTop: 14, fontSize: 12, color: ACCENT, fontFamily: "var(--font-mono, monospace)" }}>
            {error}
          </div>
        )}
        <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <div>
      <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 9, letterSpacing: "0.22em", color: ACCENT, textTransform: "uppercase", marginBottom: 16 }}>
        · The Four Pillars · LLM Analysis
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 20 }}>
        {pillars.map((pillar, i) => {
          const color = PILLAR_COLORS[i % PILLAR_COLORS.length];
          return (
            <div key={i} style={{ position: "relative", background: PANEL, border: `1px solid ${BORDER}`, padding: "28px 24px" }}>
              {/* corner ticks */}
              <span style={{ position: "absolute", top: -1, left: -1, width: 8, height: 8, borderTop: `2px solid ${color}`, borderLeft: `2px solid ${color}` }} />
              <span style={{ position: "absolute", top: -1, right: -1, width: 8, height: 8, borderTop: `2px solid ${color}`, borderRight: `2px solid ${color}` }} />
              <span style={{ position: "absolute", bottom: -1, left: -1, width: 8, height: 8, borderBottom: `2px solid ${color}`, borderLeft: `2px solid ${color}` }} />
              <span style={{ position: "absolute", bottom: -1, right: -1, width: 8, height: 8, borderBottom: `2px solid ${color}`, borderRight: `2px solid ${color}` }} />

              <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 9, letterSpacing: "0.2em", color, textTransform: "uppercase", marginBottom: 10 }}>
                Pillar {String(i + 1).padStart(2, "0")}
              </div>
              <h4 style={{ fontFamily: "var(--font-display, 'Fraunces', Georgia, serif)", fontSize: 20, fontWeight: 800, margin: "0 0 12px", color: INK, lineHeight: 1.2 }}>
                {pillar.label}
              </h4>
              <p style={{ fontSize: 13, color: INK_DIM, lineHeight: 1.7, margin: "0 0 20px" }}>
                {pillar.description}
              </p>

              {/* Evidence spokes */}
              <div style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 16, marginBottom: 16 }}>
                <div style={{ fontSize: 9, color: INK_GHOST, textTransform: "uppercase", letterSpacing: "0.18em", fontFamily: "var(--font-mono, monospace)", marginBottom: 8 }}>
                  What fed this
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {pillar.contributing_creators.slice(0, 4).map((c, j) => (
                    <span key={j} style={{ fontSize: 10, padding: "3px 8px", border: `1px solid ${color}`, color, background: `${color}12`, fontFamily: "var(--font-mono, monospace)" }}>{c}</span>
                  ))}
                  {pillar.contributing_topics.slice(0, 4).map((t, j) => (
                    <span key={`t${j}`} style={{ fontSize: 10, padding: "3px 8px", border: `1px solid ${BORDER}`, color: INK_DIM }}>{t}</span>
                  ))}
                </div>
              </div>

              {/* Ad tier */}
              <div style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 14, marginBottom: 14 }}>
                <div style={{ fontSize: 9, color: INK_GHOST, textTransform: "uppercase", letterSpacing: "0.18em", fontFamily: "var(--font-mono, monospace)", marginBottom: 6 }}>
                  What it's worth to advertisers
                </div>
                <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6 }}>{pillar.ad_tier}</div>
              </div>

              {/* Misfire */}
              <div style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 14, background: `${color}08`, margin: "0 -4px -4px", padding: "14px" }}>
                <div style={{ fontSize: 9, color, textTransform: "uppercase", letterSpacing: "0.18em", fontFamily: "var(--font-mono, monospace)", marginBottom: 6 }}>
                  Where the algorithm gets it wrong
                </div>
                <div style={{ fontSize: 12, color: INK_DIM, lineHeight: 1.6, fontStyle: "italic" }}>{pillar.misfire}</div>
              </div>
            </div>
          );
        })}
      </div>
      <button
        onClick={() => setPillars(null)}
        style={{ marginTop: 16, fontSize: 10, color: INK_GHOST, background: "transparent", border: "none", cursor: "pointer", fontFamily: "var(--font-mono, monospace)", textDecoration: "underline" }}
      >
        Regenerate
      </button>
    </div>
  );
}
