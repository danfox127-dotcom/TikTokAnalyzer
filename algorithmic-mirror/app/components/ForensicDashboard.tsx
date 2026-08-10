"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Network,
  Search,
  LayoutDashboard,
  ArrowLeft,
  Lock,
  Zap,
  TrendingUp,
  ScrollText
} from "lucide-react";
import type { GhostProfile } from "./GhostProfileHUD";
import { DownloadExportButton } from "./DownloadExportButton";
import { LocalModeBanner } from "./LocalModeBanner";
import { OverviewTab } from "./tabs/OverviewTab";
import { BehaviorTab } from "./tabs/BehaviorTab";
import { NetworkTab } from "./tabs/NetworkTab";
import { TimelineTab } from "./tabs/TimelineTab";
import { InterestsTab } from "./tabs/InterestsTab";
import { PrivacyTab } from "./tabs/PrivacyTab";
import { AiTab } from "./tabs/AiTab";
import { ClaimsTab } from "./tabs/ClaimsTab";
import {
  BG, SIDEBAR, BORDER, ACCENT, INK, INK_DIM, INK_GHOST,
  SidebarItem,
} from "./dashboardPrimitives";

// We'll import existing visualizations or build new ones inside these tabs.
// For now, let's define the tab types.
type Tab = "overview" | "behavior" | "timeline" | "network" | "interests" | "privacy" | "ai" | "claims";

interface Props {
  profile: GhostProfile;
  onReset: () => void;
  sourceFile?: File;
}

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

export function ForensicDashboard({ profile, onReset, sourceFile }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  return (
    <div style={{
      background: BG,
      minHeight: "100vh",
      display: "flex",
      color: INK,
      fontFamily: "var(--font-body, 'Iowan Old Style', Georgia, serif)"
    }}>
      {/* Sidebar */}
      <aside style={{
        width: 260,
        background: SIDEBAR,
        borderRight: `1px solid ${BORDER}`,
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
        height: "100vh",
        position: "sticky",
        top: 0
      }}>
        <div style={{ padding: "32px 24px", borderBottom: `1px solid ${BORDER}` }}>
          <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 9, letterSpacing: "0.32em", color: INK_GHOST, textTransform: "uppercase", marginBottom: 10 }}>
            The Glass House · Dossier
          </div>
          <h1 style={{ fontFamily: "var(--font-display, 'Fraunces', Georgia, serif)", fontSize: 26, fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1.0, margin: 0, color: INK }}>
            The <span style={{ fontStyle: "italic", color: ACCENT }}>Findings</span>
          </h1>
        </div>

        <nav style={{ flex: 1, padding: "24px 0" }}>
          <SidebarItem 
            icon={LayoutDashboard} 
            label="Overview" 
            active={activeTab === "overview"} 
            onClick={() => setActiveTab("overview")} 
          />
          <SidebarItem
            icon={Activity}
            label="Behavioral Signature"
            active={activeTab === "behavior"}
            onClick={() => setActiveTab("behavior")}
          />
          <SidebarItem
            icon={TrendingUp}
            label="Timeline"
            active={activeTab === "timeline"}
            onClick={() => setActiveTab("timeline")}
          />
          <SidebarItem
            icon={Network}
            label="Network & Influence" 
            active={activeTab === "network"} 
            onClick={() => setActiveTab("network")} 
          />
          <SidebarItem 
            icon={Search} 
            label="Interests & Keywords" 
            active={activeTab === "interests"} 
            onClick={() => setActiveTab("interests")} 
          />
          <SidebarItem 
            icon={Lock} 
            label="Privacy & Footprint" 
            active={activeTab === "privacy"} 
            onClick={() => setActiveTab("privacy")} 
          />
          <SidebarItem
            icon={Zap}
            label="AI Forensic Analyst"
            active={activeTab === "ai"}
            onClick={() => setActiveTab("ai")}
          />
          <SidebarItem
            icon={ScrollText}
            label="Evidence Log"
            active={activeTab === "claims"}
            onClick={() => setActiveTab("claims")}
          />
        </nav>

        <div style={{ padding: "24px", borderTop: `1px solid ${BORDER}`, display: "flex", flexDirection: "column", gap: 12 }}>
          <button
            onClick={onReset}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px",
              background: "transparent",
              border: `1px solid ${BORDER}`,
              color: INK_DIM,
              fontSize: 11,
              textTransform: "uppercase",
              cursor: "pointer",
              justifyContent: "center"
            }}
          >
            <ArrowLeft size={14} /> New Analysis
          </button>
          {sourceFile && (
            <DownloadExportButton 
              file={sourceFile} 
              apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"} 
            />
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main style={{ flex: 1, overflowY: "auto", padding: "48px" }}>
        <LocalModeBanner profile={profile} />
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === "overview" && <OverviewTab profile={profile} />}

            {activeTab === "behavior" && <BehaviorTab profile={profile} />}

            {activeTab === "network" && <NetworkTab profile={profile} />}

            {activeTab === "timeline" && <TimelineTab profile={profile} />}

            {activeTab === "interests" && <InterestsTab profile={profile} />}

            {activeTab === "privacy" && <PrivacyTab profile={profile} />}

            {activeTab === "ai" && (
              <AiTab
                sourceFile={sourceFile!}
                apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
                onBack={() => setActiveTab("overview")}
              />
            )}
            {activeTab === "claims" && <ClaimsTab profile={profile} />}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
