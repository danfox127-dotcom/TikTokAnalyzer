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

/**
 * Regression: the two range inputs overlay one track, so only the topmost
 * thumb is hit-testable where they coincide. With DOM order alone deciding
 * that, dragging Start to the last month collapsed the range to [last, last]
 * with Start buried and End unable to move right — a pointer dead end.
 */
describe('overlapping thumbs stay reachable', () => {
  const MONTHS = ['2025-01', '2025-02', '2025-03', '2025-04'];

  function layers(container: HTMLElement) {
    const start = container.querySelector('input[aria-label="Start month"]') as HTMLInputElement;
    const end = container.querySelector('input[aria-label="End month"]') as HTMLInputElement;
    return { start: Number(start.style.zIndex), end: Number(end.style.zIndex) };
  }

  it('puts End on top for a normal range, so it can always widen rightwards', () => {
    const { container } = render(
      <MonthRangeScrubber months={MONTHS} value={['2025-01', '2025-03']} onChange={() => {}} />,
    );
    const { start, end } = layers(container);
    expect(end).toBeGreaterThan(start);
  });

  it('puts End on top when both thumbs collapse at the first month', () => {
    // Only End can move here — Start clamps to min(value, endIndex) = 0.
    const { container } = render(
      <MonthRangeScrubber months={MONTHS} value={['2025-01', '2025-01']} onChange={() => {}} />,
    );
    const { start, end } = layers(container);
    expect(end).toBeGreaterThan(start);
  });

  it('raises Start above End when both collapse at the last month', () => {
    // The trap: End is pinned at the maximum and clamped to >= start, so the
    // only way out is dragging Start left — which requires Start on top.
    const { container } = render(
      <MonthRangeScrubber months={MONTHS} value={['2025-04', '2025-04']} onChange={() => {}} />,
    );
    const { start, end } = layers(container);
    expect(start).toBeGreaterThan(end);
  });

  // NB: this one passes with or without the z-index fix — fireEvent.change
  // dispatches straight at the element and never consults hit-testing, which
  // is precisely the thing that was broken. It documents that the escape route
  // exists once Start is reachable; the three tests above are what pin the
  // reachability itself.
  it('lets Start move back off the last month once it is on top', () => {
    const onChange = jest.fn();
    const { container } = render(
      <MonthRangeScrubber months={MONTHS} value={['2025-04', '2025-04']} onChange={onChange} />,
    );
    const start = container.querySelector('input[aria-label="Start month"]') as HTMLInputElement;
    fireEvent.change(start, { target: { value: '1' } });
    expect(onChange).toHaveBeenCalledWith(['2025-02', '2025-04']);
  });
});
