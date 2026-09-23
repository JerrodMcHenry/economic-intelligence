/**
 * sitemap.xml for permanent MacroChipz objects (Increment #40).
 *
 * Lists exactly what was PRERENDERED -- nothing speculative, and no
 * thin pages. A URL appears here only if a crawler fetching it will
 * find real prerendered HTML, so the sitemap cannot promise pages that
 * do not exist.
 *
 * Requires `VITE_SITE_URL`: a sitemap needs absolute URLs, and guessing
 * the origin would publish links to somewhere MacroChipz is not.
 */
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const CLIENT_DIR = join(process.cwd(), "build", "client");

/**
 * A prerendered page that declares `robots: noindex` is excluded
 * (#46C).
 *
 * Prerendering and indexing are separate decisions, and until #46C
 * nothing in MacroChipz needed them to differ. The story prototype
 * does: it is static content that SHOULD be built as real HTML, and it
 * carries a canonical pointing at `/explain/fed-and-mortgage-rates`
 * because that page — not the prototype — is the one that should rank.
 * Listing it in the sitemap while its own HTML says `noindex` would
 * hand a crawler two contradictory instructions about the same URL.
 *
 * Read from the built HTML rather than from a hand-maintained list, so
 * the sitemap cannot drift from what the pages actually declare.
 */
function declaresNoindex(path) {
  const file = join(CLIENT_DIR, path === "/" ? "index.html" : join(path, "index.html"));
  const html = readFileSync(file, "utf8");
  return /<meta[^>]+name="robots"[^>]+content="[^"]*noindex/i.test(html);
}

function prerenderedPaths(directory, prefix = "") {
  const found = [];
  for (const entry of readdirSync(directory)) {
    const full = join(directory, entry);
    if (statSync(full).isDirectory()) {
      found.push(...prerenderedPaths(full, `${prefix}/${entry}`));
    } else if (entry === "index.html") {
      found.push(prefix === "" ? "/" : prefix);
    }
  }
  return found;
}

const site = (process.env.VITE_SITE_URL ?? "").trim().replace(/\/$/, "");
if (!site) {
  console.warn("[sitemap] VITE_SITE_URL is not set — skipping sitemap.xml (it requires absolute URLs).");
} else {
  const prerendered = [...new Set(prerenderedPaths(CLIENT_DIR))].sort();
  const paths = prerendered.filter((path) => !declaresNoindex(path));
  const excluded = prerendered.length - paths.length;
  const body = paths.map((path) => `  <url><loc>${site}${path}</loc></url>`).join("\n");
  writeFileSync(
    join(CLIENT_DIR, "sitemap.xml"),
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`,
  );
  console.log(
    `[sitemap] wrote ${paths.length} prerendered URL(s)` +
      (excluded > 0 ? `; excluded ${excluded} that declare noindex.` : "."),
  );
}
