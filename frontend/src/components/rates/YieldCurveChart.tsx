import type { RateLevel } from "../../api/rates.types";
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

export function YieldCurveChart({ levels, asOfDate }: { levels: RateLevel[]; asOfDate: string | null }) {
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

  const { min, max } = axisBounds(points.map((point) => point.value));
  const label = `Nominal Treasury yield curve as of ${formatObservationDate(asOfDate)}. The same values follow in a table.`;

  return (
    <figure className="m-0">
      <CurvePlot box={MOBILE} points={points} min={min} max={max} label={label} className="sm:hidden" />
      <CurvePlot box={DESKTOP} points={points} min={min} max={max} label={label} className="hidden sm:block" />

      <figcaption className="sr-only">
        Nominal Treasury par yields by maturity as of {formatObservationDate(asOfDate)}.
      </figcaption>

      {/* The accessible, and equally authoritative, version of the chart. */}
      <table className="mt-4 w-full text-sm">
        <caption className="sr-only">Nominal Treasury par yields by maturity</caption>
        <thead>
          <tr className="text-left type-label text-fg-muted">
            <th scope="col" className="pb-1 font-semibold">
              Maturity
            </th>
            <th scope="col" className="pb-1 text-right font-semibold">
              Yield
            </th>
            <th scope="col" className="pb-1 text-right font-semibold">
              Observed
            </th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.seriesId} className="border-t border-line-subtle">
              <th scope="row" className="py-1.5 text-left font-medium text-fg">
                {point.label}
              </th>
              <td className="py-1.5 text-right type-numeric font-semibold text-fg">{formatRateValue(point.value)}</td>
              <td className="py-1.5 text-right type-meta text-fg-muted">{formatObservationDate(point.date)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
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
  min,
  max,
  label,
  className,
}: {
  box: { width: number; height: number };
  points: CurvePoint[];
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

      {/* The curve itself */}
      <path d={linePath} fill="none" className="stroke-brand" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />

      {points.map((point, index) => (
        <g key={point.seriesId}>
          <circle cx={x(index)} cy={y(point.value)} r="4.5" className="fill-brand" />
          <text
            x={x(index)}
            y={y(point.value) - 12}
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
