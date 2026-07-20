/**
 * WP-2.3 — Demographic inference module. Pure, browser-safe. Reconstructs the five
 * categories PIPEDA #2025-003 confirmed TikTok infers (interests, location, age,
 * gender, spending), each a Claim with a two-layer framing: the government citation
 * attests TikTok infers the category at all; our tier attests the reconstructed value.
 */
import type { Claim, EvidenceRef } from "./types";
import type { TargetingCardResult } from "./targetingCard";
import { parseDate } from "./parseDate";

export const PIPEDA_CITATION = "PIPEDA #2025-003";
export const AGE_BRACKETS = ["13-17", "18-24", "25-34", "35-44", "45-54", "55+"] as const;

export interface DemographicCard {
  category: "interests" | "location" | "age" | "gender" | "spending";
  status: "ok" | "insufficient_evidence";
  claims: Claim[];
  tiktok_infers: EvidenceRef;
  requirements?: { needed: string; had: string };
}
export interface DemographicModuleResult {
  moduleId: "demographics";
  status: "ok" | "insufficient_evidence" | "error";
  cards: DemographicCard[];
  error?: string;
}
export interface DemographicInput {
  parsed: any;
  profile: any;
  targeting_card?: TargetingCardResult;
  ipGeo?: Record<string, { city: string; country_name: string }>;
  now?: Date;
}

export function pipedaCitation(category: string): EvidenceRef {
  return { kind: "external_source", citation: PIPEDA_CITATION, note: `TikTok is documented to infer ${category}` };
}

export function ageToBracket(age: number): string {
  if (age <= 17) return "13-17";
  if (age <= 24) return "18-24";
  if (age <= 34) return "25-34";
  if (age <= 44) return "35-44";
  if (age <= 54) return "45-54";
  return "55+";
}

// Heuristic, tunable: category substrings that skew a viewer younger.
const YOUTH_TOPICS = ["gaming", "video games", "anime", "students", "education"];

export function ageFromBirthDate(birthDate: string, now: Date): number | null {
  const m = String(birthDate ?? "").match(/(\d{4})/); // first 4-digit run = birth year
  if (!m) return null;
  const year = Number(m[1]);
  if (year < 1900 || year > now.getUTCFullYear()) return null;
  return now.getUTCFullYear() - year;
}

function loginSpanDays(parsed: any): number | null {
  const dates: Date[] = (parsed?.login_history ?? [])
    .map((l: any) => parseDate(String(l?.date ?? "")))
    .filter((d: Date | null): d is Date => d != null);
  if (dates.length < 2) return null;
  const times = dates.map((d) => d.getTime());
  return (Math.max(...times) - Math.min(...times)) / 86400000;
}

export function buildAgeCard(input: DemographicInput): DemographicCard {
  const cite = pipedaCitation("age");
  const now = input.now ?? new Date();
  const claims: Claim[] = [];

  const age = ageFromBirthDate(input.parsed?.birth_date ?? "", now);
  if (age != null) {
    claims.push({
      id: "demo.age.declared", tier: "recorded", value: ageToBracket(age),
      method: "Age bracket computed from the declared birth year in your export profile.",
      evidence: [{ kind: "settings", note: "declared birthDate" }, cite],
    });
  }

  const bn = input.profile?.behavioral_nodes ?? {};
  const nightShift = Number(bn.night_shift_ratio ?? 0); // percentage 0–100
  const span = loginSpanDays(input.parsed);
  const segCats = (input.targeting_card?.claims ?? [])
    .map((c: any) => String(c?.value?.category ?? "").toLowerCase());
  const youthHit = segCats.some((c: string) => YOUTH_TOPICS.some((y) => c.includes(y)));

  const signals: string[] = [];
  let idx = 2; // start neutral at "25-34"
  if (nightShift > 30) { idx -= 1; signals.push(`heavy late-night use (${nightShift}% of activity)`); }
  if (youthHit) { idx -= 1; signals.push("youth-coded topics in your feed"); }
  if (span != null && span > 1095) { idx += 1; signals.push("long account tenure"); }
  if (signals.length) {
    idx = Math.max(0, Math.min(AGE_BRACKETS.length - 1, idx));
    claims.push({
      id: "demo.age.behavioral", tier: "inferred", value: AGE_BRACKETS[idx], confidence: 0.4,
      method: `Low-confidence behavioral estimate from: ${signals.join("; ")}.`,
      evidence: [{ kind: "video", note: "behavioral age signals" }, cite],
    });
  }

  if (!claims.length) {
    return {
      category: "age", status: "insufficient_evidence", claims: [], tiktok_infers: cite,
      requirements: { needed: "a declared birth year or usable behavioral signals", had: "neither present" },
    };
  }
  return { category: "age", status: "ok", claims, tiktok_infers: cite };
}

export function buildGenderCard(input: DemographicInput): DemographicCard {
  const cite = pipedaCitation("gender");
  const g = String(input.parsed?.inferred_gender ?? "").trim();
  if (!g) {
    return {
      category: "gender", status: "insufficient_evidence", claims: [], tiktok_infers: cite,
      requirements: { needed: "TikTok's stored inferredGender", had: "absent from this export" },
    };
  }
  const claim: Claim = {
    id: "demo.gender", tier: "recorded", value: g,
    method: "TikTok's own inferred-gender label, taken verbatim from your export.",
    evidence: [{ kind: "settings", note: "stored inferredGender" }, cite],
  };
  return { category: "gender", status: "ok", claims: [claim], tiktok_infers: cite };
}

export function buildDemographics(input: DemographicInput): DemographicModuleResult {
  if (!input || !input.parsed || typeof input.parsed !== "object") {
    return { moduleId: "demographics", status: "error", error: "malformed input", cards: [] };
  }
  // Cards are added by later tasks in the spec's stable order:
  // [interests, location, age, gender, spending].
  const cards: DemographicCard[] = [buildAgeCard(input), buildGenderCard(input)];
  const status: DemographicModuleResult["status"] = cards.some((c) => c.status === "ok")
    ? "ok" : "insufficient_evidence";
  return { moduleId: "demographics", status, cards };
}
