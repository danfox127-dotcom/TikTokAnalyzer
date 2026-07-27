import { runEngine } from "../pipeline";

test("runEngine surfaces a persona result", () => {
  const raw = {
    "Your Activity": {
      "Watch History": { VideoList: [
        { Date: "2024-01-01 10:00:00", Link: "https://www.tiktokv.com/share/video/111/" },
        { Date: "2024-01-01 10:01:00", Link: "https://www.tiktokv.com/share/video/222/" },
      ] },
    },
  };
  const { persona } = runEngine(raw);
  expect(persona).toBeDefined();
  expect(["ok", "insufficient_evidence", "error"]).toContain(persona.status);
  expect(typeof persona.dimensions.intentionality).toBe("number");
});
