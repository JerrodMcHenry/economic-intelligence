import { useState } from "react";
import { Link } from "react-router-dom";

import { ECONOMIC_WORLDS, world as worldById, type WorldId } from "../../worlds/registry";
import { WORLD_DISCOVERY, WORLD_IMAGERY, type WorldImagery } from "./worldImagery";

/**
 * THE LIVING ECONOMY HERO (Increment #48).
 *
 * ================================================================
 * WHAT IT IS FOR
 * ================================================================
 *
 * One job: a visitor who has never heard of MacroChipz should, within
 * one screen, understand that this is four connected parts of the
 * economy — and be one tap from the part they came for.
 *
 * It replaces `WorldOrientation` (#45B), whose job was the same and
 * which is retired in this increment. It does NOT replace THE LEDE,
 * which makes a different claim under a different authority:
 *
 *     THE LEDE     "this CHANGED"     — `homepage_presentation_v1.0`
 *     THIS         "these EXIST"      — `worlds/registry.ts`
 *
 * ================================================================
 * THE HARD RULE: NO EDGES BETWEEN WORLDS
 * ================================================================
 *
 * The mortgage story's diagram is a model where an edge means
 * "reaches" and every edge is defended by a reviewed source. The four
 * worlds here are NAVIGATION CATEGORIES. A line drawn between
 * Inflation and Jobs would assert a relationship nobody wrote down.
 *
 * So this borrows the lighting of that diagram and none of its
 * topology, and a test asserts no `<line>`, `<path>` or marker joins
 * two world tiles. `HowTheyRelate` states the one defended
 * cross-world relationship, in words, further down the page.
 *
 * ================================================================
 * IT FETCHES NOTHING
 * ================================================================
 *
 * Registry-driven and static, which is why it survives an API outage
 * — and an outage is exactly when a reader is most likely to be
 * confused about what this site is. It is also why it prerenders with
 * its real content rather than as an empty shell.
 *
 * SELECTION IS NOT NAVIGATION. Selecting updates the panel and leaves
 * focus on the control; a separate, explicit link enters the world.
 * One world is selected at all times, never zero — a hero that opens
 * explaining nothing has wasted the only screen it gets.
 */

/**
 * Rates, because it is the acquisition wedge (Product Constitution §3)
 * and the world that arriving readers are looking for. It is also the
 * only world with a verified photograph, which is a consequence of the
 * choice rather than a reason for it.
 */
const DEFAULT_WORLD: WorldId = "RATES";

/**
 * How wide a tile actually is, so the browser can choose a derivative
 * before layout exists. MEASURED, not estimated: 167px at a 390px
 * viewport (43vw), 287px at 1024 (28vw), and 390px at 1440 -- where it
 * stops growing, because `max-w-app` caps the column at 76rem. A
 * single `vw` value would over-serve the widest case and under-serve
 * the narrowest, so the cap is stated as the literal it is.
 */
const SIZES = "(min-width: 1280px) 390px, (min-width: 1024px) 28vw, 45vw";

export function LivingEconomyHero() {
  const [selected, setSelected] = useState<WorldId>(DEFAULT_WORLD);
  // `world()` throws on an unknown id rather than defaulting to the
  // first entry, so a future mistake surfaces here instead of silently
  // explaining Inflation while Housing is lit.
  const world = worldById(selected);

  return (
    <section aria-labelledby="hero-heading" className="lx-hero">
      <p className="type-label text-fg-muted">The living economy</p>

      <h1 id="hero-heading" className="type-page-title mt-2 max-w-3xl text-balance">
        Explore the living economy.
      </h1>

      <p className="mt-2.5 max-w-prose text-fg-secondary">
        Four parts of the U.S. economy. Every figure traces back to the agency that published it, with the date it was
        published.
      </p>

      <div className="mt-5">
        {/*
         * TWO-UP ON A PHONE, FOUR ACROSS FROM `md`, and the panel
         * BELOW at every width rather than beside.
         *
         * A side panel was built first and measured wrong: at 1440 the
         * tiles form a 2x2 block 522px tall while the panel is 172px,
         * so two thirds of the right-hand column is empty. Four across
         * is also what the approved prototype does, and it puts the
         * selected world's line directly under the control that
         * changed it instead of off to one side.
         */}
        <ul className="grid grid-cols-2 gap-2.5 sm:gap-3 md:grid-cols-4">
          {ECONOMIC_WORLDS.map((entry) => (
            <li key={entry.id}>
              <WorldTile
                label={entry.label}
                description={entry.description}
                imagery={WORLD_IMAGERY[entry.id]}
                selected={entry.id === selected}
                onSelect={() => setSelected(entry.id)}
              />
            </li>
          ))}
        </ul>

        {/*
         * THE DISCOVERY STRIP (#48B).
         *
         * It was a card 154px tall carrying two lines of text and one
         * button, which on a 390px screen is a fifth of the first
         * viewport spent on the least dense thing in the hero. It is
         * now a strip: the description and the route to the world sit
         * on ONE row from `sm`, and stack only where the line genuinely
         * needs the width.
         *
         * `aria-live="polite"` and NOT focus movement: a screen-reader
         * user hears the new line without being thrown out of the row
         * they are still exploring. The CTA keeps its 44px height at
         * every width -- the strip is shorter because the padding and
         * the gap shrank, never because the target did.
         */}
        <div
          className="lx-card mt-2.5 flex flex-col gap-2.5 rounded-xl px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-5"
          aria-live="polite"
        >
          <p className="max-w-prose text-[13.5px] leading-snug text-fg-secondary sm:text-sm">
            <span className="font-semibold text-fg">{world.label}</span> — {WORLD_DISCOVERY[world.id]}
          </p>
          <Link
            to={world.route}
            className="inline-flex min-h-11 flex-none items-center gap-2 self-start rounded-lg border border-[color:var(--lx-card-hi)] bg-[color:var(--lx-selected)] px-4 text-sm font-semibold text-fg transition-colors hover:bg-[color:var(--lx-selected-hover)] motion-reduce:transition-none sm:self-auto"
          >
            Open {world.label}
            <span aria-hidden="true">→</span>
          </Link>
        </div>
      </div>
    </section>
  );
}

function WorldTile({
  label,
  description,
  imagery,
  selected,
  onSelect,
}: {
  label: string;
  description: string;
  imagery: WorldImagery;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      /* The whole tile is the target, so 44px is never in question —
         the constraint that governs instead is that the CAPTION must
         stay legible over whatever is behind it. */
      className={[
        "lx-tile relative block w-full overflow-hidden rounded-xl text-left transition-[border-color,transform] motion-reduce:transition-none",
        selected ? "lx-tile-on" : "",
      ].join(" ")}
    >
      <TileArt imagery={imagery} alt={imagery.treatment === "photograph" ? imagery.alt : ""} />

      {/* The caption gradient is the reason white text is readable at
          the bottom edge of a photograph whose brightness we do not
          control. It is not decoration and must not be tuned away. */}
      <span className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-[rgba(8,9,12,0.92)] via-[rgba(8,9,12,0.62)] to-transparent px-3 pb-2.5 pt-8">
        <span className="block text-sm font-bold tracking-tight text-[#eef0ff]">{label}</span>
      </span>

      {/* The registry sentence, for assistive technology only. It is
          already the tile's meaning; printing it on a 174px-wide tile
          would shrink it to unreadable. */}
      <span className="sr-only">{description}</span>

      {imagery.treatment === "photograph" && (
        /*
         * THE CREDIT CARRIES ITS OWN SCRIM, and that is not a style
         * choice. Measured over this photograph's pale stone pediment,
         * white text on the image reached 1.12:1 -- the brightest part
         * of the frame is exactly where the top-right corner sits. A
         * text-shadow made it look survivable and changed the measured
         * ratio not at all.
         *
         * The scrim makes the contrast a property of the component
         * instead of a property of the picture, so the next verified
         * photograph cannot quietly break a required legal notice.
         */
        <span className="pointer-events-none absolute right-1.5 top-1.5 max-w-[calc(100%-12px)] rounded-md bg-[rgba(8,9,12,0.62)] px-1.5 py-0.5 text-right text-[9px] font-semibold leading-tight text-[#eef0ff]">
          {imagery.credit}
        </span>
      )}
    </button>
  );
}

/**
 * The image, or the composed gradient that stands in for one.
 *
 * `loading="eager"` and `fetchPriority="high"`: this is above the fold
 * on every viewport and is the LCP candidate, so lazy-loading it would
 * be an anti-pattern rather than an optimisation. `width`/`height`
 * reserve the box, so nothing below it moves when the bytes land.
 */
function TileArt({ imagery, alt }: { imagery: WorldImagery; alt: string }) {
  if (imagery.treatment === "photograph") {
    return (
      <>
        <picture>
          <source type="image/webp" srcSet={imagery.webpSrcSet} sizes={SIZES} />
          <img
            src={imagery.src}
            srcSet={imagery.srcSet}
            sizes={SIZES}
            width={imagery.width}
            height={imagery.height}
            alt={alt}
            loading="eager"
            fetchPriority="high"
            className="block aspect-[3/2] w-full object-cover"
            style={{ objectPosition: imagery.objectPosition }}
          />
        </picture>
        {/* Darkens the lower half only, so the caption has contrast
            without the subject being flattened. */}
        <span className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-[rgba(10,8,20,0.12)] to-[rgba(8,9,12,0.55)]" />
      </>
    );
  }

  return (
    <span
      aria-hidden="true"
      className="relative block aspect-[3/2] w-full"
      style={{ background: `linear-gradient(155deg, ${imagery.from} -30%, ${imagery.to} 55%, #140e28 100%)` }}
    >
      <TileMotif motif={imagery.motif} />
    </span>
  );
}

/**
 * An abstract mark, not an illustration of an economic claim.
 *
 * Shelves, figures and roofs — the subject of the world, drawn as
 * geometry. Nothing here encodes a quantity, a direction or a trend;
 * a chart-shaped mark would be read as data, which is precisely what
 * these tiles do not have.
 */
function TileMotif({ motif }: { motif: "shelf" | "people" | "roofs" }) {
  const common = {
    className: "absolute inset-0 h-full w-full opacity-[0.34]",
    viewBox: "0 0 160 106",
    fill: "none" as const,
    stroke: "#e6e8ff",
    strokeWidth: 1.6,
    "aria-hidden": true as const,
  };

  if (motif === "shelf") {
    return (
      <svg {...common}>
        {[0, 1].map((row) =>
          [0, 1, 2, 3, 4].map((col) => (
            <rect key={`${row}-${col}`} x={38 + col * 17} y={34 + row * 22} width={11} height={15} rx={1.5} />
          )),
        )}
        <path d="M34 53h96M34 75h96" />
      </svg>
    );
  }

  if (motif === "people") {
    return (
      <svg {...common}>
        <circle cx={58} cy={42} r={7} />
        <circle cx={80} cy={35} r={8.5} />
        <circle cx={103} cy={42} r={7} />
        <path d="M45 74c0-8 6-14 13-14s13 6 13 14M67 74c0-9 6-16 13-16s13 7 13 16M89 74c0-8 6-14 13-14s13 6 13 14" />
      </svg>
    );
  }

  return (
    <svg {...common}>
      <path d="M40 72V52l14-11 14 11v20zM74 72V44l16-13 16 13v28z" />
      <path d="M112 72V54l11-9 11 9v18z" />
    </svg>
  );
}
