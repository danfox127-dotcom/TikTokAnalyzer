import React from "react";
import { render, screen } from "@testing-library/react";
import { ClaimsTab } from "../ClaimsTab";
import type { GhostProfile } from "../../GhostProfileHUD";

const profile = { claims: [] } as unknown as GhostProfile;

test("ClaimsTab renders without throwing", () => {
  render(<ClaimsTab profile={profile} />);
  expect(screen.getByText(/Every Claim, By Tier/i)).toBeInTheDocument();
});
