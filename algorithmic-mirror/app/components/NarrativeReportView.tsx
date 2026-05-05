// algorithmic-mirror/app/components/NarrativeReportView.tsx
"use client";

import { BlockCard } from "./BlockCard";
import type { NarrativeBlock } from "../types/narrative";

const PAPER      = "#f5efe4";
const PAPER_DEEP = "#ede5d4";
const INK        = "#1a1610";
const INK_DIM    = "#6a5e4a";
const INK_GHOST  = "#a89a80";
const RULE       = "rgba(26, 22, 16, 0.14)";
const ACCENT     = "#8b2323";

interface Props {
  narrativeBlocks: NarrativeBlock[];
  onBack: () => void;
}

export function NarrativeReportView({ narrativeBlocks, onBack }: Props) {
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
            marginBottom: 80,
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
                fontSize: "clamp(36px, 5vw, 56px)",
                fontWeight: 800,
                lineHeight: 0.96,
                letterSpacing: "-0.02em",
                color: INK,
                margin: 0,
              }}
            >
              The Dossier
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

        {/* Kicker */}
        <div
          style={{
            fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
            fontSize: 11,
            letterSpacing: "0.32em",
            color: ACCENT,
            textTransform: "uppercase",
            marginBottom: 16,
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <span style={{ width: 28, height: 1, background: ACCENT, display: "inline-block" }} />
          Algorithmic Reconstruction · Classified
        </div>

        <p
          style={{
            fontFamily: "var(--font-body, Georgia, serif)",
            fontSize: "clamp(18px, 2vw, 22px)",
            lineHeight: 1.6,
            color: "#3a3024",
            maxWidth: "58ch",
            margin: "0 0 72px",
          }}
        >
          Each block below is a finding. The staff analyst reconstructed these
          from the raw data your export contained &mdash; behavioral traces, declared
          signals, and the gap between what you said and what you did.
        </p>

        {/* Block cards */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 0,
          }}
        >
          {narrativeBlocksToRender(narrativeBlocks).map((block, i) => (
            <BlockCard key={block.id} block={block} index={i} />
          ))}
        </div>

        {/* Footer rule */}
        <footer
          style={{
            marginTop: 100,
            paddingTop: 24,
            borderTop: `1px solid ${RULE}`,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 9,
              letterSpacing: "0.28em",
              color: INK_GHOST,
              textTransform: "uppercase",
            }}
          >
            End of Report · The Glass House · Vol. I
          </div>
          <div
            style={{
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 9,
              letterSpacing: "0.2em",
              color: INK_GHOST,
              textTransform: "uppercase",
            }}
          >
            Generated by Algorithmic Mirror
          </div>
        </footer>
      </div>
    </div>
  );
}

function narrativeBlocksToRender(blocks: NarrativeBlock[]): NarrativeBlock[] {
  return blocks ?? [];
}
