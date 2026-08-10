// algorithmic-mirror/app/components/__tests__/ClaimStat.test.tsx
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ClaimStat } from "../ClaimStat";
import type { Claim } from "../../../engine/types";

jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return { motion, AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children) };
});

const claim: Claim = {
  id: "attention.skip_rate_pct", tier: "derived", value: 42,
  method: "Share of conscious views skipped in under 3 seconds.",
  evidence: [{ kind: "video", note: "1200 skips / 3400 conscious views" }],
};

describe("ClaimStat", () => {
  test("renders label, value, tier badge, and method", () => {
    render(<ClaimStat claim={claim} label="Skip Rate" />);
    expect(screen.getByText("Skip Rate")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText(/derived/i)).toBeInTheDocument();
    expect(screen.getByText(claim.method)).toBeInTheDocument();
  });

  test("children override the default value display", () => {
    render(<ClaimStat claim={claim} label="Skip Rate"><span>90th percentile</span></ClaimStat>);
    expect(screen.getByText("90th percentile")).toBeInTheDocument();
    expect(screen.queryByText("42")).not.toBeInTheDocument();
  });

  test("clicking opens the evidence panel showing the evidence note", () => {
    render(<ClaimStat claim={claim} label="Skip Rate" />);
    fireEvent.click(screen.getByText("42"));
    expect(screen.getByText(/1200 skips \/ 3400 conscious views/)).toBeInTheDocument();
  });
});
