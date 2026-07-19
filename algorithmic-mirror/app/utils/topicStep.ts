/**
 * WP-2.2 — the topics-resolution step, dependency-injected so it is unit-testable
 * without a real network or localStorage. If a BYOK key is saved, POST the
 * watch-weighted candidates to /api/topics (server fetches titles + LLM-clusters);
 * otherwise fall back to the client keyword pass (which gates the card to
 * insufficient_evidence downstream).
 */
import { keywordClusters, type TopicResult } from "../../engine/keywordClusters";
import type { TopicCandidate } from "../../engine/topicCandidates";

// Same key convention LLMAnalysisView uses: `llm_api_key_<provider>`.
const PROVIDERS = ["claude", "gemini-pro", "gemini-flash"] as const;

export function readSavedKey(
  getItem: (k: string) => string | null
): { provider: string; apiKey: string } | null {
  for (const provider of PROVIDERS) {
    const apiKey = getItem(`llm_api_key_${provider}`);
    if (apiKey) return { provider, apiKey };
  }
  return null;
}

export async function resolveTopicResult(opts: {
  topicCandidates: TopicCandidate[];
  profile: any;
  getKey: () => { provider: string; apiKey: string } | null;
  post: <T>(path: string, body: unknown) => Promise<T | null>;
}): Promise<TopicResult> {
  const key = opts.getKey();
  if (key && opts.topicCandidates.length) {
    const q = new URLSearchParams({ api_key: key.apiKey, provider: key.provider });
    const res = await opts.post<TopicResult>(`/api/topics?${q.toString()}`, {
      videos: opts.topicCandidates,
    });
    if (res) return res;
  }
  return keywordClusters(opts.profile);
}
