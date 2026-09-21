import { Link } from "react-router-dom";

import type { IntelligenceObject } from "../../api/intelligence.types";
import { VisualEvidenceChart } from "../intelligence/VisualEvidenceChart";
import { isRatesMovement } from "../../homepage/presentationPolicy";
import {
  conceptShortName,
  directionWord,
  formatPercentagePoints,
  headlineChange,
  windowConsumerLabel,
  worldLabel,
} from "../../lib/intelligenceLanguage";
import { intelligencePath } from "../../lib/siteUrl";
import { ECONOMIC_WORLDS } from "../../worlds/registry";

/**
 * THE LEDE (Increment #42).
 *
 * The first thing a person sees when they open MacroChipz. Its job is
 * to make the economy concrete within seconds — a real number from a
 * real source, in words that need no finance background.
 *
 * WHAT IT IS NOT, AND CANNOT BECOME
 * ---------------------------------
 * It is not a headline, and it is not a claim about importance. The
 * object shown here was chosen by `homepage_presentation_v1.0`, a
 * deterministic PRESENTATION policy over structural facts. #39
 * publishes no significance ranking and #42 did not add one, so
 * nothing on this component may say "most important", "biggest",
 * "major", "breaking" or "significant" — a test enforces exactly that.
 *
 * TIME IS STATED, NEVER IMPLIED
 * -----------------------------
 * The local data makes this unavoidable rather than merely principled:
 * `published_at` is null on every object MacroChipz holds, and
 * `recorded_at` spans two days because it is a backfill timestamp. So
 * the only honest time anchor is `effective_period` — the period the
 * data describes — and that is what is shown. No "today", no "just
 * released", no "new".
 */
export function TheLede({
  object,
  status,
}: {
  object: IntelligenceObject | null;
  /**
   * `"unknown"` is NOT the quiet state. Before the request resolves --
   * which includes the whole of the prerendered HTML, since this page
   * fetches in the browser -- MacroChipz does not yet know whether
   * anything qualifies. Rendering the quiet lede then would bake "No
   * new tracked change" into the static page and leave it there for
   * every crawler, which would be a claim MacroChipz had not checked.
   */
  status: "unknown" | "resolved";
}) {
  if (status === "unknown") return <UnknownLede />;
  if (object === null) return <QuietLede />;
  return <ActiveLede object={object} />;
}

/** Before the answer is known. States nothing about the economy. */
function UnknownLede() {
  return (
    <section aria-labelledby="lede-heading" className="pb-2">
      <p className="type-label text-fg-muted">The economy</p>
      <h2 id="lede-heading" className="type-page-title mt-2">
        The economy right now
      </h2>
      <p className="mt-3 max-w-prose text-fg-secondary">
        Loading the latest readings MacroChipz has on file.
      </p>
      <ul className="mt-5 grid gap-3 sm:grid-cols-3">
        {ECONOMIC_WORLDS.map((world) => (
          <li key={world.id} className="rounded-lg border border-line bg-surface p-4">
            <Link to={world.route} className="text-sm font-semibold text-fg underline-offset-4 hover:underline">
              {world.label} →
            </Link>
            <p className="mt-1 text-sm text-fg-secondary">{world.description}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ActiveLede({ object }: { object: IntelligenceObject }) {
  const world = ECONOMIC_WORLDS.find((entry) => entry.analyticsWorld === object.world);
  const permanent = intelligencePath(object.id);

  return (
    <section aria-labelledby="lede-heading" className="pb-2">
      <p className="type-label text-fg-muted">
        {worldLabel(object.world)} · <time dateTime={object.effective_period}>{object.effective_period}</time>
      </p>

      {isRatesMovement(object) ? <RatesLede object={object} /> : <GenericLede object={object} />}

      <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2">
        <Link
          to={permanent}
          className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
        >
          See the evidence →
        </Link>
        {world && (
          <Link
            to={world.route}
            className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
          >
            Explore {world.label} →
          </Link>
        )}
      </div>
    </section>
  );
}

function RatesLede({ object }: { object: Extract<IntelligenceObject, { type: "RATES_MOVEMENT" }> }) {
  const name = conceptShortName(object.concepts[0], object.payload.series_title);
  const lead = headlineChange(object.payload.changes);
  const points = lead ? formatPercentagePoints(lead.change_basis_points) : null;
  const direction = lead ? directionWord(lead.change_basis_points) : null;

  return (
    <>
      <h2 id="lede-heading" className="type-page-title mt-2">
        {name}
      </h2>

      <p className="type-numeric mt-3 text-5xl font-semibold tracking-tight text-fg sm:text-6xl">
        {object.payload.latest_value === null ? (
          <span className="text-2xl font-normal text-fg-muted">No published value</span>
        ) : (
          `${object.payload.latest_value.toFixed(2)}%`
        )}
      </p>

      {lead && points && points !== "unchanged" && direction && direction !== "unchanged" && (
        <p className="mt-2 text-lg text-fg-secondary">
          <span aria-hidden="true">{direction === "up" ? "↑" : "↓"}</span>{" "}
          <span className="font-medium text-fg">
            {direction === "up" ? "Up" : "Down"} {points.replace(/^[+−]/, "")}
          </span>{" "}
          over {windowConsumerLabel(lead.sessions)}
        </p>
      )}
      {lead && points === "unchanged" && (
        <p className="mt-2 text-lg text-fg-secondary">Unchanged over {windowConsumerLabel(lead.sessions)}.</p>
      )}

      {/* The series travels inside the object (#40C). The homepage
          fetches no observation history of its own. */}
      {object.payload.visual_evidence && (
        <div className="mt-4 max-w-3xl">
          <VisualEvidenceChart evidence={object.payload.visual_evidence} seriesName={name} />
        </div>
      )}
    </>
  );
}

/**
 * Every other eligible type, rendered plainly.
 *
 * Nothing local currently reaches this branch — `homepage_presentation_v1.0`
 * admits only rates movements today, because every other object in the
 * database is backfill. It exists so a genuine revision or state
 * transition renders honestly on the day one arrives, rather than
 * crashing or being silently dropped.
 */
function GenericLede({ object }: { object: IntelligenceObject }) {
  const name = conceptShortName(object.concepts[0], object.concepts[0] ?? "This measure");
  return (
    <>
      <h2 id="lede-heading" className="type-page-title mt-2">
        {name}
      </h2>
      <p className="mt-3 max-w-prose text-fg-secondary">
        MacroChipz recorded a change here for{" "}
        <time dateTime={object.effective_period}>{object.effective_period}</time>.
      </p>
    </>
  );
}

/**
 * THE QUIET LEDE.
 *
 * Shown when no object is eligible. It does not manufacture activity
 * and it does not say "nothing is happening" — the economy is always
 * operating; MacroChipz simply has not recorded a new tracked change.
 *
 * It also refuses the tempting fallback of showing the freshest
 * ineligible object instead, because that object is, by definition,
 * one of the 1,488 coverage events or 358 first observations the
 * policy exists to keep off this page. A quiet day is a valid product
 * state. An invented headline is not.
 */
function QuietLede() {
  return (
    <section aria-labelledby="lede-heading" className="pb-2">
      <p className="type-label text-fg-muted">The economy</p>

      <h2 id="lede-heading" className="type-page-title mt-2">
        No new tracked change
      </h2>

      <p className="mt-3 max-w-prose text-fg-secondary">
        MacroChipz has not recorded a new change in the parts of the economy it tracks. That is not a claim that the
        economy is quiet — only that nothing new has arrived here. Where things stand:
      </p>

      <ul className="mt-5 grid gap-3 sm:grid-cols-3">
        {ECONOMIC_WORLDS.map((world) => (
          <li key={world.id} className="rounded-lg border border-line bg-surface p-4">
            <Link to={world.route} className="text-sm font-semibold text-fg underline-offset-4 hover:underline">
              {world.label} →
            </Link>
            <p className="mt-1 text-sm text-fg-secondary">{world.description}</p>
          </li>
        ))}
      </ul>

      <p className="mt-4 text-sm text-fg-muted">
        <Link to="/calendar" className="font-medium underline-offset-4 hover:text-fg hover:underline">
          See when the next data is scheduled →
        </Link>
      </p>
    </section>
  );
}
