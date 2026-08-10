"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import type { GhostProfile } from "../GhostProfileHUD";
import { ClaimsPanel } from "../ClaimsPanel";
import { ACCENT, DashboardPanel, SectionTitle } from "../dashboardPrimitives";

export function ClaimsTab({ profile }: { profile: GhostProfile }) {
  return (
    <div>
      <DashboardPanel label="Evidence Log" accent={ACCENT}>
        <SectionTitle>Every Claim, By Tier</SectionTitle>
        <ClaimsPanel claims={profile.claims} />
      </DashboardPanel>
    </div>
  );
}
