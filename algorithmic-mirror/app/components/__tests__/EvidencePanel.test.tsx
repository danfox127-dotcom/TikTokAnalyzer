import React from "react";
import { render, screen } from "@testing-library/react";
import { EvidencePanel } from "../EvidencePanel";
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

describe("EvidencePanel", () => {
  test("legacy string-based API still works unchanged (regression)", () => {
    render(<EvidencePanel open title="Skip Rate" claim="raw claim text" payload={{ a: 1 }} onClose={jest.fn()} />);
    expect(screen.getByText("Skip Rate")).toBeInTheDocument();
    expect(screen.getByText(/raw claim text/)).toBeInTheDocument();
  });

  test("claimObj path: shows the tier badge, method, and evidence list", () => {
    render(<EvidencePanel open title={null} claim={null} payload={null} claimObj={claim} onClose={jest.fn()} />);
    expect(screen.getByText(/derived/i)).toBeInTheDocument();
    expect(screen.getByText(claim.method)).toBeInTheDocument();
    expect(screen.getByText(/1200 skips \/ 3400 conscious views/)).toBeInTheDocument();
  });

  test("claimObj with empty evidence shows the no-evidence note, not a crash", () => {
    const empty: Claim = { ...claim, evidence: [] };
    render(<EvidencePanel open title={null} claim={null} payload={null} claimObj={empty} onClose={jest.fn()} />);
    expect(screen.getByText(/no evidence captured/i)).toBeInTheDocument();
  });
});
