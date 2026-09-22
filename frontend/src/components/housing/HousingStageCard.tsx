import type { HousingStage } from "../../api/housing.types";
import { Card } from "../Card";
import { formatPeriod } from "../../lib/format";
import {
  STAGE_COPY,
  formatHousingChange,
  formatHousingPercent,
  formatHousingUnits,
  hasPreviousComparison,
  hasYearAgoComparison,
  unitCaption,
} from "../../lib/housingFormat";

/**
 * One stage of the pipeline (Increment #45).
 *
 * THE HEADLINE FIGURE IS THE ANNUAL RATE, because it is the only one
 * comparable month to month — construction is heavily seasonal, and
 * Census publishes no seasonally adjusted monthly level. But it is
 * never shown alone: the month's actual unadjusted count sits directly
 * beneath it, which is what turns "1,394,000" from a number that looks
 * like homes built in August into a number the reader can place.
 *
 * NO STATE, AND NOTHING THAT READS LIKE ONE. There is no badge, no
 * colour-coded direction, no "up is good" tone. A change is shown as a
 * signed number and a percentage, with the two periods it spans, and
 * nothing interprets it — MacroChipz has no housing methodology, so it
 * has no opinion to render here.
 */
export function HousingStageCard({ stage }: { stage: HousingStage }) {
  const copy = STAGE_COPY[stage.stage];
  const { pace, actual } = stage;
  const headingId = `housing-stage-${stage.stage.toLowerCase()}`;

  return (
    <Card as="li">
      <h3 id={headingId} className="type-card-heading text-fg">
        {copy.name}
      </h3>
      <p className="mt-1 text-sm text-fg-secondary">{copy.meaning}</p>

      {pace.available ? (
        <>
          <p className="mt-4 type-numeric text-3xl font-semibold tracking-tight text-fg">
            {formatHousingUnits(pace.value)}
          </p>
          <p className="mt-1 text-sm text-fg-secondary">
            {unitCaption(pace.unit)} · {formatPeriod(pace.period)}
          </p>

          {/* The figure that stops the one above being misread. */}
          {actual.available && (
            <p className="mt-3 border-t border-line-subtle pt-3 text-sm text-fg-secondary">
              <span className="type-numeric font-medium text-fg">{formatHousingUnits(actual.value)}</span>{" "}
              {unitCaption(actual.unit)}, before adjusting for the season.
            </p>
          )}

          <dl className="mt-4 space-y-1.5 text-sm">
            {hasPreviousComparison(pace) && (
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-fg-muted">vs {formatPeriod(pace.previous_period)}</dt>
                <dd className="type-numeric text-fg">
                  {formatHousingChange(pace.change_from_previous)}{" "}
                  <span className="text-fg-muted">({formatHousingPercent(pace.change_percent_from_previous)})</span>
                </dd>
              </div>
            )}
            {hasYearAgoComparison(pace) && (
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-fg-muted">vs {formatPeriod(pace.year_ago_period)}</dt>
                <dd className="type-numeric text-fg">
                  {formatHousingChange(pace.change_from_year_ago)}{" "}
                  <span className="text-fg-muted">({formatHousingPercent(pace.change_percent_from_year_ago)})</span>
                </dd>
              </div>
            )}
          </dl>

          <p className="mt-3 text-xs text-fg-muted">{copy.detail}</p>
        </>
      ) : (
        <p className="mt-4 text-sm text-fg-secondary">
          {pace.unavailable_reason ?? "No data is available for this measure."} Nothing here is estimated in the
          meantime.
        </p>
      )}
    </Card>
  );
}
