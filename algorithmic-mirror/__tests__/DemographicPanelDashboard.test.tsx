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
  return { motion, AnimatePresence: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children) };
});

const cite = { kind: "external_source" as const, citation: "PIPEDA #2025-003", note: "TikTok is documented to infer gender" };
const profile = {
  primary_archetype: { name: "The Balanced Viewer" },
  stopwatch_metrics: {
    total_conscious_videos: 0,
    graveyard_skips: 0, sandbox_views: 0, deep_lingers: 0, deep_dives: 0,
  },
  behavioral_nodes: {
    linger_rate_percentage: 0, night_shift_ratio: 0, peak_hour: "12PM",
    inferred_sleep_window: "Unknown",
    social_graph_algorithmic_pct: 0, social_graph_followed_pct: 0,
  },
  demographics: {
    moduleId: "demographics", status: "ok",
    cards: [{ category: "gender", status: "ok", tiktok_infers: cite,
      claims: [{ id: "demo.gender", tier: "recorded", value: "female", method: "verbatim label.", evidence: [cite] }] }],
  },
} as unknown as GhostProfile;

test("Privacy tab renders the Demographic panel from the payload", async () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Privacy & Footprint/i));
  expect(await screen.findByText(/What TikTok Infers About You/i)).toBeInTheDocument();
  expect(await screen.findByText(/PIPEDA #2025-003/)).toBeInTheDocument();
});
