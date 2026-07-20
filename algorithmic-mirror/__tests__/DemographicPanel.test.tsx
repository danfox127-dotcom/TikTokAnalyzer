import React from "react";
import { render, screen } from "@testing-library/react";
import { DemographicPanel } from "../app/components/DemographicPanel";
import type { DemographicModuleResult } from "../engine/demographics";

const cite = { kind: "external_source" as const, citation: "PIPEDA #2025-003", note: "TikTok is documented to infer gender" };
const ok: DemographicModuleResult = {
  moduleId: "demographics", status: "ok",
  cards: [
    { category: "gender", status: "ok", tiktok_infers: cite,
      claims: [{ id: "demo.gender", tier: "recorded", value: "female", method: "verbatim label.", evidence: [cite] }] },
    { category: "location", status: "insufficient_evidence", tiktok_infers: { ...cite, note: "TikTok is documented to infer location" },
      claims: [], requirements: { needed: "≥5 logins and ≥5 geo-resolved days", had: "2 logins" } },
  ],
};

const withTrips: DemographicModuleResult = {
  moduleId: "demographics", status: "ok",
  cards: [
    { category: "location", status: "ok", tiktok_infers: { ...cite, note: "TikTok is documented to infer location" },
      claims: [{
        id: "demo.location.trips", tier: "derived",
        value: [{ city: "Miami", start: "2026-01-04", end: "2026-01-05", days: 2 }],
        method: "Detected trips from geo-resolved logins.",
        evidence: [{ kind: "login", note: "trip detection" }, cite],
      }] },
  ],
};

describe("DemographicPanel", () => {
  test("renders each card with the PIPEDA line and the reconstructed value / gated state", () => {
    render(<DemographicPanel result={ok} />);
    expect(screen.getAllByText(/PIPEDA #2025-003/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("female")).toBeInTheDocument();          // ok card value
    expect(screen.getByText(/recorded/i)).toBeInTheDocument();       // tier chip
    expect(screen.getByText(/geo-resolved days/i)).toBeInTheDocument(); // gated card requirements
  });

  test("location card with trips claim renders the city name, not [object Object]", () => {
    render(<DemographicPanel result={withTrips} />);
    expect(screen.getByText(/Miami/)).toBeInTheDocument();
    expect(screen.queryByText(/object Object/)).toBeNull();
  });

  test("module error → a plain error note", () => {
    render(<DemographicPanel result={{ moduleId: "demographics", status: "error", error: "malformed input", cards: [] }} />);
    expect(screen.getByText(/unavailable|error/i)).toBeInTheDocument();
  });

  test("undefined result renders nothing", () => {
    const { container } = render(<DemographicPanel result={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
