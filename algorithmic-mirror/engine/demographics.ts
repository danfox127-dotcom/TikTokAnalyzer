/**
 * WP-2.3 — Demographic inference module. Pure, browser-safe. Reconstructs the five
 * categories PIPEDA #2025-003 confirmed TikTok infers (interests, location, age,
 * gender, spending), each a Claim with a two-layer framing: the government citation
 * attests TikTok infers the category at all; our tier attests the reconstructed value.
 */
import type { Claim, EvidenceRef } from "./types";
import type { TargetingCardResult } from "./targetingCard";

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
  const cards: DemographicCard[] = [buildGenderCard(input)];
  const status: DemographicModuleResult["status"] = cards.some((c) => c.status === "ok")
    ? "ok" : "insufficient_evidence";
  return { moduleId: "demographics", status, cards };
}
