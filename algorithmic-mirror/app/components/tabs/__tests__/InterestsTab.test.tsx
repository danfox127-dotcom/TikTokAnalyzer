import React from "react";
import { render, screen } from "@testing-library/react";
import { InterestsTab } from "../InterestsTab";
import type { GhostProfile } from "../../GhostProfileHUD";

const profile = {
  interest_clusters: [],
  targeting_card: { moduleId: "targeting_card", status: "error", error: "no data", claims: [],
    counts: { declared_ad_interest_count: 0, segment_count: 0, confirmed_count: 0 }, taxonomy_version: "v" },
} as unknown as GhostProfile;

test("InterestsTab renders without throwing", () => {
  render(<InterestsTab profile={profile} />);
  expect(screen.getByText(/Behavioral Interest Clusters/i)).toBeInTheDocument();
});
