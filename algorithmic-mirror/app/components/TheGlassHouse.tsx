"use client";

/**
 * THE GLASS HOUSE
 * A long-form interactive investigative piece where the user's own TikTok
 * data export is the lead story. Every claim is clickable and opens a
 * side panel with the raw JSON evidence.
 *
 * Aesthetic: editorial / newsprint. Warm paper background, serif display,
 * hairline rules, marginalia. The feel of a journalist's desk.
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import { motion } from "framer-motion";
import { ArrowDown, FileText, Quote } from "lucide-react";
import type { GhostProfile } from "./GhostProfileHUD";
import { EvidencePanel } from "./EvidencePanel";
import { DownloadExportButton } from "./DownloadExportButton";

// ---------------------------------------------------------------------------
// Design tokens — warm paper, ink black, quiet accent
// ---------------------------------------------------------------------------

const PAPER = "#f5efe4";
const PAPER_DEEP = "#ede5d4";
const INK = "#1a1610";
const INK_SOFT = "#3a3024";
const INK_DIM = "#6a5e4a";
const INK_GHOST = "#a89a80";
const RULE = "rgba(26, 22, 16, 0.14)";
const ACCENT = "#8b2323"; // oxblood — for highlights and redactions
const HIGHLIGHT = "#f5d57a"; // highlighter marker

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatInt(n: number) {
  return n.toLocaleString("en-US");
}

function inferIdentity(p: GhostProfile): string {
  if (p.primary_archetype) {
    return p.primary_archetype.name;
  }
  
  const ad = p.declared_signals?.ad_interests ?? [];
  const topCreator = p.creator_entities?.vibe_cluster?.[0]?.handle ?? "";
  const night = p.night_shift?.percentage ?? p.behavioral_nodes.night_shift_ratio;
  const echoPct = p.academic_insights?.echo_chamber_index_pct ?? 0;

  const archetypes: string[] = [];
  if (night >= 20) archetypes.push("Nocturnal");
  else if (night >= 10) archetypes.push("Late-Night");
  else archetypes.push("Daytime");

  // Lightweight text clustering over declared ad interests
  const lower = ad.map(a => (a || "").toLowerCase()).join(" | ");
  const tags: string[] = [];
  if (/polit|news|geopolit|world|govern/.test(lower)) tags.push("News Reader");
  if (/anxiety|therap|mental|ptsd|trauma/.test(lower)) tags.push("Anxious Urbanite");
  if (/diy|home|decor|kitchen|renovat/.test(lower)) tags.push("Domestic Optimizer");
  if (/sport|nba|nfl|soccer|mlb|box/.test(lower)) tags.push("Sports Tactician");
  if (/food|recip|cook|bake|coffee/.test(lower)) tags.push("Food Lover");
  if (/finance|stock|crypto|money|invest/.test(lower)) tags.push("Amateur Financier");
  if (/comedy|meme|humor|funny/.test(lower)) tags.push("Humor Seeker");
  if (/music|song|concert|album/.test(lower)) tags.push("Music Listener");
  if (/fashion|style|outfit|beauty|makeup/.test(lower)) tags.push("Style-Conscious");
  if (/travel|trip|destinat|vacat/.test(lower)) tags.push("Armchair Traveller");

  const identity = [archetypes[0], ...tags.slice(0, 2)].filter(Boolean).join(" · ");
  if (identity) return identity;

  // Fallback to dominant creator type
  if (echoPct > 40) return `${archetypes[0]} · Loop-Bound Viewer`;
  if (topCreator) return `${archetypes[0]} · Follower of ${topCreator}`;
  return `${archetypes[0]} · Unclassified`;
}

// ---------------------------------------------------------------------------
// Claim — highlightable text segment that opens the evidence panel
// ---------------------------------------------------------------------------

type ClaimMeta = {
  title: string;
  claim: string;
  payload: unknown;
};

function Claim({
  children,
  onOpen,
  meta,
  variant = "underline",
}: {
  children: React.ReactNode;
  onOpen: (m: ClaimMeta) => void;
  meta: ClaimMeta;
  variant?: "underline" | "highlight" | "redaction";
}) {
  const base: React.CSSProperties = {
    cursor: "pointer",
    position: "relative",
    transition: "background 0.2s ease",
    padding: "0 2px",
  };

  const styleByVariant: Record<string, React.CSSProperties> = {
    underline: {
      ...base,
      borderBottom: `1.5px solid ${ACCENT}`,
      color: INK,
    },
    highlight: {
      ...base,
      background: `linear-gradient(180deg, transparent 55%, ${HIGHLIGHT} 55%)`,
      color: INK,
      fontWeight: 500,
    },
    redaction: {
      ...base,
      background: INK,
      color: PAPER,
      fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
      fontSize: "0.92em",
      padding: "1px 6px",
      letterSpacing: "0.05em",
    },
  };

  return (
    <span
      role="button"
      tabIndex={0}
      onClick={() => onOpen(meta)}
      onKeyDown={e => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen(meta);
        }
      }}
      style={styleByVariant[variant]}
      title="Click to see source data"
    >
      {children}
      <sup
        style={{
          fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
          fontSize: "0.62em",
          color: ACCENT,
          marginLeft: 2,
          letterSpacing: "0.05em",
          verticalAlign: "super",
        }}
      >
        [†]
      </sup>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Layout primitives
// ---------------------------------------------------------------------------

function Chapter({
  number,
  kicker,
  title,
  children,
}: {
  number: string;
  kicker: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section
      style={{
        paddingTop: 120,
        paddingBottom: 120,
        borderTop: `1px solid ${RULE}`,
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
          fontSize: 11,
          letterSpacing: "0.32em",
          color: INK_DIM,
          textTransform: "uppercase",
          marginBottom: 20,
          display: "flex",
          alignItems: "center",
          gap: 14,
        }}
      >
        <span
          style={{
            background: INK,
            color: PAPER,
            padding: "4px 10px",
            letterSpacing: "0.2em",
            fontWeight: 700,
          }}
        >
          {number}
        </span>
        <span>{kicker}</span>
      </div>
      <h2
        style={{
          fontFamily: "var(--font-display, 'Fraunces', 'Playfair Display', Georgia, serif)",
          fontWeight: 700,
          fontSize: "clamp(40px, 6vw, 68px)",
          lineHeight: 1.02,
          letterSpacing: "-0.02em",
          color: INK,
          marginTop: 0,
          marginBottom: 48,
          maxWidth: 12,
          width: "100%",
          maxInlineSize: "14ch",
        }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function Lede({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontFamily: "var(--font-body, 'Iowan Old Style', Georgia, serif)",
        fontSize: "clamp(20px, 2.2vw, 26px)",
        lineHeight: 1.55,
        color: INK,
        maxWidth: "60ch",
        margin: "0 0 40px",
        letterSpacing: "-0.005em",
      }}
    >
      {children}
    </p>
  );
}

function Body({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontFamily: "var(--font-body, 'Iowan Old Style', Georgia, serif)",
        fontSize: 18,
        lineHeight: 1.75,
        color: INK_SOFT,
        maxWidth: "60ch",
        marginTop: 0,
        marginBottom: 26,
      }}
    >
      {children}
    </p>
  );
}

function PullQuote({ children }: { children: React.ReactNode }) {
  return (
    <blockquote
      style={{
        borderLeft: `3px solid ${ACCENT}`,
        paddingLeft: 24,
        margin: "40px 0",
        maxWidth: "46ch",
        fontFamily: "var(--font-display, 'Fraunces', Georgia, serif)",
        fontStyle: "italic",
        fontSize: "clamp(22px, 2.4vw, 30px)",
        lineHeight: 1.35,
        color: INK,
        fontWeight: 500,
      }}
    >
      <Quote
        size={18}
        style={{ color: ACCENT, verticalAlign: "super", marginRight: 6 }}
      />
      {children}
    </blockquote>
  );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

interface Props {
  profile: GhostProfile;
  onReset: () => void;
  onViewRawForensics: () => void;
  sourceFile?: File;
  onOpenReport?: () => void;
  onAnalyzeWithAI?: () => void;
}

export function TheGlassHouse({ profile, onReset, onViewRawForensics, sourceFile, onOpenReport, onAnalyzeWithAI }: Props) {
  const [evidence, setEvidence] = useState<ClaimMeta | null>(null);
  const openEvidence = useCallback((m: ClaimMeta) => setEvidence(m), []);
  const closeEvidence = useCallback(() => setEvidence(null), []);

  // ESC key closes panel
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") setEvidence(null);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const identity = useMemo(() => inferIdentity(profile), [profile]);

  const sw = profile.stopwatch_metrics;
  const ai = profile.academic_insights;
  const ns = profile.night_shift ?? {
    percentage: profile.behavioral_nodes?.night_shift_ratio ?? 0,
    count: 0,
    window: "23:00 – 04:00",
  };
  const footprint = profile.digital_footprint;
  const rhythm = profile.search_rhythm;
  const gap = profile.discrepancy_gap;
  const decl = profile.declared_signals;
  const ev = profile._evidence ?? {};
  const vibe = profile.creator_entities?.vibe_cluster ?? [];

  const totalSearches = rhythm?.total_searches ?? decl?.recent_searches?.length ?? 0;

  // Peak search hour for Chapter 4 rhythm visual
  const hourHist = rhythm?.hourly_histogram ?? {};
  const maxHour = Math.max(...Object.values(hourHist), 1);
  const peakHour = Object.entries(hourHist).sort((a, b) => b[1] - a[1])[0]?.[0];

  // Inferred interests not in declared set (discrepancy candidates)
  const declaredSet = new Set((gap?.declared_surface_sample ?? []).map(s => s.toLowerCase()));
  const inferredOnly = vibe
    .filter(v => !declaredSet.has(v.handle.toLowerCase().replace(/^@/, "")))
    .slice(0, 8);

  return (
    <>
      <main
        style={{
          background: PAPER,
          color: INK,
          minHeight: "100vh",
          position: "relative",
          overflowX: "hidden",
        }}
      >
        {/* Newsprint grain overlay */}
        <div
          aria-hidden
          style={{
            position: "fixed",
            inset: 0,
            pointerEvents: "none",
            opacity: 0.5,
            mixBlendMode: "multiply",
            backgroundImage:
              "radial-gradient(rgba(26,22,16,0.06) 1px, transparent 1px)",
            backgroundSize: "3px 3px",
            zIndex: 1,
          }}
        />

        <div
          style={{
            position: "relative",
            zIndex: 2,
            maxWidth: 1100,
            margin: "0 auto",
            padding: "56px clamp(24px, 5vw, 72px) 140px",
          }}
        >
          {/* Masthead */}
          <header
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
              borderBottom: `2px solid ${INK}`,
              paddingBottom: 18,
              marginBottom: 80,
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                fontSize: 10,
                letterSpacing: "0.38em",
                color: INK_DIM,
                textTransform: "uppercase",
              }}
            >
              The Glass House · Vol. I · Dossier Edition
            </div>
            <button
              onClick={onReset}
              style={{
                fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                fontSize: 10,
                letterSpacing: "0.28em",
                textTransform: "uppercase",
                color: INK_DIM,
                background: "transparent",
                border: "none",
                cursor: "pointer",
                textDecoration: "underline",
                textUnderlineOffset: 4,
              }}
            >
              ← Upload different export
            </button>
            {sourceFile && (
              <DownloadExportButton
                file={sourceFile}
                apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
              />
            )}
            {onOpenReport && (
              <button
                onClick={onOpenReport}
                style={{
                  fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                  fontSize: 10,
                  letterSpacing: "0.28em",
                  textTransform: "uppercase",
                  color: "#1a1610",
                  background: "transparent",
                  border: "1px solid rgba(26,22,16,0.4)",
                  padding: "6px 14px",
                  cursor: "pointer",
                }}
              >
                DOSSIER →
              </button>
            )}
            {onAnalyzeWithAI && (
              <button
                onClick={onAnalyzeWithAI}
                style={{
                  fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                  fontSize: 10,
                  letterSpacing: "0.28em",
                  textTransform: "uppercase",
                  color: "#8b2323",
                  background: "transparent",
                  border: "1px solid rgba(139,35,35,0.4)",
                  padding: "6px 14px",
                  cursor: "pointer",
                }}
              >
                Analyze with AI →
              </button>
            )}
          </header>

          {/* ======================= PROLOGUE ======================= */}
          <section style={{ marginBottom: 40 }}>
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              style={{
                fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                fontSize: 11,
                letterSpacing: "0.32em",
                color: ACCENT,
                textTransform: "uppercase",
                marginBottom: 22,
                display: "flex",
                alignItems: "center",
                gap: 12,
              }}
            >
              <span
                style={{
                  width: 28,
                  height: 1,
                  background: ACCENT,
                  display: "inline-block",
                }}
              />
              Prologue · The Hook
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.1 }}
              style={{
                fontFamily:
                  "var(--font-display, 'Fraunces', 'Playfair Display', Georgia, serif)",
                fontWeight: 800,
                fontSize: "clamp(52px, 8vw, 108px)",
                lineHeight: 0.94,
                letterSpacing: "-0.035em",
                color: INK,
                margin: 0,
                maxWidth: "14ch",
              }}
            >
              The House
              <br />
              You Didn&rsquo;t
              <br />
              Know Was
              <br />
              <span
                style={{
                  fontStyle: "italic",
                  color: ACCENT,
                }}
              >
                Glass.
              </span>
            </motion.h1>

            {profile.primary_archetype && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.6, delay: 0.3 }}
                style={{
                  marginTop: 48,
                  padding: "24px 32px",
                  background: "#1a1610",
                  color: "#f5efe4",
                  display: "inline-block",
                  borderLeft: `6px solid ${ACCENT}`,
                }}
              >
                <div
                  style={{
                    fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 10,
                    letterSpacing: "0.4em",
                    textTransform: "uppercase",
                    color: ACCENT,
                    marginBottom: 12,
                    fontWeight: 700,
                  }}
                >
                  // ALGORITHMIC CHARACTERIZATION
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-display, serif)",
                    fontSize: 24,
                    fontWeight: 700,
                    marginBottom: 8,
                    letterSpacing: "-0.01em",
                  }}
                >
                  {profile.primary_archetype.name}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-body, serif)",
                    fontSize: 14,
                    opacity: 0.8,
                    lineHeight: 1.5,
                    maxWidth: 400,
                  }}
                >
                  {profile.primary_archetype.description}
                </div>
              </motion.div>
            )}

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.4 }}
              style={{
                marginTop: 48,
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 48,
                borderTop: `1px solid ${RULE}`,
                paddingTop: 36,
              }}
            >
              <div>
                <div
                  style={{
                    fontFamily:
                      "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 10,
                    letterSpacing: "0.25em",
                    color: INK_DIM,
                    textTransform: "uppercase",
                    marginBottom: 8,
                  }}
                >
                  By · Staff Analyst
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-body, Georgia, serif)",
                    fontStyle: "italic",
                    fontSize: 14,
                    color: INK_SOFT,
                    lineHeight: 1.6,
                  }}
                >
                  Reconstructed from your personal TikTok export. All claims herein
                  are backed by the exact JSON excerpts delivered to you by
                  ByteDance upon request.
                </div>
              </div>
              <div
                style={{
                  borderLeft: `1px solid ${RULE}`,
                  paddingLeft: 24,
                  fontFamily: "var(--font-body, Georgia, serif)",
                  fontSize: 14,
                  color: INK_SOFT,
                  lineHeight: 1.7,
                }}
              >
                <strong style={{ color: INK, fontWeight: 700 }}>Method.</strong>{" "}
                Every underlined phrase in this piece is a{" "}
                <em>claim</em>. Click it to reveal the raw data that supports it.
                Nothing in this dossier is inferred without a citation you can
                inspect yourself.
              </div>
            </motion.div>
          </section>

          {/* Lede paragraph */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.55 }}
            style={{ marginTop: 72 }}
          >
            <Lede>
              Based on{" "}
              <Claim
                onOpen={openEvidence}
                variant="underline"
                meta={{
                  title: "Prologue · Raw counters",
                  claim: `${formatInt(sw.total_videos)} video timestamps, ${formatInt(totalSearches)} search queries, ${formatInt(vibe.length)} resolved creators.`,
                  payload: ev.prologue,
                }}
              >
                {formatInt(sw.total_videos)} video timestamps
              </Claim>
              ,{" "}
              <Claim
                onOpen={openEvidence}
                variant="underline"
                meta={{
                  title: "Prologue · Search queries",
                  claim: `${formatInt(totalSearches)} search queries submitted.`,
                  payload: ev.search_rhythm,
                }}
              >
                {formatInt(totalSearches)} search queries
              </Claim>
              , and the quiet lean of your thumb late at night, TikTok has decided
              you are a{" "}
              <Claim
                onOpen={openEvidence}
                variant="highlight"
                meta={{
                  title: "Prologue · Inferred identity",
                  claim: `Identity derived from declared ad interests and nocturnal behavior: ${identity}.`,
                  payload: {
                    identity,
                    declared_ad_interests:
                      decl?.ad_interests?.slice(0, 12) ?? [],
                    night_shift_ratio: ns.percentage,
                    top_creators: vibe.slice(0, 5),
                  },
                }}
              >
                {identity}
              </Claim>
              .
            </Lede>

            <Body>
              You did not tell it this. You showed it. In the space between two
              videos &mdash; half a second where your thumb hesitated &mdash; you
              handed over a piece of yourself. This dossier is what the machine
              wrote down.
            </Body>
          </motion.div>

          <div
            style={{
              marginTop: 48,
              display: "flex",
              alignItems: "center",
              gap: 10,
              color: INK_DIM,
              fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 10,
              letterSpacing: "0.28em",
              textTransform: "uppercase",
            }}
          >
            <ArrowDown size={14} />
            <span>Continue the story</span>
          </div>

          {/* ======================= CHAPTER 1 ======================= */}
          <Chapter
            number="I"
            kicker="The Digital Footprint"
            title="They Watched You Log In."
          >
            <Body>
              You are not just what you scroll. You are a device model, a
              carrier, an IP string, and a date. Every time your phone
              whispered TikTok awake, it left a line on a ledger. The ledger
              now holds{" "}
              <Claim
                onOpen={openEvidence}
                variant="underline"
                meta={{
                  title: "Chapter I · Login ledger",
                  claim: `${formatInt(footprint?.login_count ?? 0)} recorded login events.`,
                  payload: ev.digital_footprint,
                }}
              >
                {formatInt(footprint?.login_count ?? 0)} recorded sessions
              </Claim>
              , spread across{" "}
              <Claim
                onOpen={openEvidence}
                variant="underline"
                meta={{
                  title: "Chapter I · Unique IPs",
                  claim: `${formatInt(footprint?.unique_ips ?? 0)} unique IP addresses captured from your login history.`,
                  payload: {
                    unique_ips: footprint?.unique_ips ?? 0,
                    ip_locations: footprint?.ip_locations ?? [],
                  },
                }}
              >
                {formatInt(footprint?.unique_ips ?? 0)} unique IPs
              </Claim>
              .
            </Body>

            {footprint?.unique_devices && footprint.unique_devices.length > 0 && (
              <Body>
                The machine knows you scroll from a{" "}
                <Claim
                  onOpen={openEvidence}
                  variant="redaction"
                  meta={{
                    title: "Chapter I · Device fingerprint",
                    claim: `Device models captured: ${footprint.unique_devices.join(", ")}.`,
                    payload: { unique_devices: footprint.unique_devices },
                  }}
                >
                  {footprint.unique_devices.slice(0, 2).join(" / ")}
                </Claim>
                . It knows the network too &mdash; whether you were on a home
                router or a coffee-shop hotspot, whether you crossed a carrier
                boundary at 2 AM on a Tuesday.
              </Body>
            )}

            {/* Ledger excerpt */}
            <div
              style={{
                marginTop: 40,
                marginBottom: 40,
                border: `1px solid ${RULE}`,
                background: PAPER_DEEP,
                padding: "20px 24px",
                maxWidth: 720,
              }}
            >
              <div
                style={{
                  fontFamily:
                    "var(--font-mono, ui-monospace, Menlo, monospace)",
                  fontSize: 10,
                  letterSpacing: "0.28em",
                  color: INK_DIM,
                  textTransform: "uppercase",
                  marginBottom: 14,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <FileText size={12} />
                Sift through the notes · recent logins
              </div>

              {(footprint?.recent_logins ?? []).slice(0, 6).map((l, i) => (
                <div
                  key={`${l.date}-${i}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "180px 1fr auto",
                    gap: 16,
                    padding: "10px 0",
                    borderTop: i === 0 ? "none" : `1px dashed ${RULE}`,
                    fontFamily:
                      "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 12,
                    color: INK_SOFT,
                  }}
                >
                  <div style={{ color: INK }}>{l.date}</div>
                  <div
                    style={{
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {l.device || "—"}
                    {l.system && (
                      <span style={{ color: INK_GHOST }}> · {l.system}</span>
                    )}
                  </div>
                  <div style={{ color: ACCENT, letterSpacing: "0.08em" }}>
                    {l.ip || "—"}
                  </div>
                </div>
              ))}

              {(footprint?.recent_logins ?? []).length === 0 && (
                <div
                  style={{
                    fontFamily:
                      "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 11,
                    color: INK_GHOST,
                  }}
                >
                  {"//"} no login history captured in this export
                </div>
              )}

              {(footprint?.recent_logins ?? []).length > 6 && (
                <button
                  onClick={() =>
                    openEvidence({
                      title: "Chapter I · Full login ledger",
                      claim: "Every captured login session from your export.",
                      payload: ev.digital_footprint,
                    })
                  }
                  style={{
                    marginTop: 14,
                    background: "transparent",
                    border: `1px solid ${INK}`,
                    padding: "6px 12px",
                    fontFamily:
                      "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 10,
                    letterSpacing: "0.2em",
                    textTransform: "uppercase",
                    color: INK,
                    cursor: "pointer",
                  }}
                >
                  See all →
                </button>
              )}
            </div>

            <PullQuote>
              The story was never where you went. It was how often you were
              tracked.
            </PullQuote>
          </Chapter>

          {/* ======================= CHAPTER 2 ======================= */}
          <Chapter
            number="II"
            kicker="The Whispered Interests"
            title="What You Told It, vs. What It Learned."
          >
            <Body>
              You told TikTok a story about yourself. You searched for{" "}
              <Claim
                onOpen={openEvidence}
                variant="underline"
                meta={{
                  title: "Chapter II · Your declared searches",
                  claim: `You actively typed ${formatInt(totalSearches)} search queries into the app.`,
                  payload: ev.discrepancy,
                }}
              >
                {formatInt(totalSearches)} things
              </Claim>
              . You ticked{" "}
              <Claim
                onOpen={openEvidence}
                variant="underline"
                meta={{
                  title: "Chapter II · Declared settings interests",
                  claim: "Interests you explicitly opted into during onboarding.",
                  payload: {
                    settings_interests: decl?.settings_interests ?? [],
                  },
                }}
              >
                {formatInt(decl?.settings_interests?.length ?? 0)} interest tags
              </Claim>{" "}
              during onboarding. This is the story you think you wrote.
            </Body>

            <Body>
              But your explicit-to-implicit ratio is{" "}
              <Claim
                onOpen={openEvidence}
                variant="highlight"
                meta={{
                  title: "Chapter II · Explicit vs Implicit",
                  claim: `For every like or comment you made, there were ${(ai ? 1 / Math.max(ai.explicit_vs_implicit_ratio, 0.001) : 0).toFixed(1)} silent lingers on videos you never acknowledged.`,
                  payload: {
                    explicit_actions_count: ai?.explicit_actions_count,
                    implicit_linger_count: ai?.implicit_linger_count,
                    ratio: ai?.explicit_vs_implicit_ratio,
                    sample_lingers: ev.feedback_loop,
                  },
                }}
              >
                {(ai?.explicit_vs_implicit_ratio ?? 0).toFixed(2)} : 1
              </Claim>
              . For every like or comment you made, there were many more videos
              you watched in silence. The algorithm wrote a different story. A
              truer one.
            </Body>

            {/* Two-column: Declared vs Inferred */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 40,
                marginTop: 52,
                marginBottom: 48,
              }}
            >
              <div
                style={{
                  borderTop: `2px solid ${INK}`,
                  paddingTop: 20,
                }}
              >
                <div
                  style={{
                    fontFamily:
                      "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 10,
                    letterSpacing: "0.25em",
                    color: INK_DIM,
                    textTransform: "uppercase",
                    marginBottom: 16,
                  }}
                >
                  What you told it
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {(decl?.ad_interests ?? []).slice(0, 18).map((t, i) => (
                    <Claim
                      key={`${t}-${i}`}
                      onOpen={openEvidence}
                      variant="underline"
                      meta={{
                        title: "Chapter II · Declared ad interest",
                        claim: `"${t}" — you or a prior account action consented to this being tracked as an interest.`,
                        payload: {
                          tag: t,
                          all_declared_ad_interests: decl?.ad_interests ?? [],
                        },
                      }}
                    >
                      <span
                        style={{
                          display: "inline-block",
                          fontFamily:
                            "var(--font-body, Georgia, serif)",
                          fontSize: 14,
                          color: INK,
                          padding: "3px 8px",
                          background: "rgba(26,22,16,0.04)",
                          borderBottom: `1.5px solid ${ACCENT}`,
                        }}
                      >
                        {t}
                      </span>
                    </Claim>
                  ))}
                  {(decl?.ad_interests ?? []).length === 0 && (
                    <div
                      style={{
                        fontFamily: "var(--font-body, Georgia, serif)",
                        fontStyle: "italic",
                        color: INK_GHOST,
                      }}
                    >
                      No declared ad interests captured.
                    </div>
                  )}
                </div>
              </div>

              <div
                style={{
                  borderTop: `2px solid ${ACCENT}`,
                  paddingTop: 20,
                }}
              >
                <div
                  style={{
                    fontFamily:
                      "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 10,
                    letterSpacing: "0.25em",
                    color: ACCENT,
                    textTransform: "uppercase",
                    marginBottom: 16,
                  }}
                >
                  What it actually learned
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                  }}
                >
                  {vibe.slice(0, 8).map((v, i) => (
                    <div
                      key={`${v.handle}-${i}`}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "24px 1fr auto",
                        alignItems: "center",
                        gap: 12,
                        paddingBottom: 8,
                        borderBottom: `1px dashed ${RULE}`,
                      }}
                    >
                      <div
                        style={{
                          fontFamily:
                            "var(--font-mono, ui-monospace, Menlo, monospace)",
                          fontSize: 10,
                          color: INK_GHOST,
                        }}
                      >
                        {String(i + 1).padStart(2, "0")}
                      </div>
                      <Claim
                        onOpen={openEvidence}
                        variant="underline"
                        meta={{
                          title: `Chapter II · ${v.handle}`,
                          claim: `The algorithm learned to serve you ${v.handle} — you lingered on their content ${v.linger_count} times.`,
                          payload: {
                            creator: v.handle,
                            linger_count: v.linger_count,
                            rank: i + 1,
                            sample_lingers:
                              (ev.feedback_loop as { top_lingers_raw?: unknown })?.top_lingers_raw ?? [],
                          },
                        }}
                      >
                        <span
                          style={{
                            fontFamily: "var(--font-body, Georgia, serif)",
                            fontSize: 15,
                            color: INK,
                          }}
                        >
                          {v.handle}
                        </span>
                      </Claim>
                      <div
                        style={{
                          fontFamily:
                            "var(--font-mono, ui-monospace, Menlo, monospace)",
                          fontSize: 11,
                          color: ACCENT,
                        }}
                      >
                        {v.linger_count} lingers
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <PullQuote>
              The gap between the interests you declared and the creators you
              gave your time to is where the machine lives.
            </PullQuote>

            {inferredOnly.length > 0 && (
              <>
                <Body>
                  These are creators the algorithm decided you love &mdash;
                  without you ever ticking a box that says so.
                </Body>
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 8,
                    marginTop: 12,
                    marginBottom: 32,
                  }}
                >
                  {inferredOnly.map(v => (
                    <Claim
                      key={v.handle}
                      onOpen={openEvidence}
                      variant="highlight"
                      meta={{
                        title: `Chapter II · Silent inference — ${v.handle}`,
                        claim: `You never searched for "${v.handle}" or ticked a matching interest. The machine inferred it from your silence.`,
                        payload: {
                          creator: v.handle,
                          linger_count: v.linger_count,
                          declared_searches_sample:
                            (ev.discrepancy as { declared_searches_raw?: unknown })?.declared_searches_raw ?? [],
                        },
                      }}
                    >
                      <span
                        style={{
                          fontFamily: "var(--font-body, Georgia, serif)",
                          fontSize: 14,
                        }}
                      >
                        {v.handle}
                      </span>
                    </Claim>
                  ))}
                </div>
              </>
            )}
          </Chapter>

          {/* ======================= CHAPTER 3 ======================= */}
          <Chapter
            number="III"
            kicker="The Psychographic Profile"
            title="Why It Thinks It Knows You."
          >
            <Body>
              TikTok does not guess at you. It arrives at you. Every tag it
              has applied &mdash;{" "}
              <Claim
                onOpen={openEvidence}
                variant="underline"
                meta={{
                  title: "Chapter III · Ad interest tags",
                  claim: `TikTok has assigned you ${formatInt(decl?.ad_interests?.length ?? 0)} distinct advertising interest categories.`,
                  payload: ev.psychographic,
                }}
              >
                {formatInt(decl?.ad_interests?.length ?? 0)} advertising
                categories
              </Claim>{" "}
              &mdash; has an audit trail. It was earned by minutes. By seconds.
              By one specific Tuesday you don&rsquo;t remember.
            </Body>

            {vibe.slice(0, 3).map((v, i) => (
              <div
                key={v.handle}
                style={{
                  marginTop: 32,
                  padding: "20px 24px",
                  borderLeft: `2px solid ${ACCENT}`,
                  background: PAPER_DEEP,
                  maxWidth: "62ch",
                }}
              >
                <div
                  style={{
                    fontFamily:
                      "var(--font-mono, ui-monospace, Menlo, monospace)",
                    fontSize: 10,
                    letterSpacing: "0.25em",
                    color: INK_DIM,
                    textTransform: "uppercase",
                    marginBottom: 8,
                  }}
                >
                  Evidence #{String(i + 1).padStart(2, "0")}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-body, Georgia, serif)",
                    fontSize: 17,
                    lineHeight: 1.6,
                    color: INK,
                  }}
                >
                  You are tagged against{" "}
                  <Claim
                    onOpen={openEvidence}
                    variant="underline"
                    meta={{
                      title: `Chapter III · ${v.handle}`,
                      claim: `The creator ${v.handle} is weighted in your psychographic model because your feed retained their content ${v.linger_count} separate times.`,
                      payload: {
                        creator: v.handle,
                        linger_count: v.linger_count,
                        top_deep_dives:
                          (ev.psychographic as { top_deep_dives?: unknown })?.top_deep_dives ?? [],
                      },
                    }}
                  >
                    {v.handle}
                  </Claim>{" "}
                  because your feed lingered on their content{" "}
                  <strong style={{ color: ACCENT }}>
                    {v.linger_count}
                  </strong>{" "}
                  times &mdash; not skimmed, not scrolled past. Lingered.
                </div>
              </div>
            ))}

            <Body>
              Each of those retained seconds is a vote. The machine counts
              them. You do not.
            </Body>
          </Chapter>

          {/* ======================= CHAPTER 4 ======================= */}
          <Chapter
            number="IV"
            kicker="The Feedback Loop"
            title="The Rhythm of Your Curiosity."
          >
            <Body>
              Search history is a kind of diary. Yours runs to{" "}
              <Claim
                onOpen={openEvidence}
                variant="underline"
                meta={{
                  title: "Chapter IV · Search timeline",
                  claim: `${formatInt(totalSearches)} search queries captured, timestamped and ordered.`,
                  payload: ev.search_rhythm,
                }}
              >
                {formatInt(totalSearches)} entries
              </Claim>
              , and it peaks at{" "}
              <Claim
                onOpen={openEvidence}
                variant="highlight"
                meta={{
                  title: "Chapter IV · Peak curiosity hour",
                  claim: `You search most often during hour ${peakHour ?? "?"} of the day.`,
                  payload: {
                    peak_hour: peakHour,
                    hourly_histogram: hourHist,
                    recent_searches: rhythm?.recent_searches?.slice(0, 12) ?? [],
                  },
                }}
              >
                {peakHour !== undefined ? `${peakHour}:00` : "an unknown hour"}
              </Claim>
              . A single search can change the weather of your feed for weeks.
            </Body>

            {/* Rhythm bar chart */}
            <div
              style={{
                marginTop: 32,
                marginBottom: 40,
                padding: "24px 28px",
                border: `1px solid ${RULE}`,
                background: PAPER_DEEP,
                maxWidth: 720,
              }}
            >
              <div
                style={{
                  fontFamily:
                    "var(--font-mono, ui-monospace, Menlo, monospace)",
                  fontSize: 10,
                  letterSpacing: "0.28em",
                  color: INK_DIM,
                  textTransform: "uppercase",
                  marginBottom: 14,
                }}
              >
                Searches by hour · 24h distribution
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-end",
                  gap: 3,
                  height: 120,
                }}
              >
                {Array.from({ length: 24 }, (_, h) => {
                  const v = hourHist[String(h)] ?? 0;
                  const pct = maxHour > 0 ? (v / maxHour) * 100 : 0;
                  const isPeak = String(h) === peakHour;
                  return (
                    <div
                      key={h}
                      title={`${h}:00 — ${v} searches`}
                      style={{
                        flex: 1,
                        display: "flex",
                        alignItems: "flex-end",
                        height: "100%",
                      }}
                    >
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: `${pct}%` }}
                        transition={{
                          duration: 0.8,
                          delay: h * 0.015,
                          ease: [0.22, 1, 0.36, 1],
                        }}
                        style={{
                          width: "100%",
                          background: isPeak ? ACCENT : INK,
                          opacity: isPeak ? 1 : 0.75,
                        }}
                      />
                    </div>
                  );
                })}
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginTop: 10,
                  fontFamily:
                    "var(--font-mono, ui-monospace, Menlo, monospace)",
                  fontSize: 9,
                  color: INK_GHOST,
                  letterSpacing: "0.12em",
                }}
              >
                <span>00</span>
                <span>06</span>
                <span>12</span>
                <span>18</span>
                <span>23</span>
              </div>
            </div>

            <Body>
              Every search is a gust. Below are a few of yours, as captured.
              Click any to see its original record.
            </Body>

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 0,
                maxWidth: 720,
              }}
            >
              {(rhythm?.recent_searches ?? []).slice(0, 8).map((s, i) => (
                <div
                  key={`${s.term}-${i}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "150px 1fr",
                    gap: 20,
                    padding: "14px 0",
                    borderTop: i === 0 ? `1px solid ${INK}` : `1px dashed ${RULE}`,
                    alignItems: "baseline",
                  }}
                >
                  <div
                    style={{
                      fontFamily:
                        "var(--font-mono, ui-monospace, Menlo, monospace)",
                      fontSize: 11,
                      color: INK_DIM,
                      letterSpacing: "0.05em",
                    }}
                  >
                    {s.date}
                  </div>
                  <div>
                    <Claim
                      onOpen={openEvidence}
                      variant="underline"
                      meta={{
                        title: `Chapter IV · "${s.term}"`,
                        claim: `You searched for "${s.term}" on ${s.date}.`,
                        payload: {
                          search: s,
                          full_recent_list:
                            rhythm?.recent_searches?.slice(0, 20) ?? [],
                        },
                      }}
                    >
                      <span
                        style={{
                          fontFamily: "var(--font-body, Georgia, serif)",
                          fontSize: 17,
                          color: INK,
                          fontStyle: "italic",
                        }}
                      >
                        &ldquo;{s.term}&rdquo;
                      </span>
                    </Claim>
                  </div>
                </div>
              ))}

              {(rhythm?.recent_searches ?? []).length === 0 && (
                <div
                  style={{
                    fontFamily: "var(--font-body, Georgia, serif)",
                    fontStyle: "italic",
                    color: INK_GHOST,
                  }}
                >
                  No search history captured in this export.
                </div>
              )}
            </div>

            <PullQuote>
              A single search for a bad night becomes three weeks of a feed
              that knows you had one.
            </PullQuote>
          </Chapter>

          {/* ======================= EPILOGUE — HUD LINK ======================= */}
          <section
            style={{
              borderTop: `2px solid ${INK}`,
              paddingTop: 60,
              paddingBottom: 40,
              marginTop: 80,
            }}
          >
            <div
              style={{
                fontFamily:
                  "var(--font-mono, ui-monospace, Menlo, monospace)",
                fontSize: 11,
                letterSpacing: "0.32em",
                color: ACCENT,
                textTransform: "uppercase",
                marginBottom: 18,
              }}
            >
              Appendix · Raw Forensics
            </div>
            <h2
              style={{
                fontFamily:
                  "var(--font-display, 'Fraunces', Georgia, serif)",
                fontSize: "clamp(36px, 4.5vw, 52px)",
                lineHeight: 1.05,
                letterSpacing: "-0.02em",
                color: INK,
                marginTop: 0,
                marginBottom: 18,
                maxWidth: "18ch",
              }}
            >
              The evidence room is open.
            </h2>
            <Body>
              You&rsquo;ve read the story. If you want to inspect the raw
              machine &mdash; the brutalist dashboard where every metric lives
              without the prose &mdash; step inside.
            </Body>
            <button
              onClick={onViewRawForensics}
              style={{
                marginTop: 20,
                padding: "14px 28px",
                background: INK,
                color: PAPER,
                border: "none",
                fontFamily:
                  "var(--font-mono, ui-monospace, Menlo, monospace)",
                fontSize: 12,
                letterSpacing: "0.28em",
                textTransform: "uppercase",
                cursor: "pointer",
              }}
            >
              View Raw Forensics →
            </button>
          </section>

          {/* Colophon */}
          <footer
            style={{
              marginTop: 80,
              paddingTop: 20,
              borderTop: `1px solid ${RULE}`,
              fontFamily:
                "var(--font-mono, ui-monospace, Menlo, monospace)",
              fontSize: 10,
              letterSpacing: "0.28em",
              color: INK_GHOST,
              textTransform: "uppercase",
              display: "flex",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <span>The Glass House · End of Dossier</span>
            <span>
              Parsed locally · Every claim cited · No data leaves your device
            </span>
          </footer>
        </div>
      </main>

      <EvidencePanel
        open={evidence !== null}
        title={evidence?.title ?? null}
        claim={evidence?.claim ?? null}
        payload={evidence?.payload ?? null}
        onClose={closeEvidence}
      />
    </>
  );
}
