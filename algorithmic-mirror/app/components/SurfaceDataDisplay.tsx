"use client";

/**
 * SurfaceDataDisplay — Miami Day Art Deco
 *
 * The bright pre-transition page. Renders only what the user explicitly
 * handed over to TikTok — declared interests, ad categories, recent searches,
 * shop history, and the four-line ATT-style permission card that summarizes
 * what they agreed to silently.
 *
 * Voice + caption strings live in app/copy/explanations.ts. Don't put copy
 * inline; pull it through `caption('surface.…')` so we have a single source
 * of truth for the newsroom register.
 *
 * Public contract (do not change without coordinating with page.tsx):
 *   - Props: { profile, onReveal }
 *   - Behavior: the sentinel near the bottom calls onReveal() once when it
 *     enters the viewport, triggering the bright→dark transition.
 *
 * Iconography: lucide-react only. See AGENTS.md.
 */

import { motion, useInView, type Variants } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import {
  Bell,
  ChevronDown,
  Compass,
  Cpu,
  Eye,
  Hash,
  Heart,
  IdCard,
  Info,
  Music,
  Palette,
  Plane,
  Search,
  Settings,
  ShoppingBag,
  Tag,
  Users,
} from "lucide-react";
import type { GhostProfile } from "./GhostProfileHUD";
import { caption } from "../copy/explanations";

// ---------------------------------------------------------------------------
// Public contract
// ---------------------------------------------------------------------------

interface Props {
  profile: GhostProfile;
  onReveal: () => void;
}

// ---------------------------------------------------------------------------
// Design tokens — Miami Day Art Deco
// ---------------------------------------------------------------------------

const TOKENS = {
  ink: "#1a1410",                  // text + 4px frame
  body: "#3a2e26",
  muted: "#5a4d44",
  paper: "#fbf8ff",
  surface: "#ffffff",
  surfaceAlt: "#fafaff",
  primary: "#9c4141",              // deep coral
  primaryContainer: "#f28482",     // bright coral — primary offset shadow
  secondary: "#45645e",            // deep teal
  secondaryContainer: "#c7eae1",   // mint — secondary offset shadow
  accent: "#7a70b0",               // violet for advertiser data
  edge: "rgba(26,20,16,0.18)",
} as const;

/** 4px black frame + 6px coral offset shadow — the "art-deco-border" of the mock. */
const decoFrame = (shadow: string = TOKENS.primaryContainer): React.CSSProperties => ({
  border: `4px solid ${TOKENS.ink}`,
  boxShadow: `6px 6px 0 0 ${shadow}`,
});

/** Inverted notch corners — used sparingly on accent panels. */
const decoClip: React.CSSProperties = {
  clipPath:
    "polygon(10px 0, 100% 0, 100% calc(100% - 10px), calc(100% - 10px) 100%, 0 100%, 0 10px)",
};

const FONT_DISPLAY =
  "var(--font-deco-display, 'Epilogue', 'Inter', system-ui, sans-serif)";
const FONT_LABEL =
  "var(--font-deco-label, 'Space Grotesk', 'Inter', system-ui, sans-serif)";
const FONT_BODY =
  "var(--font-deco-body, 'Be Vietnam Pro', 'Inter', system-ui, sans-serif)";

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
    show: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.5, ease: EASE_OUT_QUINT },
    },
  },
};

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

/** A bordered, offset-shadow panel. The visual unit of the page. */
function DecoPanel({
  children,
  shadow = TOKENS.primaryContainer,
  background = TOKENS.surface,
  style,
  className,
}: {
  children: React.ReactNode;
  shadow?: string;
  background?: string;
  style?: React.CSSProperties;
  className?: string;
}) {
  return (
    <div
      className={className}
      style={{
        background,
        ...decoFrame(shadow),
        padding: "20px 22px",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** Caps label with optional lucide icon — the "label-caps" of the mock. */
function CapsLabel({
  children,
  icon: Icon,
  color = TOKENS.ink,
}: {
  children: React.ReactNode;
  icon?: React.ComponentType<{ size?: number; color?: string }>;
  color?: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontFamily: FONT_LABEL,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: "0.16em",
        textTransform: "uppercase",
        color,
      }}
    >
      {Icon ? <Icon size={14} color={color} /> : null}
      <span>{children}</span>
    </div>
  );
}

/** A short newsroom subhed under a label. */
function PanelLede({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontFamily: FONT_BODY,
        fontSize: 13,
        lineHeight: 1.55,
        color: TOKENS.muted,
        margin: "6px 0 14px",
      }}
    >
      {children}
    </p>
  );
}

/** A horizontal divider styled as a 2px ink rule (deco header underline). */
function HeadingRule() {
  return (
    <div
      aria-hidden
      style={{
        height: 2,
        background: TOKENS.ink,
        margin: "10px 0 14px",
      }}
    />
  );
}

/** A pill-style tag inside the deco language — flat, hard-bordered. */
function DecoTag({
  children,
  accent = TOKENS.primaryContainer,
}: {
  children: React.ReactNode;
  accent?: string;
}) {
  return (
    <motion.span
      variants={stagger.item}
      style={{
        display: "inline-block",
        fontFamily: FONT_LABEL,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color: TOKENS.ink,
        background: accent,
        border: `2px solid ${TOKENS.ink}`,
        padding: "5px 10px",
      }}
    >
      {children}
    </motion.span>
  );
}

function TagCloud({
  tags,
  accent = TOKENS.primaryContainer,
}: {
  tags: string[];
  accent?: string;
}) {
  return (
    <motion.div
      variants={stagger.container}
      initial="hidden"
      animate="show"
      style={{ display: "flex", flexWrap: "wrap", gap: 8 }}
    >
      {tags.slice(0, 24).map((t, i) => (
        <DecoTag key={`${t}-${i}`} accent={accent}>
          {t}
        </DecoTag>
      ))}
    </motion.div>
  );
}

/** Animated count for stat tiles. */
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

/** Stat tile — number above caps label, deco-framed. */
function StatTile({
  value,
  label,
  shadow = TOKENS.primaryContainer,
}: {
  value: number;
  label: string;
  shadow?: string;
}) {
  return (
    <DecoPanel
      shadow={shadow}
      style={{
        flex: 1,
        textAlign: "center",
        padding: "20px 18px",
      }}
    >
      <p
        style={{
          fontFamily: FONT_DISPLAY,
          fontWeight: 900,
          fontSize: 38,
          lineHeight: 1,
          letterSpacing: "-0.03em",
          color: TOKENS.ink,
          margin: 0,
        }}
      >
        <AnimatedCount target={value} />
      </p>
      <p
        style={{
          fontFamily: FONT_LABEL,
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: TOKENS.muted,
          marginTop: 8,
        }}
      >
        {label}
      </p>
    </DecoPanel>
  );
}

/** Settings interest tile — lucide icon + caps label, hard-bordered. */
function InterestTile({
  icon: Icon,
  label,
  background,
}: {
  icon: React.ComponentType<{ size?: number; color?: string }>;
  label: string;
  background: string;
}) {
  return (
    <motion.div
      variants={stagger.item}
      style={{
        background,
        border: `2px solid ${TOKENS.ink}`,
        padding: "14px 8px",
        minHeight: 92,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
      }}
    >
      <Icon size={22} color={TOKENS.ink} />
      <span
        style={{
          fontFamily: FONT_LABEL,
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: TOKENS.ink,
          textAlign: "center",
          lineHeight: 1.2,
        }}
      >
        {label}
      </span>
    </motion.div>
  );
}

/** A single ATT-style permission row inside the permission card. */
function PermissionRow({
  icon: Icon,
  label,
  sub,
  granted,
}: {
  icon: React.ComponentType<{ size?: number; color?: string }>;
  label: string;
  sub: string;
  granted: boolean;
}) {
  return (
    <motion.div
      variants={stagger.item}
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        padding: "12px 0",
        borderBottom: `1px solid ${TOKENS.edge}`,
      }}
    >
      <div
        style={{
          width: 34,
          height: 34,
          background: granted ? TOKENS.primaryContainer : TOKENS.secondaryContainer,
          border: `2px solid ${TOKENS.ink}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <Icon size={16} color={TOKENS.ink} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          style={{
            fontFamily: FONT_BODY,
            fontSize: 13,
            fontWeight: 500,
            color: TOKENS.ink,
            lineHeight: 1.4,
            margin: 0,
          }}
        >
          {label}
        </p>
        <p
          style={{
            fontFamily: FONT_BODY,
            fontSize: 12,
            color: TOKENS.muted,
            lineHeight: 1.45,
            margin: "2px 0 0",
          }}
        >
          {sub}
        </p>
      </div>
      <span
        style={{
          fontFamily: FONT_LABEL,
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          color: granted ? TOKENS.primary : TOKENS.secondary,
          marginTop: 2,
          flexShrink: 0,
        }}
      >
        {granted ? "Collected" : "Not Collected"}
      </span>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Settings-interest mapping — the four onboarding categories the mock highlights.
// ---------------------------------------------------------------------------

const INTEREST_ICONS: Record<
  string,
  { icon: React.ComponentType<{ size?: number; color?: string }>; bg: string }
> = {
  design: { icon: Compass, bg: TOKENS.primaryContainer },
  art: { icon: Palette, bg: TOKENS.secondaryContainer },
  travel: { icon: Plane, bg: TOKENS.surfaceAlt },
  music: { icon: Music, bg: "#ffb3b0" },
};

/** Map a free-form interest string to a known lucide icon when possible. */
function resolveInterestIcon(raw: string): {
  label: string;
  icon: React.ComponentType<{ size?: number; color?: string }>;
  bg: string;
} {
  const key = raw.toLowerCase().trim();
  const match = Object.keys(INTEREST_ICONS).find((k) => key.includes(k));
  if (match) {
    return { label: raw, ...INTEREST_ICONS[match] };
  }
  // Fallback: tag icon, neutral surface.
  return { label: raw, icon: Tag, bg: TOKENS.surfaceAlt };
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function SurfaceDataDisplay({ profile, onReveal }: Props) {
  const signals = profile.declared_signals;
  const adProfile = profile.ad_profile;

  // Scroll-triggered reveal — fires once when sentinel enters viewport.
  const sentinelRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(sentinelRef, { once: true, margin: "-10% 0px" });
  const hasRevealedRef = useRef(false);

  useEffect(() => {
    if (isInView && !hasRevealedRef.current) {
      hasRevealedRef.current = true;
      const t = setTimeout(onReveal, 300);
      return () => clearTimeout(t);
    }
  }, [isInView, onReveal]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
      style={{
        minHeight: "100vh",
        background: TOKENS.paper,
        color: TOKENS.ink,
        fontFamily: FONT_BODY,
        position: "relative",
      }}
    >
      {/* ── Top app bar ─────────────────────────────────────────────────── */}
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          background: TOKENS.surface,
          borderBottom: `4px solid ${TOKENS.ink}`,
          boxShadow: `4px 4px 0 0 ${TOKENS.primaryContainer}`,
          padding: "16px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div
          style={{
            fontFamily: FONT_DISPLAY,
            fontWeight: 900,
            fontStyle: "italic",
            fontSize: 22,
            letterSpacing: "-0.02em",
            color: TOKENS.ink,
          }}
        >
          TIKTOK · DOSSIER
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <Bell size={20} color={TOKENS.ink} />
          <Settings size={20} color={TOKENS.ink} />
          <div
            aria-hidden
            style={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              background: TOKENS.primaryContainer,
              border: `2px solid ${TOKENS.ink}`,
              boxShadow: `3px 3px 0 0 ${TOKENS.secondaryContainer}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <IdCard size={16} color={TOKENS.ink} />
          </div>
        </div>
      </header>

      <div
        style={{
          position: "relative",
          maxWidth: 980,
          margin: "0 auto",
          padding: "48px 28px 80px",
        }}
      >
        {/* ── Hero ─────────────────────────────────────────────────────── */}
        <section
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1.1fr) minmax(0, 1fr)",
            gap: 32,
            alignItems: "center",
            paddingBottom: 40,
            marginBottom: 40,
            borderBottom: `4px solid ${TOKENS.ink}`,
          }}
        >
          <div>
            <p
              style={{
                fontFamily: FONT_LABEL,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.22em",
                textTransform: "uppercase",
                color: TOKENS.muted,
                marginBottom: 14,
              }}
            >
              {caption("surface.hero.kicker")}
            </p>
            <h1
              style={{
                fontFamily: FONT_DISPLAY,
                fontWeight: 900,
                fontSize: "clamp(52px, 8vw, 84px)",
                lineHeight: 1.0,
                letterSpacing: "-0.03em",
                color: TOKENS.ink,
                margin: 0,
                ...decoClip,
              }}
            >
              The
              <br />
              <span style={{ color: TOKENS.primaryContainer }}>Surface.</span>
            </h1>
            <p
              style={{
                fontFamily: FONT_BODY,
                fontSize: 16,
                lineHeight: 1.6,
                color: TOKENS.body,
                marginTop: 24,
                maxWidth: "32ch",
                borderLeft: `4px solid ${TOKENS.secondaryContainer}`,
                paddingLeft: 16,
              }}
            >
              {caption("surface.hero.lede")}
            </p>
          </div>
          <DecoPanel
            shadow={TOKENS.primaryContainer}
            background={TOKENS.surface}
            style={{ aspectRatio: "1.6", padding: 0, overflow: "hidden" }}
          >
            {/* Abstract Art Deco pattern — pure CSS, no image asset */}
            <div
              aria-hidden
              style={{
                width: "100%",
                height: "100%",
                background: `
                  repeating-linear-gradient(135deg,
                    ${TOKENS.primaryContainer} 0 24px,
                    ${TOKENS.surface} 24px 48px),
                  radial-gradient(circle at 70% 30%,
                    ${TOKENS.secondaryContainer} 0 80px,
                    transparent 81px)
                `,
                position: "relative",
              }}
            >
              <div
                aria-hidden
                style={{
                  position: "absolute",
                  inset: "20% 20%",
                  border: `3px solid ${TOKENS.ink}`,
                  background: TOKENS.surface,
                }}
              />
              <div
                aria-hidden
                style={{
                  position: "absolute",
                  inset: "32% 32%",
                  border: `2px solid ${TOKENS.ink}`,
                  background: TOKENS.primaryContainer,
                }}
              />
            </div>
          </DecoPanel>
        </section>

        {/* ── Stats row: Following / Followers ─────────────────────────── */}
        {signals && (signals.following_count > 0 || signals.follower_count > 0) && (
          <section
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 24,
              marginBottom: 32,
            }}
          >
            <StatTile
              value={signals.following_count}
              label={caption("surface.following_count")}
              shadow={TOKENS.primaryContainer}
            />
            <StatTile
              value={signals.follower_count}
              label={caption("surface.follower_count")}
              shadow={TOKENS.secondaryContainer}
            />
          </section>
        )}

        {/* ── Declared interests grid ──────────────────────────────────── */}
        {signals?.settings_interests && signals.settings_interests.length > 0 && (
          <DecoPanel
            shadow={TOKENS.primaryContainer}
            style={{ marginBottom: 24 }}
          >
            <CapsLabel icon={Heart}>
              {caption("surface.settings_interests.heading")}
            </CapsLabel>
            <PanelLede>{caption("surface.settings_interests.caption")}</PanelLede>
            <motion.div
              variants={stagger.container}
              initial="hidden"
              animate="show"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
                gap: 6,
              }}
            >
              {signals.settings_interests.slice(0, 8).map((raw, i) => {
                const { label, icon, bg } = resolveInterestIcon(raw);
                return <InterestTile key={`${label}-${i}`} icon={icon} label={label} background={bg} />;
              })}
            </motion.div>
          </DecoPanel>
        )}

        {/* ── Ad categories ────────────────────────────────────────────── */}
        {signals?.ad_interests && signals.ad_interests.length > 0 && (
          <DecoPanel
            shadow={TOKENS.secondaryContainer}
            style={{ marginBottom: 24 }}
          >
            <CapsLabel icon={Tag} color={TOKENS.accent}>
              {caption("surface.ad_interests.heading")}
            </CapsLabel>
            <PanelLede>{caption("surface.ad_interests.caption")}</PanelLede>
            <TagCloud tags={signals.ad_interests} accent={TOKENS.surfaceAlt} />
          </DecoPanel>
        )}

        {/* ── Recent searches ──────────────────────────────────────────── */}
        {signals?.recent_searches && signals.recent_searches.length > 0 && (
          <DecoPanel
            shadow={TOKENS.primaryContainer}
            style={{ marginBottom: 24 }}
          >
            <CapsLabel icon={Search} color={TOKENS.secondary}>
              {caption("surface.recent_searches.heading")}
            </CapsLabel>
            <PanelLede>{caption("surface.recent_searches.caption")}</PanelLede>
            <TagCloud
              tags={signals.recent_searches}
              accent={TOKENS.secondaryContainer}
            />
          </DecoPanel>
        )}

        {/* ── TikTok Shop ──────────────────────────────────────────────── */}
        {adProfile && adProfile.shop_order_count > 0 && (
          <DecoPanel
            shadow={TOKENS.secondaryContainer}
            style={{ marginBottom: 24 }}
          >
            <CapsLabel icon={ShoppingBag} color={TOKENS.primary}>
              {caption("surface.shop_orders.heading")}
            </CapsLabel>
            <PanelLede>
              {adProfile.shop_order_count} purchase
              {adProfile.shop_order_count === 1 ? "" : "s"} on file ·{" "}
              {caption("surface.shop_orders.caption")}
            </PanelLede>
            {adProfile.shop_products.length > 0 && (
              <ul
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  margin: 0,
                  padding: 0,
                  listStyle: "none",
                }}
              >
                {adProfile.shop_products.slice(0, 6).map((p, i) => (
                  <li
                    key={i}
                    style={{
                      fontFamily: FONT_BODY,
                      fontSize: 12,
                      color: TOKENS.body,
                      padding: "6px 10px",
                      background: "rgba(242,132,130,0.08)",
                      borderLeft: `3px solid ${TOKENS.primary}`,
                    }}
                  >
                    {p}
                  </li>
                ))}
              </ul>
            )}
          </DecoPanel>
        )}

        {/* ── Algorithm Note (anchor explanation) ──────────────────────── */}
        <DecoPanel
          shadow={TOKENS.primaryContainer}
          style={{
            marginBottom: 32,
            borderLeft: `12px solid ${TOKENS.primaryContainer}`,
            padding: "28px 28px 24px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              marginBottom: 10,
            }}
          >
            <Cpu size={26} color={TOKENS.ink} />
            <h3
              style={{
                fontFamily: FONT_DISPLAY,
                fontWeight: 800,
                fontSize: 28,
                letterSpacing: "-0.02em",
                color: TOKENS.ink,
                margin: 0,
                textTransform: "uppercase",
              }}
            >
              {caption("surface.algorithm_note.heading")}
            </h3>
          </div>
          <HeadingRule />
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 24,
            }}
          >
            <p
              style={{
                fontFamily: FONT_BODY,
                fontSize: 14,
                lineHeight: 1.65,
                color: TOKENS.body,
                margin: 0,
              }}
            >
              {caption("surface.algorithm_note.body_a")}
            </p>
            <p
              style={{
                fontFamily: FONT_BODY,
                fontSize: 14,
                lineHeight: 1.65,
                color: TOKENS.body,
                margin: 0,
              }}
            >
              {caption("surface.algorithm_note.body_b")}
            </p>
          </div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              marginTop: 18,
              padding: "8px 12px",
              background: TOKENS.secondaryContainer,
              border: `2px solid ${TOKENS.ink}`,
              ...decoClip,
            }}
          >
            <Info size={14} color={TOKENS.ink} />
            <span
              style={{
                fontFamily: FONT_LABEL,
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: TOKENS.ink,
              }}
            >
              {caption("surface.algorithm_note.weighting")}
            </span>
          </div>
        </DecoPanel>

        {/* ── ATT permission card ──────────────────────────────────────── */}
        <DecoPanel
          shadow={TOKENS.secondaryContainer}
          style={{ marginBottom: 32, padding: "24px 24px 12px" }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              marginBottom: 16,
            }}
          >
            <div
              aria-hidden
              style={{
                width: 48,
                height: 48,
                background: "linear-gradient(135deg, #ee1d52, #010101)",
                border: `2px solid ${TOKENS.ink}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 22,
                color: "white",
                flexShrink: 0,
              }}
            >
              🎵
            </div>
            <div>
              <p
                style={{
                  fontFamily: FONT_BODY,
                  fontSize: 14,
                  fontWeight: 500,
                  color: TOKENS.ink,
                  margin: 0,
                }}
              >
                {caption("surface.permissions.heading")}
              </p>
              <p
                style={{
                  fontFamily: FONT_BODY,
                  fontSize: 12,
                  color: TOKENS.muted,
                  marginTop: 2,
                  marginBottom: 0,
                }}
              >
                {caption("surface.permissions.body")}
              </p>
            </div>
          </div>
          <motion.div variants={stagger.container} initial="hidden" animate="show">
            <PermissionRow
              icon={Eye}
              label="Every video you watched"
              sub={caption("surface.permissions.watch_history")}
              granted
            />
            <PermissionRow
              icon={Users}
              label="Who you follow vs. who TikTok showed you"
              sub={caption("surface.permissions.social_graph")}
              granted
            />
            <PermissionRow
              icon={Search}
              label="Your exact active hours"
              sub={caption("surface.permissions.active_hours")}
              granted
            />
            <PermissionRow
              icon={Hash}
              label="Every immediate skip"
              sub={caption("surface.permissions.skip_signal")}
              granted
            />
          </motion.div>
        </DecoPanel>

        {/* ── Scroll cue + sentinel ────────────────────────────────────── */}
        <div style={{ textAlign: "center", padding: "32px 0 12px" }}>
          <p
            style={{
              fontFamily: FONT_BODY,
              fontSize: 14,
              color: TOKENS.muted,
              margin: 0,
            }}
          >
            {caption("surface.scroll_cue.line_1")}
          </p>
          <p
            style={{
              fontFamily: FONT_BODY,
              fontStyle: "italic",
              fontSize: 14,
              color: TOKENS.muted,
              margin: "4px 0 22px",
            }}
          >
            {caption("surface.scroll_cue.line_2")}
          </p>
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
          >
            <ChevronDown size={22} color={TOKENS.primary} style={{ display: "block", margin: "0 auto" }} />
          </motion.div>
        </div>

        {/* Sentinel — entering this triggers onReveal() once. */}
        <div
          ref={sentinelRef}
          style={{
            height: 120,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <motion.div
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: 1, duration: 1.2, ease: EASE_OUT_QUINT }}
            style={{
              width: "100%",
              height: 2,
              background: `linear-gradient(to right, transparent, ${TOKENS.ink}, transparent)`,
            }}
          />
        </div>
      </div>
    </motion.div>
  );
}
