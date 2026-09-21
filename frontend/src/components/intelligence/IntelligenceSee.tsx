import { Link } from "react-router";

import { Card } from "../Card";
import { VisualEvidenceChart } from "./VisualEvidenceChart";

import type { IntelligenceObject } from "../../api/intelligence.types";
import { WHY_THIS_MATTERS_BY_CONCEPT } from "../../content/explanations/rates";
import {
  changeClassLabel,
  conceptShortName,
  directionWord,
  formatBasisPoints,
  formatPercentagePoints,
  headline,
  headlineChange,
  rankPercent,
  summary,
  typeLabel,
  windowConsumerLabel,
  windowLabel,
  worldLabel,
} from "../../lib/intelligenceLanguage";

/**
 * SEE -> UNDERSTAND -> CONTEXT -> EXPLORE (Increment #40, consumer
 * pass in #40B).
 *
 * The first viewport answers "what is this, where is it, and how far
 * did it move?" in three lines, in language that needs no finance
 * background:
 *
 *     10-year Treasury yield
 *     5.01%
 *     up 0.05 percentage points over the last 5 trading days
 *
 * #40 led with `payload.series_title` -- "10-Year Treasury Par Yield
 * (Nominal)" -- and expressed movement in basis points. Both are
 * correct and both are finance-native. They are still on the page, in
 * "Check this" and beside the consumer figures, because the
 * professional reader needs them; they simply no longer come first.
 *
 * Machine taxonomy is translated, never displayed raw: no
 * `RATES_MOVEMENT`, no `METHODOLOGY_DERIVED`.
 *
 * Every number rendered here is read straight off the #39 object.
 * Nothing on this page computes a change, a magnitude, a percentile or
 * a state. Basis points are converted to percentage points for
 * display, which is a unit label in the same sense that `5.01` is
 * displayed as `5.01%`; see `formatPercentagePoints`.
 */
export function IntelligenceSee({ object }: { object: IntelligenceObject }) {
  if (object.type === "RATES_MOVEMENT") return <RatesMovement object={object} />;
  return <GenericIntelligence object={object} />;
}

function RatesMovement({ object }: { object: Extract<IntelligenceObject, { type: "RATES_MOVEMENT" }> }) {
  const name = conceptShortName(object.concepts[0], object.payload.series_title);
  const lead = headlineChange(object.payload.changes);
  const explanation = object.concepts[0] ? WHY_THIS_MATTERS_BY_CONCEPT[object.concepts[0]] : undefined;

  return (
    <>
      <header>
        <p className="type-label text-fg-muted">
          {worldLabel(object.world)} · <time dateTime={object.effective_period}>{object.effective_period}</time>
        </p>

        {/* SEE: the name a reader recognises, then the number, then the
            move. The provider's own title stays available in "Check
            this" rather than leading. */}
        <h1 className="type-page-title mt-2">{name}</h1>

        <p className="type-numeric mt-3 text-5xl font-semibold tracking-tight text-fg sm:text-6xl">
          {object.payload.latest_value === null ? (
            <span className="text-2xl font-normal text-fg-muted">No published value</span>
          ) : (
            `${object.payload.latest_value.toFixed(2)}%`
          )}
        </p>

        {lead && <LeadMovement change={lead} />}

        <p className="mt-4 max-w-prose text-sm text-fg-muted">{object.payload.series_title}</p>
      </header>

      {/* VISUAL EVIDENCE (#40C). Placed immediately after SEE so the
          reader can answer "what has this actually been doing?" before
          reading any explanation. The series comes from the #39 object;
          this page fetches nothing of its own. */}
      {object.payload.visual_evidence && (
        <VisualEvidenceChart evidence={object.payload.visual_evidence} seriesName={name} />
      )}

      {/* UNDERSTAND. The panel is capped at reading measure so it
          matches its own text rather than stretching across a wide
          screen. */}
      {explanation && (
        <Card as="article" className="mt-8 max-w-prose">
          <h2 id="why-heading" className="type-section-heading">
            {explanation.title}
          </h2>
          <p className="mt-2 max-w-prose text-sm text-fg-secondary">{explanation.definition}</p>
          {explanation.whyItMatters && (
            <p className="mt-2 max-w-prose text-sm text-fg-secondary">{explanation.whyItMatters}</p>
          )}
        </Card>
      )}

      {/* CONTEXT */}
      <HowFarItMoved object={object} />
      <IsThisUnusual object={object} />

      {/* EXPLORE */}
      <p className="mt-8">
        <Link
          to="/rates"
          className="inline-flex items-center gap-1 text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
        >
          Explore Rates
          <span aria-hidden="true">→</span>
        </Link>
      </p>
    </>
  );
}

/**
 * The headline movement, in percentage points.
 *
 * Direction is carried by the WORD "up"/"down" and by the sign -- never
 * by colour alone, and never by an arrow glyph alone, which a screen
 * reader would not announce.
 */
function LeadMovement({
  change,
}: {
  change: { sessions: number; change_basis_points: number | null };
}) {
  const points = formatPercentagePoints(change.change_basis_points);
  const direction = directionWord(change.change_basis_points);
  if (points === null) return null;

  if (points === "unchanged" || direction === "unchanged") {
    return (
      <p className="mt-2 text-lg text-fg-secondary">
        Unchanged over {windowConsumerLabel(change.sessions)}.
      </p>
    );
  }

  return (
    <p className="mt-2 text-lg text-fg-secondary">
      <span aria-hidden="true">{direction === "up" ? "↑" : "↓"}</span>{" "}
      <span className="font-medium text-fg">
        {direction === "up" ? "Up" : "Down"} {points.replace(/^[+−]/, "")}
      </span>{" "}
      over {windowConsumerLabel(change.sessions)}
    </p>
  );
}

/** Every available window, percentage points first, basis points beside. */
function HowFarItMoved({ object }: { object: Extract<IntelligenceObject, { type: "RATES_MOVEMENT" }> }) {
  const available = object.payload.changes.filter((change) => change.available);
  if (available.length === 0) return null;

  return (
    <section aria-labelledby="moved-heading" className="mt-8">
      <h2 id="moved-heading" className="type-section-heading">
        How far it has moved
      </h2>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
        {available.map((change) => {
          const points = formatPercentagePoints(change.change_basis_points);
          const basisPoints = formatBasisPoints(change.change_basis_points);
          const direction = directionWord(change.change_basis_points);
          return (
            <div key={change.window}>
              <dt className="text-xs text-fg-muted">{windowConsumerLabel(change.sessions)}</dt>
              <dd className="mt-1">
                <span className="type-numeric text-lg text-fg">
                  {points === null ? "not available" : points.replace(" percentage points", "")}
                </span>
                {points !== null && points !== "unchanged" && (
                  <span className="text-xs text-fg-muted"> points</span>
                )}
                {direction && direction !== "unchanged" && <span className="sr-only"> ({direction})</span>}
                {/* The canonical unit, kept beside the consumer one for
                    anyone who thinks in basis points. */}
                {basisPoints !== null && basisPoints !== "unchanged" && (
                  <span className="mt-0.5 block text-xs text-fg-muted">{basisPoints}</span>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
      <p className="mt-3 text-xs text-fg-muted">
        Windows count published trading days, never calendar days — {windowLabel("21_SESSIONS")} is roughly, not
        exactly, a month.
      </p>
    </section>
  );
}

/**
 * CONTEXT: "Is this unusual?"
 *
 * Four things #40 left ambiguous and #40B makes explicit:
 *
 * 1. **What is compared.** `rates_v1.0` ranks the 5-session CHANGE
 *    against every earlier 5-session change -- not the level. #40's
 *    page said "this level sits at the Nth percentile", which named
 *    the wrong quantity.
 * 2. **Signed versus magnitude.** Two different ranks answering two
 *    different questions, which can disagree sharply.
 * 3. **How much history.** The count is stated in the same sentence as
 *    the comparison, not in a footnote.
 * 4. **That this is not long-run context.** Said outright.
 *
 * It deliberately does NOT answer "unusual: yes/no". `rates_v1.0`
 * defines no notability threshold, and inventing one here would be a
 * significance methodology invented in the rendering layer.
 */
function IsThisUnusual({ object }: { object: Extract<IntelligenceObject, { type: "RATES_MOVEMENT" }> }) {
  const { historical_percentile_rank, historical_magnitude_percentile_rank, historical_observation_count } =
    object.payload;

  if (historical_percentile_rank === null && historical_magnitude_percentile_rank === null) return null;

  const moves = `${historical_observation_count} earlier 5-trading-day move${
    historical_observation_count === 1 ? "" : "s"
  }`;

  return (
    <section aria-labelledby="unusual-heading" className="mt-8">
      <h2 id="unusual-heading" className="type-section-heading">
        Is this unusual?
      </h2>

      <p className="mt-2 max-w-prose text-sm text-fg-secondary">
        MacroChipz can only answer that against its own record, and that record is short: {moves} in this yield.
        Compared with those —
      </p>

      <dl className="mt-3 max-w-prose space-y-2 text-sm">
        {historical_percentile_rank !== null && (
          <div className="flex flex-wrap items-baseline gap-x-2">
            <dt className="text-fg-muted">Direction and size together:</dt>
            <dd className="text-fg-secondary">
              larger than {rankPercent(historical_percentile_rank)} of them
            </dd>
          </div>
        )}
        {historical_magnitude_percentile_rank !== null && (
          <div className="flex flex-wrap items-baseline gap-x-2">
            <dt className="text-fg-muted">Size alone, ignoring direction:</dt>
            <dd className="text-fg-secondary">
              larger than {rankPercent(historical_magnitude_percentile_rank)} of them
            </dd>
          </div>
        )}
      </dl>

      <p className="mt-3 max-w-prose text-sm text-fg-muted">
        This describes the <strong className="font-medium text-fg-secondary">move over 5 trading days</strong>, not
        the level itself. And {historical_observation_count} moves is a few months of trading, not decades — it is
        not a statement about what is normal for this yield over the long run.
      </p>

      <p className="mt-2 max-w-prose text-sm text-fg-muted">
        MacroChipz does not label this move unusual or ordinary. Its rates methodology defines no threshold for that,
        so saying otherwise here would be inventing one.
      </p>
    </section>
  );
}

/**
 * Every other #39 type keeps #40's presentation unchanged.
 *
 * #40B is scoped to the RATES_MOVEMENT reference page. Giving the other
 * types a half-considered consumer treatment would be worse than
 * leaving them honest and plain until each is designed properly.
 */
function GenericIntelligence({ object }: { object: IntelligenceObject }) {
  return (
    <header>
      <p className="type-label text-fg-muted">
        {worldLabel(object.world)} · {typeLabel(object.type)}
      </p>

      <h1 className="type-page-title mt-2">{headline(object)}</h1>

      <p className="mt-1 text-sm text-fg-muted">
        For <time dateTime={object.effective_period}>{object.effective_period}</time>
      </p>

      <p className="mt-4 max-w-prose text-fg-secondary">{summary(object)}</p>

      {object.type === "OBSERVATION_CHANGE" && <ObservationKeyNumbers object={object} />}
      {object.type === "ANALYSIS_CHANGE" && (
        <p className="mt-4 text-sm text-fg-secondary">{changeClassLabel(object.payload.change_class)}</p>
      )}
      {object.type === "RELEASE_PROCESSED" && (
        <p className="mt-4 text-sm text-fg-secondary">
          {object.payload.observation_changes} data point
          {object.payload.observation_changes === 1 ? "" : "s"} recorded
          {object.payload.revised_observations > 0
            ? `, of which ${object.payload.revised_observations} were revisions`
            : ""}
          .
        </p>
      )}
    </header>
  );
}

function ObservationKeyNumbers({
  object,
}: {
  object: Extract<IntelligenceObject, { type: "OBSERVATION_CHANGE" }>;
}) {
  return (
    <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
      <div>
        <dt className="text-xs text-fg-muted">Value now</dt>
        <dd className="type-numeric mt-0.5 text-fg">{object.payload.new_value ?? "not reported"}</dd>
      </div>
      <div>
        <dt className="text-xs text-fg-muted">Value before</dt>
        <dd className="type-numeric mt-0.5 text-fg">
          {object.payload.previous_value === null ? (
            <span className="text-fg-muted">none — first report</span>
          ) : (
            object.payload.previous_value
          )}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-fg-muted">Change</dt>
        <dd className="type-numeric mt-0.5 text-fg">
          {object.payload.delta === null ? <span className="text-fg-muted">not applicable</span> : object.payload.delta}
        </dd>
      </div>
    </dl>
  );
}
