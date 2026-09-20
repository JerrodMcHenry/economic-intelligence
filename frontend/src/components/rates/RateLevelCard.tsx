import type { RateLevel } from "../../api/rates.types";
import { formatObservationDate, formatRateValue, maturityLabel } from "../../lib/ratesFormat";
import { Card } from "../Card";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import type { Explanation } from "../../content/explanations/types";
import { HistoricalContextNote } from "./HistoricalContextNote";
import { RateChangeList } from "./RateChangeList";
import { SourceProvenanceDisclosure } from "./RateProvenance";

/**
 * One canonical Treasury yield: its latest level, the four session
 * changes, historical context, and its source provenance
 * (Increment #30).
 *
 * The card shows the level and the changes by default and keeps
 * everything heavier -- ranks, provider, dataset, retrieval, source URL
 * -- one disclosure away, so the first screen stays readable while the
 * evidence remains one click from every number.
 *
 * An unavailable series renders an explicit "not yet ingested" state.
 * It never renders 0.00%.
 */
export function RateLevelCard({
  level,
  explanation,
  showContext = true,
}: {
  level: RateLevel;
  explanation: Explanation;
  showContext?: boolean;
}) {
  const maturity = maturityLabel(level.series_id);

  return (
    <Card as="li" className="flex flex-col">
      <div className="flex items-baseline justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <h3 className="type-card-heading text-fg">{maturity}</h3>
          <ExplanationTrigger explanation={explanation} />
        </div>
        <span className="type-meta text-fg-muted">{formatObservationDate(level.latest_date)}</span>
      </div>

      {level.available ? (
        <>
          <p className="mt-2 type-numeric text-3xl font-semibold tracking-tight text-fg">
            {formatRateValue(level.latest_value)}
          </p>
          <p className="type-meta text-fg-muted">{level.title}</p>

          <div className="mt-4">
            <RateChangeList changes={level.changes} label={maturity} />
          </div>

          {showContext && (
            <div className="mt-4 border-t border-line-subtle pt-3">
              <HistoricalContextNote context={level.historical_context} />
            </div>
          )}

          <div className="mt-4">
            <SourceProvenanceDisclosure provenance={level.provenance} />
          </div>
        </>
      ) : (
        <>
          <p className="mt-2 text-lg font-medium text-fg-muted">Not available</p>
          <p className="mt-1 type-meta text-fg-muted">
            {level.title} has not been ingested yet, so no level, change, or context can be shown for it.
          </p>
        </>
      )}
    </Card>
  );
}
