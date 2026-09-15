import type { InflationState } from "../api/inflation.types";
import type { LaborState } from "../api/labor.types";
import type { StateDurationResult } from "../api/stateDuration.types";
import type { ApiResourceState } from "../api/useApiResource";
import { buildStateDurationCopy } from "../lib/stateDurationCopy";
import { ErrorMessage } from "./ErrorMessage";
import { LoadingSkeleton } from "./LoadingSkeleton";

/**
 * The one small, shared presentation element behind State Duration V1
 * on both /inflation and /labor (frozen contract
 * docs/product/state-duration-v1.md §39/§40 -- one new single line
 * inside each page's own Hero, directly after the period line and
 * before the Why disclosure). Understands the states a
 * `StateDurationResult` resource can be in -- loading, an
 * infrastructure `ApiError`, `CURRENT_INSUFFICIENT`, and `AVAILABLE`
 * with its three boundary types -- but knows NOTHING about Inflation
 * formulas, Labor formulas, series IDs, or economic thresholds:
 * `resolveStateLabel` is always supplied by the caller (its own
 * monitor-specific `inflationStateLabel`/`laborStateLabel`), and every
 * number/period/state rendered is read straight off the response,
 * never recomputed here (see lib/stateDurationCopy.ts).
 *
 * An API/infrastructure failure renders the existing `ErrorMessage`
 * pattern (with retry) -- never the `CURRENT_INSUFFICIENT` copy, which
 * would misrepresent an infrastructure failure as an economic-data
 * condition (frozen contract §33/§42).
 */
export function StateDurationLine({
  resource,
  errorMessage,
  resolveStateLabel,
}: {
  resource: ApiResourceState<StateDurationResult> & { reload: () => void };
  errorMessage: string;
  resolveStateLabel: (state: InflationState | LaborState) => string;
}) {
  if (resource.status === "loading") {
    return <LoadingSkeleton label="Loading state duration" heightClassName="h-5" />;
  }

  if (resource.status === "error") {
    return <ErrorMessage message={errorMessage} onRetry={resource.reload} />;
  }

  const result = resource.data;
  const stateLabel = result.status === "AVAILABLE" ? resolveStateLabel(result.state) : "";
  const previousStateLabel =
    result.status === "AVAILABLE" && result.previous_state !== null ? resolveStateLabel(result.previous_state) : null;
  const copy = buildStateDurationCopy(result, stateLabel, previousStateLabel);

  return (
    <div className="mt-2">
      <p className="text-sm text-neutral-500">{copy.headline}</p>
      {copy.previousStateNote && <p className="mt-0.5 text-xs text-neutral-400">{copy.previousStateNote}</p>}
    </div>
  );
}
