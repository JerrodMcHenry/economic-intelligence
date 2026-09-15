import type { InflationState, SeriesMomentumResult } from "../../api/inflation.types";
import type { LaborState } from "../../api/labor.types";
import type { StateDurationResult } from "../../api/stateDuration.types";
import type { ApiResourceState } from "../../api/useApiResource";
import { CORE_PCE, MOMENTUM } from "../../content/explanations/inflation";
import { formatPercent, formatPeriod } from "../../lib/format";
import { inflationStateLabel, inflationStateTone } from "../../lib/inflationLabels";
import { StateDurationLine } from "../StateDurationLine";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import { Badge } from "./Badge";
import { WhyThisState } from "./WhyThisState";

const STATE_DURATION_ERROR_MESSAGE = "Historical state duration could not be loaded.";

// `StateDurationLine` is shared with Labor (frozen contract §29's
// identical reasoning applied to the frontend), so its own
// `resolveStateLabel` prop is typed over the union `InflationState |
// LaborState` -- this cast is safe because Inflation's own
// `/inflation/state-duration` endpoint only ever returns a real
// InflationState value here at runtime (see StateDurationLine.tsx's
// own docstring).
function resolveInflationStateLabel(state: InflationState | LaborState): string {
  return inflationStateLabel(state as InflationState);
}

const HERO_METRICS = [
  { key: "r_3m_annualized", label: "3M" },
  { key: "r_6m_annualized", label: "6M" },
  { key: "r_12m", label: "12M" },
] as const;

/**
 * The primary, strongest visual element on the page: Core PCE's
 * canonical `state` (never re-labeled as good/bad/bullish/bearish),
 * scaled up as the page's single dominant object rather than sharing
 * top billing with a specific rate reading. `INSUFFICIENT_DATA` renders
 * through the same muted "unavailable" tone as every other unavailable
 * value on the page -- it must read as missing evidence, not a
 * direction. A compact 3M/6M/12M strip gives an at-a-glance read of
 * what's behind the state; the full metrics with evidence live in
 * MomentumMetrics below, not duplicated here.
 */
export function InflationHero({
  momentum,
  stateDuration,
}: {
  momentum: SeriesMomentumResult;
  stateDuration: ApiResourceState<StateDurationResult> & { reload: () => void };
}) {
  return (
    <section aria-labelledby="underlying-momentum-heading">
      <div className="flex items-center gap-1.5">
        <h2 id="underlying-momentum-heading" className="text-sm font-medium text-neutral-500">
          Underlying momentum
        </h2>
        <ExplanationTrigger explanation={MOMENTUM} />
      </div>
      <div className="mt-3">
        <Badge label={inflationStateLabel(momentum.state)} tone={inflationStateTone(momentum.state)} size="xl" />
      </div>
      <div className="mt-2 flex items-center gap-1.5">
        <p className="text-sm text-neutral-500">
          Core PCE{momentum.calculation_period ? ` · ${formatPeriod(momentum.calculation_period)}` : ""}
        </p>
        <ExplanationTrigger explanation={CORE_PCE} />
      </div>
      <StateDurationLine resource={stateDuration} errorMessage={STATE_DURATION_ERROR_MESSAGE} resolveStateLabel={resolveInflationStateLabel} />
      <WhyThisState momentum={momentum} />

      <dl className="mt-6 flex flex-wrap gap-x-10 gap-y-3">
        {HERO_METRICS.map(({ key, label }) => (
          <div key={key}>
            <dt className="text-xs font-medium uppercase tracking-wide text-neutral-400">{label}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-neutral-900">{formatPercent(momentum[key])}</dd>
          </div>
        ))}
      </dl>

      {momentum.missing_required_metrics.length > 0 && (
        <p className="mt-3 text-sm text-neutral-500">Missing required data: {momentum.missing_required_metrics.join(", ")}</p>
      )}
    </section>
  );
}
