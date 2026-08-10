import React from "react";
import { render } from "@testing-library/react";
import { OverviewTab } from "../OverviewTab";
import type { GhostProfile } from "../../GhostProfileHUD";

jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, RadarChart: Pass, PolarGrid: Pass, PolarAngleAxis: Pass, PolarRadiusAxis: Pass, Radar: Pass };
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
  stopwatch_metrics: { total_conscious_videos: 0, graveyard_skips: 0, sandbox_views: 0, deep_lingers: 0, deep_dives: 0 },
  behavioral_nodes: { linger_rate_percentage: 0, night_shift_ratio: 0, peak_hour: "12PM", inferred_sleep_window: "Unknown" },
} as unknown as GhostProfile;

test("OverviewTab renders without throwing", () => {
  const { container } = render(<OverviewTab profile={profile} />);
  expect(container).not.toBeEmptyDOMElement();
});
