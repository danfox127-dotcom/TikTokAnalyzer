"use client";
/**
 * WP-3.2 — Evidence Log. Surfaces profile.claims (the WP-1.5 output — skip rate,
 * night shift, archetype, dissonance, etc.), grouped by tier. This data has never
 * been rendered anywhere before this panel.
 */
import type { Claim, Tier } from "../../engine/types";
import { ClaimStat } from "./ClaimStat";
import { tierMeta } from "./claimStyle";

const TIER_ORDER: Tier[] = ["recorded", "derived", "inferred"];

function labelFor(id: string): string {
  const last = id.split(".").pop() ?? id;
  return last.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function ClaimsPanel({ claims }: { claims?: Claim[] }) {
  if (!claims || claims.length === 0) {
    return <div style={{ fontSize: 12, color: "rgba(26,22,16,0.62)", fontStyle: "italic" }}>No claims in this payload.</div>;
  }

  const byTier = new Map<Tier, Claim[]>();
  for (const c of claims) {
    if (!byTier.has(c.tier)) byTier.set(c.tier, []);
    byTier.get(c.tier)!.push(c);
  }

  const counts = TIER_ORDER.map((t) => `${byTier.get(t)?.length ?? 0} ${tierMeta(t).label.toLowerCase()}`).join(" · ");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ fontSize: 12, color: "rgba(26,22,16,0.62)" }}>{counts}</div>
      {TIER_ORDER.map((tier) => {
        const group = byTier.get(tier);
        if (!group || group.length === 0) return null;
        return (
          <div key={tier} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: tierMeta(tier).color }}>
              {tierMeta(tier).label}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10 }}>
              {group.map((c) => <ClaimStat key={c.id} claim={c} label={labelFor(c.id)} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
