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
  const ips = [...new Set(logins.filter((l) => l.ip).map((l) => l.ip as string))];

  // Show the actual IPs (the user's own data) so "what was shared" is concrete
  // and verifiable, not a vague count. Cap the display so long lists don't sprawl.
  const shownIps = ips.slice(0, 4);
  const moreIps = ips.length - shownIps.length;
  const ipList = shownIps.join(", ") + (moreIps > 0 ? `, +${moreIps} more` : "");

  // Each provenance line names EXACTLY what left the device, and what came back.
  const lines: { primary: string; detail: string; ok: boolean }[] = [];
  lines.push(
    cr
      ? {
          primary: `${cr.total} TikTok video ID number${plural(cr.total)}`,
          detail: `just the numeric IDs of creators you watched — no titles, captions, or timestamps. ${cr.resolved} creator name${plural(cr.resolved)} came back.`,
          ok: true,
        }
      : { primary: "creator video IDs", detail: "not resolved — offline.", ok: false },
  );
  lines.push(
    geoRan && ips.length > 0
      ? {
          primary: `your login IP address${ips.length === 1 ? "" : "es"}`,
          detail: `${ipList} — city + country came back.`,
          ok: true,
        }
      : { primary: "login IP addresses", detail: "not resolved — offline.", ok: false },
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
          Your TikTok export was analyzed here in your browser — the file was{" "}
          <span style={{ fontStyle: "italic" }}>never uploaded</span>.
          {fullyOffline
            ? " This run was fully offline: nothing at all was sent."
            : " Exactly what was sent to our server:"}
        </div>
        {!fullyOffline && (
          <ul style={{ margin: "0 0 8px", padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 5 }}>
            {lines.map((l, i) => (
              <li key={i} style={{ fontSize: 11.5, color: INK_DIM, lineHeight: 1.5, display: "flex", gap: 8, alignItems: "baseline" }}>
                <span style={{ color: l.ok ? ACCENT : INK_GHOST, fontFamily: mono, fontSize: 10, flexShrink: 0 }}>
                  {l.ok ? "→" : "·"}
                </span>
                <span>
                  <span style={{ color: INK }}>{l.primary}</span>
                  <span style={{ color: INK_GHOST }}> — {l.detail}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
        {/* Bound the disclosure: name what specifically did NOT leave. */}
        <div style={{ fontSize: 11.5, color: INK_DIM, lineHeight: 1.5 }}>
          Your watch history, likes, searches, comments, and messages never left this device.
        </div>
      </div>
    </div>
  );
}
