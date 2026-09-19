import type { ScheduleStatus } from "../../api/releases.types";

/**
 * Renders the backend's `schedule_status` verbatim -- never recomputed,
 * never re-labeled as "Released"/"Published"/"Data available". A
 * text-first pill: the label carries the meaning on its own, color is
 * reinforcement only. Deliberately quiet, restrained tones -- neither
 * status is good or bad news, so neither gets a saturated "trading"
 * color; PAST_DUE never implies a claim about whether data actually
 * arrived (see docs/architecture/release-intelligence-v1.md #2/#13).
 *
 * A schedule status is release *logistics*, not an economic reading, so
 * it uses the generic informational feedback token -- never an economic
 * `state-*` tone (it previously shared the "cool" state's sky palette).
 */
const STATUS_LABEL: Record<ScheduleStatus, string> = {
  SCHEDULED: "Scheduled",
  PAST_DUE: "Past due",
};

const STATUS_CLASSES: Record<ScheduleStatus, string> = {
  SCHEDULED: "bg-feedback-info-subtle text-feedback-info ring-1 ring-inset ring-feedback-info-line",
  PAST_DUE: "bg-surface-secondary text-fg-secondary ring-1 ring-inset ring-line-strong",
};

export function ScheduleStatusBadge({ status }: { status: ScheduleStatus }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_CLASSES[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}
