import { getRatesMonitor } from "../api/rates";
import type { RateChange, RatesMonitorResult } from "../api/rates.types";
import { getAnalystAvailability } from "../api/analyst";
import { useApiResource } from "../api/useApiResource";
import { Disclosure } from "../components/Disclosure";
import { AskMacroChipz } from "../components/analyst/AskMacroChipz";
import { ErrorMessage } from "../components/ErrorMessage";
import { ExplanationTrigger } from "../components/explanations/ExplanationTrigger";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { PageHeader } from "../components/PageHeader";
import { CurveSpreadCard, InflationCompensationCard } from "../components/rates/DerivedMetricCard";
import { RateChangeRow } from "../components/rates/RateChangeList";
import { RateLevelCard } from "../components/rates/RateLevelCard";
import { YieldCurveChart } from "../components/rates/YieldCurveChart";
import {
  CURVE_SPREAD,
  DATA_FRESHNESS,
  INFLATION_COMPENSATION,
  NOMINAL_YIELD,
  REAL_YIELD,
  SESSION_WINDOW,
} from "../content/explanations/rates";
import { formatChangeWindow, formatObservationDate, maturityLabel } from "../lib/ratesFormat";

const MONITOR_ERROR_MESSAGE = "Rates intelligence could not be loaded.";

/**
 * Rates Intelligence (Increment #30) -- the presentation surface for
 * the deterministic `rates_v1.0` backend built in #29.
 *
 * Every number on this page is rendered exactly as the backend computed
 * it. This module (and every component it uses) performs no financial
 * arithmetic whatsoever: no spread, no basis-point conversion, no
 * compensation, no percentile. That boundary is enforced automatically
 * by src/test/no-rates-calculation.test.ts, not merely by convention.
 *
 * Page order answers the reader's questions in the order they ask them:
 * where are yields now, what shape is the curve, what are real yields
 * doing, what is the market pricing for inflation, what moved recently,
 * and how was all of it produced.
 */

/** The single window whose cross-metric comparison the "What changed" table shows. */
const WHAT_CHANGED_WINDOW = "5_SESSIONS";

function changeForWindow(changes: RateChange[]): RateChange | undefined {
  return changes.find((change) => change.window === WHAT_CHANGED_WINDOW);
}

function RatesContent({ result }: { result: RatesMonitorResult }) {
  const hasAnyData = result.as_of_date !== null;

  if (!hasAnyData) {
    return (
      <div className="mt-8 rounded-lg border border-line bg-surface p-6">
        <h2 className="type-card-heading text-fg">No rates data yet</h2>
        <p className="mt-2 max-w-prose text-sm text-fg-secondary">
          No Treasury observations have been ingested into this environment yet, so no yields, curve, spreads, or
          inflation compensation can be shown. Nothing here is estimated in the meantime.
        </p>
        <p className="mt-2 max-w-prose type-meta text-fg-muted">
          Methodology {result.methodology_id} · {result.attribution}
        </p>
      </div>
    );
  }

  return (
    <div className="mt-8 divide-y divide-line [&>*]:py-8 [&>*:first-child]:pt-0 [&>*:last-child]:pb-0">
      {/* 1. Nominal Treasury yields */}
      <section aria-labelledby="rates-nominal-heading">
        <div className="flex items-center gap-1.5">
          <h2 id="rates-nominal-heading" className="text-sm font-medium text-fg-muted">
            Treasury yields
          </h2>
          <ExplanationTrigger explanation={NOMINAL_YIELD} />
        </div>
        <ul className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {result.nominal_curve.map((level) => (
            <RateLevelCard key={level.series_id} level={level} explanation={NOMINAL_YIELD} showContext={false} />
          ))}
        </ul>
      </section>

      {/* 2. The curve, with its derived spreads beside it */}
      <section aria-labelledby="rates-curve-heading">
        <h2 id="rates-curve-heading" className="text-sm font-medium text-fg-muted">
          Treasury curve
        </h2>
        <div className="mt-3 grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div className="h-fit rounded-lg border border-line bg-surface p-5 sm:p-6">
            <YieldCurveChart levels={result.nominal_curve} asOfDate={result.as_of_date} />
          </div>
          <ul className="grid content-start gap-4">
            {result.curve_spreads.map((spread) => (
              <CurveSpreadCard key={spread.spread_id} spread={spread} explanation={CURVE_SPREAD} />
            ))}
          </ul>
        </div>
      </section>

      {/* 3. Real yields */}
      <section aria-labelledby="rates-real-heading">
        <div className="flex items-center gap-1.5">
          <h2 id="rates-real-heading" className="text-sm font-medium text-fg-muted">
            Real yields
          </h2>
          <ExplanationTrigger explanation={REAL_YIELD} />
        </div>
        <p className="mt-2 max-w-prose text-sm text-fg-secondary">
          Treasury Inflation-Protected Securities yields, published for 5-year and longer maturities.
        </p>
        <ul className="mt-3 grid gap-4 sm:grid-cols-2">
          {result.real_curve.map((level) => (
            <RateLevelCard key={level.series_id} level={level} explanation={REAL_YIELD} showContext={false} />
          ))}
        </ul>
      </section>

      {/* 4. Market-implied inflation compensation */}
      <section aria-labelledby="rates-compensation-heading">
        <div className="flex items-center gap-1.5">
          <h2 id="rates-compensation-heading" className="text-sm font-medium text-fg-muted">
            Market-implied inflation compensation
          </h2>
          <ExplanationTrigger explanation={INFLATION_COMPENSATION} />
        </div>
        <p className="mt-2 max-w-prose text-sm text-fg-secondary">
          The difference between nominal and real Treasury yields at the same maturity. It can reflect inflation
          expectations as well as liquidity and risk premia, so {result.methodology_id} does not call it an inflation
          forecast.
        </p>
        <ul className="mt-3 grid gap-4 sm:grid-cols-2">
          {result.inflation_compensation.map((compensation) => (
            <InflationCompensationCard
              key={compensation.maturity}
              compensation={compensation}
              explanation={INFLATION_COMPENSATION}
            />
          ))}
        </ul>
      </section>

      {/* 5. What changed, one window, every metric side by side */}
      <section aria-labelledby="rates-changed-heading">
        <div className="flex items-center gap-1.5">
          <h2 id="rates-changed-heading" className="text-sm font-medium text-fg-muted">
            What changed
          </h2>
          <ExplanationTrigger explanation={SESSION_WINDOW} />
        </div>
        <p className="mt-2 max-w-prose text-sm text-fg-secondary">
          Every metric over the last {formatChangeWindow(WHAT_CHANGED_WINDOW)} of published Treasury data. Each card
          above carries its own 1, 5, 21 and 63-session changes.
        </p>
        <div className="mt-3 max-w-3xl overflow-x-auto">
          <table className="w-full">
            <caption className="sr-only">
              Change over {formatChangeWindow(WHAT_CHANGED_WINDOW)} for each rates metric
            </caption>
            <thead>
              <tr className="text-left type-label text-fg-muted">
                <th scope="col" className="pb-1 font-semibold">
                  Metric
                </th>
                <th scope="col" className="pb-1 text-right font-semibold">
                  Change
                </th>
                <th scope="col" className="pb-1 text-right font-semibold">
                  From → to
                </th>
              </tr>
            </thead>
            <tbody>
              {result.nominal_curve.map((level) => {
                const change = changeForWindow(level.changes);
                return change ? (
                  <RateChangeRow key={level.series_id} name={`${maturityLabel(level.series_id)} nominal`} change={change} unit="%" />
                ) : null;
              })}
              {result.real_curve.map((level) => {
                const change = changeForWindow(level.changes);
                return change ? (
                  <RateChangeRow key={level.series_id} name={`${maturityLabel(level.series_id)} real`} change={change} unit="%" />
                ) : null;
              })}
              {result.curve_spreads.map((spread) => {
                const change = changeForWindow(spread.changes);
                return change ? <RateChangeRow key={spread.spread_id} name={spread.spread_id} change={change} unit="%" /> : null;
              })}
              {result.inflation_compensation.map((compensation) => {
                const change = changeForWindow(compensation.changes);
                return change ? (
                  <RateChangeRow
                    key={compensation.maturity}
                    name={`${compensation.maturity} compensation`}
                    change={change}
                    unit="%"
                  />
                ) : null;
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* 6. Methodology */}
      <section aria-labelledby="rates-methodology-heading">
        <h2 id="rates-methodology-heading" className="text-sm font-medium text-fg-muted">
          Evidence &amp; methodology
        </h2>
        <div className="mt-3 max-w-3xl">
          <Disclosure summary={`Methodology ${result.methodology_id}`}>
            <div className="space-y-3 text-sm text-fg-secondary">
              <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
                <dt className="text-fg-muted">Methodology</dt>
                <dd>{result.methodology_id}</dd>
                <dt className="text-fg-muted">Data basis</dt>
                <dd>{result.data_basis}</dd>
                <dt className="text-fg-muted">Provider</dt>
                <dd>{result.provider}</dd>
                <dt className="text-fg-muted">Latest observation</dt>
                <dd>{formatObservationDate(result.as_of_date)}</dd>
              </dl>
              <p>
                <span className="font-medium text-fg">Sources.</span> Nominal par yields and real (TIPS) par yields are
                published by the U.S. Department of the Treasury, derived from indicative quotations collected at
                approximately 3:30 PM ET each business day. One provider, one dataset per metric.
              </p>
              <p>
                <span className="font-medium text-fg">Session windows.</span> Changes count published business sessions,
                never calendar days, so no weekend or holiday fallback rule can alter a reported number. 21 sessions is
                approximately, not exactly, one month, which is why windows are never labelled in months.
              </p>
              <p>
                <span className="font-medium text-fg">Curve spreads.</span> 2s10s is the 10-year nominal yield minus the
                2-year; 2s30s is the 30-year minus the 2-year. Both legs must come from the same observation date.
              </p>
              <p>
                <span className="font-medium text-fg">Inflation compensation.</span> The nominal par yield minus the real
                par yield at the same maturity, on the same observation date. It contains an inflation risk premium and a
                TIPS liquidity premium, which {result.methodology_id} does not separate.
              </p>
              <p>
                <span className="font-medium text-fg">Alignment.</span> A derived value is calculated only where both
                inputs have an observation on the same date. A missing counterpart is never interpolated or carried
                forward — the value is reported as unavailable, with the reason.
              </p>
              <p>
                <span className="font-medium text-fg">Limitations.</span> These are daily, end-of-session facts, not
                intraday prices. Values reflect the latest published data including later corrections, so this is not a
                point-in-time record. {result.methodology_id} defines no state label, no forecast, and no cross-domain
                conclusion.
              </p>
              <p className="type-meta text-fg-muted">{result.attribution}</p>
            </div>
          </Disclosure>
        </div>
      </section>
    </div>
  );
}

export function RatesPage() {
  const monitor = useApiResource(getRatesMonitor);
  const analyst = useApiResource(getAnalystAvailability);

  return (
    <div>
      <PageHeader
        title="Rates Intelligence"
        description="Track U.S. Treasury yields, curve structure, real yields, and market-implied inflation compensation."
      >
        {monitor.status === "success" && monitor.data.as_of_date !== null && (
          <p className="flex items-center gap-1.5 type-meta text-fg-muted">
            <span>Latest available: {formatObservationDate(monitor.data.as_of_date)}</span>
            <ExplanationTrigger explanation={DATA_FRESHNESS} />
          </p>
        )}
      </PageHeader>

      {monitor.status === "loading" && (
        <div className="mt-8">
          <LoadingSkeleton label="Loading rates intelligence" heightClassName="h-64" />
        </div>
      )}
      {monitor.status === "error" && (
        <div className="mt-8">
          <ErrorMessage message={MONITOR_ERROR_MESSAGE} onRetry={monitor.reload} />
        </div>
      )}
      {monitor.status === "success" && <RatesContent result={monitor.data} />}

      {/* Ask MacroChipz (Increment #33) -- optional interpretive layer.
          It sits outside RatesContent so an Analyst outage, or the
          Analyst simply being unconfigured, can never affect whether the
          canonical rates content renders. */}
      <div className="mt-8 border-t border-line pt-8">
        <AskMacroChipz
          contextType="RATES"
          contextRef={{ type: "RATES" }}
          available={analyst.status === "success" && analyst.data.available}
          headingId="rates-analyst-heading"
        />
      </div>
    </div>
  );
}
