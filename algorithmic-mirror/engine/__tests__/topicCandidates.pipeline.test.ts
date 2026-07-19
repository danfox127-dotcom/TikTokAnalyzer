import { runEngine } from "../pipeline";

test("runEngine surfaces topicCandidates from watched videos", () => {
  const raw = {
    "Your Activity": {
      "Watch History": {
        VideoList: [
          { Date: "2024-01-01 10:00:00", Link: "https://www.tiktokv.com/share/video/111/" },
          { Date: "2024-01-01 10:01:00", Link: "https://www.tiktokv.com/share/video/222/" }, // ~60s linger
          { Date: "2024-01-01 10:04:30", Link: "https://www.tiktokv.com/share/video/333/" }, // ~210s deep dive
          { Date: "2024-01-01 10:05:00", Link: "" },
        ],
      },
      "Like List": { ItemFavoriteList: [{ Date: "2024-01-01 10:01:30", Link: "https://www.tiktokv.com/share/video/222/" }] },
    },
  };
  const { topicCandidates } = runEngine(raw);
  expect(Array.isArray(topicCandidates)).toBe(true);
  const ids = topicCandidates.map((c) => c.video_id);
  expect(ids).toContain("222"); // watched, non-skip → a candidate
});
