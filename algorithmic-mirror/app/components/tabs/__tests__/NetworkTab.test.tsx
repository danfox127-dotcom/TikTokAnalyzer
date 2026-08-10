import React from "react";
import { render } from "@testing-library/react";
import { NetworkTab } from "../NetworkTab";
import type { GhostProfile } from "../../GhostProfileHUD";

jest.mock("../../CreatorGraph", () => ({ CreatorGraph: () => <div data-testid="creator-graph" /> }));

const profile = {
  creator_entities: { graveyard: [], vibe_cluster: [] },
  behavioral_nodes: { social_graph_followed_pct: 0, social_graph_algorithmic_pct: 0 },
} as unknown as GhostProfile;

test("NetworkTab renders without throwing", () => {
  const { container } = render(<NetworkTab profile={profile} />);
  expect(container).not.toBeEmptyDOMElement();
});
