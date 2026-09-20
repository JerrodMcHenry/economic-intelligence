import type { HistoricalContext } from "../../api/rates.types";
import { HISTORICAL_PERCENTILE } from "../../content/explanations/rates";
import {
  formatBasisPointLevel,
  formatChangeWindow,
  formatObservationDate,
  formatPercentileOrdinal,
} from "../../lib/ratesFormat";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";

/**
 * Backend-computed historical context for one metric (Increment #30).
 *
 * States exactly what the ranks mean and nothing more. The signed rank
 * and the magnitude rank are labelled separately and never merged into
 * one "unusualness" number -- they answer different questions and
 * routinely disagree. No sentence here concludes anything ("rates are
 * volatile", "an unusually large move"); the reader is given the rank,
 * the population size, and the window the population was drawn from.
 */
export function HistoricalContextNote({ context }: { context: HistoricalContext }) {
  if (!context.available || context.observation_count === 0) {
    return (
      <p className="type-meta text-fg-muted">
        Historical context needs more history than is currently stored for this metric.
      </p>
    );
  }

  const window = formatChangeWindow(context.window);

  return (
    <div className="type-meta text-fg-muted">
      <div className="flex items-center gap-1.5">
        <span className="type-label">Historical context</span>
        <ExplanationTrigger explanation={HISTORICAL_PERCENTILE} />
      </div>
      <p className="mt-1">
        The latest {window} change ranks at the{" "}
        <span className="font-semibold text-fg-secondary">{formatPercentileOrdinal(context.percentile_rank)}</span>{" "}
        percentile of prior {window} changes by direction and size, and at the{" "}
        <span className="font-semibold text-fg-secondary">
          {formatPercentileOrdinal(context.magnitude_percentile_rank)}
        </span>{" "}
        percentile by size alone.
      </p>
      <p className="mt-1">
        Compared against {context.observation_count} prior {window} changes since{" "}
        {formatObservationDate(context.history_start_date)}, which ranged from{" "}
        {formatBasisPointLevel(context.minimum_change_basis_points)} to{" "}
        {formatBasisPointLevel(context.maximum_change_basis_points)}.
      </p>
    </div>
  );
}
