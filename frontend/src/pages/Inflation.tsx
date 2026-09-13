/**
 * Placeholder only. Deliberately does NOT fetch from
 * GET /api/v1/monitors/inflation or .../inflation/changes, and
 * contains no product UI -- both are explicitly out of scope for the
 * frontend foundation increment (#16A) and belong to the Inflation
 * Monitor UI increment (#16B).
 */
export function InflationPage() {
  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Inflation</h1>
      <p className="mt-3 text-neutral-600">
        This page will present Core PCE underlying momentum, confirmation, target level, and what changed since
        the previous period, sourced entirely from the deterministic backend.
      </p>
      <p className="mt-2 text-neutral-600">Not yet implemented.</p>
    </div>
  );
}
