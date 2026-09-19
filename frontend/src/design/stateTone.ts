/**
 * Visual "tone" for an economic state the backend has already
 * classified -- the presentation half of the five-tone taxonomy that
 * lib/inflationLabels.ts and lib/laborLabels.ts map canonical states
 * onto. Promoted into the design layer by Increment #27B so every tone
 * resolves to a semantic `state-*` token (src/styles/globals.css) with
 * independent light and dark values, instead of raw Tailwind palette
 * colors with no dark-mode counterpart.
 *
 * DOMAIN-NEUTRAL BY CONSTRUCTION: a tone describes *which kind* of
 * classification a label is (a cooler reading, a warmer reading, a
 * steady one, a mixed/caution one, or no conclusion at all) -- never
 * whether it is good or bad news. Cooling inflation is not "success";
 * a warming labor market is not "error". These maps therefore consume
 * only `state-*` tokens and must never reference the generic
 * `feedback-*` (success/error/warning/info) family -- see
 * ./stateTone.test.ts, which fails if they ever do.
 *
 * Color is always reinforcement layered on a text label (Badge), never
 * the sole carrier of meaning.
 */
export type Tone = "cool" | "neutral" | "warm" | "caution" | "unavailable";

export const TONES: ReadonlyArray<Tone> = ["cool", "neutral", "warm", "caution", "unavailable"];

/** Text-first pill treatment (Badge). */
export const TONE_CLASSES: Record<Tone, string> = {
  cool: "bg-state-cool-subtle text-state-cool ring-1 ring-inset ring-state-cool-line",
  neutral: "bg-state-neutral-subtle text-state-neutral ring-1 ring-inset ring-state-neutral-line",
  warm: "bg-state-warm-subtle text-state-warm ring-1 ring-inset ring-state-warm-line",
  caution: "bg-state-caution-subtle text-state-caution ring-1 ring-inset ring-state-caution-line",
  unavailable: "bg-state-unavailable-subtle text-state-unavailable ring-1 ring-inset ring-state-unavailable-line",
};

/** Same five tones as TONE_CLASSES, as plain text color only -- for
 * headline sentences that need tone reinforcement without a pill. */
export const TONE_TEXT_CLASSES: Record<Tone, string> = {
  cool: "text-state-cool",
  neutral: "text-state-neutral",
  warm: "text-state-warm",
  caution: "text-state-caution",
  unavailable: "text-state-unavailable",
};

/** Same five tones, as a quiet left-border accent color for grouping a
 * block of related content (e.g. one What Changed subsection). */
export const TONE_BORDER_CLASSES: Record<Tone, string> = {
  cool: "border-state-cool-line",
  neutral: "border-state-neutral-line",
  warm: "border-state-warm-line",
  caution: "border-state-caution-line",
  unavailable: "border-state-unavailable-line",
};
