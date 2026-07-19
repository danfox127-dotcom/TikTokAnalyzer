/**
 * WP-2.1 — deterministic keyword fallback (no LLM, no network). Clusters the
 * existing text footprint (interest_clusters: searches/comments/declared) by the
 * static category map. Lower-confidence than the LLM title path, honestly marked.
 */
import { categorize, CATEGORY_PHRASES } from "./pillarCategories";

export const PROMPT_VERSION = "topics-v1";

export interface TopicCluster {
  name: string;
  video_ids: string[];
  taxonomy_hint: string | null;
  confidence: number;
  evidence_kind: "video" | "term";
}
export interface TopicResult {
  source: "llm" | "keyword";
  clusters: TopicCluster[];
  prompt_version: string;
  cached: boolean;
  usage?: { input_tokens: number; output_tokens: number };
}

export function keywordClusters(profile: any): TopicResult {
  const terms: any[] = profile?.interest_clusters ?? [];
  const byCategory = new Map<string, number>(); // category → summed count
  for (const t of terms) {
    const cat = categorize(String(t?.term ?? ""));
    if (cat) byCategory.set(cat, (byCategory.get(cat) ?? 0) + Number(t?.count ?? 0));
  }
  const clusters: TopicCluster[] = [...byCategory.keys()].sort().map((cat) => ({
    name: CATEGORY_PHRASES[cat] ?? cat,
    video_ids: [],
    taxonomy_hint: null,
    confidence: 0.4,
    evidence_kind: "term",
  }));
  return { source: "keyword", clusters, prompt_version: PROMPT_VERSION, cached: false };
}
