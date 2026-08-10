// algorithmic-mirror/app/components/ClaimText.tsx
"use client";
/**
 * WP-3.2 — inline, unboxed Claim renderer. For embedding inside a panel that
 * already owns its own bordered container (e.g. TargetingCard's Segment,
 * DemographicPanel's Card) — do NOT nest this inside ClaimStat or another box.
 */
import { useState } from "react";
import type { Claim } from "../../engine/types";
import { tierMeta, renderClaimValue } from "./claimStyle";
import { EvidencePanel } from "./EvidencePanel";

export function ClaimText({ claim, children }: { claim: Claim; children?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const meta = tierMeta(claim.tier);
  return (
    <>
      <span
        onClick={() => setOpen(true)}
        role="button"
        tabIndex={0}
        style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12 }}
      >
        <span className={meta.className} style={{ padding: "1px 2px" }}>
          {children ?? renderClaimValue(claim.value)}
        </span>
        <span style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.08em", color: meta.color }}>
          {meta.label}
        </span>
      </span>
      <EvidencePanel open={open} title={null} claim={null} payload={null} claimObj={claim} onClose={() => setOpen(false)} />
    </>
  );
}
