import type { LaborMonitorResult } from "../../api/labor.types";
import { LABOR_MONITOR } from "../../content/explanations/labor";
import { formatPeriod } from "../../lib/format";
import { laborStateLabel, laborStateTone } from "../../lib/laborLabels";
import { Badge } from "../inflation/Badge";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import { WhyLaborState } from "./WhyLaborState";

/**
 * The primary, strongest visual element on the /labor page: the
 * canonical top-level `LaborState` (never re-labeled as good/bad,
 * bullish/bearish, or "the economy is..."), scaled up as the page's
 * single dominant object -- the same visual role InflationHero plays
 * on /inflation. No directional color-coding (see
 * docs/architecture/labor-ui-v1.md §8): `Badge` reuses the existing,
 * fully generic component -- it is not Inflation-specific despite its
 * current file location (no Inflation logic exists inside it).
 */
export function LaborHero({ result }: { result: LaborMonitorResult }) {
  return (
    <section aria-labelledby="labor-current-state-heading">
      <div className="flex items-center gap-1.5">
        <h2 id="labor-current-state-heading" className="text-sm font-medium text-neutral-500">
          Current state
        </h2>
        <ExplanationTrigger explanation={LABOR_MONITOR} />
      </div>
      <div className="mt-3">
        <Badge label={laborStateLabel(result.state)} tone={laborStateTone(result.state)} size="xl" />
      </div>
      <p className="mt-2 text-sm text-neutral-500">
        Labor{result.evaluation_period ? ` · ${formatPeriod(result.evaluation_period)}` : ""}
      </p>
      <WhyLaborState result={result} />
    </section>
  );
}
