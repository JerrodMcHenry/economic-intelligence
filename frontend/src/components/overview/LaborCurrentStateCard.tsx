import { Link } from "react-router-dom";

import type { LaborMonitorResult } from "../../api/labor.types";
import { formatPeriod } from "../../lib/format";
import { laborStateLabel, laborStateTone } from "../../lib/laborLabels";
import { Badge } from "../inflation/Badge";
import { WhyLaborState } from "../labor/WhyLaborState";

/**
 * The Economic Overview's Labor "Current State" card -- the peer of
 * `InflationCurrentStateCard` (Increment #20E.2). Deliberately NOT
 * `LaborHero` reused wholesale, for the identical reason Inflation's
 * own card isn't `InflationHero` reused wholesale (see that file's own
 * docstring): a compact state + period + explanation + link, no
 * Employment/Unemployment detail, all of which stay on `/labor` only.
 *
 * The "Labor" label directly beside the state Badge is the identical
 * load-bearing device Inflation's own card uses -- it is what stands
 * between "Labor is COOLING" (true, sourced) and "the economy is
 * COOLING" (a synthetic economy-wide conclusion this product must
 * never imply, docs/architecture/labor-ui-v1.md §29). Renders
 * `result.state` exactly as returned; `WhyLaborState` (reused
 * unmodified from /labor) carries the same contradictory-evidence
 * guarantee.
 */
export function LaborCurrentStateCard({ result }: { result: LaborMonitorResult }) {
  return (
    <div>
      <p className="text-sm font-semibold text-fg-secondary">Labor</p>
      <div className="mt-1.5">
        <Badge label={laborStateLabel(result.state)} tone={laborStateTone(result.state)} size="xl" />
      </div>
      <p className="mt-2 text-sm text-fg-muted">
        Labor{result.evaluation_period ? ` · ${formatPeriod(result.evaluation_period)}` : ""}
      </p>
      <WhyLaborState result={result} />

      <Link to="/labor" className="mt-4 inline-block text-sm font-medium text-fg-secondary hover:text-fg">
        Open Labor →
      </Link>
    </div>
  );
}
