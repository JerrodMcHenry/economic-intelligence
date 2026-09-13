import { TONE_CLASSES, type Tone } from "../../lib/inflationLabels";

const SIZE_CLASSES = {
  md: "px-2.5 py-0.5 text-sm font-medium",
  lg: "px-3 py-1 text-base font-medium",
  // Reserved for the page's single dominant state (InflationHero) --
  // still the same text-first pill, just scaled up to be the strongest
  // visual object on the page rather than a second color/typography system.
  xl: "px-4 py-1.5 text-2xl font-semibold sm:text-3xl",
} as const;

/**
 * A text-first pill: the label is always legible on its own, and color
 * (from `TONE_CLASSES`) is layered on only as reinforcement -- never the
 * sole carrier of meaning. Used for both `InflationState` and
 * `ConfirmationRelationship` values via the tone/label lookups in
 * ../../lib/inflationLabels.
 */
export function Badge({ label, tone, size = "md" }: { label: string; tone: Tone; size?: keyof typeof SIZE_CLASSES }) {
  return <span className={`inline-flex items-center rounded-full ${SIZE_CLASSES[size]} ${TONE_CLASSES[tone]}`}>{label}</span>;
}
