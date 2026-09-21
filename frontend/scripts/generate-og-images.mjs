/**
 * Open Graph card generation (Increment #40, ADR-039 / #36A).
 *
 * Satori (JSX -> SVG) -> sharp (SVG -> PNG), at BUILD TIME. No headless
 * browser, no page screenshot, and no runtime service: the cards are
 * static assets emitted alongside the prerendered HTML, so nothing new
 * runs in production.
 *
 * The card is composed from STRUCTURED FACTS off the #39 object -- the
 * same facts the page renders. It is not a screenshot of the page and
 * it does not reimplement the web design system; it uses a small,
 * deliberate token subset (see PALETTE) so a card is recognisably
 * MacroChipz without dragging Tailwind into an image pipeline.
 *
 * FAILURE RULES (#40 section 16):
 *
 * - No usable font anywhere -> the whole step FAILS the build. Without
 *   a font no card can be produced, so every `og:image` would 404, and
 *   shipping that silently is worse than stopping.
 * - One object missing optional facts -> that object gets the GENERIC
 *   MacroChipz card. Truthful, just less specific.
 * - One object missing REQUIRED facts (no headline) -> that object's
 *   card is skipped explicitly and logged. A misleading card is never
 *   published to avoid an empty one.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import satori from "satori";
import sharp from "sharp";

const WIDTH = 1200;
const HEIGHT = 630;
const OUT_DIR = join(process.cwd(), "build", "client", "og");

/**
 * A deliberately small subset of the `--mc-*` design tokens, restated
 * here as literals because Satori cannot resolve CSS custom properties.
 * Kept short on purpose: this is a card, not a second design system.
 */
const PALETTE = {
  canvas: "#0d1117",
  fg: "#f0f6fc",
  fgMuted: "#9198a1",
  line: "#30363d",
  brand: "#4493f8",
};

/** Fonts Satori can actually use: ttf/otf/woff only -- never woff2. */
const FONT_CANDIDATES = [
  "/System/Library/Fonts/Supplemental/Arial.ttf",
  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
  "/usr/share/fonts/dejavu/DejaVuSans.ttf",
  "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
];

export function loadFont() {
  for (const path of FONT_CANDIDATES) {
    if (existsSync(path)) return { name: "OG", data: readFileSync(path), weight: 400, style: "normal" };
  }
  throw new Error(
    `[og] No usable TTF font found. Tried:\n  ${FONT_CANDIDATES.join("\n  ")}\n` +
      `Satori accepts ttf/otf/woff (never woff2). Refusing to build: without a font every og:image would 404.`,
  );
}

/** The card, as plain objects -- Satori's JSX-shaped input, no React. */
function card({ eyebrow, headline, figures, footer }) {
  const el = (type, props, ...children) => ({ type, props: { ...props, children: children.flat() } });
  return el(
    "div",
    {
      style: {
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        backgroundColor: PALETTE.canvas,
        padding: "64px",
        fontFamily: "OG",
      },
    },
    el(
      "div",
      { style: { display: "flex", flexDirection: "column" } },
      el("div", { style: { display: "flex", fontSize: 26, color: PALETTE.brand, letterSpacing: 1 } }, eyebrow),
      el(
        "div",
        { style: { display: "flex", fontSize: 62, color: PALETTE.fg, marginTop: 20, lineHeight: 1.15 } },
        headline,
      ),
    ),
    figures.length > 0
      ? el(
          "div",
          { style: { display: "flex", gap: "48px", borderTop: `2px solid ${PALETTE.line}`, paddingTop: "28px" } },
          ...figures.map((figure) =>
            el(
              "div",
              { style: { display: "flex", flexDirection: "column" } },
              el("div", { style: { display: "flex", fontSize: 22, color: PALETTE.fgMuted } }, figure.label),
              el("div", { style: { display: "flex", fontSize: 40, color: PALETTE.fg, marginTop: 6 } }, figure.value),
            ),
          ),
        )
      : el("div", { style: { display: "flex" } }, ""),
    el(
      "div",
      { style: { display: "flex", justifyContent: "space-between", fontSize: 24, color: PALETTE.fgMuted } },
      el("div", { style: { display: "flex" } }, "MacroChipz"),
      el("div", { style: { display: "flex" } }, footer),
    ),
  );
}

const WINDOW_LABELS = {
  "1_SESSION": "1 session",
  "5_SESSIONS": "5 sessions",
  "21_SESSIONS": "21 sessions",
  "63_SESSIONS": "63 sessions",
};

function basisPoints(value) {
  if (value === null || value === undefined) return null;
  const rounded = Math.round(value);
  if (rounded === 0) return "unchanged";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded)} bp`;
}

/** Card content from an object's structured facts. `null` = skip it. */
export function compose(object) {
  const worldLabels = { inflation: "Inflation", jobs: "Jobs", rates: "Rates" };
  const eyebrow = (worldLabels[object.world] ?? "MacroChipz").toUpperCase();
  const footer = object.effective_period ?? "";

  if (object.type === "RATES_MOVEMENT") {
    const value = object.payload?.latest_value;
    if (typeof value !== "number" || !object.payload?.series_title) return null;
    const figures = (object.payload.changes ?? [])
      .filter((change) => change.available && change.change_basis_points !== null)
      .slice(0, 3)
      .map((change) => ({
        label: WINDOW_LABELS[change.window] ?? change.window,
        value: basisPoints(change.change_basis_points) ?? "—",
      }));
    return {
      eyebrow,
      headline: `${object.payload.series_title} is ${value.toFixed(2)}%`,
      figures,
      footer,
    };
  }

  // Every other type gets a truthful, less specific card rather than a
  // fabricated one.
  return { eyebrow, headline: object.id ?? "MacroChipz intelligence", figures: [], footer };
}

export async function render(content, font) {
  const svg = await satori(card(content), { width: WIDTH, height: HEIGHT, fonts: [font] });
  return sharp(Buffer.from(svg)).png().toBuffer();
}

async function main() {
  const base = (process.env.VITE_API_BASE_URL ?? "").trim().replace(/\/$/, "");
  if (!base) {
    console.warn("[og] VITE_API_BASE_URL is not set — skipping OG card generation (no objects to render).");
    return;
  }

  const font = loadFont();
  mkdirSync(OUT_DIR, { recursive: true });

  // The generic card. Always written, so a card exists even when a
  // specific one could not be composed.
  writeFileSync(
    join(OUT_DIR, "default.png"),
    await render(
      { eyebrow: "MACROCHIPZ", headline: "Economic intelligence you can check", figures: [], footer: "" },
      font,
    ),
  );

  const limit = Number(process.env.MACROCHIPZ_OG_LIMIT ?? 25);
  const response = await fetch(`${base}/api/v1/intelligence?type=RATES_MOVEMENT&limit=${limit}`, {
    signal: AbortSignal.timeout(30_000),
  });
  if (!response.ok) throw new Error(`[og] ${base} returned ${response.status}; refusing to emit partial cards.`);

  const { items } = await response.json();
  let written = 0;
  let skipped = 0;
  for (const object of items) {
    const content = compose(object);
    if (content === null) {
      // Explicit, logged, and NOT replaced with something misleading.
      console.warn(`[og] skipped ${object.id}: required facts missing for a truthful card.`);
      skipped += 1;
      continue;
    }
    writeFileSync(join(OUT_DIR, `${encodeURIComponent(object.id)}.png`), await render(content, font));
    written += 1;
  }
  console.log(`[og] wrote ${written} card(s), skipped ${skipped}, plus the generic default.`);
}

// Runs the generation only when this file is EXECUTED as the build
// step. Importing it -- which the tests do, to exercise `compose` --
// must not reach out to an API or write into the build directory.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
