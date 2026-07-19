import React from "react";
import { render, screen } from "@testing-library/react";
import { TargetingCard } from "../app/components/TargetingCard";
import type { TargetingCardResult } from "../engine/targetingCard";

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
    // confirmed vs inferred-only chips both present
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
});
