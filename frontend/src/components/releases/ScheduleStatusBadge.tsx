import type { ScheduleStatus } from "../../api/releases.types";

/**
 * Renders the backend's `schedule_status` verbatim -- never recomputed,
 * never re-labeled as "Released"/"Published"/"Data available". A
 * text-first pill: the label carries the meaning on its own, color is
 * reinforcement only. Deliberately quiet, restrained tones -- neither
 * status is good or bad news, so neither gets a saturated "trading"
 * color; PAST_DUE never implies a claim about whether data actually
 * arrived (see docs/architecture/release-intelligence-v1.md #2/#13).
 */
const STATUS_LABEL: Record<ScheduleStatus, string> = {
  SCHEDULED: "Scheduled",
  PAST_DUE: "Past due",
};

const STATUS_CLASSES: Record<ScheduleStatus, string> = {
  SCHEDULED: "bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-600/20",
  PAST_DUE: "bg-neutral-100 text-neutral-600 ring-1 ring-inset ring-neutral-500/20",
};

export function ScheduleStatusBadge({ status }: { status: ScheduleStatus }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_CLASSES[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}
