import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ForensicDashboard } from "../app/components/ForensicDashboard";
import type { GhostProfile } from "../app/components/GhostProfileHUD";

jest.mock("../app/components/CreatorGraph", () => ({ CreatorGraph: () => <div data-testid="creator-graph" /> }));
jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, LineChart: Pass, Line: Pass, XAxis: Pass, YAxis: Pass, CartesianGrid: Pass, Tooltip: Pass, Legend: Pass,
    BarChart: Pass, Bar: Pass, Cell: Pass, PieChart: Pass, Pie: Pass, RadarChart: Pass, Radar: Pass, PolarGrid: Pass, PolarAngleAxis: Pass, PolarRadiusAxis: Pass, Area: Pass, AreaChart: Pass };
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
  stopwatch_metrics: { total_conscious_videos: 100 },
  behavioral_nodes: { linger_rate_percentage: 20 },
  niche_drift: {
    status: "ok",
    series: { granularity: "month", points: [
      { period: "2026-01", value: { period: "2026-01", distinct_creators: 40, top5_concentration_pct: 34 } },
      { period: "2026-06", value: { period: "2026-06", distinct_creators: 12, top5_concentration_pct: 58 } },
    ] },
    distinct_creators_trend: { slope: -5.2, direction: "narrowing" },
    top5_concentration_trend: { slope: 4.1, direction: "narrowing" },
    resolved_coverage_pct: 82, method: "…",
  },
} as unknown as GhostProfile;

test("Timeline tab renders the niche-drift chart from the payload", async () => {
  render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
  fireEvent.click(screen.getByText(/Timeline|Evolution/i));
  expect(await screen.findByText(/narrowed from 40 to 12/i)).toBeInTheDocument();
});
