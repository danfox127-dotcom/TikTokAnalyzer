import React from "react";
import { render } from "@testing-library/react";
import { BehaviorTab } from "../BehaviorTab";
import type { GhostProfile } from "../../GhostProfileHUD";

jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const profile = {
  stopwatch_metrics: {
    total_conscious_videos: 10, graveyard_skips: 1, sandbox_views: 2, deep_lingers: 3, deep_dives: 4,
    hourly_heatmap: {}, total_raw_videos: 10,
  },
  behavioral_nodes: { night_shift_ratio: 5 },
  academic_insights: { explicit_vs_implicit_ratio: 0.5 },
} as unknown as GhostProfile;

test("BehaviorTab renders without throwing", () => {
  const { container } = render(<BehaviorTab profile={profile} />);
  expect(container).not.toBeEmptyDOMElement();
});
