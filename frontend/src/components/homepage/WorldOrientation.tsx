import { Link } from "react-router-dom";

import type { HousingResult } from "../../api/housing.types";
import type { InflationMonitorResult } from "../../api/inflation.types";
import type { IntelligenceObject } from "../../api/intelligence.types";
import type { LaborMonitorResult } from "../../api/labor.types";
import type { ApiResourceState } from "../../api/useApiResource";
import { formatPeriod } from "../../lib/format";
import { ECONOMIC_WORLDS, type WorldId } from "../../worlds/registry";

/**
 * WORLD ORIENTATION (Increment #45B).
 *
 * ================================================================
 * A DIFFERENT CLAIM FROM THE ONE THE LEDE MAKES
 * ================================================================
 *
 * #45A measured that 1,899 intelligence objects exist, **six are
 * homepage-eligible, and all six are Treasury yields**. That is not a
 * bug in `homepage_presentation_v1.0` — the policy correctly excludes
 * 1,532 coverage records and 358 first observations. It means the
 * homepage was an accurate projection of a database whose only
 * *changes* live in one world, and a reader who never scrolled left
 * believing MacroChipz was a Treasury tracker.
 *
 * The fix is NOT to weaken eligibility. THE LEDE keeps its policy and
 * its three states. This section sits beside it making a **different
 * claim**, and the distinction is the whole design:
 *
 *   THE LEDE        "this CHANGED"        — governed by the policy
 *   THIS SECTION    "this EXISTS, and
 *                    here is the latest
 *                    data on file"        — governed by the registry
 *
 * ================================================================
 * WHAT IT REFUSES TO DO
 * ================================================================
 *
 * - **No state badges.** `CurrentStateSection` already publishes
 *   Inflation's and Jobs' canonical states with a "Why Mixed?"
 *   explanation. Repeating them here would be the surface duplication
 *   #45A §A.11 flagged, and would make two places responsible for one
 *   fact.
 * - **No Housing state**, because none exists. Housing shows its
 *   latest published month, which is a fact about the data rather than
 *   a verdict on the economy.
 * - **No ordering by importance.** Registry order, which is a declared
 *   navigation order and nothing more.
 * - **No change language.** Nothing here says up, down, rose, fell,
 *   improved, worsened, or new. Those belong to the lede, which has a
 *   policy behind them.
 *
 * ================================================================
 * FAILURE ISOLATION
 * ================================================================
 *
 * The grid is rendered from `ECONOMIC_WORLDS`, so it is complete and
 * correct before any request resolves and cannot be blanked by one.
 * Each world's "latest data" line is independent: a failed Housing
 * fetch removes Housing's line and touches nothing else. A world with
 * no resolved line simply shows its description — never "no data",
 * never a zero, and never a claim that nothing is happening.
 */

/** What one world contributes, once its own resource resolves. */
type LatestLine = string | null;

export function WorldOrientation({
  inflation,
  labor,
  housing,
  intelligence,
}: {
  inflation: ApiResourceState<InflationMonitorResult>;
  labor: ApiResourceState<LaborMonitorResult>;
  housing: ApiResourceState<HousingResult>;
  /** Already-fetched objects; Rates' period is read from these rather
   * than from a sixth request. */
  intelligence: ReadonlyArray<IntelligenceObject>;
}) {
  const latest: Readonly<Record<WorldId, LatestLine>> = {
    INFLATION:
      inflation.status === "success" ? periodLine(inflation.data.underlying_momentum.calculation_period) : null,
    JOBS: labor.status === "success" ? periodLine(labor.data.evaluation_period) : null,
    RATES: periodLine(latestRatesPeriod(intelligence)),
    HOUSING: housing.status === "success" ? periodLine(housing.data.as_of_period) : null,
  };

  return (
    <section aria-labelledby="worlds-heading">
      <h2 id="worlds-heading" className="text-sm font-medium text-fg-muted">
        Explore the economy
      </h2>
      <p className="mt-2 max-w-prose text-sm text-fg-secondary">
        Four parts of the economy MacroChipz tracks, each with its own data, sources and limitations.
      </p>

      <ul className="mt-4 grid gap-3 sm:grid-cols-2">
        {ECONOMIC_WORLDS.map((world) => (
          <li key={world.id}>
            <Link
              to={world.route}
              className="block h-full rounded-lg border border-line bg-surface p-4 transition-colors hover:border-line-strong motion-reduce:transition-none"
            >
              <p className="font-medium text-fg">{world.label}</p>
              <p className="mt-1 text-sm text-fg-secondary">{world.description}</p>
              {latest[world.id] !== null && (
                <p className="mt-2 type-meta text-fg-muted">{latest[world.id]}</p>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * "Latest data: July 2026".
 *
 * A fact about the RECORD, deliberately — not about the economy. It
 * answers "does MacroChipz have current data here?", which is the
 * orientation question, and answers nothing else.
 */
function periodLine(period: string | null | undefined): LatestLine {
  if (period === null || period === undefined) return null;
  const formatted = formatPeriod(period);
  // `formatPeriod` returns this sentinel for a null period; a world
  // with no period shows no line at all rather than an absence notice.
  if (formatted === "No data available") return null;
  return `Latest data: ${formatted}`;
}

/**
 * The most recent effective period across the already-fetched rates
 * objects.
 *
 * Reads the objects the homepage ALREADY has rather than issuing a
 * sixth request. `effective_period` is the period the data describes —
 * never `recorded_at`, which on this data is a backfill timestamp.
 */
function latestRatesPeriod(objects: ReadonlyArray<IntelligenceObject>): string | null {
  const periods = objects.filter((object) => object.world === "rates").map((object) => object.effective_period);
  return periods.length === 0 ? null : periods.reduce((a, b) => (a > b ? a : b));
}
