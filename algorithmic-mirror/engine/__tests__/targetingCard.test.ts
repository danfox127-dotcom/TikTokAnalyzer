import { buildTargetingCard } from "../targetingCard";
import { validateClaims } from "../claims";
import { TAXONOMY_VERSION } from "../taxonomyIndex";
import type { TopicResult } from "../keywordClusters";

// "Education" and "Personal Finance" are real taxonomy names; "Blahblah" is not.
const cluster = (name: string, taxonomy_hint: string | null, video_ids: string[], confidence = 0.7) =>
  ({ name, taxonomy_hint, video_ids, confidence, evidence_kind: "video" as const });
const llm = (clusters: any[]): TopicResult =>
  ({ source: "llm", clusters, prompt_version: "topics-v1", cached: false });
const profile = (ad_interests: string[] = []) => ({ declared_signals: { ad_interests } });

describe("buildTargetingCard", () => {
  test("keyword source → insufficient_evidence gate, no claims", () => {
    const res = buildTargetingCard(
      { source: "keyword", clusters: [], prompt_version: "topics-v1", cached: false },
      profile()
    );
    expect(res.status).toBe("insufficient_evidence");
    expect(res.requirements?.needed).toMatch(/bring your own key/i);
    expect(res.claims).toEqual([]);
  });

  test("matched cluster with ≥3 videos → inferred segment Claim citing the videos", () => {
    const res = buildTargetingCard(
      llm([cluster("study tips", "Education", ["1", "2", "3"])]),
      profile()
    );
    expect(res.status).toBe("ok");
    expect(res.claims).toHaveLength(1);
    const s = res.claims[0];
    expect(s.tier).toBe("inferred");
    expect((s.value as any).category).toBe("Education");
    expect((s.value as any).matched).toBe(true);
    expect(s.evidence.map((e) => e.id)).toEqual(["1", "2", "3"]);
    expect(s.method).toContain(TAXONOMY_VERSION);
    expect(validateClaims(res.claims)).toEqual([]); // valid Claim set
  });

  test("clusters under the 3-video bar are dropped; all-dropped → insufficient", () => {
    const res = buildTargetingCard(
      llm([cluster("thin", "Education", ["1", "2"])]),
      profile()
    );
    expect(res.status).toBe("insufficient_evidence");
    expect(res.requirements?.had).toMatch(/3/);
  });

  test("strict match: near-miss hint → Uncategorized interest (still ships with videos)", () => {
    const res = buildTargetingCard(
      llm([cluster("finance stuff", "Finance", ["1", "2", "3"])]), // not exactly a taxonomy name
      profile()
    );
    expect(res.status).toBe("ok");
    expect((res.claims[0].value as any).category).toBe("Uncategorized interest");
    expect((res.claims[0].value as any).matched).toBe(false);
  });

  test("two matched clusters on the same category → ONE merged segment (union videos, max confidence)", () => {
    const res = buildTargetingCard(
      llm([
        cluster("a", "Education", ["1", "2"], 0.7),
        cluster("b", "Education", ["2", "3", "4"], 0.9),
      ]),
      profile()
    );
    expect(res.claims).toHaveLength(1);
    expect(res.claims[0].evidence.map((e) => e.id).sort()).toEqual(["1", "2", "3", "4"]);
    expect(res.claims[0].confidence).toBe(0.9);
  });

  test("tiktok_confirmed flag + card-level counts from declared ad_interests", () => {
    const res = buildTargetingCard(
      llm([
        cluster("study tips", "Education", ["1", "2", "3"]),
        cluster("budget hacks", "Financial Services", ["4", "5", "6"]),
      ]),
      profile(["Education"]) // TikTok already lists Education, not Financial Services
    );
    const byCat = Object.fromEntries(res.claims.map((c) => [(c.value as any).category, c]));
    expect((byCat["Education"].value as any).tiktok_confirmed).toBe(true);
    expect((byCat["Financial Services"].value as any).tiktok_confirmed).toBe(false);
    expect(res.counts).toEqual({ declared_ad_interest_count: 1, segment_count: 2, confirmed_count: 1 });
  });

  test("two uncategorized clusters stay separate with unique ids", () => {
    const res = buildTargetingCard(
      llm([
        cluster("mystery one", null, ["1", "2", "3"]),
        cluster("mystery two", null, ["4", "5", "6"]),
      ]),
      profile()
    );
    expect(res.claims).toHaveLength(2);
    const ids = res.claims.map((c) => c.id);
    expect(new Set(ids).size).toBe(2); // unique
    expect(validateClaims(res.claims)).toEqual([]);
  });

  test("malformed TopicResult → status error, not a crash", () => {
    const res = buildTargetingCard({} as any, profile());
    expect(res.status).toBe("error");
  });

  test("a declared interest that is only a SUBSTRING of the cluster name does NOT confirm", () => {
    // declared "art" ⊂ cluster name "martial arts training", but "art" is not the
    // category ("Education") nor an exact cluster-name match → must stay unconfirmed.
    const res = buildTargetingCard(
      llm([cluster("martial arts training", "Education", ["1", "2", "3"])]),
      profile(["art"])
    );
    expect((res.claims[0].value as any).tiktok_confirmed).toBe(false);
  });

  test("an EXACT cluster-name match still confirms, even for an uncategorized segment", () => {
    const res = buildTargetingCard(
      llm([cluster("yoga", null, ["1", "2", "3"])]),
      profile(["yoga"])
    );
    expect((res.claims[0].value as any).category).toBe("Uncategorized interest");
    expect((res.claims[0].value as any).tiktok_confirmed).toBe(true);
  });
});
