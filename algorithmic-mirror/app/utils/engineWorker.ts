/**
 * Browser-local engine, off the main thread.
 *
 * Runs the parity-locked engine inside a Web Worker so a 40k-video export
 * analyzes without janking the UI (and without anything leaving the device).
 * The `new URL(..., import.meta.url)` form is what lets Next 16 / Turbopack detect
 * and bundle the worker as its own chunk.
 *
 * A fresh worker per call (terminated on completion) keeps the lifecycle trivial;
 * analysis runs at most twice (pre/post creator resolution) so this is cheap.
 */

import { runEngine, EngineOptions, EngineResult } from "../../engine/pipeline";

export function runEngineInWorker(rawExport: unknown, opts?: EngineOptions): Promise<EngineResult> {
  return new Promise<EngineResult>((resolve, reject) => {
    let worker: Worker;
    try {
      worker = new Worker(new URL("../../engine/worker.ts", import.meta.url), { type: "module" });
    } catch (e) {
      reject(e instanceof Error ? e : new Error(String(e)));
      return;
    }
    worker.onmessage = (e: MessageEvent) => {
      worker.terminate();
      if (e.data?.ok) resolve(e.data.result as EngineResult);
      else reject(new Error(e.data?.error ?? "engine worker failed"));
    };
    worker.onerror = (e: ErrorEvent) => {
      worker.terminate();
      reject(new Error(e.message || "engine worker error"));
    };
    worker.postMessage({ rawExport, opts });
  });
}

/**
 * Run the engine off-thread, falling back to a synchronous main-thread run if the
 * Worker is unavailable (older browser, bundling edge, SSR). Correctness is
 * identical either way — the fallback only costs the no-jank property.
 */
export async function runEngineOffThread(rawExport: unknown, opts?: EngineOptions): Promise<EngineResult> {
  if (typeof Worker === "undefined") return runEngine(rawExport, opts);
  try {
    return await runEngineInWorker(rawExport, opts);
  } catch {
    return runEngine(rawExport, opts);
  }
}
