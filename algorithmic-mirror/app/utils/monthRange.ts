/**
 * WP-3.3 — pure month-range filtering helpers for the Timeline scrubber.
 * No React, no side effects — trivial filters, safe to unit-test directly.
 */

export function unionMonths(...monthLists: string[][]): string[] {
  const set = new Set<string>();
  for (const list of monthLists) {
    for (const month of list) set.add(month);
  }
  return [...set].sort();
}

export function isMonthInRange(month: string, range: [string, string]): boolean {
  const [start, end] = range;
  return month >= start && month <= end;
}

export function filterEntriesByRange<T>(
  entries: [string, T][],
  range: [string, string],
): [string, T][] {
  return entries.filter(([month]) => isMonthInRange(month, range));
}

function quarterMonthBounds(quarterKey: string): [string, string] {
  const [year, q] = quarterKey.split("-Q");
  const quarterNum = Number(q);
  const startMonthNum = (quarterNum - 1) * 3 + 1;
  const endMonthNum = startMonthNum + 2;
  const pad = (n: number) => String(n).padStart(2, "0");
  return [`${year}-${pad(startMonthNum)}`, `${year}-${pad(endMonthNum)}`];
}

export function quarterOverlapsRange(quarterKey: string, range: [string, string]): boolean {
  const [qStart, qEnd] = quarterMonthBounds(quarterKey);
  const [rStart, rEnd] = range;
  return qStart <= rEnd && rStart <= qEnd;
}
