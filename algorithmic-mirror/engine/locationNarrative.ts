/**
 * WP-2.3 — location movement narrative. Pure, browser-safe. Over the full login
 * history joined to an IP→city map: home base (modal night-hours city), work base
 * (modal day-hours city, only if it differs), and trips (≥2 consecutive days in a
 * single non-home city). Emits only IDs/cities/derived facts — no titles, no raw IPs.
 */
import { parseDate } from "./parseDate";
import type { Claim } from "./types";
import { pipedaCitation, type DemographicCard, type DemographicInput } from "./demographics";

const NIGHT_HOURS = new Set([23, 0, 1, 2, 3]);
const DAY_HOURS = new Set([9, 10, 11, 12, 13, 14, 15, 16]);
const MIN_LOGINS = 5;
const MIN_GEO_DAYS = 5;

interface GeoLogin { city: string; day: string; hour: number; }

function modalCity(cities: string[]): string | null {
  if (!cities.length) return null;
  const counts = new Map<string, number>();
  for (const c of cities) counts.set(c, (counts.get(c) ?? 0) + 1);
  // highest count, ties broken by city name ascending (stable/deterministic)
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))[0][0];
}

function isNextDay(a: string, b: string): boolean {
  const da = new Date(a + "T00:00:00Z").getTime();
  const db = new Date(b + "T00:00:00Z").getTime();
  return db - da === 86400000;
}

function detectTrips(geoLogins: GeoLogin[], home: string) {
  const byDay = new Map<string, string[]>();
  for (const g of geoLogins) {
    if (!byDay.has(g.day)) byDay.set(g.day, []);
    byDay.get(g.day)!.push(g.city);
  }
  const dayCity = [...byDay.entries()]
    .map(([day, cities]) => ({ day, city: modalCity(cities)! }))
    .sort((a, b) => (a.day < b.day ? -1 : 1));

  const trips: { city: string; start: string; end: string; days: number }[] = [];
  let i = 0;
  while (i < dayCity.length) {
    const city = dayCity[i].city;
    let j = i;
    while (j + 1 < dayCity.length && dayCity[j + 1].city === city && isNextDay(dayCity[j].day, dayCity[j + 1].day)) j++;
    const runLen = j - i + 1;
    if (city !== home && runLen >= 2) trips.push({ city, start: dayCity[i].day, end: dayCity[j].day, days: runLen });
    i = j + 1;
  }
  return trips;
}

export function buildLocationCard(input: DemographicInput): DemographicCard {
  const cite = pipedaCitation("location");
  const logins: any[] = input.parsed?.login_history ?? [];
  const ipGeo = input.ipGeo ?? {};

  const geoLogins: GeoLogin[] = [];
  for (const l of logins) {
    const d = parseDate(String(l?.date ?? ""));
    const g = ipGeo[String(l?.ip ?? "")];
    if (!d || !g?.city) continue;
    geoLogins.push({ city: g.city, day: d.toISOString().slice(0, 10), hour: d.getUTCHours() });
  }
  const geoDays = new Set(geoLogins.map((g) => g.day));

  if (logins.length < MIN_LOGINS || geoDays.size < MIN_GEO_DAYS) {
    return {
      category: "location", status: "insufficient_evidence", claims: [], tiktok_infers: cite,
      requirements: {
        needed: `≥${MIN_LOGINS} logins and ≥${MIN_GEO_DAYS} geo-resolved days`,
        had: `${logins.length} logins, ${geoDays.size} geo-resolved days`,
      },
    };
  }

  const home =
    modalCity(geoLogins.filter((g) => NIGHT_HOURS.has(g.hour)).map((g) => g.city)) ??
    modalCity(geoLogins.map((g) => g.city))!;
  const work = modalCity(geoLogins.filter((g) => DAY_HOURS.has(g.hour)).map((g) => g.city));

  const claims: Claim[] = [{
    id: "demo.location.home", tier: "derived", value: home,
    method: "Most frequent city among your 11pm–4am logins.",
    evidence: [{ kind: "login", note: "night-hours logins" }, cite],
  }];
  if (work && work !== home) {
    claims.push({
      id: "demo.location.work", tier: "derived", value: work,
      method: "Most frequent city among your 9am–5pm logins.",
      evidence: [{ kind: "login", note: "day-hours logins" }, cite],
    });
  }
  const trips = detectTrips(geoLogins, home);
  if (trips.length) {
    claims.push({
      id: "demo.location.trips", tier: "derived", value: trips,
      method: "Cities where you logged in for ≥2 consecutive days away from home.",
      evidence: [{ kind: "login", note: `${trips.length} trip(s)` }, cite],
    });
  }
  return { category: "location", status: "ok", claims, tiktok_infers: cite };
}
