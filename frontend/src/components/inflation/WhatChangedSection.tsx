import { Fragment, type ReactNode } from "react";

import type {
  ChangeEvent,
  ConfirmationSectionChanges,
  InflationWhatChangedResult,
  SeriesMomentumSectionChanges,
  TargetSectionChanges,
} from "../../api/inflation.types";
import { formatMetricValueOrUnavailable, formatPercentagePoints, formatPeriodPair } from "../../lib/format";
import {
  changeFieldLabel,
  confirmationRelationshipLabelOrRaw,
  confirmationRelationshipTone,
  inflationStateLabelOrRaw,
  inflationStateTone,
  inflationStateToneOrNeutral,
  TONE_BORDER_CLASSES,
  TONE_TEXT_CLASSES,
  type Tone,
} from "../../lib/inflationLabels";

/**
 * Itemized non-headline change events, aligned as a compact three-column
 * grid (field · previous → current · delta) rather than a run-on
 * sentence -- every value is exactly what the backend returned; nothing
 * here is recomputed by subtracting values client-side. 1M readings
 * (context-only per the methodology) render visually muted relative to
 * 3M/6M/12M rows.
 */
function ChangeEventList({ events }: { events: ChangeEvent[] }) {
  if (events.length === 0) return null;
  return (
    <div className="mt-3 grid grid-cols-[minmax(7rem,auto)_1fr_auto] items-baseline gap-x-4 gap-y-1.5 text-sm">
      {events.map((event, index) => {
        const isContextOnly = event.field === "r_1m_annualized";
        return (
          <Fragment key={`${event.component}-${event.event_type}-${event.field}-${index}`}>
            <span className="text-fg-muted">{changeFieldLabel(event.field)}</span>
            <span className={`tabular-nums ${isContextOnly ? "text-fg-muted" : "text-fg-secondary"}`}>
              {formatMetricValueOrUnavailable(event.previous_value)}
              <span aria-hidden="true" className="mx-1.5 text-fg-faint">
                →
              </span>
              {formatMetricValueOrUnavailable(event.current_value)}
            </span>
            <span className="text-right tabular-nums text-fg-muted">
              {event.delta !== null ? formatPercentagePoints(event.delta) : null}
            </span>
          </Fragment>
        );
      })}
    </div>
  );
}

function SectionHeader({ label, periodPair }: { label: string; periodPair: string }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
      <h3 className="text-sm font-semibold text-fg">{label}</h3>
      <span className="text-xs font-medium tabular-nums text-fg-muted">{periodPair}</span>
    </div>
  );
}

/** Wraps one subsection with a quiet left-border accent, colored by its
 * own current tone -- purely a scanning aid grouping "everything about
 * this component" into one visually distinguishable block. */
function SubsectionBlock({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <div className={`border-l-2 py-0.5 pl-4 ${TONE_BORDER_CLASSES[tone]}`}>{children}</div>;
}

/**
 * A momentum-shaped section (Core PCE, Headline PCE, or Headline CPI).
 * Precedence, in order: a STATE_CHANGED/AVAILABILITY_* event on the
 * "state" field is always the headline; otherwise, an empty `changes`
 * list means nothing changed at all; otherwise metrics changed but the
 * state itself didn't -- rendered as an explicit "State remains X"
 * (never silently collapsed into "No change"), except when both periods
 * are INSUFFICIENT_DATA, where "remains" would misleadingly read as a
 * direction.
 */
function MomentumSectionSummary({ label, section }: { label: string; section: SeriesMomentumSectionChanges }) {
  if (!section.comparison_available) {
    return (
      <SubsectionBlock tone="unavailable">
        <h3 className="text-sm font-semibold text-fg">{label}</h3>
        <p className="mt-1 text-sm text-fg-muted">Previous-period comparison unavailable.</p>
      </SubsectionBlock>
    );
  }

  const stateEvent = section.changes.find((event) => event.field === "state");
  const metricEvents = section.changes.filter((event) => event.field !== "state");

  let headline: string;
  let headlineClass = "text-fg-muted";
  let borderTone: Tone = section.current_evidence ? inflationStateTone(section.current_evidence.state) : "neutral";

  if (stateEvent) {
    const prev =
      typeof stateEvent.previous_value === "string"
        ? inflationStateLabelOrRaw(stateEvent.previous_value)
        : formatMetricValueOrUnavailable(stateEvent.previous_value);
    const curr =
      typeof stateEvent.current_value === "string"
        ? inflationStateLabelOrRaw(stateEvent.current_value)
        : formatMetricValueOrUnavailable(stateEvent.current_value);
    headline = `${label} state: ${prev} → ${curr}`;
    const currentTone = typeof stateEvent.current_value === "string" ? inflationStateToneOrNeutral(stateEvent.current_value) : "neutral";
    headlineClass = `font-semibold ${TONE_TEXT_CLASSES[currentTone]}`;
    borderTone = currentTone;
  } else if (section.changes.length === 0) {
    headline = "No canonical changes detected.";
  } else if (section.current_evidence?.state === "INSUFFICIENT_DATA") {
    headline = "Insufficient data in both periods.";
  } else {
    headline = section.current_evidence
      ? `State remains ${inflationStateLabelOrRaw(section.current_evidence.state)}.`
      : "No canonical changes detected.";
    if (section.current_evidence) {
      headlineClass = `font-semibold ${TONE_TEXT_CLASSES[inflationStateTone(section.current_evidence.state)]}`;
    }
  }

  return (
    <SubsectionBlock tone={borderTone}>
      <SectionHeader label={label} periodPair={formatPeriodPair(section.previous_period, section.current_period)} />
      <p className={`mt-1 text-sm ${headlineClass}`}>{headline}</p>
      <ChangeEventList events={metricEvents} />
    </SubsectionBlock>
  );
}

/**
 * Confirmation has no independent "state" field of its own -- only a
 * relationship. A `CONFIRMATION_CHANGED` event is always the relevant
 * headline when present (availability loss/restoration is itself a
 * relationship transition to/from UNAVAILABLE, so no separate branch is
 * needed for it).
 */
function ConfirmationSectionSummary({ section }: { section: ConfirmationSectionChanges }) {
  if (!section.comparison_available) {
    return (
      <SubsectionBlock tone="unavailable">
        <h3 className="text-sm font-semibold text-fg">Confirmation</h3>
        <p className="mt-1 text-sm text-fg-muted">Previous-period comparison unavailable.</p>
      </SubsectionBlock>
    );
  }

  const relationshipChanged =
    section.relationship_changed && section.previous_relationship !== null && section.current_relationship !== null;

  const headline = relationshipChanged
    ? `Confirmation: ${confirmationRelationshipLabelOrRaw(section.previous_relationship as string)} → ${confirmationRelationshipLabelOrRaw(section.current_relationship as string)}`
    : section.changes.length === 0
      ? "No canonical changes detected."
      : null;

  const borderTone: Tone = section.current_relationship ? confirmationRelationshipTone(section.current_relationship) : "neutral";
  const headlineClass = relationshipChanged && section.current_relationship
    ? `font-semibold ${TONE_TEXT_CLASSES[confirmationRelationshipTone(section.current_relationship)]}`
    : "text-fg-muted";

  return (
    <SubsectionBlock tone={borderTone}>
      <SectionHeader
        label="Confirmation"
        periodPair={formatPeriodPair(section.previous_confirmation_period, section.current_confirmation_period)}
      />
      {headline && <p className={`mt-1 text-sm ${headlineClass}`}>{headline}</p>}
      <ChangeEventList events={section.changes} />
    </SubsectionBlock>
  );
}

/** Target has no state concept -- only headline_pce_yoy/target_gap_pp metric events. */
function TargetSectionSummary({ section }: { section: TargetSectionChanges }) {
  if (!section.comparison_available) {
    return (
      <SubsectionBlock tone="unavailable">
        <h3 className="text-sm font-semibold text-fg">Target</h3>
        <p className="mt-1 text-sm text-fg-muted">Previous-period comparison unavailable.</p>
      </SubsectionBlock>
    );
  }

  return (
    <SubsectionBlock tone="neutral">
      <SectionHeader label="Target" periodPair={formatPeriodPair(section.previous_period, section.current_period)} />
      {section.changes.length === 0 ? (
        <p className="mt-1 text-sm text-fg-muted">No canonical changes detected.</p>
      ) : (
        <ChangeEventList events={section.changes} />
      )}
    </SubsectionBlock>
  );
}

/**
 * Canonical output of `GET /api/v1/monitors/inflation/changes`, rendered
 * deterministically. Each subsection below carries its own independent
 * comparison-period pair -- there is deliberately no single page-wide
 * "as of" period, since Core PCE, confirmation, target, and the two
 * headline series can each have last updated on a different release
 * schedule.
 */
export function WhatChangedSection({ whatChanged }: { whatChanged: InflationWhatChangedResult }) {
  return (
    <section aria-labelledby="what-changed-heading">
      <h2 id="what-changed-heading" className="text-sm font-medium text-fg-muted">
        What changed
      </h2>
      <div className="mt-4 max-w-3xl space-y-6">
        <MomentumSectionSummary label="Core PCE" section={whatChanged.primary_momentum_changes} />
        <ConfirmationSectionSummary section={whatChanged.confirmation_changes} />
        <TargetSectionSummary section={whatChanged.target_changes} />
        <MomentumSectionSummary label="Headline PCE" section={whatChanged.headline_pce_changes} />
        <MomentumSectionSummary label="Headline CPI" section={whatChanged.headline_cpi_changes} />
      </div>
    </section>
  );
}
