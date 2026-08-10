// algorithmic-mirror/app/components/__tests__/ClaimText.test.tsx
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ClaimText } from "../ClaimText";
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
  id: "demo.gender", tier: "recorded", value: "female",
  method: "TikTok's own inferred-gender label, taken verbatim from your export.",
  evidence: [{ kind: "settings", note: "stored inferredGender" }],
};

describe("ClaimText", () => {
  test("default: renders the formatted value and the tier label", () => {
    render(<ClaimText claim={claim} />);
    expect(screen.getByText("female")).toBeInTheDocument();
    expect(screen.getByText(/recorded/i)).toBeInTheDocument();
  });

  test("children override the default value display", () => {
    render(<ClaimText claim={claim}><span>custom content</span></ClaimText>);
    expect(screen.getByText("custom content")).toBeInTheDocument();
    expect(screen.queryByText("female")).not.toBeInTheDocument();
  });

  test("clicking opens the evidence panel showing the method", () => {
    render(<ClaimText claim={claim} />);
    fireEvent.click(screen.getByText("female"));
    expect(screen.getByText(claim.method)).toBeInTheDocument();
  });

  test("pressing Enter opens the evidence panel showing the method", () => {
    render(<ClaimText claim={claim} />);
    fireEvent.keyDown(screen.getByText("female"), { key: "Enter" });
    expect(screen.getByText(claim.method)).toBeInTheDocument();
  });
});
