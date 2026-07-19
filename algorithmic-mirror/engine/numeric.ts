/**
 * WP-1.1 engine port — numeric helpers shared across modules.
 */

/** Python's round(): round-half-to-even (banker's rounding). JS Math.round is half-up. */
export function pyRound(x: number, ndigits = 0): number {
  const m = Math.pow(10, ndigits);
  const scaled = x * m;
  const floor = Math.floor(scaled);
  const diff = scaled - floor;
  let rounded: number;
  if (Math.abs(diff - 0.5) < 1e-9) {
    rounded = floor % 2 === 0 ? floor : floor + 1;
  } else {
    rounded = Math.round(scaled);
  }
  return rounded / m;
}
