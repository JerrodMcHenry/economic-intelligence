import { useState } from "react";

import type { LaborMonitorResult } from "../../api/labor.types";
import type { SeriesObservationsResponse } from "../../api/series.types";
import { percentOf } from "../../lib/cssUnits";
import { formatPeriod } from "../../lib/format";

/**
 * TWO SURVEYS, AND THE THRESHOLD THAT CLASSIFIED EACH (Increment #51B).
 *
 * ================================================================
 * WHY A THRESHOLD AND NOT A LINE CHART
 * ================================================================
 *
 * #51A asked the API what the Jobs world actually has before designing
 * anything. Two series answer — `PAYEMS` and `UNRATE`, 60 monthly
 * observations each. Five do not: participation, the employment ratio,
 * U-6, job openings and initial claims all 404. So this page cannot be
 * about how hard it is to find a job, and does not pretend to be.
 *
 * What Jobs has that no other world has is an EXPLICIT NUMERIC
 * DEADBAND on every classification — `momentum_deadband_jobs` and
 * `unemployment_deadband_pp` are both in the response and neither was
 * ever rendered. A reader could see that payroll employment is
 * "Cooling" and unemployment "Stable" and had no way to learn why one
 * number counted as a move and the other did not.
 *
 * So the hero is that deadband, drawn: an axis centred on no change,
 * the band shaded, the measure's own change plotted as a point.
 * Payroll employment sits outside its band; unemployment sits inside
 * its own. Same diagram, two verdicts, one labour market — which is
 * exactly what the formal `MIXED` classification means.
 *
 * ================================================================
 * WHAT IT REFUSES TO DO
 * ================================================================
 *
 * - **No arithmetic.** Every average, delta, deadband and state is the
 *   backend's own. `labor_v1.0` stays authoritative.
 * - **No combined score.** The two measures are never averaged.
 * - **No good/bad colouring.** The two surveys are distinguished by
 *   hue inside the shared family; economic-state tones stay out, per
 *   #27B.
 * - **No claim about job-search difficulty.** This world has no data
 *   that speaks to it.
 * - **No value where the provider published none.** See `segments()`.
 */

/** Which measure the reader is looking at. */
type SurveyKey = "employment" | "unemployment";

interface Survey {
  readonly key: SurveyKey;
  readonly who: string;
  readonly what: string;
  readonly seriesId: string;
  readonly current: number | null;
  readonly prior: number | null;
  readonly delta: number | null;
  readonly band: number;
  readonly state: string;
  readonly currentLabel: string;
  readonly priorLabel: string;
  /** Consumer-readable, with the exact survey-specific threshold. */
  readonly bandLabel: string;
  readonly extra: ReadonlyArray<readonly [string, string]>;
  readonly format: (value: number | null) => string;
  readonly formatDelta: (value: number | null) => string;
  readonly accent: string;
}

function jobs(value: number | null): string {
  return value === null ? "unavailable" : `${Math.round(value).toLocaleString("en-US")}`;
}
function signedJobs(value: number | null): string {
  if (value === null) return "unavailable";
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(Math.round(value)).toLocaleString("en-US")}`;
}
function percent(value: number | null): string {
  return value === null ? "unavailable" : `${value.toFixed(2)}%`;
}
function signedPp(value: number | null): string {
  if (value === null) return "unavailable";
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(2)} pp`;
}
function sentenceCase(value: string): string {
  return value.charAt(0) + value.slice(1).toLowerCase().replace(/_/g, " ");
}

function surveysFor(result: LaborMonitorResult): Survey[] {
  const e = result.employment;
  const u = result.unemployment;
  return [
    {
      key: "employment",
      who: "Employer survey",
      what: "Payroll employment",
      seriesId: e.series_id,
      current: e.current_3m_avg_jobs,
      prior: e.prior_3m_avg_jobs,
      delta: e.momentum_delta_jobs,
      band: e.momentum_deadband_jobs,
      state: e.state,
      currentLabel: "The last 3 months",
      priorLabel: "The 3 months before that",
      bandLabel: `anything within 50,000 jobs a month either way counts as no real change`,
      extra: [
        ["Hiring condition", e.condition],
        ["Momentum", e.momentum],
      ],
      format: jobs,
      formatDelta: signedJobs,
      accent: "#b9a6ff",
    },
    {
      key: "unemployment",
      who: "Household survey",
      what: "Unemployment rate",
      seriesId: u.series_id,
      current: u.current_3m_avg,
      prior: u.prior_year_3m_avg,
      delta: u.delta_pp,
      band: u.unemployment_deadband_pp,
      state: u.state,
      currentLabel: "The last 3 months",
      priorLabel: "The same 3 months a year earlier",
      bandLabel: `anything within 0.2 percentage points either way counts as no real change`,
      extra: [],
      format: percent,
      formatDelta: signedPp,
      accent: "#8fc3e8",
    },
  ];
}

/**
 * The published line, broken wherever the provider published nothing.
 *
 * A NULL IS A GAP, NOT A ZERO. `UNRATE` carries one (2025-10-01), and
 * feeding the raw values to `Math.min` coerces that `null` to `0` —
 * which both destroys the axis floor and draws the line down to a
 * value nobody published. The domain below is computed from real
 * values only, and the path is emitted as one segment per run.
 */
function segments(
  observations: SeriesObservationsResponse["observations"],
  min: number,
  max: number,
): string[] {
  const paths: string[] = [];
  let run: string[] = [];
  observations.forEach((observation, index) => {
    if (observation.value === null) {
      if (run.length > 1) paths.push(run.join(" "));
      run = [];
      return;
    }
    const x = 2 + (index / (observations.length - 1)) * 96;
    const y = 8 + 84 * (1 - (observation.value - min) / (max - min));
    run.push(`${run.length === 0 ? "M" : "L"} ${x} ${y}`);
  });
  if (run.length > 1) paths.push(run.join(" "));
  return paths;
}

export function SurveyThreshold({
  result,
  payroll,
  unemployment,
}: {
  result: LaborMonitorResult;
  /** `null` when the observations request failed or is still in flight. */
  payroll: SeriesObservationsResponse | null;
  unemployment: SeriesObservationsResponse | null;
}) {
  const surveys = surveysFor(result);
  const [selectedKey, setSelectedKey] = useState<SurveyKey>("employment");
  const selected = surveys.find((s) => s.key === selectedKey) ?? surveys[0]!;
  const series = selected.key === "employment" ? payroll : unemployment;

  const usable = selected.delta !== null && selected.current !== null && selected.prior !== null;
  const inside = usable && Math.abs(selected.delta as number) <= selected.band;

  // The axis is scaled so the band and the point are both legible.
  const span = usable ? Math.max(Math.abs(selected.delta as number), selected.band) * 1.6 : selected.band * 2;
  const position = (value: number) => percentOf((50 + (value / span) * 50) / 100);

  const real = series ? series.observations.filter((o) => o.value !== null) : [];
  const gaps = series ? series.observations.length - real.length : 0;
  const values = real.map((o) => o.value as number);
  const lowest = values.length ? Math.min(...values) : 0;
  const highest = values.length ? Math.max(...values) : 1;
  const headroom = (highest - lowest) * 0.14 || 1;

  return (
    <div>
      <div role="group" aria-label="Choose a survey" className="grid grid-cols-2 gap-2">
        {surveys.map((survey) => {
          const on = survey.key === selected.key;
          return (
            <button
              key={survey.key}
              type="button"
              aria-pressed={on}
              onClick={() => setSelectedKey(survey.key)}
              className={[
                "min-h-11 rounded-xl border p-3 text-left transition-colors motion-reduce:transition-none",
                on
                  ? "border-[color:var(--lx-card-hi)] bg-[color:var(--mc-selected)] text-fg"
                  : "border-line text-fg-secondary hover:text-fg",
              ].join(" ")}
            >
              <span className="type-label block text-fg-muted">{survey.who}</span>
              <span className="mt-0.5 block text-sm font-bold">{survey.what}</span>
            </button>
          );
        })}
      </div>

      <div aria-live="polite" className="lx-card mt-3 rounded-xl p-4 sm:p-6">
        <p className="type-label text-fg-muted">
          {selected.who} · {selected.seriesId}
        </p>

        {usable ? (
          <>
            {/* THE THRESHOLD. Every number below is the backend's. */}
            <div className="relative mt-4 h-24">
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label={
                `${selected.what}: a change of ${selected.formatDelta(selected.delta)} against a neutral band of ` +
                `${selected.key === "employment" ? "50,000 jobs" : "0.2 percentage points"} either way, which falls ` +
                `${inside ? "inside" : "outside"} the band. ${sentenceCase(selected.state)}.`
              } className="absolute inset-0 h-full w-full">
                <rect
                  x={50 - (selected.band / span) * 50}
                  y={38}
                  width={(selected.band / span) * 100}
                  height={24}
                  fill="rgba(159,172,241,0.13)"
                  stroke="rgba(159,172,241,0.32)"
                  strokeWidth={0.4}
                  vectorEffect="non-scaling-stroke"
                />
                <line x1={0} x2={100} y1={50} y2={50} stroke="rgba(255,255,255,0.14)" strokeWidth={0.5} vectorEffect="non-scaling-stroke" />
                <line x1={50} x2={50} y1={30} y2={70} stroke="rgba(255,255,255,0.28)" strokeWidth={0.5} vectorEffect="non-scaling-stroke" />
                <line
                  x1={50}
                  x2={50 + ((selected.delta as number) / span) * 50}
                  y1={50}
                  y2={50}
                  stroke={selected.accent}
                  strokeWidth={2.4}
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                />
              </svg>

              <div aria-hidden="true" className="pointer-events-none absolute inset-0">
                <span
                  className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full"
                  style={{ left: position(selected.delta as number), top: "50%", background: selected.accent }}
                />
                <span
                  className="type-numeric absolute -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded-md border border-[color:var(--lx-card-hi)] bg-[rgba(10,8,20,0.78)] px-1.5 py-0.5 text-[12.5px] font-bold text-fg"
                  style={{ left: position(selected.delta as number), top: "18%" }}
                >
                  {selected.formatDelta(selected.delta)}
                  {selected.key === "employment" ? " jobs a month" : ""}
                </span>
                <span className="absolute bottom-0 left-1/2 -translate-x-1/2 text-[11px] text-fg-muted">no change</span>
              </div>
            </div>

            {/* The band, in the reader's words, with the exact threshold. */}
            <p className="mt-1 max-w-prose text-xs text-fg-muted">
              The shaded band is what {result.methodology_id} treats as no meaningful move —{" "}
              {selected.bandLabel}.
            </p>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-full border border-line bg-surface-secondary px-3 py-1 text-sm font-bold text-fg">
                {sentenceCase(selected.state)}
              </span>
              {selected.extra.map(([label, value]) => (
                <span
                  key={label}
                  className="inline-flex items-center rounded-full border border-line px-3 py-1 text-sm font-medium text-fg-secondary"
                >
                  {label}: {sentenceCase(value)}
                </span>
              ))}
            </div>

            <p className="mt-3 max-w-prose text-sm text-fg-secondary">
              {selected.currentLabel} averaged{" "}
              <span className="type-numeric font-semibold text-fg">{selected.format(selected.current)}</span>
              {selected.key === "employment" ? " jobs a month" : ""}. {selected.priorLabel} averaged{" "}
              <span className="type-numeric font-semibold text-fg">{selected.format(selected.prior)}</span>
              {selected.key === "employment" ? " jobs a month" : ""}. The difference of{" "}
              <span className="type-numeric font-semibold text-fg">{selected.formatDelta(selected.delta)}</span> falls{" "}
              {inside ? "inside" : "outside"} that band, which is why {result.methodology_id} records{" "}
              <span className="font-semibold text-fg">{sentenceCase(selected.state)}</span>.
            </p>
          </>
        ) : (
          <p className="mt-3 max-w-prose text-sm text-fg-muted">
            {selected.what} has not been computed for this period, so no comparison is shown. Nothing is estimated in
            its place.
          </p>
        )}

        {/* The published series, as context rather than as the hero. */}
        <div className="mt-5 border-t border-line pt-4">
          {series === null ? (
            <p className="text-sm text-fg-muted">
              The published observations for this survey are not available, so the change over time is not shown. The
              classification above still comes from {result.methodology_id}.
            </p>
          ) : (
            <>
              <p className="type-label text-fg-muted">
                {real.length} published observations · {series.units}
              </p>
              <div className="relative mt-2 h-20">
                <svg
                  viewBox="0 0 100 100"
                  preserveAspectRatio="none"
                  role="img"
                  aria-label={
                    `${series.title}, ${series.units}, ${series.observations.length} monthly observations from ` +
                    `${formatPeriod(series.observations[0]?.date ?? null)} to ${formatPeriod(series.observations[series.observations.length - 1]?.date ?? null)}.` +
                    (gaps > 0
                      ? ` ${gaps} month${gaps > 1 ? "s" : ""} in that range has no published value and is left as a gap.`
                      : "")
                  }
                  className="absolute inset-0 h-full w-full"
                >
                  {segments(series.observations, lowest - headroom, highest + headroom).map((d) => (
                    <path
                      key={d}
                      d={d}
                      fill="none"
                      stroke={selected.accent}
                      strokeWidth={1.6}
                      strokeLinejoin="round"
                      vectorEffect="non-scaling-stroke"
                    />
                  ))}
                </svg>
              </div>
              <div className="mt-1.5 flex flex-wrap items-baseline justify-between gap-x-3 type-meta text-fg-muted">
                <span className="type-numeric">
                  {formatPeriod(real[0]?.date ?? null)} · {real[0]?.value?.toLocaleString("en-US")}
                </span>
                {gaps > 0 && (
                  /* The gap is disclosed in words as well as drawn, so a
                     reader never has to infer it from a break in a line. */
                  <span className="font-medium">
                    {gaps} month{gaps > 1 ? "s" : ""} not published
                  </span>
                )}
                <span className="type-numeric">
                  {formatPeriod(real[real.length - 1]?.date ?? null)} ·{" "}
                  {real[real.length - 1]?.value?.toLocaleString("en-US")}
                </span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
