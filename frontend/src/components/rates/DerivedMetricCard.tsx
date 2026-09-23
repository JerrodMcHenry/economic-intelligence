import type { CurveSpread, InflationCompensation } from "../../api/rates.types";
import { describeUnavailableReason, formatBasisPointLevel, formatObservationDate, formatRateValue } from "../../lib/ratesFormat";
import { Card } from "../Card";
import { Disclosure } from "../Disclosure";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import type { Explanation } from "../../content/explanations/types";
import { HistoricalContextNote } from "./HistoricalContextNote";
import { RateChangeList } from "./RateChangeList";
import { DerivedProvenanceDisclosure } from "./RateProvenance";

/**
 * A value MacroChipz calculated, presented so it can never be mistaken
 * for one Treasury published (Increment #30).
 *
 * The distinction is made three ways: an explicit "Calculated" marker
 * on the face of the card, the inputs shown inline as the arithmetic
 * that produced it, and a provenance panel naming the methodology
 * rather than a provider.
 *
 * When the value is unavailable the card explains WHY in the
 * backend's own terms -- most importantly, that a missing shared
 * observation date means the value was not calculated rather than
 * estimated.
 */

function DerivedShell({
  heading,
  subtitle,
  explanation,
  observationDate,
  children,
}: {
  heading: string;
  subtitle: string;
  explanation: Explanation;
  observationDate: string | null;
  children: React.ReactNode;
}) {
  return (
    <Card as="li" className="flex flex-col">
      <div className="flex items-baseline justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <h3 className="type-card-heading text-fg">{heading}</h3>
          <ExplanationTrigger explanation={explanation} />
        </div>
        <span className="type-meta text-fg-muted">{formatObservationDate(observationDate)}</span>
      </div>
      <p className="type-meta text-fg-muted">{subtitle}</p>
      <span className="mt-2 inline-flex w-fit items-center rounded-md bg-surface-secondary px-2 py-0.5 type-label text-fg-muted">
        Calculated by MacroChipz
      </span>
      {children}
    </Card>
  );
}

export function CurveSpreadCard({ spread, explanation }: { spread: CurveSpread; explanation: Explanation }) {
  return (
    /* #49B: the CALCULATION leads and the identifier follows. "2s10s"
       is a trading desk's word; "10-Year minus 2-Year" is the backend's
       own `title` and is what the reader can act on. Nothing is hidden
       -- the id is still printed directly beneath. */
    <DerivedShell
      heading={spread.title}
      subtitle={spread.spread_id}
      explanation={explanation}
      observationDate={spread.observation_date}
    >
      {spread.available ? (
        <>
          <p className="mt-2 type-numeric text-3xl font-semibold tracking-tight text-fg">
            {formatBasisPointLevel(spread.spread_basis_points)}
          </p>
          <p className="mt-1 type-meta text-fg-muted">
            {formatRateValue(spread.long_value)} ({spread.long_series_id.replace("UST_NOMINAL_", "")}){" "}
            <span aria-hidden="true">−</span>
            <span className="sr-only">minus</span> {formatRateValue(spread.short_value)} (
            {spread.short_series_id.replace("UST_NOMINAL_", "")})
          </p>

          <div className="mt-4">
            <RateChangeList changes={spread.changes} label={spread.spread_id} />
          </div>

          {/* #49B: behind a disclosure on the DERIVED cards.
              Four of these render at once and each carried two
              paragraphs of rank prose, which made this section 2,334px
              of a 5,863px phone page. The data is unchanged and one
              tap away; the selected maturity's own context stays open,
              because only one of those is on screen. */}
          <div className="mt-4 border-t border-line-subtle pt-1">
            <Disclosure summary="Historical context" summaryClassName="min-h-11">
              <HistoricalContextNote context={spread.historical_context} />
            </Disclosure>
          </div>

          <div className="mt-4">
            <DerivedProvenanceDisclosure provenance={spread.provenance} />
          </div>
        </>
      ) : (
        <>
          <p className="mt-2 text-lg font-medium text-fg-muted">Not available</p>
          <p className="mt-1 type-meta text-fg-muted">{describeUnavailableReason(spread.unavailable_reason)}</p>
        </>
      )}
    </DerivedShell>
  );
}

export function InflationCompensationCard({
  compensation,
  explanation,
}: {
  compensation: InflationCompensation;
  explanation: Explanation;
}) {
  return (
    <DerivedShell
      heading={compensation.title}
      subtitle={`${compensation.maturity} compensation`}
      explanation={explanation}
      observationDate={compensation.observation_date}
    >
      {compensation.available ? (
        <>
          <p className="mt-2 type-numeric text-3xl font-semibold tracking-tight text-fg">
            {formatRateValue(compensation.compensation_percent)}
          </p>
          <p className="mt-1 type-meta text-fg-muted">
            {formatRateValue(compensation.nominal_value)} nominal <span aria-hidden="true">−</span>
            <span className="sr-only">minus</span> {formatRateValue(compensation.real_value)} real
          </p>

          <div className="mt-4">
            <RateChangeList changes={compensation.changes} label={`${compensation.maturity} compensation`} />
          </div>

          <div className="mt-4 border-t border-line-subtle pt-1">
            <Disclosure summary="Historical context" summaryClassName="min-h-11">
              <HistoricalContextNote context={compensation.historical_context} />
            </Disclosure>
          </div>

          <div className="mt-4">
            <DerivedProvenanceDisclosure provenance={compensation.provenance} />
          </div>
        </>
      ) : (
        <>
          <p className="mt-2 text-lg font-medium text-fg-muted">Not available</p>
          <p className="mt-1 type-meta text-fg-muted">{describeUnavailableReason(compensation.unavailable_reason)}</p>
        </>
      )}
    </DerivedShell>
  );
}
