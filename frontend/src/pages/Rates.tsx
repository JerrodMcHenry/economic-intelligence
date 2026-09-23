import { useState } from "react";

import { getRatesMonitor } from "../api/rates";
import type { RateLevel, RatesMonitorResult } from "../api/rates.types";
import { getAnalystAvailability } from "../api/analyst";
import { useApiResource } from "../api/useApiResource";
import { Disclosure } from "../components/Disclosure";
import { AskMacroChipz } from "../components/analyst/AskMacroChipz";
import { ErrorMessage } from "../components/ErrorMessage";
import { ExplanationTrigger } from "../components/explanations/ExplanationTrigger";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { UnderstandWorld } from "../components/explainers/UnderstandLinks";
import { RevisionsLink } from "../components/revisions/RevisionsLink";
import { Link } from "react-router-dom";
import { CurveSpreadCard, InflationCompensationCard } from "../components/rates/DerivedMetricCard";
import { RateLevelCard } from "../components/rates/RateLevelCard";
import { SelectedMaturityPanel } from "../components/rates/SelectedMaturityPanel";
import { StoryTeaser } from "../components/homepage/StoryTeaser";
import { YieldCurveChart } from "../components/rates/YieldCurveChart";
import {
  CURVE_SPREAD,
  DATA_FRESHNESS,
  INFLATION_COMPENSATION,
  NOMINAL_YIELD,
  REAL_YIELD,
} from "../content/explanations/rates";
import { formatObservationDate } from "../lib/ratesFormat";

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

function RatesContent({ result }: { result: RatesMonitorResult }) {
  const hasAnyData = result.as_of_date !== null;

  /*
   * DEFAULT 10Y. The product's own explainer singles it out — "Why does
   * everyone watch the 10-year Treasury?" — and the homepage lede
   * promotes it. If the 10-year is not ingested, the first maturity
   * that IS becomes the default rather than the panel opening empty.
   *
   * ABOVE THE EMPTY-STATE RETURN, and not for style: a hook after a
   * conditional return changes the hook order between a rendered page
   * and an un-ingested one, which is the bug `rules-of-hooks` exists to
   * catch. In an environment with no observations this simply holds
   * `undefined` and nothing below it renders.
   */
  const selectable = result.nominal_curve.filter((level) => level.available && level.latest_value !== null);
  const preferred = selectable.find((level) => level.series_id === "UST_NOMINAL_10Y") ?? selectable[0];
  const [selectedId, setSelectedId] = useState<string | undefined>(preferred?.series_id);
  const selected: RateLevel | undefined =
    result.nominal_curve.find((level) => level.series_id === selectedId) ?? preferred;

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
    <div className="mt-6 space-y-8 sm:mt-8">
      {/* 1. The curve, as one selectable instrument */}
      <section aria-labelledby="rates-curve-heading">
        <div className="flex items-center gap-1.5">
          <h2 id="rates-curve-heading" className="text-sm font-medium text-fg-muted">
            Treasury curve
          </h2>
          <ExplanationTrigger explanation={NOMINAL_YIELD} />
        </div>
        <div className="lx-card mt-3 rounded-xl p-4 sm:p-6">
          <YieldCurveChart
            levels={result.nominal_curve}
            asOfDate={result.as_of_date}
            selectedId={selected?.series_id}
            onSelect={setSelectedId}
          />
        </div>
      </section>

      {/* 2. The maturity the reader selected */}
      {selected && (
        <section aria-labelledby="rates-selected-heading">
          <h2 id="rates-selected-heading" className="text-sm font-medium text-fg-muted">
            The maturity you selected
          </h2>
          <div className="mt-3">
            <SelectedMaturityPanel level={selected} explanation={NOMINAL_YIELD} />
          </div>
        </section>
      )}

      {/* 3. The story, immediately after the panel and before the
             calculated measures. #49A measured zero links from this
             page to the story that explains where these yields end up. */}
      <StoryTeaser alwaysVisible />

      {/* 4. Real yields — PUBLISHED observations, not calculated, so
             they keep their own section rather than joining §5. */}
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

      {/* 5. Everything MacroChipz calculated from the curve */}
      <section aria-labelledby="rates-derived-heading">
        <div className="flex items-center gap-1.5">
          <h2 id="rates-derived-heading" className="text-sm font-medium text-fg-muted">
            Calculated from the curve
          </h2>
          <ExplanationTrigger explanation={CURVE_SPREAD} />
        </div>
        <p className="mt-2 max-w-prose text-sm text-fg-secondary">
          Differences MacroChipz computes between published yields. Inflation compensation can reflect inflation
          expectations as well as liquidity and risk premia, so {result.methodology_id} does not call it an inflation
          forecast.
        </p>
        <ul className="mt-3 grid gap-4 sm:grid-cols-2">
          {result.curve_spreads.map((spread) => (
            <CurveSpreadCard key={spread.spread_id} spread={spread} explanation={CURVE_SPREAD} />
          ))}
          {result.inflation_compensation.map((compensation) => (
            <InflationCompensationCard
              key={compensation.maturity}
              compensation={compensation}
              explanation={INFLATION_COMPENSATION}
            />
          ))}
        </ul>
      </section>

      {/* 6. Where these rates show up elsewhere (#45B).
             NAVIGATION ONLY. #45A found cross-world linking was
             one-directional -- `/housing` pointed here and nothing
             pointed back. No causal claim is made or implied: the
             frozen cross-domain prohibition in
             relate-compare-audit-v1.md sections 15/16 is untouched,
             and this section asserts nothing about how the two move. */}
      <section aria-labelledby="rates-elsewhere-heading">
        <h2 id="rates-elsewhere-heading" className="text-sm font-medium text-fg-muted">
          Where these numbers come up
        </h2>
        <p className="mt-2 max-w-prose text-sm text-fg-secondary">
          Long-term borrowing costs are part of the backdrop to home building, and the difference between nominal and
          real yields is MacroChipz&rsquo;s market-implied inflation compensation above. MacroChipz publishes no
          relationship between them — these are links, not conclusions.
        </p>
        <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
          <li>
            <Link
              to="/housing"
              className="inline-flex min-h-11 items-center text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
            >
              Explore Housing →
            </Link>
          </li>
          <li>
            <Link
              to="/inflation"
              className="inline-flex min-h-11 items-center text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
            >
              Explore Inflation →
            </Link>
          </li>
        </ul>
      </section>

      {/* 7. Methodology */}
      <section aria-labelledby="rates-methodology-heading">
        <h2 id="rates-methodology-heading" className="text-sm font-medium text-fg-muted">
          Evidence &amp; methodology
        </h2>
        <div className="mt-3 max-w-3xl">
          <Disclosure summary="Where these numbers come from" summaryClassName="min-h-11">
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
      {/*
       * THE HERO (#49B), replacing `PageHeader`.
       *
       * ================================================================
       * THE COPY IS PRECISE ON PURPOSE, AND IT IS NOT NEW
       * ================================================================
       *
       * A Treasury yield is the return an investor earns on a security
       * trading in the market. It is NOT the government's exact cost of
       * any new borrowing — that depends on what is issued, at what
       * coupon, at which auction. The page used to say "Track U.S.
       * Treasury yields, curve structure, real yields, and
       * market-implied inflation compensation", which named four
       * constructs and defined none of them.
       *
       * Both sentences below are VERBATIM from the #44 explainer
       * registry (`explain.what-is-a-treasury-yield`), so the precision
       * is reviewed rather than invented here.
       *
       * KNOWN INCONSISTENCY, NOT FIXED HERE: that same explainer's own
       * `answer`, and the homepage's world discovery line, both use the
       * looser "what it costs the government to borrow" framing. Those
       * are reviewed copy owned by the registry and the homepage, and
       * rewriting them from this page would be the wrong place to do
       * it. Flagged in the #49B notes for a copy review.
       */}
      <header>
        <p className="type-label text-fg-muted">Rates</p>
        <h1 className="type-page-title mt-2 max-w-3xl text-balance">
          What investors earn on U.S. government debt.
        </h1>
        <p className="mt-3 max-w-prose text-fg-secondary">
          The yield is the annual return an investor earns by holding one. Investors buy and sell Treasuries
          continuously, and the yield moves with what they are willing to accept.
        </p>

        {/*
         * HUMAN-READABLE SOURCE AND DATE.
         *
         * "TREASURY · rates_v1.0 · latest_published_data" was three
         * machine identifiers in the most prominent metadata slot on
         * the page. All three are still published, verbatim, in the
         * methodology disclosure at the foot — which is where an
         * identifier belongs and where the audit's "retain" column put
         * them.
         */}
        {monitor.status === "success" && monitor.data.as_of_date !== null && (
          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-fg-muted">
            <span className="inline-flex items-center gap-2 rounded-full border border-line px-3 py-1">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-brand" />
              Latest published: {formatObservationDate(monitor.data.as_of_date)}
            </span>
            <span className="inline-flex items-center gap-1.5">
              Published by the U.S. Department of the Treasury
              <ExplanationTrigger explanation={DATA_FRESHNESS} />
            </span>
          </div>
        )}
      </header>

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
      <div className="mt-10 border-t border-line pt-8">
        <RevisionsLink context="Treasury" />
      </div>
      <div className="mt-10 border-t border-line pt-8">
        <UnderstandWorld world="RATES" />
      </div>
    </div>
  );
}
