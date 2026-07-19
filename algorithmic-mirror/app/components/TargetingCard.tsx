"use client";
/**
 * WP-2.2 — minimal, functional Targeting Card. Renders the three InsightModuleResult
 * states from payload alone. Deliberately unstyled beyond the shared warm-paper
 * register; the animated case-file panel is WP-3.4.
 */
import { ShieldCheck, ShieldAlert, Lock, AlertTriangle } from "lucide-react";
import type { TargetingCardResult, TargetingSegment } from "../../engine/targetingCard";

const BORDER = "rgba(26, 22, 16, 0.16)";
const INK = "#1a1610";
const INK_DIM = "rgba(26, 22, 16, 0.62)";
const ACCENT = "#8b2323";

function Segment({ seg }: { seg: TargetingSegment }) {
  const v = seg.value;
  return (
    <div style={{ padding: "10px 12px", border: `1px solid ${BORDER}`, display: "flex",
      flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600, color: INK }}>{v.category}</span>
        {v.tiktok_confirmed ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: ACCENT }}>
            <ShieldCheck size={13} /> TikTok confirms
          </span>
        ) : (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: INK_DIM }}>
            <ShieldAlert size={13} /> inferred-only
          </span>
        )}
      </div>
      <div style={{ fontSize: 11, color: INK_DIM }}>
        {seg.evidence.length} watched videos · confidence {seg.confidence}
      </div>
      <div style={{ fontSize: 10, color: INK_DIM }}>{seg.method}</div>
    </div>
  );
}

export function TargetingCard({ result }: { result?: TargetingCardResult }) {
  if (!result) return null;

  if (result.status === "error") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: INK_DIM, fontSize: 12 }}>
        <AlertTriangle size={15} /> Targeting analysis unavailable ({result.error ?? "error"}).
      </div>
    );
  }

  if (result.status === "insufficient_evidence") {
    return (
      <div style={{ display: "flex", gap: 8, color: INK_DIM, fontSize: 12, alignItems: "flex-start" }}>
        <Lock size={15} style={{ marginTop: 2, flexShrink: 0 }} />
        <span>
          Run topic analysis with your own key to see exactly what advertisers can target.
          <br />
          <span style={{ fontSize: 11 }}>Needs {result.requirements?.needed}; have {result.requirements?.had}.</span>
        </span>
      </div>
    );
  }

  const { counts } = result;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <p style={{ fontSize: 12, color: INK_DIM }}>
        TikTok admits <strong style={{ color: INK }}>{counts.declared_ad_interest_count}</strong> interest categories;
        your watched behavior surfaced <strong style={{ color: INK }}>{counts.segment_count}</strong> targetable
        segments, <strong style={{ color: INK }}>{counts.confirmed_count}</strong> already on TikTok&apos;s list.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {result.claims.map((s) => <Segment key={s.id} seg={s} />)}
      </div>
    </div>
  );
}
