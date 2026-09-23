import { Link } from "react-router-dom";

import type { IntelligenceObject } from "../../api/intelligence.types";
import { RecentIntelligence } from "./RecentIntelligence";
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
  alsoRecorded = [],
}: {
  object: IntelligenceObject | null;
  /**
   * What `selection.whatChanged` returned -- a DIFFERENT selection
   * from the one that chose `object`, rendered beside it rather than
   * in a section of its own (#48A). On this data both are the same
   * world and the same period, so two headings and a rule between
   * them was splitting one reading in half.
   *
   * It is passed in rather than fetched: this component still issues
   * no request of its own.
   */
  alsoRecorded?: IntelligenceObject[];
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
  return <ActiveLede object={object} alsoRecorded={alsoRecorded} />;
}

/** Before the answer is known. States nothing about the economy. */
function UnknownLede() {
  return (
    <LedeShell
      heading="Not yet known"
      body="MacroChipz has not finished checking whether anything new has arrived. This is deliberately not the quiet state — saying nothing happened before asking would be a claim rather than a fact."
      note="Shown while the request is unresolved, and if it fails."
    />
  );
}

function ActiveLede({
  object,
  alsoRecorded,
}: {
  object: IntelligenceObject;
  alsoRecorded: IntelligenceObject[];
}) {
  const world = ECONOMIC_WORLDS.find((entry) => entry.analyticsWorld === object.world);
  const permanent = intelligencePath(object.id);
  const hasRail = alsoRecorded.length > 0;

  return (
    /* #48: the same glass card the two non-development states use, so
       the slot keeps one shape whichever state fills it. The content,
       the policy that chose the object and the figures are unchanged.
       #48A: and the other readings for the same period now sit inside
       it, as a rail at `lg` and beneath the chart below that. */
    <section aria-labelledby="lede-heading" className="lx-card rounded-xl p-5 sm:p-6">
      <div className={hasRail ? "lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,16rem)] lg:gap-8" : undefined}>
        <div className="min-w-0">
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
        </div>

        {hasRail && (
          <div className="mt-6 border-t border-line-subtle pt-5 lg:mt-0 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
            <RecentIntelligence objects={alsoRecorded} />
          </div>
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
    <LedeShell
      heading="No new tracked change"
      body="MacroChipz has not recorded a new change in the parts of the economy it tracks. That is not a claim that the economy is quiet — the economy is always operating. It means nothing new has arrived here."
      note="Roughly two thirds of business days have no scheduled release. This is the normal state, not a failure."
    />
  );
}

/**
 * The shell the two non-development states share (Increment #48).
 *
 * ================================================================
 * WHAT #48 REMOVED, AND WHY
 * ================================================================
 *
 * Both states used to render their own four-world grid. With the
 * Living Economy hero directly above — four worlds, photographed,
 * selectable — that grid was the same four links a second time within
 * one screen. It is gone, and the space it used goes to the two
 * actions, which are now buttons rather than a footnote.
 *
 * Quiet is the MAJORITY state: roughly two thirds of business days
 * carry no scheduled release. A state that common gets design
 * attention rather than an apology, and that is the whole reason this
 * component is compact instead of large and empty.
 *
 * Both routes are real and already exist. Nothing here fetches, so
 * this renders identically during an API outage.
 */
function LedeShell({ heading, body, note }: { heading: string; body: string; note: string }) {
  return (
    <section aria-labelledby="lede-heading" className="lx-card rounded-xl p-5 sm:p-6">
      <p className="type-label text-fg-muted">The economy</p>

      <h2 id="lede-heading" className="mt-2 text-xl font-semibold tracking-tight text-fg sm:text-2xl">
        {heading}
      </h2>

      <p className="mt-2 max-w-prose text-sm text-fg-secondary sm:text-base">{body}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          to="/calendar"
          className="inline-flex min-h-11 items-center rounded-lg border border-[color:var(--lx-card-hi)] bg-[color:var(--lx-selected)] px-4 text-sm font-semibold text-fg transition-colors hover:bg-[color:var(--lx-selected-hover)] motion-reduce:transition-none"
        >
          See when the next data is scheduled
        </Link>
        <Link
          to="/explain"
          className="inline-flex min-h-11 items-center rounded-lg border border-line px-4 text-sm font-medium text-fg-secondary transition-colors hover:text-fg motion-reduce:transition-none"
        >
          How every figure is produced
        </Link>
      </div>

      <p className="mt-3 type-meta text-fg-muted">{note}</p>
    </section>
  );
}
