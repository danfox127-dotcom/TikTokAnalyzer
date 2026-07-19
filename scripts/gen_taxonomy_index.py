# scripts/gen_taxonomy_index.py
"""WP-2.2 — generate the browser-safe taxonomy index from the committed source.
Run: python3 scripts/gen_taxonomy_index.py  (re-run whenever data/tiktok-ad-taxonomy.json changes)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "tiktok-ad-taxonomy.json")
OUT = os.path.join(ROOT, "algorithmic-mirror", "engine", "taxonomyIndex.ts")


def main() -> None:
    with open(SRC) as f:
        data = json.load(f)
    names = [c["name"] for c in data["categories"] if c.get("name")]
    body = ",\n  ".join(json.dumps(n) for n in names)
    content = (
        "// AUTO-GENERATED from data/tiktok-ad-taxonomy.json by "
        "scripts/gen_taxonomy_index.py — do not edit by hand.\n"
        f"export const TAXONOMY_VERSION = {json.dumps(data.get('version', ''))};\n"
        f"export const TAXONOMY_RETRIEVED = {json.dumps(data.get('retrieved_date', ''))};\n"
        "export const TAXONOMY_NAMES: string[] = [\n"
        f"  {body},\n"
        "];\n"
    )
    with open(OUT, "w") as f:
        f.write(content)
    print(f"wrote {OUT}: {len(names)} names")


if __name__ == "__main__":
    main()
