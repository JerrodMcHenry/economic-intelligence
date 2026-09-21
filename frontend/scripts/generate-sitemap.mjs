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
import { readdirSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const CLIENT_DIR = join(process.cwd(), "build", "client");

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
  const paths = [...new Set(prerenderedPaths(CLIENT_DIR))].sort();
  const body = paths.map((path) => `  <url><loc>${site}${path}</loc></url>`).join("\n");
  writeFileSync(
    join(CLIENT_DIR, "sitemap.xml"),
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`,
  );
  console.log(`[sitemap] wrote ${paths.length} prerendered URL(s).`);
}
