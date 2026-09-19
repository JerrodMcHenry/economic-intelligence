import type { InflationState } from "../../api/inflation.types";
import type { LaborMonitorResult, LaborState } from "../../api/labor.types";
import type { StateDurationResult } from "../../api/stateDuration.types";
import type { ApiResourceState } from "../../api/useApiResource";
import { LABOR_MONITOR } from "../../content/explanations/labor";
import { formatPeriod } from "../../lib/format";
import { laborStateLabel, laborStateTone } from "../../lib/laborLabels";
import { StateDurationLine } from "../StateDurationLine";
import { Badge } from "../inflation/Badge";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import { WhyLaborState } from "./WhyLaborState";

const STATE_DURATION_ERROR_MESSAGE = "Historical state duration could not be loaded.";

// `StateDurationLine` is shared with Inflation (frozen contract §29's
// identical reasoning applied to the frontend), so its own
// `resolveStateLabel` prop is typed over the union `InflationState |
// LaborState` -- this cast is safe because Labor's own
// `/labor/state-duration` endpoint only ever returns a real LaborState
// value here at runtime (see StateDurationLine.tsx's own docstring).
function resolveLaborStateLabel(state: InflationState | LaborState): string {
  return laborStateLabel(state as LaborState);
}

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
export function LaborHero({
  result,
  stateDuration,
}: {
  result: LaborMonitorResult;
  stateDuration: ApiResourceState<StateDurationResult> & { reload: () => void };
}) {
  return (
    <section aria-labelledby="labor-current-state-heading">
      <div className="flex items-center gap-1.5">
        <h2 id="labor-current-state-heading" className="text-sm font-medium text-fg-muted">
          Current state
        </h2>
        <ExplanationTrigger explanation={LABOR_MONITOR} />
      </div>
      <div className="mt-3">
        <Badge label={laborStateLabel(result.state)} tone={laborStateTone(result.state)} size="xl" />
      </div>
      <p className="mt-2 text-sm text-fg-muted">
        Labor{result.evaluation_period ? ` · ${formatPeriod(result.evaluation_period)}` : ""}
      </p>
      <StateDurationLine resource={stateDuration} errorMessage={STATE_DURATION_ERROR_MESSAGE} resolveStateLabel={resolveLaborStateLabel} />
      <WhyLaborState result={result} />
    </section>
  );
}
