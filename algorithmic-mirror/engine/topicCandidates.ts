/**
 * WP-2.1 — deterministic topic candidate selection.
 * Picks the top-N watch-weighted watched videos, month-proportionally sampled so
 * a heavy month can't crowd out the temporal picture. Pure + browser-safe: it
 * emits video IDs + weights only, never titles.
 */
export interface TopicCandidate {
  video_id: string;
  weight: number;
}

const LINGER_WEIGHT = 0.5;
const DEEP_DIVE_WEIGHT = 1.0;
const DEFAULT_LIMIT = 800;

function byWeightThenId(a: TopicCandidate, b: TopicCandidate): number {
  return b.weight - a.weight || (a.video_id < b.video_id ? -1 : a.video_id > b.video_id ? 1 : 0);
}

export function selectTopicCandidates(profile: any, opts: { limit?: number } = {}): TopicCandidate[] {
  const limit = opts.limit ?? DEFAULT_LIMIT;
  const sw = profile?.stopwatch_metrics ?? {};
  const lingerEvents: any[] = sw.linger_events ?? [];
  const deepDiveIds = new Set<string>((sw.deep_dive_events ?? []).map((e: any) => e.video_id));

  const weight = new Map<string, number>();
  const monthOf = new Map<string, { m: string; w: number }>(); // month of the heaviest single event
  for (const ev of lingerEvents) {
    const vid = ev?.video_id;
    if (!vid) continue;
    const w = (deepDiveIds.has(vid) ? DEEP_DIVE_WEIGHT : LINGER_WEIGHT) * Number(ev.time_spent ?? 0);
    weight.set(vid, (weight.get(vid) ?? 0) + w);
    const month = ev._month ?? "";
    const cur = monthOf.get(vid);
    if (!cur || w > cur.w || (w === cur.w && month < cur.m)) monthOf.set(vid, { m: month, w });
  }

  const all: TopicCandidate[] = [...weight.entries()].map(([video_id, w]) => ({ video_id, weight: w }));
  if (all.length <= limit) return all.sort(byWeightThenId);

  // Group by month, then largest-remainder allocation of the N-slot budget.
  const byMonth = new Map<string, TopicCandidate[]>();
  for (const c of all) {
    const m = monthOf.get(c.video_id)!.m;
    if (!byMonth.has(m)) byMonth.set(m, []);
    byMonth.get(m)!.push(c);
  }
  const months = [...byMonth.keys()].sort();
  const total = all.length;
  const quotas = months.map((m) => {
    const exact = (byMonth.get(m)!.length * limit) / total;
    const floor = Math.floor(exact);
    return { m, floor, rem: exact - floor };
  });
  const budget = new Map(quotas.map((q) => [q.m, q.floor]));
  let used = quotas.reduce((s, q) => s + q.floor, 0);
  const order = [...quotas].sort((a, b) => b.rem - a.rem || (a.m < b.m ? -1 : 1));
  for (let i = 0; used < limit && i < order.length; i++, used++) {
    budget.set(order[i].m, budget.get(order[i].m)! + 1);
  }

  const picked: TopicCandidate[] = [];
  for (const m of months) {
    picked.push(...byMonth.get(m)!.sort(byWeightThenId).slice(0, budget.get(m) ?? 0));
  }
  return picked.sort(byWeightThenId);
}
