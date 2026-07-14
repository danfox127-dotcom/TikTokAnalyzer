/**
 * WP-1.1 engine — the composition root.
 * Pure, dependency-free pipeline that turns a raw TikTok export into the full
 * Ghost Profile payload + narrative blocks. No network, no filesystem, no DOM —
 * runs identically on the main thread, in a Web Worker (browser-local mode), or
 * in a Node/edge context. This is the entry point Gate 0 (TypeScript-everywhere)
 * exists to enable.
 */

import { parseTiktokData } from "./parser";
import { buildGhostProfile } from "./ghostProfile";
import { buildNarrativeBlocks } from "./narratives";

export interface EngineOptions {
  excludeHours?: number[];
  /** video_id → handle map from the (server-side) creator-resolution pipeline. */
  linkHandleMap?: Record<string, string> | null;
}

export interface EngineResult {
  parsed: Record<string, any>;
  profile: Record<string, any>;
  narratives: any[];
}

/** Full pipeline from a raw export: parse → behavioral profile → narrative blocks. */
export function runEngine(rawExport: any, opts: EngineOptions = {}): EngineResult {
  const parsed = parseTiktokData(rawExport);
  return runEngineFromParsed(parsed, opts);
}

/** Pipeline from an already-parsed export (skips the parse stage). */
export function runEngineFromParsed(parsed: any, opts: EngineOptions = {}): EngineResult {
  const profile = buildGhostProfile(parsed, opts.excludeHours ?? [], opts.linkHandleMap ?? null);
  const narratives = buildNarrativeBlocks(profile, parsed);
  return { parsed, profile, narratives };
}
