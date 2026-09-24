import { useState } from "react";

import type { InflationMetricEvidence, SeriesMomentumResult } from "../../api/inflation.types";
import type { SeriesObservationsResponse } from "../../api/series.types";
import { percentOf } from "../../lib/cssUnits";
import { formatPercent, formatPeriod } from "../../lib/format";

/**
 * THE CLIMB (Increment #50B).
 *
 * ================================================================
 * WHY A PAGE ABOUT INFLATION NEEDS A PICTURE OF PRICES
 * ================================================================
 *
 * #50A measured `/inflation` rendering 41 percentage values, zero
 * charts, and the price level nowhere — while the monitor's own
 * `evidence_12m` carried it (126.43 -> 130.658) and an existing
 * endpoint served 59 monthly observations of it.
 *
 * So the page showed the RATE OF CHANGE and never the thing that was
 * changing. That is the exact mechanism by which "inflation is
 * falling" is heard as "prices are falling".
 *
 * This component draws the index itself as an AREA, because the
 * subject is accumulation: the mass under the line only ever grows.
 * Selecting a window brackets that span and reports, together:
 *
 *   - the rate `inflation_v1.0` computed for it, and
 *   - the two index values at its endpoints, from that window's own
 *     evidence.
 *
 * Selecting "1 month" lights a sliver at the end of a five-year ascent
 * and reports a smaller rate than "12 months" does. A reader sees a
 * SMALLER RATE ON A LINE THAT IS STILL GOING UP, which is the
 * misconception dismantled by geometry rather than by assertion.
 *
 * ================================================================
 * WHAT IT REFUSES TO DO
 * ================================================================
 *
 * - **No rate line.** The API publishes rates for one period. Deriving
 *   a rate history from these levels would be client-side economics,
 *   and `src/test/no-inflation-derivation.test.ts` forbids it. The
 *   dependency is documented, not simulated.
 * - **No second index overlaid.** CPI runs 273->334 and PCE 109->130;
 *   one axis would require rebasing, which changes displayed values.
 * - **No target band on a level chart.** The 2% objective is a rate
 *   objective. Painting it here would assert a price path nobody
 *   published.
 * - **No arithmetic.** Every rate is the backend's own; every level is
 *   the provider's own. This file maps numbers onto coordinates.
 *
 * ================================================================
 * VISUALS ARE SVG. INTERACTION AND TYPE ARE HTML.
 * ================================================================
 *
 * The area and the line are SVG on a `preserveAspectRatio="none"`
 * board, so the plot reaches the real box at any width. Everything a
 * reader reads or presses is HTML positioned over it — an 11px label
 * stays 11px, a 44px target stays 44px, and an endpoint marker stays
 * ROUND, which an SVG circle on a stretched board does not (#48B).
 */

/** The board's own coordinate space. Percentages, not pixels. */
const PAD = { top: 14, right: 5, bottom: 18, left: 13 };

interface Window {
  readonly key: string;
  readonly label: string;
  readonly rate: number | null;
  readonly evidence: InflationMetricEvidence | null;
  /** 1, 3 and 6 month rates are annualised; the 12-month one is not. */
  readonly annualised: boolean;
}

function windowsFor(momentum: SeriesMomentumResult): Window[] {
  return [
    { key: "1m", label: "1 month", rate: momentum.r_1m_annualized, evidence: momentum.evidence_1m, annualised: true },
    { key: "3m", label: "3 months", rate: momentum.r_3m_annualized, evidence: momentum.evidence_3m, annualised: true },
    { key: "6m", label: "6 months", rate: momentum.r_6m_annualized, evidence: momentum.evidence_6m, annualised: true },
    { key: "12m", label: "12 months", rate: momentum.r_12m, evidence: momentum.evidence_12m, annualised: false },
  ];
}

export function PriceClimb({
  momentum,
  series,
}: {
  momentum: SeriesMomentumResult;
  series: SeriesObservationsResponse;
}) {
  const windows = windowsFor(momentum);
  const available = windows.filter((w) => w.evidence !== null && w.rate !== null);
  /* Default 12 months, falling back to whichever window IS computed so
     the reading never opens empty. */
  const fallback = available.find((w) => w.key === "12m") ?? available[0];
  const [selectedKey, setSelectedKey] = useState<string | undefined>(fallback?.key);
  const selected = windows.find((w) => w.key === selectedKey) ?? fallback;

  const observations = series.observations;
  if (observations.length < 2) {
    return (
      <p className="text-sm text-fg-muted">
        The price level cannot be drawn until at least two observations have been ingested for {series.series_id}.
      </p>
    );
  }

  const values = observations.map((o) => o.value);
  const lowest = Math.min(...values);
  const highest = Math.max(...values);
  const headroom = (highest - lowest) * 0.12;
  const min = lowest - headroom;
  const max = highest + headroom;

  const xUnits = (index: number) => PAD.left + (index / (observations.length - 1)) * (100 - PAD.left - PAD.right);
  const yUnits = (value: number) => PAD.top + (100 - PAD.top - PAD.bottom) * (1 - (value - min) / (max - min));
  const x = (index: number) => percentOf(xUnits(index) / 100);
  const y = (value: number) => percentOf(yUnits(value) / 100);

  const linePath = observations.map((o, i) => `${i ? "L" : "M"} ${xUnits(i)} ${yUnits(o.value)}`).join(" ");
  const areaPath = `${linePath} L ${xUnits(observations.length - 1)} ${100 - PAD.bottom} L ${xUnits(0)} ${100 - PAD.bottom} Z`;

  const dateIndex = (iso: string | null) => (iso === null ? -1 : observations.findIndex((o) => o.date === iso));
  const from = selected?.evidence ? dateIndex(selected.evidence.endpoint_date_past) : -1;
  const to = selected?.evidence ? dateIndex(selected.evidence.endpoint_date_current) : -1;
  const hasSpan = from >= 0 && to >= 0 && to > from;

  const gridValues = [min, (min + max) / 2, max];
  const first = observations[0]!;
  const last = observations[observations.length - 1]!;

  const description = [
    `${series.title}, ${series.units}, ${observations.length} monthly observations from ${formatPeriod(first.date)} to ${formatPeriod(last.date)}.`,
    `The index rises from ${first.value} to ${last.value} over this period.`,
    selected?.evidence
      ? `The highlighted span is the ${selected.label} window: ${selected.evidence.endpoint_value_past} on ${formatPeriod(selected.evidence.endpoint_date_past)} to ${selected.evidence.endpoint_value_current} on ${formatPeriod(selected.evidence.endpoint_date_current)}.`
      : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div>
      <div className="lx-card rounded-xl p-4 sm:p-6">
        <div className="relative h-[250px] w-full sm:h-[320px]">
          <svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            role="img"
            aria-label={description}
            className="absolute inset-0 h-full w-full"
          >
            <defs>
              <linearGradient id="inflation-climb-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(124,96,240,0.42)" />
                <stop offset="100%" stopColor="rgba(124,96,240,0.02)" />
              </linearGradient>
            </defs>

            {gridValues.map((value) => (
              <line
                key={value}
                x1={PAD.left}
                x2={100 - PAD.right}
                y1={yUnits(value)}
                y2={yUnits(value)}
                stroke="rgba(255,255,255,0.08)"
                strokeWidth={0.4}
                vectorEffect="non-scaling-stroke"
              />
            ))}

            <path d={areaPath} fill="url(#inflation-climb-fill)" />
            <path
              d={linePath}
              fill="none"
              stroke="rgba(159,172,241,0.30)"
              strokeWidth={1.6}
              strokeLinejoin="round"
              vectorEffect="non-scaling-stroke"
            />

            {hasSpan && (
              <>
                <path
                  d={observations
                    .slice(from, to + 1)
                    .map((o, i) => `${i ? "L" : "M"} ${xUnits(from + i)} ${yUnits(o.value)}`)
                    .join(" ")}
                  fill="none"
                  stroke="#b9a6ff"
                  strokeWidth={3.2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  vectorEffect="non-scaling-stroke"
                />
                {/* The RISE, as a bracket. This is the height the rate
                    describes, and it is what a rate alone never shows. */}
                <line
                  x1={xUnits(to)}
                  x2={xUnits(to)}
                  y1={yUnits(observations[from]!.value)}
                  y2={yUnits(observations[to]!.value)}
                  stroke="#b9a6ff"
                  strokeWidth={1}
                  strokeDasharray="2 2"
                  vectorEffect="non-scaling-stroke"
                />
                <line
                  x1={xUnits(from)}
                  x2={xUnits(to)}
                  y1={yUnits(observations[from]!.value)}
                  y2={yUnits(observations[from]!.value)}
                  stroke="#b9a6ff"
                  strokeWidth={1}
                  strokeDasharray="2 2"
                  vectorEffect="non-scaling-stroke"
                />
              </>
            )}
          </svg>

          {/* Every label and marker is HTML. */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-0">
            {gridValues.map((value) => (
              <span
                key={value}
                className="absolute left-0 -translate-y-1/2 type-numeric text-[11px] text-fg-muted"
                style={{ top: y(value) }}
              >
                {value.toFixed(0)}
              </span>
            ))}

            {hasSpan &&
              [from, to].map((index) => (
                <span
                  key={index}
                  /* Round because its own box is square. An SVG circle
                     on this board would be an ellipse (#48B). */
                  className="absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-fg"
                  style={{ left: x(index), top: y(observations[index]!.value) }}
                />
              ))}

            {hasSpan && (
              <span
                className="absolute -translate-x-1/2 -translate-y-full rounded-md border border-[color:var(--lx-card-hi)] bg-[rgba(10,8,20,0.72)] px-1.5 py-0.5 type-numeric text-[12px] font-bold text-fg"
                style={{ left: x(to), top: `calc(${y(observations[to]!.value)} - 10px)` }}
              >
                {observations[to]!.value}
              </span>
            )}

            {/*
             * ANCHORED TO THE EDGES, NOT CENTRED ON A PERCENTAGE.
             * Centring on 6% worked in the prototype, which used short
             * month names. `formatPeriod` renders "September 2021",
             * and centred on 6% that starts 8px OUTSIDE the card.
             * Measured at 390px before this was changed.
             */}
            <span className="absolute bottom-0 left-0 text-[11px] text-fg-muted">{formatPeriod(first.date)}</span>
            <span className="absolute bottom-0 right-0 text-[11px] text-fg-muted">{formatPeriod(last.date)}</span>
          </div>
        </div>

        {/*
         * 2x2 ON A PHONE (#50B). Four controls in one row at 390px give
         * each about 78px, which fits the label and not the rate beside
         * it. Two rows of two keeps both legible and keeps every target
         * at 44px.
         */}
        <div role="group" aria-label="Choose a window" className="mt-4 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
          {windows.map((w) => {
            const usable = w.evidence !== null && w.rate !== null;
            const isSelected = usable && w.key === selected?.key;
            return (
              <button
                key={w.key}
                type="button"
                aria-pressed={isSelected}
                disabled={!usable}
                onClick={() => setSelectedKey(w.key)}
                className={[
                  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-semibold transition-colors motion-reduce:transition-none",
                  isSelected
                    ? "border-[color:var(--lx-card-hi)] bg-[color:var(--mc-selected)] text-fg"
                    : "border-line text-fg-secondary hover:text-fg",
                  usable ? "" : "cursor-not-allowed opacity-50",
                ].join(" ")}
              >
                <span>{w.label}</span>
                <span className="type-numeric font-normal opacity-80">
                  {usable ? formatPercent(w.rate) : "n/a"}
                </span>
              </button>
            );
          })}
        </div>

        {/*
         * ONE reading, not three (#50B). The prototype explained the
         * movement twice under the chart; this states the rate, the two
         * real endpoints, and the single sentence that ties them.
         */}
        <div aria-live="polite" className="mt-5 border-t border-line pt-5">
          {selected?.evidence && selected.rate !== null ? (
            <>
              <p className="type-numeric text-4xl font-semibold tracking-tight text-fg sm:text-5xl">
                {formatPercent(selected.rate)}
              </p>
              <p className="mt-2 text-sm text-fg-muted">
                {selected.label}
                {selected.annualised ? ", annualised — the recent pace expressed as a yearly rate" : " — the change over twelve months"}
              </p>
              <p className="mt-3 max-w-prose text-sm text-fg-secondary">
                The index went{" "}
                <span className="type-numeric font-semibold text-fg">{selected.evidence.endpoint_value_past}</span> in{" "}
                {formatPeriod(selected.evidence.endpoint_date_past)} to{" "}
                <span className="type-numeric font-semibold text-fg">{selected.evidence.endpoint_value_current}</span>{" "}
                in {formatPeriod(selected.evidence.endpoint_date_current)}. That rise is what the rate describes.
              </p>
            </>
          ) : (
            <p className="max-w-prose text-sm text-fg-muted">
              This window has not been computed for the latest period, so no rate is shown for it. Nothing is estimated
              in its place.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
