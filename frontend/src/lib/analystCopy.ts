import type { AnalystContextType } from "../api/analyst.types";

/**
 * Every user-facing string in the MacroChipz Analyst surface
 * (Increment #33), as frozen templates.
 *
 * **Suggested questions are deterministic UI copy.** They are written
 * here, reviewed here, and shipped here. The Analyst is never called to
 * generate them: a suggestion produced by a model would be an
 * unreviewed prompt the product puts in a user's mouth, and it would
 * turn opening a page into a billable request.
 *
 * The heading deliberately says "Ask MacroChipz", not "Ask AI". The
 * Analyst speaks for the system; it is not a separate oracle sitting
 * beside it.
 */

export const HEADING = "Ask MacroChipz";

export const UNAVAILABLE_COPY = "MacroChipz Analyst is unavailable.";

export const INPUT_LABEL = "Ask a question about this page";

export const SUBMIT_LABEL = "Ask";

export const PENDING_LABEL = "MacroChipz is answering";

export const ERROR_MESSAGE = "MacroChipz Analyst could not answer right now.";

export const ANSWER_HEADING = "Answer";
export const EVIDENCE_HEADING = "Evidence used";
export const LIMITATIONS_HEADING = "Limitations";
export const SUGGESTED_HEADING = "Suggested questions";

/**
 * The standing disclosure. The Analyst explains MacroChipz's
 * deterministic conclusions; it does not produce them, and it is not
 * financial advice. Both halves matter and both are always shown.
 */
export const ANALYST_DISCLOSURE =
  "The Analyst explains MacroChipz's deterministic analysis in plain English. It does not calculate economic states, make forecasts, or give financial advice.";

const INTRO: Record<AnalystContextType, string> = {
  INFLATION: "Understand this inflation assessment.",
  LABOR: "Understand this labor market assessment.",
  RATES: "Understand this rates intelligence.",
  MONITOR_HISTORY: "Understand this historical result and how it compares with today's data.",
};

export function introCopy(context: AnalystContextType): string {
  return INTRO[context];
}

/**
 * Deterministic suggestions per context. Phrased as questions a reader
 * would actually ask, and answerable from the context packet the server
 * builds for that same page -- a suggestion the evidence cannot support
 * would just teach users the Analyst is evasive.
 */
const SUGGESTED: Record<AnalystContextType, readonly string[]> = {
  INFLATION: [
    "Why is inflation in this state?",
    "What evidence supports this conclusion?",
    "What changed recently?",
  ],
  LABOR: [
    "Why is the labor market in this state?",
    "What does the employment evidence show?",
    "What changed recently?",
  ],
  RATES: [
    "What does the 2s10s spread represent?",
    "What changed in rates?",
    "What is inflation compensation?",
  ],
  MONITOR_HISTORY: [
    "Why is today's view different from what MacroChipz knew then?",
    "What does the replay status mean?",
    "What does it mean that some inputs were reconstructed?",
  ],
};

export function suggestedQuestions(context: AnalystContextType): readonly string[] {
  return SUGGESTED[context];
}
