/**
 * WP-1.6 — export schema fingerprinting. New functionality; unit-tested against
 * the spec (no Python oracle). AC: known layouts map to a named version; a
 * mutated/unknown export yields "unknown" + unknown_sections[] without crashing.
 */
import { fingerprintExport } from "../schemaFingerprint";
import { runEngine } from "../pipeline";

const nestedV1 = {
  "Your Activity": {
    "Watch History": { VideoList: [{ Date: "2024-01-01 10:00:00", Link: "x" }] },
    Searches: { SearchList: [] },
  },
  "Profile And Settings": { "Profile Info": { ProfileMap: {} } },
};

const flatLegacy = {
  Activity: {
    "Video Browsing History": { VideoList: [{ Date: "2024-01-01 10:00:00", Link: "x" }] },
  },
};

describe("fingerprintExport — known layouts", () => {
  test("nested_v1 (Your Activity → Watch History) is named", () => {
    const fp = fingerprintExport(nestedV1);
    expect(fp.schema_version).toBe("nested_v1");
    expect(fp.unknown_sections).toEqual([]);
    expect(fp.known_sections).toEqual(["Profile And Settings", "Your Activity"]);
    expect(fp.fingerprint).toMatch(/^[0-9a-f]{8}$/);
  });

  test("flat_legacy (Activity → Video Browsing History) is named", () => {
    const fp = fingerprintExport(flatLegacy);
    expect(fp.schema_version).toBe("flat_legacy");
    expect(fp.unknown_sections).toEqual([]);
  });

  test("browsing-history variant under Your Activity is named", () => {
    const fp = fingerprintExport({
      "Your Activity": { "Video Browsing History": { VideoList: [] } },
    });
    expect(fp.schema_version).toBe("nested_v1_browsing");
  });
});

describe("fingerprintExport — stability & drift", () => {
  test("fingerprint is stable across key reordering (value-independent)", () => {
    const a = { "Your Activity": { "Watch History": { VideoList: [{ x: 1 }] }, Searches: { SearchList: [] } } };
    const b = { "Your Activity": { Searches: { SearchList: [{ q: "z" }] }, "Watch History": { VideoList: [] } } };
    expect(fingerprintExport(a).fingerprint).toBe(fingerprintExport(b).fingerprint);
  });

  test("a new/renamed top-level section changes the fingerprint", () => {
    const base = fingerprintExport(nestedV1).fingerprint;
    const mutated = fingerprintExport({ ...nestedV1, "Watch History V2": { VideoList: [] } }).fingerprint;
    expect(mutated).not.toBe(base);
  });

  test("unknown top-level sections are surfaced, not thrown on", () => {
    const fp = fingerprintExport({
      "Your Activity": { "Watch History": { VideoList: [] } },
      "Neural Implant Log": { events: [] },
      "Mystery Section": {},
    });
    expect(fp.schema_version).toBe("nested_v1"); // still recognizes the known marker
    expect(fp.unknown_sections).toEqual(["Mystery Section", "Neural Implant Log"]);
    expect(fp.known_sections).toEqual(["Your Activity"]);
  });

  test("a wholly unrecognized export → unknown, without crashing", () => {
    const fp = fingerprintExport({ Foo: { a: 1 }, Bar: [] });
    expect(fp.schema_version).toBe("unknown");
    expect(fp.unknown_sections).toEqual(["Bar", "Foo"]);
    expect(fp.known_sections).toEqual([]);
  });

  test("degenerate inputs do not crash", () => {
    for (const bad of [null, undefined, [], 42, "nope"]) {
      const fp = fingerprintExport(bad as any);
      expect(fp.schema_version).toBe("unknown");
      expect(fp.known_sections).toEqual([]);
      expect(fp.unknown_sections).toEqual([]);
    }
  });
});

describe("pipeline integration", () => {
  test("runEngine surfaces the schema fingerprint", () => {
    const { schema } = runEngine(nestedV1);
    expect(schema?.schema_version).toBe("nested_v1");
    expect(schema?.fingerprint).toMatch(/^[0-9a-f]{8}$/);
  });
});
