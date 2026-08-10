import React from "react";
import { render, screen } from "@testing-library/react";
import { PrivacyTab } from "../PrivacyTab";
import type { GhostProfile } from "../../GhostProfileHUD";

const profile = {
  digital_footprint: { unique_ips: 0, unique_devices: [], recent_logins: [] },
} as unknown as GhostProfile;

test("PrivacyTab renders without throwing", () => {
  render(<PrivacyTab profile={profile} />);
  expect(screen.getByText(/Geographic & Device Trace/i)).toBeInTheDocument();
});
