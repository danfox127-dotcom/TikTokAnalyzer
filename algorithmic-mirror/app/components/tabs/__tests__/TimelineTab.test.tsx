import React from "react";
import { render } from "@testing-library/react";
import { TimelineTab } from "../TimelineTab";
import type { GhostProfile } from "../../GhostProfileHUD";

jest.mock("recharts", () => {
  const React = require("react");
  const Pass = ({ children }: any) => React.createElement("div", null, children);
  return { ResponsiveContainer: Pass, LineChart: Pass, Line: Pass, XAxis: Pass, YAxis: Pass, CartesianGrid: Pass, Tooltip: Pass, Legend: Pass };
});

const profile = {
  stopwatch_metrics: {},
} as unknown as GhostProfile;

test("TimelineTab renders without throwing", () => {
  const { container } = render(<TimelineTab profile={profile} />);
  expect(container).not.toBeEmptyDOMElement();
});
