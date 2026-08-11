import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { TimelineTab } from "../TimelineTab";
import type { GhostProfile } from "../../GhostProfileHUD";

jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, LineChart: Pass, Line: Pass, XAxis: Pass, YAxis: Pass, CartesianGrid: Pass, Tooltip: Pass, Legend: Pass };
});

const minimalProfile = {
  stopwatch_metrics: {},
} as unknown as GhostProfile;

const richProfile = {
  stopwatch_metrics: {
    monthly_skip_rates: { "2026-01": 40, "2026-02": 35, "2026-03": 50 },
  },
  skip_anomalies: [
    { month: "2026-03", skip_rate: 50, baseline_avg: 38, delta: 12, direction: "spike" as const },
  ],
  monthly_creator_trends: {
    "2026-01": [{ handle: "@one", count: 10 }],
    "2026-02": [{ handle: "@two", count: 8 }],
    "2026-03": [{ handle: "@three", count: 5 }],
  },
  monthly_topic_trends: {
    "2026-01": [{ term: "cooking", count: 12 }],
    "2026-02": [{ term: "hiking", count: 9 }],
    "2026-03": [{ term: "coding", count: 7 }],
  },
} as unknown as GhostProfile;

test("TimelineTab renders without throwing", () => {
  const { container } = render(<TimelineTab profile={minimalProfile} />);
  expect(container).not.toBeEmptyDOMElement();
});

test("with < 2 months of history, no scrubber renders", () => {
  render(<TimelineTab profile={minimalProfile} />);
  expect(screen.queryByLabelText("Start month")).not.toBeInTheDocument();
});

test("with >= 2 months of history, the scrubber renders spanning the full range", () => {
  render(<TimelineTab profile={richProfile} />);
  expect(screen.getByLabelText("Start month")).toHaveValue("0");
  expect(screen.getByLabelText("End month")).toHaveValue("2");
});

test("narrowing the range hides creator/topic cards outside it", () => {
  render(<TimelineTab profile={richProfile} />);
  expect(screen.getByText("@one")).toBeInTheDocument();
  expect(screen.getByText("@three")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("End month"), { target: { value: "0" } });

  expect(screen.getByText("@one")).toBeInTheDocument();
  expect(screen.queryByText("@three")).not.toBeInTheDocument();
});

test("narrowing the range drops out-of-window anomalies", () => {
  render(<TimelineTab profile={richProfile} />);
  expect(screen.getByText(/anomaly/i)).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("End month"), { target: { value: "0" } });

  expect(screen.queryByText(/anomaly/i)).not.toBeInTheDocument();
});
