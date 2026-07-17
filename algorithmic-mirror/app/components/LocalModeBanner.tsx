"use client";

import { ShieldCheck } from "lucide-react";
import type { GhostProfile } from "./GhostProfileHUD";

// Warm-paper dossier register (mirrors ForensicDashboard's private constants).
const BORDER = "rgba(26, 22, 16, 0.16)";
const INK = "#1a1610";
const INK_DIM = "rgba(26, 22, 16, 0.62)";
const INK_GHOST = "rgba(26, 22, 16, 0.4)";
const ACCENT = "#8b2323"; // oxblood

const mono = "var(--font-mono, monospace)";

const plural = (n: number) => (n === 1 ? "" : "s");

/**
 * Provenance strip for browser-local mode. States plainly that the raw export
 * never left the device, and names the two thin lookups that DID reach the server
 * — reflecting what actually happened (resolved, or offline/degraded). Honest by
 * construction: it reads the real flags rather than asserting "nothing leaves".
 */
export function LocalModeBanner({ profile }: { profile: GhostProfile }) {
  if (!profile._local_mode) return null;

  const cr = profile.creator_resolution;
  const logins = profile.digital_footprint?.recent_logins ?? [];
  const geoRan = logins.some((l) => l.city !== undefined);
  const ipsSent = new Set(logins.filter((l) => l.ip).map((l) => l.ip)).size;

  // Each provenance line: what left the device, and what came back.
  const lines: { sent: string; got: string; ok: boolean }[] = [];
  lines.push(
    cr
      ? { sent: `${cr.total} creator video ID${plural(cr.total)}`, got: `${cr.resolved} creator name${plural(cr.resolved)} resolved`, ok: true }
      : { sent: "creator video IDs", got: "not resolved — offline", ok: false },
  );
  lines.push(
    geoRan && ipsSent > 0
      ? { sent: `${ipsSent} login IP${plural(ipsSent)}`, got: "city labels", ok: true }
      : { sent: "login IPs", got: "not resolved — offline", ok: false },
  );

  const fullyOffline = lines.every((l) => !l.ok);

  return (
    <div
      style={{
        marginBottom: 32,
        padding: "14px 18px",
        border: `1px solid ${BORDER}`,
        background: "rgba(139, 35, 35, 0.035)",
        display: "flex",
        gap: 14,
        alignItems: "flex-start",
      }}
    >
      <ShieldCheck size={16} color={ACCENT} style={{ flexShrink: 0, marginTop: 2 }} strokeWidth={1.75} />
      <div style={{ minWidth: 0 }}>
        <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.3em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 6 }}>
          Provenance · Analyzed on this device
        </div>
        <div style={{ fontSize: 12.5, color: INK, lineHeight: 1.55, marginBottom: fullyOffline ? 0 : 8 }}>
          Your TikTok export was read and analyzed here in your browser — it was{" "}
          <span style={{ fontStyle: "italic" }}>never uploaded</span>.
          {fullyOffline
            ? " This run was fully offline: nothing at all left this device."
            : " The only things sent to our server:"}
        </div>
        {!fullyOffline && (
          <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 4 }}>
            {lines.map((l, i) => (
              <li key={i} style={{ fontSize: 11.5, color: INK_DIM, lineHeight: 1.5, display: "flex", gap: 8, alignItems: "baseline" }}>
                <span style={{ color: l.ok ? ACCENT : INK_GHOST, fontFamily: mono, fontSize: 10, flexShrink: 0 }}>
                  {l.ok ? "→" : "·"}
                </span>
                <span>
                  <span style={{ color: INK }}>{l.sent}</span>
                  <span style={{ color: INK_GHOST }}> — {l.got}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
