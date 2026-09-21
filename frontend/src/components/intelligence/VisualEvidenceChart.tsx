import type { TimeSeriesVisualEvidence } from "../../api/intelligence.types";
import { Disclosure } from "../Disclosure";

/**
 * VISUAL EVIDENCE (Increment #40C).
 *
 * Draws the bounded observation series the #39 object already carries.
 * It performs **no fetch of its own** — the points arrive inside the
 * intelligence object, from the same canonical service, in the same
 * read as every number printed around it. A chart assembled from a
 * second query would be a second account of reality, and it could
 * disagree with the object it sits under.
 *
 * Hand-authored SVG per ADR-041: no charting library, no runtime
 * measurement, nothing that needs JavaScript to be comprehensible. The
 * scales are two linear interpolations, which is not enough arithmetic
 * to justify adding `d3-scale` (ADR-041 permits it; it is not required,
 * and 15.7 KB for `a + (b - a) * t` is not a trade worth making).
 *
 * WHAT THIS COMPONENT MAY DO: position, label, format, describe.
 * WHAT IT MAY NOT DO: interpolate a missing value, smooth the line,
 * extrapolate, compute a change the object did not supply, or imply
 * that any movement is good, bad or significant.
 *
 * ADR-041 recorded two live defects in the existing yield-curve chart
 * and made them acceptance criteria. Both are addressed here:
 *
 * 1. **`preserveAspectRatio="none"` distorts at mobile width.** This
 *    chart uses `xMidYMid meet` with a VIEWBOX PER BREAKPOINT — the
 *    ADR's own SSR-safe prescription, since `ResizeObserver` would
 *    reintroduce the server-rendering failure that disqualified
 *    Recharts. Two `<svg>` elements, CSS-swapped; `display: none`
 *    keeps the hidden one out of the accessibility tree, so a screen
 *    reader hears one chart, not two.
 * 2. **The ARIA pattern was both decorative-plus-table AND
 *    labelled-image.** This chart picks one: a labelled image, with
 *    the underlying numbers available as a real table behind
 *    progressive disclosure.
 */

/** Wide on desktop, taller on a phone. Uniform scaling in both. */
const DESKTOP = { width: 760, height: 240 } as const;
const MOBILE = { width: 360, height: 210 } as const;
const PADDING = { top: 14, right: 16, bottom: 26, left: 44 } as const;

export function VisualEvidenceChart({
  evidence,
  seriesName,
}: {
  evidence: TimeSeriesVisualEvidence;
  seriesName: string;
}) {
  const points = evidence.points;
  const first = points[0];
  const last = points[points.length - 1];

  if (first === undefined || last === undefined) return null;

  const caption = `Last ${evidence.available_sessions} published trading session${
    evidence.available_sessions === 1 ? "" : "s"
  } · ${shortDate(first.observation_date)} → ${shortDate(last.observation_date)}`;

  return (
    <figure className="m-0 mt-6">
      {points.length === 1 ? (
        <p className="text-sm text-fg-secondary">
          Only one published observation is available for this series, so there is no line to draw yet.
        </p>
      ) : (
        <>
          <Plot box={MOBILE} points={points} label={describe(evidence, seriesName)} className="sm:hidden" />
          <Plot box={DESKTOP} points={points} label={describe(evidence, seriesName)} className="hidden sm:block" />
        </>
      )}

      <figcaption className="mt-2 text-xs text-fg-muted">
        {caption}
        {evidence.available_sessions < evidence.requested_sessions && (
          <>
            {" "}
            — fewer than the {evidence.requested_sessions} requested, because that is all MacroChipz has published
            observations for.
          </>
        )}
      </figcaption>

      <div className="mt-3">
        <Disclosure summary={`The ${points.length} values behind this chart`}>
          <div className="max-h-72 overflow-y-auto overflow-x-auto">
            <table className="w-full text-left text-sm text-fg-secondary">
              <caption className="sr-only">
                Every published observation drawn in the chart above, oldest first.
              </caption>
              <thead>
                <tr className="text-xs text-fg-muted">
                  <th scope="col" className="pr-6 font-medium">
                    Date
                  </th>
                  <th scope="col" className="font-medium">
                    {evidence.unit}
                  </th>
                </tr>
              </thead>
              <tbody>
                {points.map((point) => (
                  <tr key={point.observation_date}>
                    <td className="pr-6 py-0.5">
                      <time dateTime={point.observation_date}>{point.observation_date}</time>
                    </td>
                    <td className="py-0.5 type-numeric">{point.value}</td>
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

/**
 * One rendering of the series at one viewBox size.
 *
 * `role="img"` plus `aria-label`: the chart is announced as a single
 * described image rather than as a tree of unlabelled shapes. Every
 * shape inside is therefore presentational, and the numbers themselves
 * live in the table above.
 */
function Plot({
  box,
  points,
  label,
  className,
}: {
  box: { width: number; height: number };
  points: ReadonlyArray<{ observation_date: string; value: number }>;
  label: string;
  className: string;
}) {
  const plotWidth = box.width - PADDING.left - PADDING.right;
  const plotHeight = box.height - PADDING.top - PADDING.bottom;

  const values = points.map((point) => point.value);
  const { min, max } = domain(values);

  // X is positioned by DATE, not by array index. A gap in publication
  // therefore shows as a gap in spacing rather than being silently
  // closed up, which is what "never fabricate missing trading days"
  // means in practice.
  const times = points.map((point) => Date.parse(point.observation_date));
  const firstTime = times[0] ?? 0;
  const lastTime = times[times.length - 1] ?? 1;
  const span = lastTime - firstTime || 1;

  const x = (time: number) => PADDING.left + ((time - firstTime) / span) * plotWidth;
  const y = (value: number) => PADDING.top + plotHeight - ((value - min) / (max - min)) * plotHeight;

  const line = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${round(x(times[index] ?? 0))} ${round(y(point.value))}`)
    .join(" ");

  const gridValues = [min, (min + max) / 2, max];
  const lastPoint = points[points.length - 1];
  const lastTimeValue = times[times.length - 1] ?? 0;

  return (
    <svg
      viewBox={`0 0 ${box.width} ${box.height}`}
      // Uniform scaling. NEVER `none` -- see this module's header.
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
            className="fill-fg-muted text-[11px] tabular-nums"
          >
            {value.toFixed(2)}
          </text>
        </g>
      ))}

      {/* The series. A single neutral stroke: semantic state colours
          mean something specific in this design system, and a yield
          moving up is neither good nor bad. */}
      <path d={line} fill="none" className="stroke-fg" strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />

      {/* The latest observation, identifiable without hovering. */}
      {lastPoint && (
        <circle cx={round(x(lastTimeValue))} cy={round(y(lastPoint.value))} r="3.5" className="fill-fg" />
      )}

      <text x={PADDING.left} y={box.height - 8} className="fill-fg-muted text-[11px]">
        {shortDate(points[0]?.observation_date ?? "")}
      </text>
      <text x={box.width - PADDING.right} y={box.height - 8} textAnchor="end" className="fill-fg-muted text-[11px]">
        {shortDate(lastPoint?.observation_date ?? "")}
      </text>
    </svg>
  );
}

/**
 * The y-axis domain: the data's own range, padded slightly.
 *
 * Deliberately NOT zero-based. A yield chart forced to a zero baseline
 * compresses every real movement into a flat line near the top, which
 * is its own kind of dishonesty; a non-zero baseline is the convention
 * for a time-series line chart precisely because the shape is the
 * point. The axis labels always state the actual values, so the scale
 * is never hidden.
 */
function domain(values: ReadonlyArray<number>): { min: number; max: number } {
  const low = Math.min(...values);
  const high = Math.max(...values);
  if (low === high) return { min: low - 0.5, max: high + 0.5 };
  const padding = (high - low) * 0.12;
  return { min: low - padding, max: high + padding };
}

/**
 * The screen-reader description: what is charted, over what span,
 * where it started, where it ended, and which way it went.
 *
 * The direction word is a comparison of two values the object already
 * supplied — the first and last drawn points. It states no magnitude
 * the object did not carry, and no significance at all.
 */
function describe(evidence: TimeSeriesVisualEvidence, seriesName: string): string {
  const points = evidence.points;
  const first = points[0];
  const last = points[points.length - 1];
  if (first === undefined || last === undefined) return `${seriesName}: no observations available.`;

  const direction = last.value > first.value ? "higher" : last.value < first.value ? "lower" : "unchanged";
  const ending = direction === "unchanged" ? "ending unchanged at" : `ending ${direction} at`;

  return (
    `Line chart of ${seriesName} in ${evidence.unit.toLowerCase()}, over the last ` +
    `${evidence.available_sessions} published trading sessions, from ${first.value} on ` +
    `${shortDate(first.observation_date)} to ${last.value} on ${shortDate(last.observation_date)}, ` +
    `${ending} ${last.value}. The full list of values follows the chart.`
  );
}

/** `2026-09-18` -> `18 Sep 2026`, without pulling in a date library. */
function shortDate(iso: string): string {
  const [year, month, day] = iso.split("-");
  if (year === undefined || month === undefined || day === undefined) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${Number(day)} ${months[Number(month) - 1] ?? month} ${year}`;
}

/** Keeps generated path data small; 0.1 units is far below one pixel. */
function round(value: number): number {
  return Math.round(value * 10) / 10;
}
