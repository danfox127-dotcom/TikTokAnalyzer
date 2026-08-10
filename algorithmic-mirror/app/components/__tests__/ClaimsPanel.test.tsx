import React from "react";
import { render, screen } from "@testing-library/react";
import { ClaimsPanel } from "../ClaimsPanel";
import type { Claim } from "../../../engine/types";

jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const claims: Claim[] = [
  { id: "declared.follower_count", tier: "recorded", value: 120, method: "From the export.", evidence: [{ kind: "follow" }] },
  { id: "attention.skip_rate_pct", tier: "derived", value: 42, method: "Computed.", evidence: [{ kind: "video" }] },
  { id: "identity.archetype", tier: "inferred", value: "The Seeker", method: "Nearest centroid.", confidence: 0.7, evidence: [{ kind: "video" }] },
];

describe("ClaimsPanel", () => {
  test("groups claims by tier with per-tier counts", () => {
    render(<ClaimsPanel claims={claims} />);
    expect(screen.getByText(/1 recorded/i)).toBeInTheDocument();
    expect(screen.getByText(/1 derived/i)).toBeInTheDocument();
    expect(screen.getByText(/1 inferred/i)).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("The Seeker")).toBeInTheDocument();
  });

  test("empty/undefined claims → a plain note, not a crash", () => {
    render(<ClaimsPanel claims={[]} />);
    expect(screen.getByText(/no claims/i)).toBeInTheDocument();
    render(<ClaimsPanel claims={undefined} />);
    expect(screen.getAllByText(/no claims/i).length).toBeGreaterThan(0);
  });
});
