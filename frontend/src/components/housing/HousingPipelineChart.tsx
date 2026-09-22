import type { HousingStage } from "../../api/housing.types";
import { Disclosure } from "../Disclosure";
import { STAGE_COPY } from "../../lib/housingFormat";

/**
 * The construction pipeline, as ONE chart (Increment #45).
 *
 * ================================================================
 * WHY ONE CHART AND NOT THREE
 * ================================================================
 *
 * #45 asked whether three charts or one combined treatment produces
 * better comprehension. One does, and the reason is specific rather
 * than aesthetic: permits, starts and completions are measured in the
 * SAME UNIT on the SAME DATES, and the question a reader arrives with —
 * "are more homes entering the pipeline?" — is answered by their
 * relationship, not by any one of them. Three charts would put three
 * independent y-axes on the page and invite the reader to compare
 * shapes across scales that are not the same scale.
 *
 * Drawn from the SEASONALLY ADJUSTED ANNUAL RATE only. The unadjusted
 * monthly counts are on the page as figures, but plotting both units on
 * one axis would be the exact conflation this world's concept design
 * exists to prevent.
 *
 * ================================================================
 * WHAT IT REFUSES TO DO
 * ================================================================
 *
 * No interpolation, no smoothing, no forecast, no trend line, and no
 * fill between the series — a shaded gap between permits and starts
 * would draw a "pipeline backlog" that MacroChipz does not measure and
 * that the data does not support (these are three separate
 * measurements, not one cohort followed through time).
 *
 * No red/green. A line moving down is not bad and a line moving up is
 * not good; there is no housing methodology to say either. The three
 * series are distinguished by DASH PATTERN as well as by tone, so they
 * remain distinguishable without colour, and each is labelled at its
 * own end rather than through a legend the reader has to map back.
 *
 * Nothing depends on hover. Every value is in the table beneath.
 *
 * Hand-authored SVG per ADR-041: no charting library, and a viewBox per
 * breakpoint with `xMidYMid meet` rather than runtime measurement,
 * which is the ADR's own SSR-safe prescription.
 */

const DESKTOP = { width: 760, height: 300 } as const;
const MOBILE = { width: 360, height: 280 } as const;
const PADDING = { top: 16, right: 74, bottom: 30, left: 56 } as const;

/**
 * Stroke patterns, in pipeline order. Solid reads as the "leading"
 * series, which permits genuinely is in sequence — not in importance.
 */
const STROKE_PATTERNS: ReadonlyArray<string | undefined> = [undefined, "6 3", "2 3"];

interface Series {
  readonly stage: HousingStage["stage"];
  readonly label: string;
  readonly points: ReadonlyArray<{ observation_date: string; value: number }>;
  readonly dash: string | undefined;
}

export function HousingPipelineChart({ stages }: { stages: ReadonlyArray<HousingStage> }) {
  const series: Series[] = stages
    .map((stage, index) => ({
      stage: stage.stage,
      label: STAGE_COPY[stage.stage].name,
      points: stage.pace.trend?.points ?? [],
      dash: STROKE_PATTERNS[index],
    }))
    .filter((entry) => entry.points.length > 1);

  if (series.length === 0) return null;

  const months = Math.max(...series.map((entry) => entry.points.length));
  const span = describeSpan(series);

  return (
    <figure className="m-0">
      <Plot box={MOBILE} series={series} label={describe(series)} className="sm:hidden" />
      <Plot box={DESKTOP} series={series} label={describe(series)} className="hidden sm:block" />

      <figcaption className="mt-2 text-xs text-fg-muted">
        Seasonally adjusted annual rate, {months} published months · {span}. Each line is a separate measurement;
        they are not the same homes followed through the pipeline.
      </figcaption>

      <div className="mt-3">
        <Disclosure summary="The values behind this chart">
          <div className="max-h-72 overflow-auto">
            <table className="w-full text-left text-sm text-fg-secondary">
              <caption className="sr-only">
                Every published month drawn in the chart above, oldest first, at a seasonally adjusted annual rate.
              </caption>
              <thead>
                <tr className="text-xs text-fg-muted">
                  <th scope="col" className="pr-6 font-medium">
                    Month
                  </th>
                  {series.map((entry) => (
                    <th key={entry.stage} scope="col" className="pr-6 font-medium">
                      {entry.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows(series).map((row) => (
                  <tr key={row.month}>
                    <td className="py-0.5 pr-6">
                      <time dateTime={row.month}>{row.month}</time>
                    </td>
                    {series.map((entry) => (
                      <td key={entry.stage} className="py-0.5 pr-6 type-numeric">
                        {/* A month a series did not publish is blank, never zero. */}
                        {row.values[entry.stage] ?? "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Disclosure>
      </div>
    </figure>
  );
}

function Plot({
  box,
  series,
  label,
  className,
}: {
  box: { width: number; height: number };
  series: ReadonlyArray<Series>;
  label: string;
  className: string;
}) {
  const plotWidth = box.width - PADDING.left - PADDING.right;
  const plotHeight = box.height - PADDING.top - PADDING.bottom;

  const allValues = series.flatMap((entry) => entry.points.map((point) => point.value));
  const allTimes = series.flatMap((entry) => entry.points.map((point) => Date.parse(point.observation_date)));
  const { min, max } = domain(allValues);
  const firstTime = Math.min(...allTimes);
  const lastTime = Math.max(...allTimes);
  const timeSpan = lastTime - firstTime || 1;

  // X is positioned by DATE, so a month a series did not publish shows
  // as a gap in spacing rather than being silently closed up.
  const x = (time: number) => PADDING.left + ((time - firstTime) / timeSpan) * plotWidth;
  const y = (value: number) => PADDING.top + plotHeight - ((value - min) / (max - min)) * plotHeight;

  const gridValues = [min, (min + max) / 2, max];

  return (
    <svg
      viewBox={`0 0 ${box.width} ${box.height}`}
      // Uniform scaling. NEVER `none` -- see ADR-041's recorded defect.
      preserveAspectRatio="xMidYMid meet"
      className={`w-full ${className}`}
      role="img"
      aria-label={label}
    >
      {gridValues.map((value) => (
        <g key={value}>
          <line
            x1={PADDING.left}
            x2={box.width - PADDING.right}
            y1={round(y(value))}
            y2={round(y(value))}
            className="stroke-line"
            strokeWidth="1"
          />
          <text
            x={PADDING.left - 8}
            y={round(y(value)) + 4}
            textAnchor="end"
            className="fill-fg-muted text-[10px] tabular-nums"
          >
            {compact(value)}
          </text>
        </g>
      ))}

      {series.map((entry) => {
        const path = entry.points
          .map(
            (point, index) =>
              `${index === 0 ? "M" : "L"} ${round(x(Date.parse(point.observation_date)))} ${round(y(point.value))}`,
          )
          .join(" ");
        const last = entry.points[entry.points.length - 1];
        if (last === undefined) return null;
        return (
          <g key={entry.stage}>
            <path
              d={path}
              fill="none"
              // One neutral stroke for all three. Semantic state colours
              // mean something specific in this design system, and none
              // of these lines is good or bad news.
              className="stroke-fg"
              strokeWidth="1.6"
              strokeDasharray={entry.dash}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            <circle cx={round(x(Date.parse(last.observation_date)))} cy={round(y(last.value))} r="3" className="fill-fg" />
            {/* Labelled at its own end, so no legend has to be mapped
                back to a line, and so the chart survives without
                colour. */}
            <text
              x={box.width - PADDING.right + 6}
              y={round(y(last.value)) + 3.5}
              className="fill-fg-secondary text-[11px]"
            >
              {entry.label}
            </text>
          </g>
        );
      })}

      <text x={PADDING.left} y={box.height - 8} className="fill-fg-muted text-[10px]">
        {shortMonth(isoFromTime(firstTime))}
      </text>
      <text
        x={box.width - PADDING.right}
        y={box.height - 8}
        textAnchor="end"
        className="fill-fg-muted text-[10px]"
      >
        {shortMonth(isoFromTime(lastTime))}
      </text>
    </svg>
  );
}

/**
 * The y-axis domain: the data's own range, padded slightly.
 *
 * Deliberately NOT zero-based. Three series sharing one axis over sixty
 * months already span a wide range; forcing a zero baseline would
 * compress every real movement toward the top of the plot, which is its
 * own kind of dishonesty. The axis labels always state the actual
 * values, so the scale is never hidden.
 */
function domain(values: ReadonlyArray<number>): { min: number; max: number } {
  const low = Math.min(...values);
  const high = Math.max(...values);
  if (low === high) return { min: low * 0.95, max: high * 1.05 };
  const padding = (high - low) * 0.1;
  return { min: low - padding, max: high + padding };
}

/**
 * The screen-reader description: what is charted, over what span, and
 * where each series started and ended.
 *
 * States the two endpoint values each series already carries and the
 * direction between them. No magnitude the data did not supply, and no
 * significance at all.
 */
function describe(series: ReadonlyArray<Series>): string {
  const parts = series.map((entry) => {
    const first = entry.points[0];
    const last = entry.points[entry.points.length - 1];
    if (first === undefined || last === undefined) return `${entry.label}: no data.`;
    const direction = last.value > first.value ? "higher" : last.value < first.value ? "lower" : "unchanged";
    return (
      `${entry.label}: from ${Math.round(first.value).toLocaleString("en-US")} in ${shortMonth(first.observation_date)} ` +
      `to ${Math.round(last.value).toLocaleString("en-US")} in ${shortMonth(last.observation_date)}, ending ${direction}.`
    );
  });
  return (
    "Line chart of U.S. housing permits, starts and completions at a seasonally adjusted annual rate. " +
    `${parts.join(" ")} The full list of values follows the chart.`
  );
}

function describeSpan(series: ReadonlyArray<Series>): string {
  const times = series.flatMap((entry) => entry.points.map((point) => Date.parse(point.observation_date)));
  return `${shortMonth(isoFromTime(Math.min(...times)))} → ${shortMonth(isoFromTime(Math.max(...times)))}`;
}

function tableRows(series: ReadonlyArray<Series>) {
  const months = new Set<string>();
  for (const entry of series) for (const point of entry.points) months.add(point.observation_date);

  return [...months]
    .sort()
    .map((month) => {
      const values: Record<string, string> = {};
      for (const entry of series) {
        const point = entry.points.find((candidate) => candidate.observation_date === month);
        if (point !== undefined) values[entry.stage] = Math.round(point.value).toLocaleString("en-US");
      }
      return { month, values };
    });
}

/** 1394000 -> "1.39M" for an axis label, where the exact figure is in the table. */
function compact(value: number): string {
  return `${(value / 1_000_000).toFixed(2)}M`;
}

/** "2026-08-01" -> "Aug 2026", without pulling in a date library. */
function shortMonth(iso: string): string {
  const [year, month] = iso.split("-");
  if (year === undefined || month === undefined) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[Number(month) - 1] ?? month} ${year}`;
}

function isoFromTime(time: number): string {
  return new Date(time).toISOString().slice(0, 10);
}

/** Keeps generated path data small; 0.1 units is far below one pixel. */
function round(value: number): number {
  return Math.round(value * 10) / 10;
}
