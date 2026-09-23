/**
 * Build the responsive derivatives for the one VERIFIED world
 * photograph (#48 production integration).
 *
 * Run by hand, and its OUTPUT IS COMMITTED. Nothing in the build
 * depends on this script or on the network: `npm run build` must work
 * on a machine that has never run it.
 *
 * Source of truth for rights, attribution and the required credit line:
 * docs/product/mockups/v48/ASSETS.md. In short — Carol M. Highsmith,
 * Library of Congress, LC-DIG-highsm-16870; the photographer dedicated
 * the archive's rights to the American people for copyright-free
 * access, which is the commercial basis, not the item-level "no known
 * restrictions" advisory.
 *
 * WHY `public/` AND NOT A HASHED VITE IMPORT. The project has no
 * `vite-env.d.ts`, so `import url from "./x.jpg"` has no type and
 * would need one added for the type-check, the prerender pass and
 * vitest alike. The filename already carries the Library's own digital
 * id plus the width, so it identifies its content without a hash. The
 * trade-off accepted: these URLs cannot be served `immutable`.
 *
 * Budget, asserted below rather than hoped for: <= 120 KB for the
 * largest derivative.
 */
import { mkdirSync, statSync } from "node:fs";
import { join } from "node:path";
import sharp from "sharp";

const SOURCE = join(process.cwd(), "..", "docs", "product", "mockups", "v48", "img", "rates-treasury-highsm-16870.jpg");
const OUT = join(process.cwd(), "public", "img", "worlds");
const BASE = "rates-treasury-highsm-16870";
/**
 * TWO widths, not three. The tile is ~174 CSS px at a 390px viewport
 * and ~380 CSS px in the desktop hero's left column, so 960 already
 * covers a 2.5x device pixel ratio at the largest size the image is
 * ever painted. A 1440 derivative was built, measured at 162 KB as
 * JPEG -- over budget -- and DROPPED rather than having the budget
 * raised for a size nothing requests.
 */
const WIDTHS = [480, 960];
const MAX_BYTES = 120 * 1024;

mkdirSync(OUT, { recursive: true });

const meta = await sharp(SOURCE).metadata();
console.log(`source ${meta.width}x${meta.height}`);

const failures = [];
for (const width of WIDTHS) {
  const jpg = join(OUT, `${BASE}-${width}.jpg`);
  const webp = join(OUT, `${BASE}-${width}.webp`);
  await sharp(SOURCE).resize({ width }).jpeg({ quality: 74, mozjpeg: true }).toFile(jpg);
  await sharp(SOURCE).resize({ width }).webp({ quality: 72 }).toFile(webp);
  for (const file of [jpg, webp]) {
    const bytes = statSync(file).size;
    console.log(`${file.split("/").pop()}  ${(bytes / 1024).toFixed(1)} KB`);
    if (bytes > MAX_BYTES) failures.push(`${file} is ${(bytes / 1024).toFixed(1)} KB, over the ${MAX_BYTES / 1024} KB budget`);
  }
}

if (failures.length > 0) {
  for (const failure of failures) console.error(`FAIL ${failure}`);
  process.exit(1);
}
console.log("world images built within budget");
