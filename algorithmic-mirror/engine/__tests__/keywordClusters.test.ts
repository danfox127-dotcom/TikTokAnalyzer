import { keywordClusters } from "../keywordClusters";

describe("keywordClusters", () => {
  const profile = {
    interest_clusters: [
      { term: "coding", count: 5 },   // → tech
      { term: "ai", count: 3 },       // → tech
      { term: "gym", count: 4 },      // → fitness
      { term: "zzzznonsense", count: 1 }, // → uncategorized, dropped
    ],
  };

  test("groups terms by category into keyword-source clusters", () => {
    const res = keywordClusters(profile);
    expect(res.source).toBe("keyword");
    expect(res.cached).toBe(false);
    const names = res.clusters.map((c) => c.name).sort();
    // CATEGORY_PHRASES: tech → "technology and digital tools", fitness → "body, movement, and physical challenge"
    expect(names).toEqual(["body, movement, and physical challenge", "technology and digital tools"]);
  });

  test("clusters carry lower confidence, term evidence, null taxonomy_hint", () => {
    const res = keywordClusters(profile);
    for (const c of res.clusters) {
      expect(c.confidence).toBe(0.4);
      expect(c.evidence_kind).toBe("term");
      expect(c.video_ids).toEqual([]);
      expect(c.taxonomy_hint).toBeNull();
    }
  });

  test("deterministic: same input → identical output", () => {
    expect(keywordClusters(profile)).toEqual(keywordClusters(profile));
  });

  test("empty interest_clusters → no clusters", () => {
    expect(keywordClusters({ interest_clusters: [] }).clusters).toEqual([]);
  });
});
