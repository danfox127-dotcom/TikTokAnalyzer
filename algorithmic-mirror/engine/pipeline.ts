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
import { computeCoverage, evaluateGates, Coverage, GateResult } from "./coverage";
import { buildClaims } from "./claims";
import { fingerprintExport, SchemaFingerprint } from "./schemaFingerprint";
import { buildPersona, PersonaResult } from "./persona";
import { buildNicheDrift, NicheDriftResult } from "./nicheDrift";
import { Claim } from "./types";
import { selectTopicCandidates, TopicCandidate } from "./topicCandidates";

export interface EngineOptions {
  excludeHours?: number[];
  /** video_id → handle map from the (server-side) creator-resolution pipeline. */
  linkHandleMap?: Record<string, string> | null;
}

export interface EngineResult {
  parsed: Record<string, any>;
  profile: Record<string, any>;
  narratives: any[];
  /** Export date-span per section (WP-1.2) — coverage banner data. */
  coverage: Coverage;
  /** Per-insight-module sufficiency gates (WP-1.2). */
  gates: Record<string, GateResult>;
  /** Tiered, evidence-carrying insight claims (WP-1.5). */
  claims: Claim[];
  /** WP-2.1 topic candidates: top-N watch-weighted video ids (no titles). */
  topicCandidates: TopicCandidate[];
  /** WP-2.4 persona: 6-dimension vector + archetype (supersedes the old primary_archetype). */
  persona: PersonaResult;
  /** WP-2.5 niche-drift: per-period creator concentration + fitted trend. */
  niche_drift: NicheDriftResult;
  /**
   * Structural fingerprint of the raw export (WP-1.6) — named layout + any
   * unrecognized top-level sections. Only present when the pipeline was fed a
   * RAW export (runEngine); undefined when entered from an already-parsed dict.
   */
  schema?: SchemaFingerprint;
}

/** Full pipeline from a raw export: parse → behavioral profile → narrative blocks. */
export function runEngine(rawExport: any, opts: EngineOptions = {}): EngineResult {
  const schema = fingerprintExport(rawExport);
  const parsed = parseTiktokData(rawExport);
  return { ...runEngineFromParsed(parsed, opts), schema };
}

/** Pipeline from an already-parsed export (skips the parse stage). */
export function runEngineFromParsed(parsed: any, opts: EngineOptions = {}): EngineResult {
  const profile = buildGhostProfile(parsed, opts.excludeHours ?? [], opts.linkHandleMap ?? null);
  const narratives = buildNarrativeBlocks(profile, parsed);
  const coverage = computeCoverage(parsed);
  const gates = evaluateGates(coverage, {
    consciousViews: Number(profile.stopwatch_metrics?.total_conscious_videos ?? 0),
  });
  const claims = buildClaims(profile);
  const topicCandidates = selectTopicCandidates(profile);
  const persona = buildPersona(profile, coverage);
  const niche_drift = buildNicheDrift(profile, opts.linkHandleMap ?? null);
  return { parsed, profile, narratives, coverage, gates, claims, topicCandidates, persona, niche_drift };
}
