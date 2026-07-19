/**
 * WP-2.2 — Targeting Card engine. Pure, browser-safe: maps WP-2.1 topic clusters
 * onto TikTok's ad taxonomy and emits advertiser segments as inferred Claims with
 * real video evidence. Keyword-only (no LLM key) input gates to insufficient_evidence.
 */
import { TAXONOMY_NAMES, TAXONOMY_VERSION } from "./taxonomyIndex";
import type { Claim, EvidenceRef } from "./types";
import type { TopicResult } from "./keywordClusters";

const MIN_VIDEOS = 3;
const UNCATEGORIZED = "Uncategorized interest";

const norm = (s: string) => String(s ?? "").toLowerCase().trim();
const slug = (s: string) =>
  String(s ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");

// Strict, normalized exact-match lookup + canonical (file-cased) name.
const CANONICAL_BY_NORM = new Map<string, string>(TAXONOMY_NAMES.map((n) => [norm(n), n]));

export interface TargetingSegmentValue {
  category: string;
  cluster_name: string;
  matched: boolean;
  tiktok_confirmed: boolean;
}
export type TargetingSegment = Claim<TargetingSegmentValue>;

export interface TargetingCardResult {
  moduleId: "targeting_card";
  status: "ok" | "insufficient_evidence" | "error";
  requirements?: { needed: string; had: string };
  claims: TargetingSegment[];
  counts: { declared_ad_interest_count: number; segment_count: number; confirmed_count: number };
  taxonomy_version: string;
  error?: string;
}

export function buildTargetingCard(topicResult: TopicResult, profile: any): TargetingCardResult {
  const declared: string[] = profile?.declared_signals?.ad_interests ?? [];
  const declaredNorm = declared.map(norm).filter(Boolean);
  const base = { moduleId: "targeting_card" as const, taxonomy_version: TAXONOMY_VERSION };
  const zeroCounts = { declared_ad_interest_count: declared.length, segment_count: 0, confirmed_count: 0 };
  const insufficient = (had: string): TargetingCardResult => ({
    ...base, status: "insufficient_evidence",
    requirements: { needed: "LLM topic pass (bring your own key)", had },
    claims: [], counts: zeroCounts,
  });

  if (!topicResult || !Array.isArray((topicResult as any).clusters)) {
    return { ...base, status: "error", error: "malformed TopicResult", claims: [], counts: zeroCounts };
  }
  if (topicResult.source === "keyword") return insufficient("keyword fallback (no LLM key)");
  if (topicResult.clusters.length === 0) return insufficient("no topic clusters");

  // Group matched clusters by canonical category; keep unmatched separate.
  const matched = new Map<string, { videos: Set<string>; names: string[]; conf: number }>();
  const uncategorized: { name: string; videos: string[]; conf: number }[] = [];
  for (const c of topicResult.clusters) {
    const vids = Array.isArray(c.video_ids) ? c.video_ids.map(String) : [];
    const hitNorm = norm(String(c.taxonomy_hint ?? ""));
    const canonical = c.taxonomy_hint ? CANONICAL_BY_NORM.get(hitNorm) : undefined;
    if (canonical) {
      const g = matched.get(canonical) ?? { videos: new Set<string>(), names: [], conf: 0 };
      vids.forEach((v) => g.videos.add(v));
      g.names.push(c.name);
      g.conf = Math.max(g.conf, Number(c.confidence ?? 0));
      matched.set(canonical, g);
    } else {
      uncategorized.push({ name: c.name, videos: vids, conf: Number(c.confidence ?? 0) });
    }
  }

  // Confirm when a declared interest matches the taxonomy CATEGORY (exact or
  // substring either direction — category is controlled vocabulary, safe) OR
  // EXACTLY equals the cluster name. cluster_name is free LLM text, so only an
  // exact match counts there: a substring like declared "art" ⊂ "martial arts"
  // must NOT falsely confirm (honesty — over-claiming confirmation is worse).
  const isConfirmed = (category: string, clusterName: string): boolean => {
    const cat = norm(category);
    const cn = norm(clusterName);
    return declaredNorm.some(
      (d) => (!!cat && (cat === d || cat.includes(d) || d.includes(cat))) || (!!cn && cn === d)
    );
  };
  const makeSegment = (
    id: string, category: string, cluster_name: string, matchedFlag: boolean,
    videos: string[], confidence: number,
  ): TargetingSegment | null => {
    const uniq = [...new Set(videos)];
    if (uniq.length < MIN_VIDEOS) return null;
    const tiktok_confirmed = isConfirmed(category, cluster_name);
    const evidence: EvidenceRef[] = uniq.map((v) => ({ kind: "video", id: v }));
    const method =
      `Matched watched-video topics to TikTok ad taxonomy ${TAXONOMY_VERSION}; ` +
      `${matchedFlag ? "category confirmed in file" : "no taxonomy match (uncategorized)"}; ` +
      `${tiktok_confirmed ? "TikTok already lists this interest" : "not in TikTok's declared interests"}.`;
    return {
      id, tier: "inferred", confidence, evidence, method,
      value: { category, cluster_name, matched: matchedFlag, tiktok_confirmed },
    };
  };

  const segments: TargetingSegment[] = [];
  for (const [category, g] of matched) {
    const s = makeSegment(`targeting.segment.${slug(category)}`, category, g.names.join(", "),
      true, [...g.videos], g.conf);
    if (s) segments.push(s);
  }
  const usedIds = new Set<string>();
  uncategorized.forEach((u, i) => {
    let id = `targeting.segment.uncategorized.${slug(u.name)}`;
    while (usedIds.has(id)) id = `${id}_${i}`;
    usedIds.add(id);
    const s = makeSegment(id, UNCATEGORIZED, u.name, false, u.videos, u.conf);
    if (s) segments.push(s);
  });

  if (segments.length === 0) return insufficient("no cluster met the ≥3 evidence-video bar");

  const confirmed_count = segments.filter((s) => s.value.tiktok_confirmed).length;
  return {
    ...base, status: "ok", claims: segments,
    counts: { declared_ad_interest_count: declared.length, segment_count: segments.length, confirmed_count },
  };
}
