import React from "react";
import { render } from "@testing-library/react";
import { AiTab } from "../AiTab";

test("AiTab renders without throwing", () => {
  const { container } = render(
    <AiTab sourceFile={new File(["{}"], "x.json")} apiUrl="http://localhost:8005" onBack={jest.fn()} />
  );
  expect(container).not.toBeEmptyDOMElement();
});
