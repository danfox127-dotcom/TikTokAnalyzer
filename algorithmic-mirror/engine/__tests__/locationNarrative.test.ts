import { buildLocationCard } from "../locationNarrative";

// Build a login at a given datetime + ip. NOTE: no trailing "Z" — the engine's
// parseDate accepts "YYYY-MM-DDTHH:MM:SS" (and space form) but NOT a Z suffix;
// it builds the Date via Date.UTC, so these hours read back via getUTCHours().
const login = (date: string, ip: string) => ({ date, ip });
const geo = (m: Record<string, string>) =>
  Object.fromEntries(Object.entries(m).map(([ip, city]) => [ip, { city, country_name: "US" }]));

describe("buildLocationCard", () => {
  test("home base = modal night-hours city; work = modal day-hours city when it differs", () => {
    // 5 distinct days. Nights (hour 02) in Chicago; days (hour 12) in New York.
    const parsed = {
      login_history: [
        login("2026-01-01T02:00:00", "1"), login("2026-01-01T12:00:00", "2"),
        login("2026-01-02T02:00:00", "1"), login("2026-01-02T12:00:00", "2"),
        login("2026-01-03T02:00:00", "1"), login("2026-01-03T12:00:00", "2"),
        login("2026-01-04T02:00:00", "1"), login("2026-01-04T12:00:00", "2"),
        login("2026-01-05T02:00:00", "1"), login("2026-01-05T12:00:00", "2"),
      ],
    };
    const card = buildLocationCard({ parsed, profile: {}, ipGeo: geo({ "1": "Chicago", "2": "New York" }) });
    expect(card.status).toBe("ok");
    const home = card.claims.find((c) => c.id === "demo.location.home")!;
    const work = card.claims.find((c) => c.id === "demo.location.work")!;
    expect(home.value).toBe("Chicago");
    expect(home.tier).toBe("derived");
    expect(work.value).toBe("New York");
  });

  test("trip = ≥2 consecutive days in a single non-home city", () => {
    const parsed = {
      login_history: [
        login("2026-01-01T02:00:00", "h"), login("2026-01-02T02:00:00", "h"),
        login("2026-01-03T02:00:00", "h"),
        login("2026-01-04T02:00:00", "t"), login("2026-01-05T02:00:00", "t"), // 2 consecutive away
        login("2026-01-06T02:00:00", "h"),
      ],
    };
    const card = buildLocationCard({ parsed, profile: {}, ipGeo: geo({ h: "Denver", t: "Miami" }) });
    const trips = card.claims.find((c) => c.id === "demo.location.trips")!;
    expect(trips.value).toEqual([{ city: "Miami", start: "2026-01-04", end: "2026-01-05", days: 2 }]);
  });

  test("single away-day is NOT a trip", () => {
    const parsed = {
      login_history: [
        login("2026-01-01T02:00:00", "h"), login("2026-01-02T02:00:00", "h"),
        login("2026-01-03T02:00:00", "t"),                              // one day away only
        login("2026-01-04T02:00:00", "h"), login("2026-01-05T02:00:00", "h"),
      ],
    };
    const card = buildLocationCard({ parsed, profile: {}, ipGeo: geo({ h: "Denver", t: "Miami" }) });
    expect(card.claims.find((c) => c.id === "demo.location.trips")).toBeUndefined();
  });

  test("< 5 geo-resolved days → insufficient_evidence", () => {
    const parsed = {
      login_history: [
        login("2026-01-01T02:00:00", "h"), login("2026-01-02T02:00:00", "h"),
        login("2026-01-03T02:00:00", "h"), login("2026-01-04T02:00:00", "x"), // "x" has no geo
        login("2026-01-05T02:00:00", "x"),
      ],
    };
    const card = buildLocationCard({ parsed, profile: {}, ipGeo: geo({ h: "Denver" }) });
    expect(card.status).toBe("insufficient_evidence");
    expect(card.requirements?.needed).toMatch(/geo-resolved days/i);
  });
});
