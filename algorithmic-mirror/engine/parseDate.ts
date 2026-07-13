/**
 * WP-1.1 engine port — date parsing.
 *
 * Mirrors `parsers.tiktok._parse_date` (the one `_run_stopwatch` uses).
 * Parity notes:
 *  - Built with `Date.UTC(...)` and read back with `getUTC*` throughout the
 *    engine, so the literal string hour/weekday round-trips to Python's naive
 *    `datetime` — no timezone drift, and DST is irrelevant to both sides.
 *  - Python returns None on an unrecognized format; we return null (NO
 *    `new Date(str)` fallback — that would parse strings Python drops).
 *  - The fractional-seconds branch captures `.%f` but ignores it; the oracle's
 *    fixtures are whole-second, and sub-second deltas can't survive strftime.
 *    A real `.%f` input would diverge by <1s — documented, not yet exercised.
 *
 * This lives here temporarily; promotes to the shared engine package when the
 * WP-1.1 layout is settled. The Supabase Deno copy is frozen/legacy.
 */

const PATTERNS: RegExp[] = [
  /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/,        // 2024-05-22 14:30:00
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})$/,        // 2024-05-22T14:30:00
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d+)$/, // 2024-05-22T14:30:00.000
  /^(\d{4})-(\d{2})-(\d{2})$/,                                 // 2024-05-22
];

export function parseDate(dateStr: string): Date | null {
  if (!dateStr) return null;
  for (const re of PATTERNS) {
    const m = dateStr.match(re);
    if (m) {
      const y = +m[1];
      const mo = +m[2];
      const d = +m[3];
      const h = m[4] !== undefined ? +m[4] : 0;
      const min = m[5] !== undefined ? +m[5] : 0;
      const s = m[6] !== undefined ? +m[6] : 0;
      return new Date(Date.UTC(y, mo - 1, d, h, min, s));
    }
  }
  return null;
}
