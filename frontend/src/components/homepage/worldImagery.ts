import type { WorldId } from "../../worlds/registry";

/**
 * THE ONE PLACE A RIGHTS-BEARING IMAGE IS NAMED (Increment #48).
 *
 * ================================================================
 * WHY THIS IS A MODULE AND NOT FOUR `<img>` TAGS
 * ================================================================
 *
 * Before #48 the application contained ZERO images. Introducing them
 * introduces an obligation the rest of the codebase does not have: an
 * asset can be legally unusable in a way that no test of layout,
 * contrast or accessibility will ever catch. So the asset, its
 * attribution and its verification status travel together in one
 * object, and `worldImagery.test.ts` fails the build if a `verified`
 * entry is missing its credit.
 *
 * `worlds/registry.ts` deliberately does NOT hold this. Its own header
 * says a world is "not a CMS" and carries identity and language only;
 * an `image` field there would make the registry an asset manifest.
 *
 * ================================================================
 * THE RULES AN ENTRY MUST SATISFY BEFORE IT MAY BE `verified`
 * ================================================================
 *
 * 1. Documented rights suitable for commercial use -- and the
 *    INSTRUMENT that grants them, not merely a catalogue field that
 *    reads like permission.
 * 2. No identifiable person without a model release; no identifiable
 *    private property without a property release.
 * 3. No third-party trademarks, brand packaging or signage.
 * 4. No legible price, figure or date in frame. This rule came out of
 *    reviewing candidate images for #48: one showed a shelf price tag,
 *    and on an Inflation tile a photographed price reads as a data
 *    claim -- in a product whose whole promise is that every figure
 *    traces to the agency that published it, and a figure that arrived
 *    through a photograph traces to nobody.
 * 5. The credit line is stored here and rendered by the component.
 *
 * Full evidence, the searches run and the rights problems found in the
 * rejected candidates: docs/product/mockups/v48/ASSETS.md.
 *
 * ================================================================
 * THREE WORLDS HAVE NO PHOTOGRAPH, ON PURPOSE
 * ================================================================
 *
 * Inflation, Jobs and Housing are `treatment: "gradient"`. The
 * Highsmith archive is architecture and landscape; the wider
 * no-known-restrictions pool at the Library of Congress is 1880-1950,
 * and a 1940 grocery photograph on a page whose entire claim is
 * CURRENT, SOURCED data misrepresents by context even when every word
 * on the page is true.
 *
 * They render as composed gradients rather than as marked
 * placeholders. A prototype should announce its gaps; a shipped
 * homepage should not wear a chip saying "PLACEHOLDER". The gap is
 * recorded in ASSETS.md, which is where a gap belongs.
 */

/** A photograph whose rights have been verified and documented. */
interface VerifiedPhotograph {
  readonly treatment: "photograph";
  /** Served from `public/`; see `scripts/build-world-images.mjs`. */
  readonly src: string;
  readonly srcSet: string;
  /**
   * The same frames as WebP, offered first. ~25% smaller at equal
   * quality; the JPEG below it is what a browser without WebP gets, so
   * nothing depends on the newer format.
   */
  readonly webpSrcSet: string;
  /**
   * Intrinsic size of the LARGEST derivative, so the browser can
   * reserve the box before the bytes arrive. The element is
   * `object-fit: cover`, so this is an aspect ratio, not a layout size.
   */
  readonly width: number;
  readonly height: number;
  /**
   * What the reader sees on the frame. A SHORT form -- the full
   * required notice is rendered verbatim by `ImageCredits` in the
   * footer region, because at small sizes a one-line credit either
   * truncates or crowds the subject, and a truncated attribution is
   * not an attribution.
   */
  readonly credit: string;
  /**
   * Which part of the frame survives the crop. The tile is far wider
   * than tall on mobile and nearly square on desktop, and the default
   * centre put the horizon through the middle of the colonnade.
   */
  readonly objectPosition: string;
  /**
   * Describes the PHOTOGRAPH, never the economy. "The Treasury
   * building" is a fact about the picture; "borrowing costs are
   * rising" would be a claim, and an alt attribute is not a place to
   * make one.
   */
  readonly alt: string;
}

/** No verified photograph exists yet. Composed, not apologetic. */
interface GradientTreatment {
  readonly treatment: "gradient";
  /** Two stops for the tile wash, inside the luminous violet family. */
  readonly from: string;
  readonly to: string;
  /** Which abstract mark is drawn. Decorative; `aria-hidden`. */
  readonly motif: "shelf" | "people" | "roofs";
}

export type WorldImagery = VerifiedPhotograph | GradientTreatment;

/**
 * The verbatim credit line the Library of Congress asks for, plus the
 * honest statement about the other three worlds. Rendered in full.
 */
export const IMAGE_CREDITS =
  "Rates: U.S. Treasury Department Building, Washington, D.C. Photographs in the Carol M. Highsmith " +
  "Archive, Library of Congress, Prints and Photographs Division (LC-DIG-highsm-16870). Inflation, " +
  "Jobs and Housing are illustrated with abstract artwork; no photograph has been licensed for them.";

const RATES_BASE = "/img/worlds/rates-treasury-highsm-16870";

export const WORLD_IMAGERY: Readonly<Record<WorldId, WorldImagery>> = {
  INFLATION: { treatment: "gradient", from: "#8f7bff", to: "#5b4bc4", motif: "shelf" },
  JOBS: { treatment: "gradient", from: "#7c8cf0", to: "#4a53a8", motif: "people" },
  RATES: {
    treatment: "photograph",
    src: `${RATES_BASE}-960.jpg`,
    srcSet: `${RATES_BASE}-480.jpg 480w, ${RATES_BASE}-960.jpg 960w`,
    webpSrcSet: `${RATES_BASE}-480.webp 480w, ${RATES_BASE}-960.webp 960w`,
    width: 960,
    height: 738,
    credit: "Carol M. Highsmith Archive, Library of Congress",
    objectPosition: "50% 58%",
    alt: "The U.S. Treasury Department building in Washington, D.C., seen from the street.",
  },
  HOUSING: { treatment: "gradient", from: "#a88cf0", to: "#6a4fb0", motif: "roofs" },
};

/**
 * One concise line per world, shown when that world is selected.
 *
 * NOT the registry `description` -- that already appears on the tile,
 * and v47's panel repeating it back at the reader is exactly the
 * duplication #48 set out to remove. Each line is a consumer
 * consequence supported by reviewed explainer copy, and none of them
 * states a figure, a direction or a date.
 */
export const WORLD_DISCOVERY: Readonly<Record<WorldId, string>> = {
  INFLATION: "Falling inflation does not mean falling prices — it means they are rising more slowly.",
  JOBS: "Two different surveys measure the job market, and they can disagree in the same month.",
  RATES:
    "Treasury yields are what it costs the government to borrow — and the reference other borrowing is priced against.",
  HOUSING: "Permits, starts and completions are three stages of one pipeline, and they move at different times.",
};
