import { Link } from "react-router-dom";

import type { IntelligenceListResponse } from "../../api/intelligence.types";
import type { ApiResourceState } from "../../api/useApiResource";
import { eligibility, comparePresentation, isRatesMovement } from "../../homepage/presentationPolicy";
import { basisLabel, conceptShortName, knowledgeLabel } from "../../lib/intelligenceLanguage";
import { formatObservationDate, formatRateValue } from "../../lib/ratesFormat";
import { intelligencePath } from "../../lib/siteUrl";
import { Disclosure } from "../Disclosure";
import { ErrorMessage } from "../ErrorMessage";
import { LoadingSkeleton } from "../LoadingSkeleton";

const ERROR_MESSAGE = "Recorded movements could not be loaded.";

/**
 * The movements MacroChipz recorded, on the page that is about them
 * (Increment #52B).
 *
 * ================================================================
 * SIX OBJECTS THAT RENDERED NOWHERE
 * ================================================================
 *
 * #52A's audit found that `/api/v1/intelligence?world=rates` returns
 * six `RATES_MOVEMENT` objects, one per ingested Treasury series, and
 * that `/rates` showed none of them. Inflation and Jobs both carry a
 * history section; Rates carried only `RevisionsLink`.
 *
 * It could not simply reuse `IntelligenceHistorySection`. That consumes
 * `MonitorHistoryResponse` from `/api/v1/monitors/{monitor}/history`,
 * and that route accepts only `inflation` and `labor` — `rates` returns
 * 422. Rates has no recorded-RESULT history, which is a real gap
 * documented in the audit, not something to paper over here. These are
 * a different kind of object: one recorded observation per series,
 * carrying its own evidence.
 *
 * ================================================================
 * SECONDARY CONTEXT, AND LABELLED AS A DIFFERENT KIND OF FACT
 * ================================================================
 *
 * The curve above is the CURRENT published reading. These are things
 * MacroChipz RECORDED, at a time MacroChipz recorded them. Conflating
 * the two would be the worst outcome available here, so every row
 * carries both dates under distinct labels: the observation date the
 * reading is about, and `recorded_at`, which is when this product
 * wrote it down.
 *
 * `published_at` is deliberately absent: it is `null` on every object
 * MacroChipz holds, and an empty "published" field beside a date reads
 * as a claim that the provider published at that moment.
 *
 * ================================================================
 * ELIGIBILITY AND LIMITATIONS ARE THE OBJECTS' OWN
 * ================================================================
 *
 * Rows are filtered by `homepage_presentation_v1.0`'s `eligibility` and
 * ordered by its `comparePresentation` — the product's existing,
 * tested, score-free policy, not a second one invented for this page.
 * The one thing NOT reused is its per-concept deduplication, which
 * exists because the homepage is an orientation surface; the Rates
 * world is where all six maturities belong.
 *
 * Each row's limitations come from the object itself. They are not
 * summarised, rewritten or selected from — including the one that
 * matters most here, which says in the backend's own words that a
 * recorded movement carries no significance claim.
 *
 * ================================================================
 * COLLAPSED BY DEFAULT, AND NOTHING IS DROPPED TO ACHIEVE IT
 * ================================================================
 *
 * Six cards measured 1,500px at 390px — on a page #52A had already
 * measured at 5,646px, and which this increment legitimately grows by
 * another 633px for the comparison that is its whole point. Secondary
 * context taking a fifth of a phone page is not secondary.
 *
 * So the list sits behind one disclosure. The heading, the explanation
 * of what these are, and the COUNT stay visible, so a reader can see
 * that six records exist and what they are before deciding to open
 * them. No record is omitted, none is summarised, and every field —
 * including all three limitations per object — is in the same place it
 * was. The page is shorter; the product says exactly as much.
 */
export function RecordedMovements({
  movements,
  headingId,
}: {
  movements: ApiResourceState<IntelligenceListResponse> & { reload: () => void };
  headingId: string;
}) {
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId} className="text-sm font-medium text-fg-muted">
        Movements MacroChipz recorded
      </h2>
      <p className="mt-2 max-w-prose text-sm text-fg-secondary">
        Each Treasury observation MacroChipz has processed is recorded on its own, with the evidence behind it. These are
        records of what was observed and when it was written down &mdash; not the current reading, which is the curve
        above.
      </p>

      {movements.status === "loading" && (
        <div className="mt-4">
          <LoadingSkeleton label="Loading recorded movements" heightClassName="h-32" />
        </div>
      )}
      {movements.status === "error" && (
        <div className="mt-4">
          <ErrorMessage message={ERROR_MESSAGE} onRetry={movements.reload} />
        </div>
      )}
      {movements.status === "success" && <MovementList response={movements.data} />}
    </section>
  );
}

/** How many rows the disclosure promises, so the count is visible while the list is not. */
function summaryLabel(count: number): string {
  return count === 1 ? "Show the 1 recorded movement" : `Show all ${count} recorded movements`;
}

/**
 * Eligible rates movements, in the product's existing order.
 *
 * `eligibility` and `comparePresentation` are `homepage_presentation_v1.0`'s
 * own — a tested, score-free policy — rather than a second one written
 * here. Its per-concept deduplication is deliberately NOT reused: that
 * exists because the homepage is an orientation surface, and the Rates
 * world is where all six maturities belong.
 */
function selectMovements(response: IntelligenceListResponse) {
  return response.items
    .filter((object) => object.world === "rates")
    .filter((object) => eligibility(object).eligible)
    .filter(isRatesMovement)
    .sort(comparePresentation);
}

function MovementList({ response }: { response: IntelligenceListResponse }) {
  const rows = selectMovements(response);

  if (rows.length === 0) {
    return (
      <p className="mt-4 max-w-prose text-sm text-fg-muted">
        MacroChipz has recorded no Treasury movements yet. Nothing is shown in their place.
      </p>
    );
  }

  return (
    <div className="mt-4 max-w-3xl">
      <Disclosure summary={summaryLabel(rows.length)} summaryClassName="min-h-11">
        <MovementCards rows={rows} />
      </Disclosure>
    </div>
  );
}

function MovementCards({ rows }: { rows: ReturnType<typeof selectMovements> }) {
  return (
    <ul className="mt-3 grid gap-3 sm:grid-cols-2">
      {rows.map((object) => {
        const evidence = object.evidence[0];
        return (
          <li key={object.id} className="lx-card rounded-xl p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <Link
                to={intelligencePath(object.id)}
                className="text-sm font-semibold text-fg underline-offset-4 hover:underline"
              >
                {conceptShortName(object.concepts[0], object.payload.series_title)}
              </Link>
              {object.payload.latest_value !== null && (
                <span className="type-numeric text-sm font-semibold text-fg">
                  {formatRateValue(object.payload.latest_value)}
                </span>
              )}
            </div>

            {/* Two dates, two different facts, never merged. */}
            <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-0.5 type-meta text-fg-muted">
              <dt>Observed</dt>
              <dd className="type-numeric">
                <time dateTime={object.effective_period}>{formatObservationDate(object.effective_period)}</time>
              </dd>
              <dt>Recorded</dt>
              <dd className="type-numeric">
                <time dateTime={object.recorded_at}>{formatObservationDate(object.recorded_at)}</time>
              </dd>
            </dl>

            <p className="mt-2 type-meta text-fg-muted">
              {basisLabel(object)} &middot; {knowledgeLabel(object)}
            </p>

            <div className="mt-3">
              <Disclosure summary="Evidence and limitations" summaryClassName="min-h-11">
                <div className="space-y-3 pt-1 text-sm text-fg-secondary">
                  {evidence !== undefined && (
                    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 type-meta">
                      <dt className="text-fg-muted">Provider</dt>
                      <dd>{evidence.provider}</dd>
                      <dt className="text-fg-muted">Series</dt>
                      <dd>{evidence.provider_series_id}</dd>
                      <dt className="text-fg-muted">Observation</dt>
                      <dd className="type-numeric">
                        {formatObservationDate(evidence.observation_date)} &middot;{" "}
                        {formatRateValue(evidence.value)}
                      </dd>
                    </dl>
                  )}
                  {/* Verbatim. Not summarised, not selected from. */}
                  <ul className="space-y-1.5">
                    {object.limitations.map((limitation) => (
                      <li key={limitation} className="type-meta text-fg-muted">
                        {limitation}
                      </li>
                    ))}
                  </ul>
                </div>
              </Disclosure>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
