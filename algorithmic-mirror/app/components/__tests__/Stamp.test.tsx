import React from "react";
import { render, screen } from "@testing-library/react";
import { Stamp } from "../Stamp";

test("renders the given label", () => {
  render(<Stamp label="SEALED" />);
  expect(screen.getByText("SEALED")).toBeInTheDocument();
});

test("renders a different label", () => {
  render(<Stamp label="INSUFFICIENT EVIDENCE" />);
  expect(screen.getByText("INSUFFICIENT EVIDENCE")).toBeInTheDocument();
});
