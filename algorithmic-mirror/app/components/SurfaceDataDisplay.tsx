"use client";

import { motion, useInView, type Variants } from "framer-motion";
import { useRef, useEffect, useState } from "react";
import { Eye, Hash, Search, Users, Heart, ShoppingBag, ChevronDown } from "lucide-react";
import type { GhostProfile } from "./GhostProfileHUD";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Props {
  profile: GhostProfile;
  onReveal: () => void;
}

// ---------------------------------------------------------------------------
// Animation helpers
// ---------------------------------------------------------------------------

const EASE_OUT_QUINT: [number, number, number, number] = [0.22, 1, 0.36, 1];

const stagger: { container: Variants; item: Variants } = {
  container: {
    hidden: {},
    show: { transition: { staggerChildren: 0.07, delayChildren: 0.1 } },
  },
  item: {
    hidden: { opacity: 0, y: 18 },
    show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE_OUT_QUINT } },
  },
};

const tagStagger: { container: Variants; item: Variants } = {
  container: {
    hidden: {},
    show: { transition: { staggerChildren: 0.04, delayChildren: 0.2 } },
  },
  item: {
    hidden: { opacity: 0, scale: 0.88 },
    show: { opacity: 1, scale: 1, transition: { duration: 0.3, ease: "easeOut" as const } },
  },
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TagCloud({ tags, accent }: { tags: string[]; accent?: string }) {
  const color = accent ?? "#b07040";
  return (
    <motion.div
      variants={tagStagger.container}
      initial="hidden"
      animate="show"
      className="flex flex-wrap gap-2 mt-3"
    >
      {tags.slice(0, 24).map((tag, i) => (
        <motion.span
          key={`${tag}-${i}`}
          variants={tagStagger.item}
          style={{
            display: "inline-block",
            fontSize: 12,
            padding: "4px 10px",
            background: `${color}14`,
            border: `1px solid ${color}38`,
            borderRadius: 3,
            color: color,
            fontFamily: "system-ui, sans-serif",
            letterSpacing: "0.02em",
          }}
        >
          {tag}
        </motion.span>
      ))}
    </motion.div>
  );
}

function PermissionRow({
  icon: Icon,
  label,
  sub,
  granted,
}: {
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
  label: string;
  sub: string;
  granted: boolean;
}) {
  return (
    <motion.div
      variants={stagger.item}
      className="flex items-start gap-3 py-3.5"
      style={{ borderBottom: "1px solid rgba(180,170,160,0.14)" }}
    >
      <div
        style={{
          width: 36, height: 36, borderRadius: 9,
          background: granted ? "rgba(220,60,60,0.08)" : "rgba(60,180,100,0.08)",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}
      >
        <Icon size={17} style={{ color: granted ? "#c84" : "#4a9" }} />
      </div>
      <div className="flex-1 min-w-0">
        <p style={{ fontSize: 13, color: "#1a1410", fontWeight: 500, marginBottom: 2, lineHeight: 1.4 }}>{label}</p>
        <p style={{ fontSize: 12, color: "#8a7e72", lineHeight: 1.45 }}>{sub}</p>
      </div>
      <span style={{
        fontSize: 11, fontWeight: 600,
        color: granted ? "#c66" : "#4a9",
        letterSpacing: "0.04em", marginTop: 1, flexShrink: 0,
      }}>
        {granted ? "COLLECTED" : "NOT COLLECTED"}
      </span>
    </motion.div>
  );
}

function AnimatedCount({ target }: { target: number }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let frame: number;
    const start = performance.now();
    const duration = 1200;
    const animate = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(ease * target));
      if (t < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [target]);
  return <>{display.toLocaleString()}</>;
}

function SurfaceCard({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.6, ease: EASE_OUT_QUINT }}
      style={{
        background: "rgba(255,255,255,0.72)",
        border: "1px solid rgba(180,160,130,0.22)",
        borderRadius: 12,
        padding: "20px 22px",
        marginBottom: 16,
        backdropFilter: "blur(8px)",
      }}
    >
      {children}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function SurfaceDataDisplay({ profile, onReveal }: Props) {
  const signals = profile.declared_signals;
  const adProfile = profile.ad_profile;

  // Scroll-triggered reveal — fires once when the sentinel enters viewport
  const sentinelRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(sentinelRef, { once: true, margin: "-10% 0px" });
  const hasRevealedRef = useRef(false);

  useEffect(() => {
    if (isInView && !hasRevealedRef.current) {
      hasRevealedRef.current = true;
      // Small delay so user sees the transition start
      setTimeout(onReveal, 300);
    }
  }, [isInView, onReveal]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
      style={{
        minHeight: "100vh",
        background: "linear-gradient(160deg, #faf8f5 0%, #f2ede6 55%, #ece4d8 100%)",
        fontFamily: "system-ui, -apple-system, sans-serif",
        padding: "0 0 0",
      }}
    >
      {/* Ambient oculus — Bespin ceiling ref */}
      <div aria-hidden style={{
        position: "fixed", top: "-30vh", left: "50%", transform: "translateX(-50%)",
        width: "70vw", height: "70vw", maxWidth: 900, maxHeight: 900, borderRadius: "50%",
        background: "radial-gradient(ellipse, rgba(255,220,180,0.28) 0%, rgba(255,200,150,0.08) 50%, transparent 75%)",
        pointerEvents: "none", zIndex: 0,
      }} />

      {/* Dot grid — Cloud City ceiling */}
      <div aria-hidden style={{
        position: "fixed", top: 0, left: 0, right: 0, height: "40vh",
        backgroundImage: `radial-gradient(circle, rgba(180,160,130,0.18) 2px, transparent 2px)`,
        backgroundSize: "36px 36px", backgroundPosition: "center top",
        pointerEvents: "none", zIndex: 0,
        maskImage: "linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, transparent 100%)",
        WebkitMaskImage: "linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, transparent 100%)",
      }} />

      <div style={{ position: "relative", zIndex: 1, maxWidth: 560, margin: "0 auto", padding: "0 20px 60px" }}>

        {/* ── HEADER ────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: EASE_OUT_QUINT }}
          style={{ paddingTop: 72, marginBottom: 36, textAlign: "center" }}
        >
          <p style={{ fontSize: 11, letterSpacing: "0.2em", color: "#b0a090", textTransform: "uppercase", marginBottom: 10, fontWeight: 600 }}>
            TIKTOK DATA EXPORT
          </p>
          <h1 style={{ fontSize: 32, fontWeight: 300, color: "#1a1410", lineHeight: 1.2, letterSpacing: "-0.02em", marginBottom: 12 }}>
            Here&rsquo;s what you<br />
            <em style={{ fontStyle: "italic", fontWeight: 400 }}>told</em> TikTok about yourself.
          </h1>
          <p style={{ fontSize: 14, color: "#8a7e72", lineHeight: 1.6, maxWidth: 380, margin: "0 auto" }}>
            This is the easy part — the data you entered directly. Interests you picked, things you searched. Keep scrolling.
          </p>
        </motion.div>

        {/* ── PROFILE STATS ─────────────────────────────────────── */}
        {signals && (signals.following_count > 0 || signals.follower_count > 0) && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6, ease: EASE_OUT_QUINT }}
            className="flex gap-4 mb-4"
          >
            {[
              { label: "Following", value: signals.following_count },
              { label: "Followers", value: signals.follower_count },
            ].map(({ label, value }) => (
              <div key={label} style={{
                flex: 1, background: "rgba(255,255,255,0.7)",
                border: "1px solid rgba(180,160,130,0.22)", borderRadius: 12,
                padding: "18px 20px", textAlign: "center", backdropFilter: "blur(8px)",
              }}>
                <p style={{ fontSize: 26, fontWeight: 300, color: "#1a1410", letterSpacing: "-0.03em" }}>
                  <AnimatedCount target={value} />
                </p>
                <p style={{ fontSize: 11, color: "#b0a090", letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 4 }}>
                  {label}
                </p>
              </div>
            ))}
          </motion.div>
        )}

        {/* ── DECLARED INTERESTS ────────────────────────────────── */}
        {signals?.settings_interests && signals.settings_interests.length > 0 && (
          <SurfaceCard delay={0.28}>
            <div className="flex items-center gap-2 mb-1">
              <Heart size={14} style={{ color: "#c0855a" }} />
              <p style={{ fontSize: 11, color: "#b0a090", letterSpacing: "0.12em", textTransform: "uppercase", fontWeight: 600 }}>
                Your Declared Interests
              </p>
            </div>
            <p style={{ fontSize: 12, color: "#a09080", marginBottom: 4 }}>
              You selected these in TikTok&rsquo;s onboarding.
            </p>
            <TagCloud tags={signals.settings_interests} accent="#b07040" />
          </SurfaceCard>
        )}

        {/* ── AD CATEGORIES ─────────────────────────────────────── */}
        {signals?.ad_interests && signals.ad_interests.length > 0 && (
          <SurfaceCard delay={0.34}>
            <div className="flex items-center gap-2 mb-1">
              <Hash size={14} style={{ color: "#8a7eb0" }} />
              <p style={{ fontSize: 11, color: "#b0a090", letterSpacing: "0.12em", textTransform: "uppercase", fontWeight: 600 }}>
                Ad Categories
              </p>
            </div>
            <p style={{ fontSize: 12, color: "#a09080", marginBottom: 4 }}>
              TikTok uses these to decide which ads you see.
            </p>
            <TagCloud tags={signals.ad_interests} accent="#7a70b0" />
          </SurfaceCard>
        )}

        {/* ── RECENT SEARCHES ───────────────────────────────────── */}
        {signals?.recent_searches && signals.recent_searches.length > 0 && (
          <SurfaceCard delay={0.40}>
            <div className="flex items-center gap-2 mb-1">
              <Search size={14} style={{ color: "#60a080" }} />
              <p style={{ fontSize: 11, color: "#b0a090", letterSpacing: "0.12em", textTransform: "uppercase", fontWeight: 600 }}>
                Recent Searches
              </p>
            </div>
            <p style={{ fontSize: 12, color: "#a09080", marginBottom: 4 }}>
              The last {Math.min(signals.recent_searches.length, 24)} things you searched for.
            </p>
            <TagCloud tags={signals.recent_searches} accent="#408060" />
          </SurfaceCard>
        )}

        {/* ── TIKTOK SHOP ───────────────────────────────────────── */}
        {adProfile && adProfile.shop_order_count > 0 && (
          <SurfaceCard delay={0.46}>
            <div className="flex items-center gap-2 mb-1">
              <ShoppingBag size={14} style={{ color: "#b06040" }} />
              <p style={{ fontSize: 11, color: "#b0a090", letterSpacing: "0.12em", textTransform: "uppercase", fontWeight: 600 }}>
                TikTok Shop Orders
              </p>
            </div>
            <p style={{ fontSize: 12, color: "#a09080", marginBottom: 10 }}>
              {adProfile.shop_order_count} purchases on record. TikTok treats these as first-party purchase intent signals.
            </p>
            {adProfile.shop_products.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {adProfile.shop_products.slice(0, 6).map((p, i) => (
                  <div key={i} style={{
                    fontSize: 12, color: "#6a5e54", padding: "6px 10px",
                    background: "rgba(180,120,60,0.07)", borderRadius: 4,
                    borderLeft: "2px solid rgba(180,120,60,0.35)",
                  }}>
                    {p}
                  </div>
                ))}
              </div>
            )}
          </SurfaceCard>
        )}

        {/* ── APPLE ATT PERMISSION CARD ─────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.52, duration: 0.6, ease: EASE_OUT_QUINT }}
          style={{
            background: "rgba(255,255,255,0.88)",
            border: "1px solid rgba(180,160,130,0.28)",
            borderRadius: 16,
            padding: "22px 22px 10px",
            marginBottom: 20,
            backdropFilter: "blur(12px)",
          }}
        >
          {/* ATT-style app icon row */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
            <div style={{
              width: 48, height: 48, borderRadius: 11,
              background: "linear-gradient(135deg, #ee1d52, #010101)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 22, flexShrink: 0,
            }}>
              🎵
            </div>
            <div>
              <p style={{ fontSize: 14, color: "#1a1410", fontWeight: 600, marginBottom: 2 }}>TikTok</p>
              <p style={{ fontSize: 12, color: "#8a7e72" }}>would also like permission to track you</p>
            </div>
          </div>

          <p style={{ fontSize: 13, color: "#3a2e26", lineHeight: 1.6, marginBottom: 14 }}>
            Beyond what you told it, TikTok silently recorded everything you did — and you already said yes when you created the account.
          </p>

          <motion.div variants={stagger.container} initial="hidden" animate="show">
            <PermissionRow
              icon={Eye} label="Every video you watched"
              sub="How long, whether you replayed it, whether you skipped."
              granted={true}
            />
            <PermissionRow
              icon={Users} label="Who you follow vs. who TikTok shows you"
              sub="The algorithm tracks creators you chose vs. ones it pushed on you."
              granted={true}
            />
            <PermissionRow
              icon={Search} label="Your exact active hours"
              sub="What time of day you open the app — including late nights."
              granted={true}
            />
            <PermissionRow
              icon={Hash} label="Every immediate skip"
              sub="Content you rejected in under 3 seconds is used to refine your profile."
              granted={true}
            />
          </motion.div>
        </motion.div>

        {/* ── SCROLL TRIGGER ZONE ───────────────────────────────── */}
        {/*
          The ghost profile reveals when this section scrolls into view.
          No button — the act of scrolling to see more IS the decision.
        */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7, duration: 0.8 }}
          style={{ textAlign: "center", padding: "32px 0 16px" }}
        >
          <p style={{ fontSize: 13, color: "#8a7e72", lineHeight: 1.6, marginBottom: 6 }}>
            That was the surface layer.
          </p>
          <p style={{ fontSize: 13, color: "#8a7e72", lineHeight: 1.6, marginBottom: 24, fontStyle: "italic" }}>
            Keep scrolling to see what the algorithm actually built.
          </p>
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
          >
            <ChevronDown size={20} style={{ color: "#c0a888", margin: "0 auto", display: "block" }} />
          </motion.div>
        </motion.div>

        {/* Spacer that triggers the reveal when it enters viewport */}
        <div ref={sentinelRef} style={{ height: 120, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <motion.div
            style={{ width: "100%", height: 1, background: "linear-gradient(to right, transparent, rgba(180,140,80,0.3), transparent)" }}
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: 1, duration: 1.2, ease: EASE_OUT_QUINT }}
          />
        </div>

      </div>
    </motion.div>
  );
}
