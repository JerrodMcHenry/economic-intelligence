import { Link } from "react-router-dom";

import type { SeriesMomentumResult } from "../../api/inflation.types";
import { formatPeriod } from "../../lib/format";
import { inflationStateLabel, inflationStateTone } from "../../lib/inflationLabels";
import { Badge } from "../inflation/Badge";
import { WhyThisState } from "../inflation/WhyThisState";

/**
 * The Economic Overview's "Current State" section -- deliberately NOT
 * `InflationHero` reused wholesale (that would make Overview a second
 * `/inflation`; see docs/ENGINEERING_JOURNAL.md's #19A entry for why).
 * This renders only state + the label naming WHICH dimension that
 * state belongs to + period + the existing contradiction-proof
 * `WhyThisState` explanation + a link to the full page -- no 3M/6M/12M
 * strip, no target/confirmation/headline detail, all of which stay on
 * `/inflation` only.
 *
 * The "Inflation" label directly beside the state Badge is deliberate
 * and load-bearing: it is the one thing standing between "Inflation is
 * MIXED" (true, sourced) and "the economy is MIXED" (a synthetic
 * economy-wide conclusion this product must never imply). Renders
 * `momentum.state` exactly as returned -- there is no branch here that
 * inspects `r_3m_annualized`/`r_6m_annualized`/`r_12m` to decide
 * anything; `WhyThisState` (reused unmodified) carries the same
 * contradictory-evidence guarantee it already has on `/inflation`.
 */
export function CurrentStateSection({ momentum }: { momentum: SeriesMomentumResult }) {
  return (
    <section aria-labelledby="overview-current-state-heading">
      <h2 id="overview-current-state-heading" className="text-sm font-medium text-neutral-500">
        Current State
      </h2>

      <div className="mt-3">
        <p className="text-sm font-semibold text-neutral-700">Inflation</p>
        <div className="mt-1.5">
          <Badge label={inflationStateLabel(momentum.state)} tone={inflationStateTone(momentum.state)} size="xl" />
        </div>
        <p className="mt-2 text-sm text-neutral-500">
          Core PCE{momentum.calculation_period ? ` · ${formatPeriod(momentum.calculation_period)}` : ""}
        </p>
        <WhyThisState momentum={momentum} />
      </div>

      <p className="mt-4 max-w-prose text-xs text-neutral-400">
        Inflation is the first fully deterministic monitor. More are being added as their methodologies are built.
      </p>

      <Link to="/inflation" className="mt-4 inline-block text-sm font-medium text-neutral-700 hover:text-neutral-900">
        Open Inflation →
      </Link>
    </section>
  );
}
