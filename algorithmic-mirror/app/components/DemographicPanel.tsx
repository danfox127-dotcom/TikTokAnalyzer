"use client";
/**
 * WP-2.3 — minimal Demographic panel. Renders the five inference cards from payload
 * alone (ok / insufficient_evidence per card; error at the module level). Each card
 * shows the "TikTok is documented to infer this · PIPEDA #2025-003" line plus the
 * reconstructed value + tier. The polished redaction-reveal panel is WP-3.4.
 */
import { ShieldAlert, Lock, AlertTriangle } from "lucide-react";
import type { DemographicModuleResult, DemographicCard } from "../../engine/demographics";
import { ClaimText } from "./ClaimText";

const BORDER = "rgba(26, 22, 16, 0.16)";
const INK = "#1a1610";
const INK_DIM = "rgba(26, 22, 16, 0.62)";
const ACCENT = "#8b2323";

const LABELS: Record<DemographicCard["category"], string> = {
  interests: "Interests", location: "Location", age: "Age range", gender: "Gender", spending: "Spending power",
};


function Card({ card }: { card: DemographicCard }) {
  return (
    <div style={{ padding: "12px 14px", border: `1px solid ${BORDER}`, display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ fontWeight: 600, color: INK }}>{LABELS[card.category]}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: INK_DIM }}>
        <ShieldAlert size={13} /> TikTok is documented to infer this · {card.tiktok_infers.citation}
      </div>
      {card.status === "ok" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {card.claims.map((c) => (
            <div key={c.id} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <ClaimText claim={c} />
              <div style={{ fontSize: 10, color: INK_DIM }}>{c.method}</div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: "flex", gap: 6, alignItems: "flex-start", fontSize: 11, color: INK_DIM }}>
          <Lock size={13} style={{ marginTop: 1, flexShrink: 0 }} />
          <span>Not enough in your export to reconstruct this. Needs {card.requirements?.needed}; have {card.requirements?.had}.</span>
        </div>
      )}
    </div>
  );
}

export function DemographicPanel({ result }: { result?: DemographicModuleResult }) {
  if (!result) return null;
  if (result.status === "error") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: INK_DIM, fontSize: 12 }}>
        <AlertTriangle size={15} /> Demographic analysis unavailable ({result.error ?? "error"}).
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
      {result.cards.map((c) => <Card key={c.category} card={c} />)}
    </div>
  );
}
