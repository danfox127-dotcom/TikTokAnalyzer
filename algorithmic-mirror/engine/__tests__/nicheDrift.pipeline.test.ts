import { runEngine } from "../pipeline";

test("runEngine surfaces a niche_drift result", () => {
  const raw = {
    "Your Activity": {
      "Watch History": { VideoList: [
        { Date: "2024-01-01 10:00:00", Link: "https://www.tiktok.com/@creator/video/111" },
        { Date: "2024-01-01 10:01:00", Link: "https://www.tiktok.com/@creator/video/222" },
      ] },
    },
  };
  const { niche_drift } = runEngine(raw);
  expect(niche_drift).toBeDefined();
  expect(["ok", "insufficient_evidence", "error"]).toContain(niche_drift.status);
  expect(niche_drift.series).toBeDefined();
});
