import React from "react";
import { render, screen } from "@testing-library/react";
import { ForensicDashboard } from "../app/components/ForensicDashboard";
import type { GhostProfile } from "../app/components/GhostProfileHUD";

jest.mock("../app/components/CreatorGraph", () => ({ CreatorGraph: () => <div data-testid="creator-graph" /> }));
jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, RadarChart: Pass, PolarGrid: Pass, PolarAngleAxis: Pass, PolarRadiusAxis: Pass, Radar: Pass,
    // some dashboard children may use other recharts pieces; stub broadly:
    BarChart: Pass, Bar: Pass, XAxis: Pass, YAxis: Pass, Tooltip: Pass, Cell: Pass, PieChart: Pass, Pie: Pass, LineChart: Pass, Line: Pass, CartesianGrid: Pass, Area: Pass, AreaChart: Pass };
});
jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const profile = {
  primary_archetype: { name: "The Balanced Viewer" },
  stopwatch_metrics: {
    total_conscious_videos: 100,
    sleep_anomalies_scrubbed: 0,
    sleep_scrubbed: 0,
    graveyard_skips: 0,
    sandbox_views: 0,
    deep_lingers: 0,
    deep_dives: 0,
  },
  behavioral_nodes: {
    linger_rate_percentage: 12,
    night_shift_ratio: 8,
    inferred_sleep_window: "Unknown",
    peak_hour: "9 PM",
  },
  persona: {
    status: "ok",
    dimensions: { intentionality: 70, capture_susceptibility: 25, nocturnality: 90, exploration: 88, expressiveness: 55, parasociality: 40 },
    base_archetype: "The Seeker", nocturnality_modifier: "Nocturnal", display_name: "Nocturnal Seeker", confidence: 0.72, method: "…",
  },
} as unknown as GhostProfile;

test("Overview tab renders the Persona radar from the payload", async () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  expect(await screen.findByText("Nocturnal Seeker")).toBeInTheDocument();
});
