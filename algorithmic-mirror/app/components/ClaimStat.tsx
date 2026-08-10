// algorithmic-mirror/app/components/ClaimStat.tsx
"use client";
/**
 * WP-3.2 — standalone stat-card Claim renderer (LABEL / VALUE / tier badge /
 * method), for panels with no pre-existing box, e.g. the Evidence Log grid.
 */
import { useState } from "react";
import type { Claim } from "../../engine/types";
import { tierMeta, renderClaimValue } from "./claimStyle";
import { EvidencePanel } from "./EvidencePanel";

export function ClaimStat({ claim, label, children }: { claim: Claim; label: string; children?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const meta = tierMeta(claim.tier);
  return (
    <>
      <div
        onClick={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen(true);
          }
        }}
        role="button"
        tabIndex={0}
        className={meta.className}
        style={{ padding: "10px 12px", cursor: "pointer", display: "flex", flexDirection: "column", gap: 4 }}
      >
        <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(26,22,16,0.62)" }}>
          {label}
        </div>
        <div style={{ fontSize: 16, fontWeight: 600, color: meta.color }}>
          {children ?? renderClaimValue(claim.value)}
        </div>
        <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.08em", color: meta.color }}>
          {meta.label}
        </div>
        <div style={{ fontSize: 10, color: "rgba(26,22,16,0.62)" }}>{claim.method}</div>
      </div>
      <EvidencePanel open={open} title={label} claim={null} payload={null} claimObj={claim} onClose={() => setOpen(false)} />
    </>
  );
}
