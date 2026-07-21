import React from "react";
import { render, screen } from "@testing-library/react";
import { PersonaRadar } from "../app/components/PersonaRadar";
import type { PersonaResult } from "../engine/persona";

// recharts needs layout that jsdom lacks; stub to plain passthroughs so we test
// the component's own text output, not SVG geometry.
jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, RadarChart: Pass, PolarGrid: Pass, PolarAngleAxis: Pass, PolarRadiusAxis: Pass, Radar: Pass };
});

const ok: PersonaResult = {
  status: "ok",
  dimensions: { intentionality: 70, capture_susceptibility: 25, nocturnality: 90, exploration: 88, expressiveness: 55, parasociality: 40 },
  base_archetype: "The Seeker", nocturnality_modifier: "Nocturnal", display_name: "Nocturnal Seeker",
  secondary: "The Intentional Curator", confidence: 0.72, method: "…",
};

describe("PersonaRadar", () => {
  test("ok: shows display name, secondary, confidence", () => {
    render(<PersonaRadar result={ok} />);
    expect(screen.getByText("Nocturnal Seeker")).toBeInTheDocument();
    expect(screen.getByText(/Intentional Curator/)).toBeInTheDocument();
    expect(screen.getByText(/72%|0\.72/)).toBeInTheDocument();
  });

  test("insufficient_evidence: gated message", () => {
    render(<PersonaRadar result={{ status: "insufficient_evidence", dimensions: ok.dimensions, base_archetype: "", nocturnality_modifier: "", display_name: "", confidence: 0, requirements: { needed: "≥30 days and ≥500 conscious views", had: "5 days" }, method: "" }} />);
    expect(screen.getByText(/not enough|insufficient|30 days/i)).toBeInTheDocument();
  });

  test("undefined → renders nothing", () => {
    const { container } = render(<PersonaRadar result={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
