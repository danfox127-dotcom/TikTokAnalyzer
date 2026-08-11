import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MonthRangeScrubber } from "../MonthRangeScrubber";

const months = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05"];

test("renders start and end month labels", () => {
  render(<MonthRangeScrubber months={months} value={["2025-01", "2025-05"]} onChange={() => {}} />);
  expect(screen.getByText("2025-01")).toBeInTheDocument();
  expect(screen.getByText("2025-05")).toBeInTheDocument();
});

test("dragging the start thumb forward calls onChange with the new start, unchanged end", () => {
  const onChange = jest.fn();
  render(<MonthRangeScrubber months={months} value={["2025-01", "2025-05"]} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("Start month"), { target: { value: "2" } });
  expect(onChange).toHaveBeenCalledWith(["2025-03", "2025-05"]);
});

test("dragging the end thumb backward calls onChange with unchanged start, new end", () => {
  const onChange = jest.fn();
  render(<MonthRangeScrubber months={months} value={["2025-01", "2025-05"]} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("End month"), { target: { value: "2" } });
  expect(onChange).toHaveBeenCalledWith(["2025-01", "2025-03"]);
});

test("the start thumb cannot be dragged past the end thumb", () => {
  const onChange = jest.fn();
  render(<MonthRangeScrubber months={months} value={["2025-01", "2025-02"]} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("Start month"), { target: { value: "4" } });
  expect(onChange).toHaveBeenCalledWith(["2025-02", "2025-02"]);
});

test("the end thumb cannot be dragged before the start thumb", () => {
  const onChange = jest.fn();
  render(<MonthRangeScrubber months={months} value={["2025-03", "2025-04"]} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("End month"), { target: { value: "0" } });
  expect(onChange).toHaveBeenCalledWith(["2025-03", "2025-03"]);
});
