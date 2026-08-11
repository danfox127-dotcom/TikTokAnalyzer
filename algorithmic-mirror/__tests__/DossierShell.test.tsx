// algorithmic-mirror/__tests__/DossierShell.test.tsx
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
    const { initial, animate, exit, transition, whileHover, whileTap, onAnimationComplete, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap; void onAnimationComplete;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return {
    motion,
    AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children),
    useReducedMotion: () => false,
  };
});

const profile = {
  primary_archetype: { name: "The Balanced Viewer" },
  stopwatch_metrics: { total_conscious_videos: 0, graveyard_skips: 0, sandbox_views: 0, deep_lingers: 0, deep_dives: 0, hourly_heatmap: {} },
  behavioral_nodes: { linger_rate_percentage: 0, night_shift_ratio: 0, peak_hour: "12PM", inferred_sleep_window: "Unknown" },
} as unknown as GhostProfile;

describe("DossierShell (via ForensicDashboard)", () => {
  test("all 8 tab labels render in the sidebar", () => {
    render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
    for (const label of ["Overview", "Behavioral Signature", "Timeline", "Network & Influence", "Interests & Keywords", "Privacy & Footprint", "AI Forensic Analyst", "Evidence Log"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  test("clicking a tab switches activeTab and (async) renders its lazy-loaded content", async () => {
    render(<ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={new File(["{}"], "x.json")} />);
    fireEvent.click(screen.getByText("Behavioral Signature"));
    expect(await screen.findByText(/True Stopwatch Funnel/i)).toBeInTheDocument();
  });

  test("reset button fires onReset", () => {
    const onReset = jest.fn();
    render(<ForensicDashboard profile={profile} onReset={onReset} sourceFile={new File(["{}"], "x.json")} />);
    fireEvent.click(screen.getByText(/New Analysis/i));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
