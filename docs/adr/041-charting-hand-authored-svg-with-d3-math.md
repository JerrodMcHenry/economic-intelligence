# ADR-041: Charts Are Hand-Authored SVG Over d3 Math Primitives, Not a Charting Library

## Status
Proposed (Increment #36A)

## Context

MacroChipz 2.0 needs charts across six economic worlds: time series at monthly and daily frequency, multi-series, yield curves, **revision overlays**, annotations, shaded comparison bands, tooltips with touch interaction, accessible alternatives, and possibly brushing later. Today there is exactly **one** chart — a hand-written inline SVG yield curve (166 lines) — and no charting library.

ADR-039 makes **server-renderability a hard requirement**: pre-rendering produces the initial HTML, and Open Graph images are generated at build time. A chart that cannot render without a DOM cannot satisfy either.

### The evidence

Candidates were tested empirically against React 19.2.8 via `renderToStaticMarkup()` in plain Node with no DOM globals, and bundle cost measured through Vite 8 in lib mode with tree-shaking — not quoted from documentation or whole-package size services.

| Candidate | Server output | SSR |
|---|---|---|
| **visx primitives** (`LinePath`, `@visx/scale`, axes) | 8,633 bytes, 17 `<svg>`, real coordinates | **PASS** |
| **visx `XYChart`** (high-level) | 128 bytes — background rect only | **FAIL** |
| **Nivo `<Line>`** | 8,358 bytes, real SVG | **PASS** |
| **Nivo `<ResponsiveLine>`** | throws `Element type is invalid` | **FAIL** |
| **ECharts `renderToSVGString()`** | 5,823 bytes, real SVG, zero DOM | **PASS** |
| **Observable Plot** | throws without a DOM; passes only with jsdom injected | **CONDITIONAL** |
| **Recharts** | **127 bytes, zero `<svg>`** | **FAIL** |
| **uPlot / Chart.js** | constructor throws; Canvas | **FAIL** |

**The headline result: Recharts — the default React answer — is disqualified on the requirement, not on taste.** A `<LineChart>` with explicit width and height, axes, grid, reference lines and two series produces a 127-byte empty `<div>`. This is not a `ResponsiveContainer` problem and not a missing-DOM problem: re-running with full jsdom globals produced the identical output. Recharts 3.x defers layout to effects, which never run on the server. It is a tracked regression from 2.x ([recharts#5997](https://github.com/recharts/recharts/issues/5997), open; [#6139](https://github.com/recharts/recharts/issues/6139), closed as duplicate), **unfixed fifteen months after 3.0**, with no maintainer position found either way.

**Bundle cost, measured through our own build tooling:**

| Option | Δ gzip |
|---|---|
| Hand-rolled SVG (zero deps) | **+0.1 KB** |
| **d3-scale + d3-shape + d3-time-format** | **+15.7 KB** |
| visx minimal | +21.0 KB |
| ECharts, tree-shaken, SVG renderer | +26.0 KB |
| visx fuller | +31.3 KB |
| Nivo `<Line>` | +111.6 KB |
| Recharts | +126.1 KB |

Two corrections to conventional wisdom worth recording: **ECharts is not 359 KB** — that is the whole package; tree-shaken through `echarts/core` it is 26 KB. And **Nivo and Recharts do not meaningfully tree-shake** for one line chart, costing 6–8× the entire d3 math layer.

### Two defects found in the existing chart

Both must be fixed regardless of this decision, and one corrects a claim this project has been repeating.

1. **The SVG is not `aria-hidden`.** `YieldCurveChart.tsx`'s own doc comment says it is; the code uses `role="img"` with an `aria-label`, **plus** an `sr-only` `<figcaption>`, **plus** the data table. A screen reader therefore encounters the labelled image *and* the caption *and* the table — redundancy, not the clean decorative-image pattern. **`macrochipz-2.0-architecture.md` §1.2 and §23 and the #35 research both described the pattern as "aria-hidden SVG + table". That description was wrong and is corrected here.**
2. **`preserveAspectRatio="none"` distorts the chart at mobile width.** The viewBox is 720×260 rendered into `h-56 w-full`; at 390px that is 390×224, so x scales 0.542 against y 0.862 — **text and strokes are squashed roughly 37% horizontally.** The Constitution treats mobile as first-class, so this is a live bug, and it is evidence that "responsive" was deferred rather than solved.

### The actual question

The SSR requirement eliminates five of eight candidates outright. What remains is not really "library versus hand-rolled" but: **do we want to own touch-tooltip code?**

Everything else on the requirement list is either cheap to hand-author — **revision overlays are a second `<path>` with a dash array and a different token**, and hand-authoring gives *better* control here than libraries that resist "two series that are the same series" — or purchasable as pure functions for ~16 KB.

What is genuinely hard, in order: touch tooltips with hit-testing and scroll-safety (200–400 lines of device-specific code whose failure modes only appear on real devices) · nice axis ticks · **time axes at monthly and daily frequency** (month boundaries, DST, leap years, label thinning) · responsive layout done properly · label collision avoidance · brushing.

**Three of those six are pure functions of data.** They are exactly what d3's math modules are.

## Decision

**Hand-author SVG markup over d3 math primitives. Adopt no charting library for in-page charts. Reserve ECharts for server-side image rendering only.**

Three parts:

### 1. Adopt `d3-scale`, `d3-shape`, `d3-time-format` (+15.7 KB)

Pure functions, no DOM, trivially server-renderable. They solve nice ticks, time-axis formatting and path generation — the three hard problems that are *pure computation* — while leaving markup, ARIA and theming entirely ours.

Note these modules are released infrequently (`d3-scale` 4.0.2, `d3-shape` 3.2.0). For a stable math library that reflects completion rather than abandonment. They ship no bundled types; add `@types/d3-*`.

### 2. Keep owning the `<svg>` element, the ARIA and the tokens

This is the decisive property, and no library preserves it. Because we author the SVG tag, our accessibility pattern transfers unchanged and there is **no library-generated ARIA to fight**. `stroke="var(--mc-brand)"` was verified to survive into SSR output byte-for-byte, and Tailwind utility classes pass through.

### 3. ECharts server-side only, never in the client bundle

ECharts has a **first-class, zero-dependency server-to-SVG-string renderer** (`renderToSVGString()`, SSR mode, no DOM) — verified. It is the only candidate offering this.

**Used server-side only, it costs 0 KB on the client.** It is available to ADR-039's build-time Open Graph pipeline where a card needs a chart, complementing Satori — Satori renders the card (layout, type, branding), ECharts can render a chart inside it. Its documented SSR limitation (no interactivity) is irrelevant for a static image.

**It must never be imported into client code.** A guard test enforces this.

### Disqualified, with reasons

| Library | Reason |
|---|---|
| **Recharts** | **Fails the hard SSR requirement.** Healthy project otherwise; irrelevant. |
| **uPlot, Chart.js** | Canvas — fails SSR, no per-element ARIA, no CSS-variable theming. uPlot is excellent for tens of thousands of points at 60fps, which is not our problem: macro series are hundreds to low thousands. |
| **Observable Plot** | Requires jsdom on the server; returns detached DOM nodes rather than React elements, so it fights React and breaks hydration; 19 months without a release. |
| **Nivo** | Passes SSR only in non-responsive form, costs 111.6 KB, and has not shipped a release in 16 months with a React 19 bug open 5 months. |
| **Victory** | Unmaintained — 20 months since release, 9 months without commits. |

## Deferred, with an explicit trigger

**visx primitives remain the designated escape hatch**, and only the primitives — `XYChart` fails SSR. visx *is* d3 math plus React-shaped wrappers with real TypeScript types, it preserves our ARIA pattern because we still own the `<svg>`, and it ships `@visx/tooltip`, which is precisely the code we least want to write.

**Trigger: adopt visx primitives when touch tooltips are required on more than one chart.** That is the single capability that justifies the +5 KB over d3 math alone and visx's maintenance cadence (one release in 12 months, preceded by a 19-month gap).

**Not deferred indefinitely — it is the first thing to reconsider in #41**, the first increment building charts across multiple worlds.

## Consequences

- **Bundle stays small** and charts stay out of the initial bundle (Constitution §33).
- **Every chart is server-renderable by construction**, satisfying ADR-039's prerendering and build-time OG images.
- **The accessibility pattern stays ours.** No library ARIA to override.
- **We own touch-tooltip code until the trigger fires.** Accepted knowingly; the trigger exists so it is a decision rather than a drift.
- **Two existing defects become acceptance criteria in #41**: reconcile the ARIA pattern (choose decorative-plus-table *or* labelled-image, not both), and fix `preserveAspectRatio` — the SSR-safe fix is a viewBox per breakpoint with `xMidYMid meet`, since `ResizeObserver`-based measurement would reintroduce exactly the server-rendering failure that disqualified Recharts.
- **A chart primitive set must be designed**, not accreted — axis, line, band, annotation, overlay — or six worlds will produce six divergent implementations.
- **A guard test forbids importing `echarts` from client code.**

**Trigger to revisit the whole decision:** brushing/zoom becoming a requirement, or three or more charts independently reimplementing the same interaction.

---

## Implementation notes (Increment #40C)

First chart built under this ADR: `VisualEvidenceChart.tsx`, the recent-yield series on the permanent intelligence page.

**No charting library was added.** Confirmed by test, which fails on an import of Recharts, Chart.js, ECharts, Nivo, Victory, Plotly or visx.

**`d3-scale`/`d3-shape` were NOT adopted either**, though this ADR permits them. A single time-series line needs two linear interpolations and a path string; the ADR's own 15.7 KB figure buys nothing over `a + (b - a) * t` and `points.map(...).join(" ")`. The adoption decision stands for the case it was written for — the moment a chart needs ordinal bands, stacking, ticks with nice-number rounding, or time-axis formatting, `d3-scale` is the right answer and this note should not be read as arguing otherwise.

**Both recorded defects were treated as acceptance criteria, as this ADR intended:**

1. **`preserveAspectRatio`.** Implemented exactly as the ADR prescribed — *"a viewBox per breakpoint with `xMidYMid meet`, since `ResizeObserver`-based measurement would reintroduce exactly the server-rendering failure that disqualified Recharts."* Two `<svg>` elements (360×210 and 760×240), CSS-swapped at `sm`. Verified in real Chrome through the DevTools protocol: viewBox aspect and rendered aspect match to three decimals at both 390 px (1.714) and 1440 px (3.167).

2. **The ARIA pattern.** Reconciled to **labelled-image**: `role="img"` with an `aria-label` naming the metric, span, start value, latest value and direction, with the underlying numbers as a real table behind a disclosure. The decorative-plus-table variant was not used, so the two patterns are no longer mixed.

**The existing `/rates` yield-curve chart still carries defect 1.** #40C deliberately did not widen its scope to fix it — no code is shared between the two — so it remains this ADR's acceptance criterion for #41.

**Trigger unchanged:** adopt visx primitives when touch tooltips are required on more than one chart. #40C required none: nothing on the chart depends on hover, by design.

### Rates curve chart corrected (Increment #41)

This ADR listed two defects in `YieldCurveChart` as acceptance criteria for #41. Both are now addressed, using the pattern #40C established.

**1. `preserveAspectRatio="none"`.** Replaced with `xMidYMid meet` and a viewBox per breakpoint (`MOBILE 360×240`, `DESKTOP 760×260`), CSS-swapped at `sm`. This is the ADR's own prescribed fix, chosen over `ResizeObserver` measurement for the reason the ADR gave: measurement would reintroduce the server-rendering failure that disqualified Recharts.

Verified in real Chrome through the DevTools protocol, not in jsdom: viewBox aspect and rendered aspect match to three decimals at **390 px (1.500 / 1.500)** and at **1440 px (2.923 / 2.923)**. The ~37% horizontal squash this ADR measured is gone.

**2. The mixed ARIA pattern.** The module's docstring claimed the SVG was `aria-hidden` with a table beneath, while the code did labelled-image *and* a table. Reconciled to **labelled-image**, matching `VisualEvidenceChart`: `role="img"` with the existing `aria-label`, and the table kept as the equally authoritative published version. `display: none` on the inactive breakpoint keeps it out of the accessibility tree, so a screen reader still encounters one chart.

No charting library was added, and `d3-scale` was again not required — the curve needs the same two linear interpolations #40C's note describes.

**Nothing else in the repo was rebuilt.** #41 §9 scoped this to the one documented defect.


### The Housing pipeline chart (Increment #45)

Third chart under this ADR, and the first **multi-series** one — which is the case the ADR's "a chart primitive set must be designed, not accreted" consequence was written about.

**Still no charting library, and still no `d3-scale`.** Three series sharing one linear y-axis and one time axis need the same two linear interpolations #40C's note describes. The ADR's 15.7 KB remains unspent, and the adoption trigger it names (ordinal bands, stacking, nice-number ticks, time-axis formatting) is still not met. **Measured client JS delta for the whole increment, including the page, the chart and two explainers: +21.7 KB raw / +5.3 KB gzipped, with `entry.client` unchanged at 0 bytes** — no new dependency entered the framework bundle.

**One chart, not three, and the reason is comprehension rather than economy.** Permits, starts and completions share a unit and a date axis, and the reader's question is answered by their relationship. Three charts would present three independent y-axes and invite comparison across scales that are not the same scale.

**Both recorded defects were treated as constraints from the start**, not retrofitted: viewBox per breakpoint (`MOBILE 360×280`, `DESKTOP 760×300`) with `xMidYMid meet`, no `ResizeObserver`. Verified in real Chrome through the DevTools protocol: viewBox aspect and rendered aspect match to three decimals at **390 px (1.286 / 1.286)** and at **1440 px (2.533 / 2.533)**.

**Two things this chart needed that the previous two did not:**

1. **Series identity without colour.** Three lines cannot be told apart by one neutral stroke. They are distinguished by **dash pattern** as well as tone, and **labelled at their own line ends** rather than through a legend — so the chart survives monochrome rendering and needs no mapping step from the reader. Semantic state colours were rejected outright: they mean something specific in this design system, and none of these lines is good or bad news.
2. **A multi-series accessible alternative.** The value table is one row per month with one column per series, and a month a series did not publish renders as an em dash rather than a zero. The `aria-label` names each series' two endpoints and its direction, and nothing more.

**Still nothing depends on hover**, so the visx trigger ("touch tooltips required on more than one chart") remains unfired after three charts.

**`preserveAspectRatio` and the mixed ARIA pattern are now correct on every chart in the repository** — this one, `VisualEvidenceChart` (#40C) and `YieldCurveChart` (#41). The ADR's two acceptance criteria are fully discharged.
