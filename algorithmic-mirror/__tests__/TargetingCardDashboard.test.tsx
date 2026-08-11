import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ForensicDashboard } from "../app/components/ForensicDashboard";
import type { GhostProfile } from "../app/components/GhostProfileHUD";

jest.mock("../app/components/CreatorGraph", () => ({ CreatorGraph: () => <div data-testid="creator-graph" /> }));
jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, {
    get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
      const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
      void initial; void animate; void exit; void transition; void whileHover; void whileTap;
      return React.createElement(tag, dom, children as React.ReactNode);
    },
  });
  return {
    motion,
    AnimatePresence: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    useReducedMotion: () => false,
  };
});

// Minimal profile: only what the Interests tab touches. Pad with any field the
// component dereferences if the mount throws (optional-chained fields default fine).
const profile = {
  primary_archetype: { name: "The Balanced Viewer" },
  interest_clusters: [],
  stopwatch_metrics: {
    total_conscious_videos: 0,
    graveyard_skips: 0, sandbox_views: 0, deep_lingers: 0, deep_dives: 0,
  },
  behavioral_nodes: {
    linger_rate_percentage: 0, night_shift_ratio: 0, peak_hour: "12PM",
    inferred_sleep_window: "Unknown",
    social_graph_algorithmic_pct: 0, social_graph_followed_pct: 0,
  },
  targeting_card: {
    moduleId: "targeting_card", status: "insufficient_evidence", taxonomy_version: "2026.03-1",
    requirements: { needed: "LLM topic pass (bring your own key)", had: "keyword fallback (no LLM key)" },
    claims: [], counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 },
  },
} as unknown as GhostProfile;

test("Interests tab renders the Targeting Card panel from the payload", async () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Interests & Keywords/i));
  expect(await screen.findByText(/Targeting Card/i)).toBeInTheDocument();
  expect(await screen.findByText(/bring your own key/i)).toBeInTheDocument();
});
