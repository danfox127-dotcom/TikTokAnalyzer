import { readSavedKey, resolveTopicResult } from "../app/utils/topicStep";

describe("readSavedKey", () => {
  test("returns the first provider with a stored key", () => {
    const store: Record<string, string> = { "llm_api_key_gemini-flash": "AIzaXXX" };
    expect(readSavedKey((k) => store[k] ?? null)).toEqual({ provider: "gemini-flash", apiKey: "AIzaXXX" });
  });
  test("returns null when no key is stored", () => {
    expect(readSavedKey(() => null)).toBeNull();
  });
});

describe("resolveTopicResult", () => {
  const candidates = [{ video_id: "1", weight: 3 }, { video_id: "2", weight: 1 }];

  test("with a key: POSTs to /api/topics with the key in the X-API-Key header (never the query) and returns the server TopicResult", async () => {
    const calls: { path: string; headers?: Record<string, string> }[] = [];
    const post = async <T>(path: string, _body: unknown, headers?: Record<string, string>): Promise<T | null> => {
      calls.push({ path, headers });
      return { source: "llm", clusters: [], prompt_version: "topics-v1", cached: false } as unknown as T;
    };
    const res = await resolveTopicResult({
      topicCandidates: candidates, profile: {},
      getKey: () => ({ provider: "claude", apiKey: "sk-ant-1" }), post,
    });
    expect(res.source).toBe("llm");
    expect(calls[0].path).toContain("/api/topics?");
    expect(calls[0].path).toContain("provider=claude");
    expect(calls[0].path).not.toContain("api_key");       // secret never in the URL
    expect(calls[0].path).not.toContain("sk-ant-1");
    expect(calls[0].headers).toEqual({ "X-API-Key": "sk-ant-1" });
  });

  test("no key: falls back to keywordClusters (source keyword), no POST", async () => {
    let posted = false;
    const res = await resolveTopicResult({
      topicCandidates: candidates,
      profile: { interest_clusters: [{ term: "coding", count: 3 }] },
      getKey: () => null,
      post: async () => { posted = true; return null; },
    });
    expect(res.source).toBe("keyword");
    expect(posted).toBe(false);
  });

  test("server returns null (offline/error) → keyword fallback", async () => {
    const res = await resolveTopicResult({
      topicCandidates: candidates, profile: { interest_clusters: [] },
      getKey: () => ({ provider: "claude", apiKey: "sk-ant-1" }),
      post: async () => null,
    });
    expect(res.source).toBe("keyword");
  });
});
