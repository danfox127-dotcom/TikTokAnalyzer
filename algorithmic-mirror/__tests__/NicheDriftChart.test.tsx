import React from "react";
import { render, screen } from "@testing-library/react";
import { NicheDriftChart } from "../app/components/NicheDriftChart";
import type { NicheDriftResult } from "../engine/nicheDrift";

// recharts needs layout jsdom lacks; stub to passthroughs so we test text output.
jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  const LineChart = ({ children, data }: any) =>
    React.createElement("div", { "data-testid": "linechart", "data-points": String((data ?? []).length) }, children);
  return { ResponsiveContainer: Pass, LineChart, Line: Pass, XAxis: Pass, YAxis: Pass, CartesianGrid: Pass, Tooltip: Pass, Legend: Pass };
});

const ok: NicheDriftResult = {
  status: "ok",
  series: { granularity: "month", points: [
    { period: "2026-01", value: { period: "2026-01", distinct_creators: 40, top5_concentration_pct: 34 } },
    { period: "2026-06", value: { period: "2026-06", distinct_creators: 12, top5_concentration_pct: 58 } },
  ] },
  distinct_creators_trend: { slope: -5.2, direction: "narrowing" },
  top5_concentration_trend: { slope: 4.1, direction: "narrowing" },
  resolved_coverage_pct: 82,
  method: "…",
};

describe("NicheDriftChart", () => {
  test("ok narrowing: renders the narrative headline (first→last creators)", () => {
    render(<NicheDriftChart result={ok} />);
    expect(screen.getByText(/narrowed/i)).toBeInTheDocument();
    expect(screen.getByText(/40/)).toBeInTheDocument();
    expect(screen.getByText(/12/)).toBeInTheDocument();
  });

  test("insufficient_evidence: gated message", () => {
    render(<NicheDriftChart result={{
      status: "insufficient_evidence",
      series: { granularity: "month", points: [] },
      distinct_creators_trend: { slope: null, direction: "insufficient_trend" },
      top5_concentration_trend: { slope: null, direction: "insufficient_trend" },
      resolved_coverage_pct: 20,
      requirements: { needed: "≥40% of watched videos resolved to a creator", had: "20%" },
      method: "…",
    }} />);
    expect(screen.getByText(/resolved to a creator|not enough/i)).toBeInTheDocument();
  });

  test("ok with insufficient_trend on 2 points: does not claim 'held steady', shows honest fallback", () => {
    const insufficientTrend: NicheDriftResult = {
      status: "ok",
      series: { granularity: "month", points: [
        { period: "2026-01", value: { period: "2026-01", distinct_creators: 30, top5_concentration_pct: 40 } },
        { period: "2026-02", value: { period: "2026-02", distinct_creators: 28, top5_concentration_pct: 42 } },
      ] },
      distinct_creators_trend: { slope: null, direction: "insufficient_trend" },
      top5_concentration_trend: { slope: null, direction: "insufficient_trend" },
      resolved_coverage_pct: 82,
      method: "…",
    };
    render(<NicheDriftChart result={insufficientTrend} />);
    expect(screen.queryByText(/held steady/i)).not.toBeInTheDocument();
    expect(screen.getByText(/too few periods/i)).toBeInTheDocument();
  });

  test("undefined → renders nothing", () => {
    const { container } = render(<NicheDriftChart result={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  test("no visibleRange: plots every point", () => {
    render(<NicheDriftChart result={ok} />);
    expect(screen.getByTestId("linechart")).toHaveAttribute("data-points", "2");
  });

  test("visibleRange narrows the plotted points but not the headline", () => {
    render(<NicheDriftChart result={ok} visibleRange={["2026-01", "2026-01"]} />);
    expect(screen.getByTestId("linechart")).toHaveAttribute("data-points", "1");
    // headline still reads the full, unfiltered result (40 → 12), not the visible slice
    expect(screen.getByText(/narrowed/i)).toBeInTheDocument();
    expect(screen.getByText(/40/)).toBeInTheDocument();
    expect(screen.getByText(/12/)).toBeInTheDocument();
  });

  test("visibleRange with quarter granularity keeps a quarter whose range overlaps at all", () => {
    const quarterly: NicheDriftResult = {
      ...ok,
      series: { granularity: "quarter", points: [
        { period: "2026-Q1", value: { period: "2026-Q1", distinct_creators: 40, top5_concentration_pct: 34 } },
        { period: "2026-Q3", value: { period: "2026-Q3", distinct_creators: 12, top5_concentration_pct: 58 } },
      ] },
    };
    render(<NicheDriftChart result={quarterly} visibleRange={["2026-02", "2026-02"]} />);
    // 2026-02 falls inside Q1 (Jan-Mar), not Q3 (Jul-Sep)
    expect(screen.getByTestId("linechart")).toHaveAttribute("data-points", "1");
  });
});
