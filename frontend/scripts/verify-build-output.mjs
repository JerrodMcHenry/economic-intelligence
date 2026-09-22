/**
 * Build-output verification (Increment #40, section 22).
 *
 * The prerendered HTML is the artifact a crawler reads and an unfurl
 * scrapes. Its correctness cannot be asserted from a unit test, because
 * it is produced by the build, not by application code -- so it is
 * asserted HERE, against the real output, on every build.
 *
 * This step FAILS THE BUILD. A permanent URL that ships without its
 * metadata is not a cosmetic defect: the link is permanent, and the
 * first scrape is what social platforms cache.
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const CLIENT_DIR = join(process.cwd(), "build", "client");
const INTELLIGENCE_DIR = join(CLIENT_DIR, "intelligence");

/**
 * Patterns that must NEVER appear in a generated artifact. Deliberately
 * matches the SHAPE of a secret rather than any specific value, so this
 * file itself stays safe to read and to commit.
 */
const SECRET_PATTERNS = [
  /\b[A-Z0-9_]*(?:SECRET|PASSWORD|PRIVATE_KEY)[A-Z0-9_]*\s*[:=]\s*\S/,
  /\bpostgres(?:ql)?:\/\/[^\s"']+/,
  /\bsk-[A-Za-z0-9]{16,}/,
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
];

const failures = [];

function check(condition, message) {
  if (!condition) failures.push(message);
}

if (!existsSync(INTELLIGENCE_DIR)) {
  // Not a failure by itself: a build with no VITE_API_BASE_URL
  // legitimately prerenders no objects. Say so plainly rather than
  // passing silently.
  console.warn("[verify] No prerendered intelligence pages — nothing to verify.");
  process.exit(0);
}

const pages = readdirSync(INTELLIGENCE_DIR, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => join(INTELLIGENCE_DIR, entry.name, "index.html"))
  .filter((path) => existsSync(path));

check(pages.length > 0, "build/client/intelligence exists but contains no index.html.");

const siteUrl = (process.env.VITE_SITE_URL ?? "").trim().replace(/\/$/, "");

for (const path of pages) {
  const html = readFileSync(path, "utf8");
  const where = path.replace(`${process.cwd()}/`, "");

  // The metadata must be IN THE HTML, not applied by client script:
  // a crawler that does not execute JavaScript has to see it.
  check(/<title>[^<]+—\s*MacroChipz<\/title>/.test(html), `${where}: no baked <title>.`);
  check(/<meta[^>]+name="description"[^>]+content="[^"]{20,}"/.test(html), `${where}: no description.`);
  for (const property of ["og:title", "og:description", "og:type", "og:site_name"]) {
    check(html.includes(`property="${property}"`), `${where}: missing ${property}.`);
  }
  check(html.includes('name="twitter:card"'), `${where}: missing twitter:card.`);

  // Body content, not an empty shell waiting for a fetch.
  check(/<h1[^>]*>[^<]/.test(html), `${where}: no prerendered <h1> — the page is an empty shell.`);

  // Visual evidence (#40C) must be IN the HTML: a chart that needs a
  // browser fetch to appear is invisible to a crawler and to anyone
  // whose JavaScript has not run yet.
  const scriptless = html.replace(/<script[\s\S]*?<\/script>/g, "");
  const charts = scriptless.match(/<svg[^>]*role="img"[\s\S]*?<\/svg>/g) ?? [];
  check(charts.length === 2, `${where}: expected 2 prerendered chart SVGs (one per breakpoint), found ${charts.length}.`);
  for (const chart of charts) {
    check(
      /preserveAspectRatio="xMidYMid meet"/.test(chart),
      `${where}: a chart does not preserve its aspect ratio (ADR-041).`,
    );
    check(/<path d="M [\d.]+ [\d.]+ L/.test(chart), `${where}: a chart has no plotted line.`);
    check(/aria-label="[^"]{40,}"/.test(chart), `${where}: a chart has no meaningful accessible description.`);
  }

  // Canonical and og:image only when an origin is configured; when it
  // is, they must be present and absolute.
  if (siteUrl) {
    check(html.includes(`rel="canonical"`), `${where}: VITE_SITE_URL is set but no canonical link.`);
    check(html.includes(`content="${siteUrl}/intelligence/`), `${where}: og:url is not absolute.`);
    check(html.includes(`content="${siteUrl}/og/`), `${where}: og:image is not absolute.`);
  }

  for (const pattern of SECRET_PATTERNS) {
    check(!pattern.test(html), `${where}: matches a secret-shaped pattern (${pattern}).`);
  }
}

// #44: explainers are finite and static, so unlike the world pages
// their SUBSTANCE must be in the prerendered HTML -- that is the whole
// point of a page meant to be found by search or opened from a video.
const EXPLAIN_DIR = join(CLIENT_DIR, "explain");
if (existsSync(EXPLAIN_DIR)) {
  const explainers = readdirSync(EXPLAIN_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => join(EXPLAIN_DIR, entry.name, "index.html"))
    .filter((path) => existsSync(path));

  check(explainers.length > 0, "build/client/explain exists but contains no prerendered explainer.");

  for (const path of explainers) {
    const where = path.replace(`${process.cwd()}/`, "");
    const html = readFileSync(path, "utf8");
    const scriptless = html.replace(/<script[\s\S]*?<\/script>/g, "");
    const text = scriptless.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

    check(/<h1[^>]*>[^<]/.test(scriptless), `${where}: no prerendered <h1>.`);
    check(text.length > 1200, `${where}: only ${text.length} chars of text without JavaScript — the explanation is not really there.`);
    check(/What it actually is/.test(text), `${where}: missing the explanation body.`);
    check(/Explore next/.test(text), `${where}: missing the onward rabbit hole.`);
    check(/How we know/.test(text), `${where}: missing the basis section.`);
    check(/<title>[^<]+—\s*MacroChipz<\/title>/.test(html), `${where}: no baked <title>.`);
  }
}

if (failures.length > 0) {
  console.error(`[verify] ${failures.length} problem(s) in the build output:`);
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}

console.log(`[verify] ${pages.length} prerendered intelligence page(s) + explainers: metadata present, charts drawn, content present, no secrets.`);
