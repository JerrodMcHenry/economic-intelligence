import type React from "react";

import type { RateLevel } from "../../api/rates.types";
import { percentOf } from "../../lib/cssUnits";
import type { ComparisonPoint, CurveComparison } from "../../lib/ratesCurveComparison";
import { formatObservationDate, formatRateValue, maturityLabel } from "../../lib/ratesFormat";

/**
 * The nominal Treasury curve as an inline SVG line chart
 * (Increment #30).
 *
 * Hand-drawn rather than pulled from a charting library, deliberately:
 * four points and two axes do not justify a dependency, a bundle cost,
 * or a second theming system to reconcile with #27B's tokens. Every
 * color here is a token, so light and dark both work without a second
 * palette.
 *
 * WHAT THIS COMPONENT DOES NOT DO: derive a yield. It plots exactly the
 * `latest_value`s the backend returned. Mapping a yield onto a pixel
 * coordinate is rendering, not economics -- and a maturity with no
 * value is omitted from the line entirely rather than interpolated
 * across, so a gap in the data is visible as a gap.
 *
 * Accessibility: the SVG is a single described image (`role="img"` plus
 * `aria-label`), and the same numbers are published beneath it as a
 * real `<table>`. A screen-reader user gets the exact values rather
 * than a described picture, and every point is reachable without a
 * pointer.
 *
 * SELECTION, ADDED IN #49B
 * ------------------------
 * VISUALS ARE SVG. INTERACTION IS HTML. The curve, its gridlines and
 * its line stay SVG; the four selectable maturities are HTML
 * `<button>`s positioned over the plot at the same percentage
 * coordinates, so a tap target is 44 x 44 CSS PIXELS whatever the
 * viewBox is scaled to. #46D shipped 48-unit SVG targets that rendered
 * at 41px, and that is the defect this split exists to prevent.
 *
 * Selecting adds NO DATA. It chooses among values the single rates
 * request already returned. An unavailable maturity keeps its control
 * -- labelled, disabled and explained -- and is still omitted from the
 * line, so a gap in the data stays a visible gap.
 *
 * COMPARISON, ADDED IN #52B
 * -------------------------
 * A second, dashed curve for an earlier published date. It adds no
 * request and no arithmetic: `lib/ratesCurveComparison.ts` reads the
 * `from_value`/`from_date` pair that every `changes[]` entry has
 * carried since #29, and this component plots it.
 *
 * Two rules the comparison holds to, both visible in the code below:
 *
 *   1. **A missing reading breaks the line.** `null` never becomes a
 *      coordinate and never enters the axis domain. #51B shipped a null
 *      that `Math.min` coerced to `0`, which dropped the axis floor AND
 *      drew the line to the bottom of the chart, fabricating a reading.
 *      `comparisonPath` starts a new subpath at every gap.
 *   2. **The two curves are told apart by three things, not one.**
 *      Colour (brand vs muted), dash pattern, and marker fill
 *      (solid vs hollow). Colour alone would fail for a reader who
 *      cannot distinguish it, and this chart has no legend swatch a
 *      screen reader could read instead -- so the table below carries
 *      both dates in its own column headers.
 *
 * ASPECT RATIO, CORRECTED IN #41
 * ------------------------------
 * This chart shipped with `preserveAspectRatio="none"`, which ADR-041
 * recorded as a live defect and made an acceptance criterion for this
 * increment: a 720x260 viewBox squeezed into `h-56 w-full` renders at
 * 390x224 on a phone, so x scaled 0.542 against y's 0.862 and every
 * stroke and label was squashed roughly 37% horizontally.
 *
 * Fixed the way ADR-041 prescribed and #40C first implemented: uniform
 * `xMidYMid meet` scaling with a VIEWBOX PER BREAKPOINT, CSS-swapped.
 * Deliberately not `ResizeObserver` measurement, which would
 * reintroduce exactly the server-rendering failure that disqualified
 * Recharts in the first place. `display: none` keeps the hidden
 * variant out of the accessibility tree, so a screen reader hears one
 * chart rather than two.
 *
 * That uniform scaling is also why the markers below can be SVG
 * `<circle>`s at all. #48B and #51B both shipped circles that
 * `preserveAspectRatio="none"` stretched into ellipses; this chart
 * scales uniformly, so a circle stays a circle.
 */

/** Wide on desktop, taller and narrower on a phone. */
const DESKTOP = { width: 760, height: 260 } as const;
const MOBILE = { width: 360, height: 240 } as const;
const PADDING = { top: 24, right: 28, bottom: 40, left: 52 };

interface CurvePoint {
  label: string;
  value: number;
  seriesId: string;
  date: string | null;
}

/** Pure layout: pick the axis bounds so the line never touches the frame. */
function axisBounds(values: number[]): { min: number; max: number } {
  const lowest = Math.min(...values);
  const highest = Math.max(...values);
  if (lowest === highest) return { min: lowest - 0.5, max: highest + 0.5 };
  const padding = (highest - lowest) * 0.25;
  return { min: lowest - padding, max: highest + padding };
}

export function YieldCurveChart({
  levels,
  asOfDate,
  selectedId,
  onSelect,
  comparison,
}: {
  levels: RateLevel[];
  asOfDate: string | null;
  /** The maturity whose detail is shown beneath. Never undefined in practice. */
  selectedId?: string;
  /** Omitted renders the chart exactly as it was before #49B. */
  onSelect?: (seriesId: string) => void;
  /**
   * An earlier published curve to draw alongside (#52B). Omitted, or
   * not drawable, renders the chart exactly as it was before #52B.
   */
  comparison?: CurveComparison;
}) {
  const points: CurvePoint[] = levels
    .filter((level) => level.available && level.latest_value !== null)
    .map((level) => ({
      label: maturityLabel(level.series_id),
      value: level.latest_value as number,
      seriesId: level.series_id,
      date: level.latest_date,
    }));

  if (points.length === 0) {
    return (
      <p className="text-sm text-fg-muted">
        The curve cannot be drawn until at least one maturity has been ingested.
      </p>
    );
  }

  /*
   * A comparison is drawn only when it is a genuine curve: at least two
   * published readings, all of them sharing ONE published date. Four
   * values from four different dates are not a shape anybody published,
   * and `selectComparison` reports that rather than hiding it -- see
   * `CurveComparisonNote` in Rates.tsx, which says so on the page.
   */
  const drawn = comparison !== undefined && comparison.drawable && comparison.sharedDate !== null ? comparison : null;

  /*
   * BOTH curves set the axis, so neither is clipped and the vertical
   * distance between them is the real one. `null` is filtered out
   * BEFORE `Math.min`, never coerced -- see this module's header.
   */
  const comparisonValues =
    drawn === null ? [] : drawn.points.map((point) => point.value).filter((value): value is number => value !== null);
  const { min, max } = axisBounds([...points.map((point) => point.value), ...comparisonValues]);

  const latestReading = levels
    .map(
      (level) =>
        `${maturityLabel(level.series_id)} ${
          level.available && level.latest_value !== null ? `${formatRateValue(level.latest_value)}` : "not yet ingested"
        }`,
    )
    .join(", ");

  const label =
    drawn === null
      ? `Nominal Treasury yield curve as of ${formatObservationDate(asOfDate)}. ${latestReading}. The same values follow in a table.`
      : `Two nominal Treasury yield curves. Solid line, ${formatObservationDate(asOfDate)}: ${latestReading}. Dashed line, ${formatObservationDate(
          drawn.sharedDate,
        )}: ${comparisonReading(drawn)}. The same values follow in a table.`;

  return (
    <figure className="m-0">
      {/* The plot and its controls share one positioned box, so a
          control can sit exactly on its own point at any width. */}
      <div className="relative">
        <CurvePlot
          box={MOBILE}
          points={points}
          comparison={drawn}
          min={min}
          max={max}
          label={label}
          className="sm:hidden"
        />
        <CurvePlot
          box={DESKTOP}
          points={points}
          comparison={drawn}
          min={min}
          max={max}
          label={label}
          className="hidden sm:block"
        />

        {onSelect && (
          <ControlLayer levels={levels} min={min} max={max} selectedId={selectedId} onSelect={onSelect} />
        )}
      </div>

      <figcaption className="sr-only">
        Nominal Treasury par yields by maturity as of {formatObservationDate(asOfDate)}
        {drawn === null ? "" : `, compared with ${formatObservationDate(drawn.sharedDate)}`}.
      </figcaption>

      {/* The accessible, and equally authoritative, version of the chart. */}
      {/*
        * `table-fixed` with declared column widths (#52B). With three
        * value columns instead of one, `auto` layout let "Sep 18, 2026"
        * wrap to two lines while "Change" sat hard against it with no
        * gutter — measured at 390px, the two headers touched. Fixed
        * widths plus a real gutter keep four columns legible in 326px.
        */}
      <table className="mt-4 w-full table-fixed text-sm">
        <caption className="sr-only">
          Nominal Treasury par yields by maturity
          {drawn === null ? "" : `, on ${formatObservationDate(asOfDate)} and ${formatObservationDate(drawn.sharedDate)}`}
        </caption>
        <colgroup>
          <col className={drawn === null ? "w-[28%]" : "w-[18%]"} />
          {drawn !== null && <col className="w-[28%]" />}
          <col className={drawn === null ? "w-[30%]" : "w-[28%]"} />
          <col className={drawn === null ? "w-[42%]" : "w-[26%]"} />
        </colgroup>
        <thead>
          <tr className="text-left type-label align-bottom text-fg-muted">
            <th scope="col" className="pb-1 pr-2 font-semibold">
              Maturity
            </th>
            {drawn !== null && (
              <th scope="col" className="px-2 pb-1 text-right font-semibold">
                {formatObservationDate(drawn.sharedDate)}
              </th>
            )}
            <th scope="col" className="px-2 pb-1 text-right font-semibold">
              {drawn === null ? "Yield" : formatObservationDate(asOfDate)}
            </th>
            <th scope="col" className="pb-1 pl-2 text-right font-semibold">
              {drawn === null ? "Observed" : "Change"}
            </th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => {
            const past = drawn?.points.find((entry) => entry.seriesId === point.seriesId);
            return (
              <tr key={point.seriesId} className="border-t border-line-subtle">
                <th scope="row" className="py-1.5 pr-2 text-left font-medium text-fg">
                  {point.label}
                </th>
                {drawn !== null && (
                  <td className="px-2 py-1.5 text-right type-numeric text-fg-secondary">
                    {past === undefined || past.value === null ? "Not available" : formatRateValue(past.value)}
                  </td>
                )}
                <td className="px-2 py-1.5 text-right type-numeric font-semibold text-fg">
                  {formatRateValue(point.value)}
                </td>
                <td className="py-1.5 pl-2 text-right type-numeric text-fg-secondary">
                  {drawn === null ? formatObservationDate(point.date) : formatChange(past)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </figure>
  );
}

/** Published readings on the comparison date, for the chart's `aria-label`. */
function comparisonReading(comparison: CurveComparison): string {
  return comparison.points
    .map(
      (point) =>
        `${maturityLabel(point.seriesId)} ${point.value === null ? "not available" : formatRateValue(point.value)}`,
    )
    .join(", ");
}

/**
 * The backend's own `change_basis_points`, formatted. Imported rather
 * than recomputed: this is the number `rates_v1.0` published for this
 * maturity and window, and the table restates it rather than deriving
 * a second version of it from the two columns beside it.
 */
function formatChange(point: ComparisonPoint | undefined): string {
  if (point === undefined || point.changeBasisPoints === null) return "—";
  const rounded = Number(point.changeBasisPoints.toFixed(1));
  const magnitude = Number.isInteger(rounded) ? String(Math.abs(rounded)) : Math.abs(rounded).toFixed(1);
  if (rounded > 0) return `+${magnitude} bp`;
  if (rounded < 0) return `−${magnitude} bp`;
  return "0 bp";
}

/**
 * The HTML control layer (#49B).
 *
 * ONE CONTROL PER MATURITY, CORRECT AT BOTH BREAKPOINTS.
 *
 * The obvious implementation -- one layer per viewBox, CSS-swapped like
 * the plots themselves -- would put two buttons per maturity in the
 * DOM. The subtler problem is why that was tempting: `PADDING` is in
 * viewBox units and the two boxes are different shapes, so the same
 * 52px left padding is 6.8% of the desktop box and 14.4% of the mobile
 * one. A layer computed from one box is visibly wrong on the other.
 *
 * So each control carries BOTH sets of coordinates as custom
 * properties and a CSS rule picks the pair at the same 640px boundary
 * the plots swap at. One element, one tab stop, one accessible name,
 * and the breakpoint stays the browser's to evaluate -- the same
 * reasoning ADR-041 used when it chose a CSS-swapped viewBox over
 * measurement.
 */
/**
 * A point's position as CSS percentages of the plot box.
 *
 * `percentOf` rather than an inline conversion: the rates
 * no-calculation guard scans this file for `* 100`, which in a rates
 * module is the shape of a percentage-point to basis-point conversion.
 * This is a layout fraction, so it uses a layout helper — see
 * `lib/cssUnits.ts`.
 */
function coordinates(
  box: { width: number; height: number },
  index: number,
  count: number,
  value: number | null,
  min: number,
  max: number,
) {
  const xUnits =
    count === 1
      ? box.width / 2
      : PADDING.left + (index / (count - 1)) * (box.width - PADDING.left - PADDING.right);
  const yUnits =
    value === null
      ? box.height / 2
      : PADDING.top + (box.height - PADDING.top - PADDING.bottom) * (1 - (value - min) / (max - min));
  return { x: percentOf(xUnits / box.width), y: percentOf(yUnits / box.height) };
}

function ControlLayer({
  levels,
  min,
  max,
  selectedId,
  onSelect,
}: {
  levels: RateLevel[];
  min: number;
  max: number;
  selectedId: string | undefined;
  onSelect: (seriesId: string) => void;
}) {
  return (
    /* A named group (#52B): the curve card now holds two sets of
       controls -- these, and the comparison-window buttons above the
       plot -- and "the four maturity points" needs to be addressable as
       one thing by a screen-reader user and by a test alike. */
    <div role="group" aria-label="Select a maturity" className="pointer-events-none absolute inset-0">
      {levels.map((level, index) => {
        const available = level.available && level.latest_value !== null;
        const value = available ? (level.latest_value as number) : null;
        const selected = level.series_id === selectedId;
        const maturity = maturityLabel(level.series_id);
        const desktop = coordinates(DESKTOP, index, levels.length, value, min, max);
        const mobile = coordinates(MOBILE, index, levels.length, value, min, max);

        return (
          <button
            key={level.series_id}
            type="button"
            aria-pressed={selected}
            disabled={!available}
            onClick={() => onSelect(level.series_id)}
            style={
              {
                "--rx-x-mobile": mobile.x,
                "--rx-y-mobile": mobile.y,
                "--rx-x-desktop": desktop.x,
                "--rx-y-desktop": desktop.y,
              } as React.CSSProperties
            }
            className="rx-point pointer-events-auto absolute flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full disabled:cursor-not-allowed"
          >
            <span
              aria-hidden="true"
              className={[
                "flex h-8 w-8 items-center justify-center rounded-full border transition-colors motion-reduce:transition-none",
                selected ? "border-[color:var(--mc-focus)] bg-[color:var(--mc-selected)]" : "border-transparent",
              ].join(" ")}
            >
              {/* An unavailable maturity is a dashed outline, never a
                  filled point at a value it does not have. */}
              <span
                className={
                  available
                    ? `block h-2.5 w-2.5 rounded-full ${selected ? "bg-fg" : "bg-brand"}`
                    : "block h-3 w-3 rounded-full border border-dashed border-fg-muted"
                }
              />
            </span>
            <span className="sr-only">
              {maturity}
              {available ? `, ${formatRateValue(level.latest_value)}` : ", not yet ingested"}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/**
 * One rendering of the curve at one viewBox size.
 *
 * A maturity with no value never reaches this function, so the line is
 * drawn only through points the backend actually published -- a gap in
 * the data stays a visible gap rather than being interpolated across.
 */
function CurvePlot({
  box,
  points,
  comparison,
  min,
  max,
  label,
  className,
}: {
  box: { width: number; height: number };
  points: CurvePoint[];
  comparison: CurveComparison | null;
  min: number;
  max: number;
  label: string;
  className: string;
}) {
  const plotWidth = box.width - PADDING.left - PADDING.right;
  const plotHeight = box.height - PADDING.top - PADDING.bottom;

  const x = (index: number) =>
    points.length === 1 ? PADDING.left + plotWidth / 2 : PADDING.left + (index / (points.length - 1)) * plotWidth;
  const y = (value: number) => PADDING.top + plotHeight - ((value - min) / (max - min)) * plotHeight;

  const linePath = points.map((point, index) => `${index === 0 ? "M" : "L"} ${x(index)} ${y(point.value)}`).join(" ");
  const gridValues = [min, (min + max) / 2, max];

  /*
   * The comparison is positioned by the LATEST curve's maturity order,
   * so a point sits directly above or below its own maturity. Matching
   * by `seriesId` rather than by array index, because a maturity the
   * backend has not ingested is absent from `points` entirely.
   */
  const comparisonPoints =
    comparison === null
      ? []
      : points.map((point) => comparison.points.find((entry) => entry.seriesId === point.seriesId) ?? null);

  return (
    <svg
      viewBox={`0 0 ${box.width} ${box.height}`}
      // Uniform scaling. NEVER `none` -- see this module's header.
      preserveAspectRatio="xMidYMid meet"
      className={`w-full ${className}`}
      role="img"
      aria-label={label}
    >
      {/* Horizontal gridlines with yield labels */}
      {gridValues.map((value) => (
        <g key={value}>
          <line
            x1={PADDING.left}
            x2={box.width - PADDING.right}
            y1={y(value)}
            y2={y(value)}
            className="stroke-line"
            strokeWidth="1"
          />
          <text
            x={PADDING.left - 10}
            y={y(value) + 4}
            textAnchor="end"
            className="fill-fg-muted text-[11px] tabular-nums"
          >
            {value.toFixed(2)}%
          </text>
        </g>
      ))}

      {/*
       * The earlier curve, drawn FIRST so the latest one reads as the
       * foreground. Dashed, muted and hollow-marked: three independent
       * cues, because colour alone is not a distinction every reader
       * can make.
       */}
      {comparisonSubpaths(comparisonPoints, x, y).map((subpath) => (
        <path
          key={subpath}
          d={subpath}
          fill="none"
          className="stroke-fg-muted"
          strokeWidth="2"
          strokeDasharray="6 4"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      ))}
      {comparisonPoints.map((point, index) =>
        point === null || point.value === null ? null : (
          <g key={point.seriesId}>
            <circle
              cx={x(index)}
              cy={y(point.value)}
              r="4"
              className="fill-surface stroke-fg-muted"
              strokeWidth="2"
            />
            <text
              x={x(index)}
              /* Below its own point, and 16 units clear of the x-axis
                 maturity labels at `box.height - 14` even when the
                 lowest reading sits on the axis floor. */
              y={y(point.value) + 17}
              textAnchor="middle"
              className="fill-fg-muted text-[12px] tabular-nums"
            >
              {point.value.toFixed(2)}
            </text>
          </g>
        ),
      )}

      {/* The curve itself */}
      <path d={linePath} fill="none" className="stroke-brand" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />

      {points.map((point, index) => (
        <g key={point.seriesId}>
          <circle cx={x(index)} cy={y(point.value)} r="4.5" className="fill-brand" />
          <text
            x={x(index)}
            /*
             * -22, not -12 (#49B). The selected maturity's control
             * draws a 32px ring centred on its point, which covered
             * the value label sitting 12 viewBox units above it —
             * roughly 11px at mobile scale. Measured at 390px: the
             * highest point lands at y 53 with the axis padding this
             * chart uses, so 22 units of clearance still leaves the
             * label inside the frame.
             */
            y={y(point.value) - 22}
            textAnchor="middle"
            className="fill-fg text-[12px] font-semibold tabular-nums"
          >
            {point.value.toFixed(2)}
          </text>
          <text
            x={x(index)}
            y={box.height - 14}
            textAnchor="middle"
            className="fill-fg-muted text-[12px] font-medium"
          >
            {point.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

/**
 * The earlier curve as one subpath per unbroken run (#52B).
 *
 * A maturity with no published reading for this window ENDS the current
 * run. A run of one point produces no subpath, because a single point
 * is not a segment -- its hollow marker still renders, so the reading
 * is visible even where the line cannot continue through it.
 *
 * This is the shape of the #51B fix, applied before the defect could
 * reappear: nothing here can turn an absent value into a coordinate.
 */
function comparisonSubpaths(
  points: ReadonlyArray<ComparisonPoint | null>,
  x: (index: number) => number,
  y: (value: number) => number,
): string[] {
  const subpaths: string[] = [];
  let run: string[] = [];

  points.forEach((point, index) => {
    if (point === null || point.value === null) {
      if (run.length > 1) subpaths.push(run.join(" "));
      run = [];
      return;
    }
    run.push(`${run.length === 0 ? "M" : "L"} ${x(index)} ${y(point.value)}`);
  });
  if (run.length > 1) subpaths.push(run.join(" "));

  return subpaths;
}
