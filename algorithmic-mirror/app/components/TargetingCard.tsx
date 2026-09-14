"use client";
/**
 * WP-2.2 — Targeting Card. Renders the three InsightModuleResult states from
 * payload alone.
 * WP-3.4a — ok state gets a one-shot wax-seal reveal on mount; insufficient_evidence
 * gets a permanent "INSUFFICIENT EVIDENCE" stamp alongside its existing copy.
 */
import { useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { ShieldCheck, ShieldAlert, Lock, AlertTriangle } from "lucide-react";
import type { TargetingCardResult, TargetingSegment } from "../../engine/targetingCard";
import { ClaimText } from "./ClaimText";
import { Stamp } from "./Stamp";

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
      <ClaimText claim={seg}>{seg.evidence.length} watched videos</ClaimText>
      <div style={{ fontSize: 10, color: INK_DIM }}>{seg.method}</div>
    </div>
  );
}

/**
 * Spec WP-3.4a §5: the seal "never re-seals — no re-trigger on re-render,
 * tab-switch, or data scrub". DossierShell renders tab bodies as
 * `{activeTab === "interests" && <InterestsTab/>}`, so this component is
 * unmounted whenever the user looks at another tab and ordinary useState would
 * reset. Module scope outlives the remount; a page reload starts sealed again,
 * which is the intended once-per-visit reveal.
 *
 * Safe under SSR despite being module-level mutable state: the only writer is
 * the seal's onAnimationComplete, which never runs on the server, so a server
 * render always emits the sealed markup and hydration matches.
 */
let sealAlreadyBroken = false;

/** Test seam: restore the pre-reveal state. Not used by application code. */
export function __resetTargetingCardSeal() {
  sealAlreadyBroken = false;
}

export function TargetingCard({ result }: { result?: TargetingCardResult }) {
  const prefersReducedMotion = useReducedMotion();
  const [hasRevealed, setHasRevealed] = useState(sealAlreadyBroken);
  const revealed = Boolean(prefersReducedMotion) || hasRevealed;
  const showStamp = !revealed;
  const contentTransition = prefersReducedMotion
    ? { duration: 0 }
    : { duration: 0.4, ease: "easeOut" as const, delay: 0.15 };

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
      <div style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "center" }}>
        <Stamp label="INSUFFICIENT EVIDENCE" />
        <div style={{ display: "flex", gap: 8, color: INK_DIM, fontSize: 12, alignItems: "flex-start" }}>
          <Lock size={15} style={{ marginTop: 2, flexShrink: 0 }} />
          <span>
            Run topic analysis with your own key to see exactly what advertisers can target.
            <br />
            <span style={{ fontSize: 11 }}>Needs {result.requirements?.needed}; have {result.requirements?.had}.</span>
          </span>
        </div>
      </div>
    );
  }

  const { counts } = result;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, position: "relative" }}>
      <AnimatePresence>
        {showStamp && (
          <motion.div
            key="seal"
            initial={{ scale: 1, opacity: 1 }}
            animate={{ scale: 1.15, opacity: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            onAnimationComplete={() => {
              sealAlreadyBroken = true;
              setHasRevealed(true);
            }}
            // Overlay, not a flow item. As a flex child the seal added its own
            // height to the card and the content snapped upward when it
            // unmounted; the container's `position: relative` exists for this.
            style={{
              position: "absolute",
              inset: 0,
              zIndex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Stamp label="SEALED" />
          </motion.div>
        )}
      </AnimatePresence>
      <motion.div
        // Animates from mount rather than waiting on `revealed`. Gating it on
        // the seal's onAnimationComplete made the two run in sequence: the
        // seal vanished at 0.4s and the content only began its 0.15s-delayed
        // fade afterwards, leaving the card blank in between. Spec §5 wants
        // them concurrent — seal out over 0.4s, content in over 0.15s-0.55s,
        // so the stamp is gone just before the content reaches full opacity.
        initial={{ opacity: prefersReducedMotion ? 1 : 0 }}
        animate={{ opacity: 1 }}
        transition={contentTransition}
        style={{ display: "flex", flexDirection: "column", gap: 12 }}
      >
        <p style={{ fontSize: 12, color: INK_DIM }}>
          TikTok admits <strong style={{ color: INK }}>{counts.declared_ad_interest_count}</strong> interest categories;
          your watched behavior surfaced <strong style={{ color: INK }}>{counts.segment_count}</strong> targetable
          segments, <strong style={{ color: INK }}>{counts.confirmed_count}</strong> already on TikTok&apos;s list.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {result.claims.map((s) => <Segment key={s.id} seg={s} />)}
        </div>
      </motion.div>
    </div>
  );
}
