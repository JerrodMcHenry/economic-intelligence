/**
 * Every route that has not yet graduated into framework mode
 * (Increment #40).
 *
 * Renders the existing `<App />` unchanged, so Home, the three economic
 * worlds, Calendar and the 404 keep their current behaviour, their
 * current tests, and their current URLs. This file is the whole reason
 * the migration is incremental rather than a rewrite.
 *
 * PER-ROUTE METADATA (#41). One module serves every one of these paths,
 * so `meta` branches on the pathname. That is enough to give each
 * canonical route a real `<title>` and description in the PRERENDERED
 * HTML -- which is what a crawler and an unfurl read.
 *
 * What it is NOT: crawler-visible economic content. These pages fetch
 * their data in the browser (`useApiResource`), so the prerendered body
 * is the application shell, not a rendered monitor. Making that content
 * crawlable means giving each world a real framework route with a
 * loader, which is a larger change than #41 owns. Recorded honestly in
 * `docs/architecture/rendering-and-permanent-objects.md` §20 rather
 * than implied away.
 */

/* oxlint-disable react/only-export-components --
   A React Router FRAMEWORK MODE route module is required by the
   framework to export `meta` beside its component; that is the route
   contract, not an accident of organisation. */
import App from "../App";
import { ECONOMIC_WORLDS } from "../worlds/registry";

const SITE_NAME = "MacroChipz";

interface RouteMeta {
  title: string;
  description: string;
}

const HOME: RouteMeta = {
  title: `${SITE_NAME} — MacroChipz`,
  description:
    "What changed in the economy, and the evidence behind each conclusion — inflation, jobs and Treasury rates, analysed by versioned methodologies.",
};

const CALENDAR: RouteMeta = {
  title: `Release calendar — ${SITE_NAME}`,
  description: "When the official economic data MacroChipz tracks is scheduled to be published.",
};

const BY_PATH: Readonly<Record<string, RouteMeta>> = {
  "/": HOME,
  "/calendar": CALENDAR,
  ...Object.fromEntries(
    ECONOMIC_WORLDS.map((world) => [
      world.route,
      { title: `${world.label} — ${SITE_NAME}`, description: world.description },
    ]),
  ),
};

export function meta({ location }: { location: { pathname: string } }) {
  const pathname = location.pathname.length > 1 ? location.pathname.replace(/\/$/, "") : location.pathname;
  const route = BY_PATH[pathname];

  // An unknown path gets the site default rather than a guessed title.
  // It is also the 404, which must never be indexed as though it were
  // a page.
  if (!route) {
    return [{ title: HOME.title }, { name: "description", content: HOME.description }, { name: "robots", content: "noindex" }];
  }

  return [
    { title: route.title },
    { name: "description", content: route.description },
    { property: "og:title", content: route.title },
    { property: "og:description", content: route.description },
    { property: "og:type", content: "website" },
    { property: "og:site_name", content: SITE_NAME },
  ];
}

export default function CatchAll() {
  return <App />;
}
