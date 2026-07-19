import fs from "fs";
import path from "path";
import { TAXONOMY_NAMES, TAXONOMY_VERSION, TAXONOMY_RETRIEVED } from "../taxonomyIndex";

// Node-side build-parity check: the committed generated module must match the
// source file (a stale index fails CI). This test may use fs; the runtime module
// it imports is a plain string array (browser-safe).
const src = JSON.parse(
  fs.readFileSync(path.join(__dirname, "../../../data/tiktok-ad-taxonomy.json"), "utf-8")
);
const names: string[] = src.categories.filter((c: any) => c?.name).map((c: any) => c.name);

test("generated taxonomy index matches the source file", () => {
  expect(TAXONOMY_NAMES).toEqual(names);
  expect(TAXONOMY_NAMES.length).toBe(716);
  expect(TAXONOMY_VERSION).toBe(src.version);
  expect(TAXONOMY_RETRIEVED).toBe(src.retrieved_date);
});
