import type { ReplayOutcome } from "../../api/monitorHistory.types";
import { REPLAY_OUTCOME_CLASSES, REPLAY_OUTCOME_DESCRIPTION, REPLAY_OUTCOME_LABEL } from "../../lib/historyLabels";

/**
 * Whether a recorded conclusion still reproduces from the data
 * available when it was made (Increment #32).
 *
 * Text-first, exactly like every other badge here: the outcome is
 * readable as a word, and colour is reinforcement layered on top rather
 * than the carrier of meaning. The colours come from the generic
 * `feedback-*` family rather than the economic `state-*` family,
 * because this is a verdict about MacroChipz's own integrity, not an
 * economic classification -- see `historyLabels.ts` for the full
 * reasoning.
 *
 * A `MISMATCH` is never softened. It carries the error treatment and a
 * screen-reader description saying plainly that it is a data-integrity
 * issue rather than an economic signal.
 */
export function ReplayStatusBadge({ outcome, className = "" }: { outcome: ReplayOutcome; className?: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${REPLAY_OUTCOME_CLASSES[outcome]} ${className}`}
      title={REPLAY_OUTCOME_DESCRIPTION[outcome]}
    >
      {REPLAY_OUTCOME_LABEL[outcome]}
      <span className="sr-only"> — {REPLAY_OUTCOME_DESCRIPTION[outcome]}</span>
    </span>
  );
}
