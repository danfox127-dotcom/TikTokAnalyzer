"use client";
/**
 * WP-3.1 — thin orchestrator. All rendering logic lives in DossierShell.tsx
 * and the extracted tab components; this file exists to keep the public
 * `ForensicDashboard` import path stable for existing callers (page.tsx).
 */
import type { GhostProfile } from "./GhostProfileHUD";
import { DossierShell } from "./DossierShell";

interface Props {
  profile: GhostProfile;
  onReset: () => void;
  sourceFile?: File;
}

export function ForensicDashboard(props: Props) {
  return <DossierShell {...props} />;
}
