import React from "react";
import { render, screen } from "@testing-library/react";
import { useReducedMotion } from "framer-motion";
import { TargetingCard } from "../app/components/TargetingCard";
import type { TargetingCardResult } from "../engine/targetingCard";

jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy({}, { get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
    const { initial, animate, exit, transition, whileHover, whileTap, onAnimationComplete, ...dom } = rest as Record<string, unknown>;
    void initial; void animate; void exit; void transition; void whileHover; void whileTap; void onAnimationComplete;
    return React.createElement(tag, dom, children as React.ReactNode); } });
  return {
    motion,
    AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children),
    useReducedMotion: jest.fn(() => false),
  };
});

beforeEach(() => {
  (useReducedMotion as jest.Mock).mockReturnValue(false);
});

const ok: TargetingCardResult = {
  moduleId: "targeting_card", status: "ok", taxonomy_version: "2026.03-1",
  counts: { declared_ad_interest_count: 5, segment_count: 2, confirmed_count: 1 },
  claims: [
    { id: "targeting.segment.education", tier: "inferred", confidence: 0.7,
      evidence: [{ kind: "video", id: "1" }, { kind: "video", id: "2" }, { kind: "video", id: "3" }],
      method: "…taxonomy 2026.03-1…",
      value: { category: "Education", cluster_name: "study tips", matched: true, tiktok_confirmed: true } },
    { id: "targeting.segment.uncategorized.mystery", tier: "inferred", confidence: 0.7,
      evidence: [{ kind: "video", id: "4" }, { kind: "video", id: "5" }, { kind: "video", id: "6" }],
      method: "…taxonomy 2026.03-1…",
      value: { category: "Uncategorized interest", cluster_name: "mystery", matched: false, tiktok_confirmed: false } },
  ],
};

describe("TargetingCard", () => {
  test("ok: renders the cross-reference summary and each segment", () => {
    render(<TargetingCard result={ok} />);
    expect(screen.getByText(/TikTok admits/i)).toBeInTheDocument();
    expect(screen.getByText("Education")).toBeInTheDocument();
    expect(screen.getByText("Uncategorized interest")).toBeInTheDocument();
    expect(screen.getByText(/TikTok confirms/i)).toBeInTheDocument();
    expect(screen.getByText(/inferred-only/i)).toBeInTheDocument();
  });

  test("insufficient_evidence: renders the gated 'bring your own key' state", () => {
    render(<TargetingCard result={{
      moduleId: "targeting_card", status: "insufficient_evidence", taxonomy_version: "2026.03-1",
      requirements: { needed: "LLM topic pass (bring your own key)", had: "keyword fallback (no LLM key)" },
      claims: [], counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 },
    }} />);
    expect(screen.getByText(/bring your own key/i)).toBeInTheDocument();
  });

  test("error: renders a plain error note", () => {
    render(<TargetingCard result={{
      moduleId: "targeting_card", status: "error", error: "malformed TopicResult", taxonomy_version: "2026.03-1",
      claims: [], counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 },
    }} />);
    expect(screen.getByText(/couldn't|error|unavailable/i)).toBeInTheDocument();
  });

  test("undefined result renders nothing", () => {
    const { container } = render(<TargetingCard result={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  test("ok + motion enabled: SEALED stamp is present alongside segments (structural wiring of the reveal sequence)", () => {
    render(<TargetingCard result={ok} />);
    expect(screen.getByText("SEALED")).toBeInTheDocument();
    expect(screen.getByText("Education")).toBeInTheDocument();
  });

  test("ok + reduced motion: no SEALED stamp, segments render immediately", () => {
    (useReducedMotion as jest.Mock).mockReturnValue(true);
    render(<TargetingCard result={ok} />);
    expect(screen.queryByText("SEALED")).not.toBeInTheDocument();
    expect(screen.getByText("Education")).toBeInTheDocument();
  });

  test("insufficient_evidence: renders the INSUFFICIENT EVIDENCE stamp alongside the existing gated copy", () => {
    render(<TargetingCard result={{
      moduleId: "targeting_card", status: "insufficient_evidence", taxonomy_version: "2026.03-1",
      requirements: { needed: "LLM topic pass (bring your own key)", had: "keyword fallback (no LLM key)" },
      claims: [], counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 },
    }} />);
    expect(screen.getByText("INSUFFICIENT EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText(/bring your own key/i)).toBeInTheDocument();
  });

  test("error: does not render any stamp", () => {
    render(<TargetingCard result={{
      moduleId: "targeting_card", status: "error", error: "malformed TopicResult", taxonomy_version: "2026.03-1",
      claims: [], counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 },
    }} />);
    expect(screen.queryByText("SEALED")).not.toBeInTheDocument();
    expect(screen.queryByText("INSUFFICIENT EVIDENCE")).not.toBeInTheDocument();
  });
});
