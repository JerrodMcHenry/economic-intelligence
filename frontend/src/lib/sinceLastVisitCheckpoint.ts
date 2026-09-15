/**
 * Local checkpoint persistence for Increment #25H's Since Last Visit
 * V1 return experience -- see docs/product/since-last-visit-v1.md
 * (#25F), specifically §8-9/§13/§87/§93. This is the FIRST module in
 * this frontend to use browser storage of any kind (confirmed absent
 * everywhere else, #25F §2/§8).
 *
 * HARD REQUIREMENT (contract §10-13, restated for the frontend): the
 * ONLY checkpoint value this module ever persists is a server-issued
 * `through` watermark, copied verbatim from a successful
 * `SinceLastVisitResponse`. This module contains no call to the
 * browser's own wall clock anywhere -- it cannot construct a
 * checkpoint value on its own, only store and return one it was
 * handed. See `../test/no-since-last-visit-derivation.test.ts` for
 * the structural guard proving this.
 *
 * `localStorage` is treated as untrusted input throughout: a missing
 * key, a JSON parse failure, an unexpected shape, a `schemaVersion`
 * mismatch, or `getItem`/`setItem` throwing (private browsing,
 * disabled storage, a quota error) are all handled by degrading to
 * "no checkpoint" (read) or "write silently skipped" (write) -- never
 * a thrown error, never a console error, never a blocked Overview
 * (contract §7/§87).
 */

const STORAGE_KEY = "economic-intelligence:since-last-visit:v1";
const SCHEMA_VERSION = 1;

export interface SinceLastVisitCheckpoint {
  schemaVersion: number;
  through: string;
}

function isValidCheckpoint(value: unknown): value is SinceLastVisitCheckpoint {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.schemaVersion === SCHEMA_VERSION &&
    typeof candidate.through === "string" &&
    candidate.through.length > 0 &&
    !Number.isNaN(Date.parse(candidate.through))
  );
}

/**
 * Reads the stored checkpoint, or `null` if none exists, storage is
 * unavailable, or the stored value is malformed/old-shaped in any way
 * -- every one of those conditions degrades identically to "first
 * visit" (contract §7/§87), never a thrown error. `Date.parse` above
 * is used only to VALIDATE that `through` is a real, parseable
 * timestamp string -- never to construct or replace it; the string
 * value itself, exactly as stored, is what this function returns.
 */
export function readSinceLastVisitCheckpoint(): SinceLastVisitCheckpoint | null {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
  if (raw === null) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }

  return isValidCheckpoint(parsed) ? parsed : null;
}

/**
 * Persists `through` -- a value that MUST have come verbatim from a
 * successful `SinceLastVisitResponse.through` (contract §93's own
 * exact checkpoint-update sequence; enforced at the call site, this
 * function itself accepts any string and does not, and cannot,
 * validate provenance). A write failure (quota exceeded, storage
 * disabled) is caught and silently ignored -- the recap still
 * rendered successfully; simply not persisting is strictly safer than
 * surfacing a page failure for a purely additive feature (contract
 * §61/§87-88).
 */
export function writeSinceLastVisitCheckpoint(through: string): void {
  const checkpoint: SinceLastVisitCheckpoint = { schemaVersion: SCHEMA_VERSION, through };
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(checkpoint));
  } catch {
    // Intentionally swallowed -- see this function's own docstring.
  }
}
