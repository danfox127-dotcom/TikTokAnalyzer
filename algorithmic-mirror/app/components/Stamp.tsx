"use client";
/**
 * WP-3.4a — small stateless wax-seal stamp graphic + label. Reused for the
 * pre-reveal "SEALED" cover on TargetingCard's ok state, and permanently on
 * its insufficient_evidence state ("INSUFFICIENT EVIDENCE"). No motion baked
 * in — callers decide whether/how it animates.
 */
import { ACCENT } from "./dashboardPrimitives";

export interface StampProps {
  label: string;
}

export function Stamp({ label }: StampProps) {
  return (
    <div
      style={{
        width: 90,
        height: 90,
        borderRadius: "50%",
        background: `radial-gradient(circle at 35% 30%, ${ACCENT}, #6b1818)`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "#f5efe4",
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        textAlign: "center",
        boxShadow: "0 3px 6px rgba(0,0,0,0.3)",
        transform: "rotate(4deg)",
        padding: 8,
        fontFamily: "var(--font-mono, monospace)",
      }}
    >
      {label}
    </div>
  );
}
