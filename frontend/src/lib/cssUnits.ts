/**
 * CSS unit helpers. Layout arithmetic, never economic arithmetic.
 *
 * ================================================================
 * WHY THIS FILE EXISTS
 * ================================================================
 *
 * `src/test/no-rates-calculation.test.ts` scans every Rates UI file for
 * `* 100` and `/ 100`, because in that context those are the shape of a
 * percentage-point to basis-point conversion — exactly the financial
 * arithmetic the frontend is forbidden from doing.
 *
 * #49B's curve control layer needs to turn a 0..1 position into a CSS
 * percentage, which is the same two characters and an entirely
 * different act. The answer is not to loosen the guard, which is one of
 * the load-bearing protections in this codebase. It is to put the
 * conversion where it actually belongs: a shared layout helper, outside
 * the economics boundary, doing something no reader could mistake for a
 * rate calculation.
 */

/** A 0..1 fraction of a container, as a CSS percentage string. */
export function percentOf(fraction: number): string {
  return `${fraction * 100}%`;
}
