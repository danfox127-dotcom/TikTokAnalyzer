/**
 * WP-1.6 — export schema fingerprinting.
 *
 * NEW functionality (not a port). TikTok's export layout drifts between app
 * versions and locales: keys get renamed ("Comment" → "Comments"), sections nest
 * differently ("Your Activity" vs "Activity"), and brand-new sections appear. The
 * parser copes via fallback dig-chains, but silently — when a section moves to an
 * unrecognized path we just get empty data with no signal that the layout changed.
 *
 * This module fingerprints the export's STRUCTURE (top-level keys + their
 * immediate child keys — never the values, which are bulk PII) into a stable hash,
 * matches it against a registry of known layouts, and reports any top-level
 * sections we don't recognize. Purely diagnostic: it never throws on an unknown
 * shape, it describes it. Layered in the pipeline alongside coverage/claims.
 *
 * AC: known fixtures map to a named layout; a mutated/unknown fixture yields
 * schema_version "unknown" with a populated unknown_sections[] and does not crash.
 */

/** The top-level sections TikTok is known to emit (any layout/locale). */
const KNOWN_TOP_LEVEL = new Set<string>([
  "Your Activity",
  "Activity",
  "Profile And Settings",
  "Profile",
  "Likes and Favorites",
  "Comment",
  "Comments",
  "Direct Message",
  "Direct Messages",
  "TikTok Shop",
  "Ad Interests",
  "App Settings",
  "Tiktok Live",
  "TikTok Live",
  "Tiktok Shopping",
  "Video",
]);

/**
 * A named layout is identified by a marker path that must resolve to a non-null
 * value. Order matters: the first matching layout wins. `flat_legacy` (the older
 * "Activity" nesting) is checked before `nested_v1` because a hybrid export can
 * carry both, and we want to name it by its watch-history home.
 */
interface KnownLayout {
  version: string;
  /** All marker paths must be present (non-null) for the layout to match. */
  markers: string[][];
}

const KNOWN_LAYOUTS: KnownLayout[] = [
  {
    version: "nested_v1",
    markers: [["Your Activity", "Watch History", "VideoList"]],
  },
  {
    version: "nested_v1_browsing",
    markers: [["Your Activity", "Video Browsing History", "VideoList"]],
  },
  {
    version: "flat_legacy",
    markers: [["Activity", "Video Browsing History", "VideoList"]],
  },
];

function digPresent(data: any, keys: string[]): boolean {
  let current = data;
  for (const key of keys) {
    if (current === null || typeof current !== "object" || Array.isArray(current)) return false;
    if (!(key in current)) return false;
    current = current[key];
    if (current === null || current === undefined) return false;
  }
  return true;
}

/** djb2 string hash → 8-char hex. Dependency-free, deterministic, browser-safe. */
function hashString(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h + s.charCodeAt(i)) | 0; // h * 33 + c, wrapped to int32
  }
  return (h >>> 0).toString(16).padStart(8, "0");
}

/**
 * Structural skeleton: each top-level key with its sorted immediate child keys.
 * Values are never included. Keys are sorted so ordering never perturbs the hash.
 */
function skeleton(data: any): string {
  if (data === null || typeof data !== "object" || Array.isArray(data)) return "";
  const lines: string[] = [];
  for (const top of Object.keys(data).sort()) {
    const child = data[top];
    let childKeys: string[] = [];
    if (child !== null && typeof child === "object" && !Array.isArray(child)) {
      childKeys = Object.keys(child).sort();
    }
    lines.push(`${top}:{${childKeys.join(",")}}`);
  }
  return lines.join("\n");
}

export interface SchemaFingerprint {
  /** Named layout ("nested_v1", …) or "unknown" if no marker path matched. */
  schema_version: string;
  /** Stable structural hash of the export skeleton (top-level + child keys). */
  fingerprint: string;
  /** Recognized top-level sections present in this export. */
  known_sections: string[];
  /** Top-level sections we have no vocabulary for — the drift signal. */
  unknown_sections: string[];
}

export function fingerprintExport(rawExport: any): SchemaFingerprint {
  const isObj =
    rawExport !== null && typeof rawExport === "object" && !Array.isArray(rawExport);
  const topKeys = isObj ? Object.keys(rawExport) : [];

  const known_sections: string[] = [];
  const unknown_sections: string[] = [];
  for (const k of topKeys.sort()) {
    (KNOWN_TOP_LEVEL.has(k) ? known_sections : unknown_sections).push(k);
  }

  let schema_version = "unknown";
  for (const layout of KNOWN_LAYOUTS) {
    if (layout.markers.every((path) => digPresent(rawExport, path))) {
      schema_version = layout.version;
      break;
    }
  }

  return {
    schema_version,
    fingerprint: hashString(skeleton(rawExport)),
    known_sections,
    unknown_sections,
  };
}
