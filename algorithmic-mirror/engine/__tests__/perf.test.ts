/**
 * WP-1.1 acceptance: the engine runs a ~40k-video export end-to-end in < 30s.
 *
 * Exercises the exact code path a browser Web Worker runs (runEngine) on the main
 * thread here — a valid perf + purity proxy: it completes in Node with no DOM /
 * network / filesystem, proving zero server-only dependencies. The Worker
 * (engine/worker.ts) runs the identical function off the UI thread.
 */
import { runEngine } from "../pipeline";

const N = 40000;
const CREATORS = 500;
// 2.5s graveyard / 5s sandbox / 60s linger / 200s deep-dive. Kept >=2s so no
// autoplay-artifact removal; engagement events (below) keep sessions non-passive,
// so watch_history_active ≈ N and the engine does real work at scale.
const DELTAS_MS = [2500, 5000, 60000, 200000];

function pad(n: number): string {
  return String(n).padStart(2, "0");
}
function fmt(ms: number): string {
  const d = new Date(ms);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ` +
    `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}

function syntheticExport(n: number): any {
  const videoList: any[] = [];
  const likeList: any[] = [];
  let cursor = Date.UTC(2024, 0, 1, 8, 0, 0);
  for (let i = 0; i < n; i++) {
    cursor += DELTAS_MS[i % DELTAS_MS.length];
    if (i % 2000 === 0) cursor += 3 * 24 * 3600 * 1000; // periodic multi-day gap → sessions + months
    const date = fmt(cursor);
    videoList.push({ Date: date, Link: `https://www.tiktok.com/@creator${i % CREATORS}/video/${i}` });
    // an engagement event every 200 videos keeps each session non-passive
    if (i % 200 === 0) likeList.push({ Date: date, Link: `https://www.tiktok.com/@creator${i % CREATORS}/video/${i}` });
  }
  return {
    "Your Activity": { "Watch History": { VideoList: videoList } },
    "Likes and Favorites": { "Like List": { ItemFavoriteList: likeList } },
    Comment: { Comments: { CommentsList: [] } },
  };
}

describe("engine performance", () => {
  test(
    `${N}-video export → full pipeline under 30s`,
    () => {
      const raw = syntheticExport(N);
      const t0 = performance.now();
      const { profile, narratives } = runEngine(raw);
      const ms = performance.now() - t0;
      const active = profile.stopwatch_metrics.total_raw_videos;
      // eslint-disable-next-line no-console
      console.log(`[perf] ${N}-video pipeline: ${ms.toFixed(0)}ms (active videos: ${active})`);

      expect(profile.status).toBe("success");
      expect(active).toBeGreaterThan(N * 0.95); // ~all videos stayed active → engine did real work
      expect(profile.creator_entities.vibe_cluster.length).toBeGreaterThan(0);
      expect(narratives.length).toBe(9);
      expect(ms).toBeLessThan(30000);
    },
    60000, // jest per-test timeout
  );
});
