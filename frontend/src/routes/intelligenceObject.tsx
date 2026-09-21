/**
 * The permanent page for one Structured Intelligence Object
 * (Increment #40; loader split out in #40A).
 *
 * The first route to graduate out of `App`'s `<Routes>` tree into
 * React Router framework mode, because it is the first route that
 * needs what framework mode provides: prerendered HTML a crawler can
 * read, and route-specific metadata that survives being shared.
 *
 * This is the CLIENT-SIDE variant: it loads the object in the browser.
 * `./intelligenceObject.prerendered.tsx` re-exports everything here and
 * adds the build-time `loader`; `src/routes.ts` picks between them,
 * because under `ssr: false` a `loader` export is legal only on a route
 * the build actually prerenders (#40A).
 *
 * This page CONSUMES #39. It formats facts and never recomputes them --
 * no change magnitude, no revision amount, no economic state, no
 * evidence association, no world classification. Guarded by
 * `src/test/no-intelligence-derivation.test.ts`.
 */

/* oxlint-disable react/only-export-components --
   A React Router FRAMEWORK MODE route module is required by the
   framework to export `loader`, `clientLoader`, `meta` and
   `ErrorBoundary` beside its component; that is the route contract,
   not an accident of organisation. The rule guards Fast Refresh, a
   development-only convenience, and splitting these exports into
   another file would break the contract to satisfy it. */
import { isRouteErrorResponse, useLoaderData, useParams, useRouteError } from "react-router";

import { getIntelligenceObject } from "../api/intelligence";
import type { IntelligenceObject } from "../api/intelligence.types";
import { isApiError } from "../api/errors";
import { IntelligenceSee } from "../components/intelligence/IntelligenceSee";
import { IntelligenceVerify } from "../components/intelligence/IntelligenceVerify";
import { PageContainer } from "../components/PageContainer";
import { ShareButton } from "../components/ShareButton";
import { headline } from "../lib/intelligenceLanguage";
import { intelligenceMeta } from "../lib/intelligenceMetadata";
import { absoluteUrl, intelligencePath } from "../lib/siteUrl";

export interface LoaderData {
  object: IntelligenceObject | null;
  intelligenceId: string;
}

/**
 * The one fetch both variants share.
 *
 * A 404 becomes a not-found STATE -- a fact about the world, and a page
 * the reader should see. Anything else is rethrown: at build time that
 * fails the build rather than emitting a permanent URL with nothing
 * behind it, and in the browser it surfaces the `ErrorBoundary`. The
 * distinction is the whole point; see `NotFound` and `ErrorBoundary`.
 */
export async function loadIntelligence(intelligenceId: string): Promise<LoaderData> {
  try {
    return { object: await getIntelligenceObject(intelligenceId), intelligenceId };
  } catch (error) {
    if (isApiError(error) && error.status === 404) return { object: null, intelligenceId };
    throw error;
  }
}

/** Runs in the browser, for any path that was not prerendered. */
export async function clientLoader({ params }: { params: { intelligenceId?: string } }): Promise<LoaderData> {
  return loadIntelligence(params.intelligenceId ?? "");
}

export function meta({ data }: { data?: LoaderData }) {
  return intelligenceMeta(data?.object ?? null, data?.intelligenceId ?? "");
}

export default function IntelligenceObjectRoute() {
  const { object, intelligenceId } = useLoaderData() as LoaderData;

  if (object === null) return <NotFound />;

  const url = absoluteUrl(intelligencePath(intelligenceId));

  return (
    <PageContainer>
      <article className="py-8">
        <IntelligenceSee object={object} />

        <IntelligenceVerify object={object} />

        {/* SHARE closes the page (#40B): SEE -> UNDERSTAND -> CONTEXT
            -> EXPLORE -> VERIFY -> SHARE. It stays easy to find
            because "Check this" above it is three collapsed
            disclosures, not a wall of data. */}
        <div className="mt-8 border-t border-line pt-6">
          {/* Falls back to the relative path when no site origin is
              configured, so sharing still works in development. */}
          <ShareButton
            objectType={object.type}
            title={headline(object)}
            url={url ?? intelligencePath(intelligenceId)}
          />
        </div>
      </article>
    </PageContainer>
  );
}

function NotFound() {
  return (
    <PageContainer>
      <div className="py-16">
        <h1 className="type-page-title">No intelligence here</h1>
        <p className="mt-3 max-w-prose text-fg-secondary">
          MacroChipz has nothing recorded at this address. The link may be mistyped, or it may point at something
          MacroChipz never published.
        </p>
        <a href="/" className="mt-6 inline-block text-sm font-medium text-fg-secondary hover:text-fg">
          Go to MacroChipz →
        </a>
      </div>
    </PageContainer>
  );
}

/**
 * A genuine failure -- the backend was unreachable, or returned
 * something unusable. Deliberately distinct from "not found": one is a
 * fact about the world, the other is a fault.
 */
export function ErrorBoundary() {
  const error = useRouteError();
  const params = useParams();
  const isNotFound = isRouteErrorResponse(error) && error.status === 404;

  if (isNotFound) return <NotFound />;

  return (
    <PageContainer>
      <div className="py-16">
        <h1 className="type-page-title">This could not be loaded</h1>
        <p className="mt-3 max-w-prose text-fg-secondary">
          MacroChipz could not read the intelligence at this address. This is a problem on our side, not with the
          link. Try again shortly.
        </p>
        <p className="mt-4 text-sm text-fg-muted">Reference: {params.intelligenceId}</p>
      </div>
    </PageContainer>
  );
}
