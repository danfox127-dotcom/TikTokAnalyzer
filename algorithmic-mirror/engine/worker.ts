/**
 * WP-1.1 engine — browser Web Worker entry (browser-local mode).
 *
 * Runs the entire deterministic engine off the main thread so a 40k-video export
 * analyzes without janking the UI and without anything leaving the device.
 *
 * Protocol: the main thread posts { rawExport, opts } (or { parsed, opts }); the
 * worker replies { ok: true, result } or { ok: false, error }.
 *
 * Usage (main thread):
 *   const worker = new Worker(new URL("./engine/worker.ts", import.meta.url), { type: "module" });
 *   worker.onmessage = (e) => { if (e.data.ok) render(e.data.result); };
 *   worker.postMessage({ rawExport });
 */

import { runEngine, runEngineFromParsed, EngineOptions } from "./pipeline";

interface WorkerRequest {
  rawExport?: any;
  parsed?: any;
  opts?: EngineOptions;
}

// `self` is the DedicatedWorkerGlobalScope in a worker; typed loosely so this
// file compiles under the app's DOM lib without pulling in the webworker lib.
const ctx = self as any;

ctx.addEventListener("message", (event: MessageEvent<WorkerRequest>) => {
  try {
    const { rawExport, parsed, opts } = event.data ?? {};
    const result = parsed !== undefined
      ? runEngineFromParsed(parsed, opts)
      : runEngine(rawExport, opts);
    ctx.postMessage({ ok: true, result });
  } catch (e) {
    ctx.postMessage({ ok: false, error: (e as Error)?.message ?? String(e) });
  }
});
