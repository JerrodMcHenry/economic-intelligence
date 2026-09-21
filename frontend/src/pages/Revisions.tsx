import { Link } from "react-router-dom";

import { listHomepageIntelligence } from "../api/intelligence";
import { useApiResource } from "../api/useApiResource";
import { Card } from "../components/Card";
import { Disclosure } from "../components/Disclosure";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { PageHeader } from "../components/PageHeader";
import { RevisionComparison } from "../components/revisions/RevisionComparison";
import { conceptShortName } from "../lib/intelligenceLanguage";
import { intelligencePath } from "../lib/siteUrl";
import { selectRevisions } from "../revisions/selectRevisions";
import { ECONOMIC_WORLDS } from "../worlds/registry";

const ERROR_MESSAGE = "Revision history could not be loaded.";

/**
 * Revision Intelligence (Increment #43).
 *
 * Answers one consumer question: *"the number changed — did that change
 * what we thought was happening?"*
 *
 * NOT a fourth economic world. Revisions happen across Inflation and
 * Jobs, so this is a cross-world capability and is deliberately absent
 * from `ECONOMIC_WORLDS` (a test asserts that).
 *
 * THE CURRENT STATE IS EMPTY, AND HONESTLY SO. Measured before this
 * page was written: 1,072 versioned observation rows, every one
 * `is_backfilled = true`; zero observations with a second version;
 * zero superseded rows; all 358 `OBSERVATION_CHANGE` objects are
 * `NEW`. **MacroChipz has never captured a genuine revision.** So this
 * page teaches the feature rather than faking it — no placeholder
 * revision, no sample data dressed as history.
 */
export function RevisionsPage() {
  const intelligence = useApiResource(listHomepageIntelligence);
  const revisions = intelligence.status === "success" ? selectRevisions(intelligence.data.items) : [];

  return (
    <div>
      <PageHeader
        title="Revision history"
        description="Economic data is often revised after it is first published. When that happens, MacroChipz shows what changed — and whether its own conclusion changed with it."
      />

      <div className="mt-8 space-y-8">
        {intelligence.status === "loading" && <LoadingSkeleton label="Loading revision history" heightClassName="h-40" />}
        {intelligence.status === "error" && <ErrorMessage message={ERROR_MESSAGE} onRetry={intelligence.reload} />}

        {intelligence.status === "success" && revisions.length === 0 && <WatchingForRevisions />}

        {intelligence.status === "success" &&
          revisions.map((revision) => (
            <Card as="article" key={revision.id}>
              <h2 className="type-section-heading">
                {conceptShortName(revision.concepts[0], revision.payload.series_title ?? revision.payload.provider_series_id)} ·{" "}
                <time dateTime={revision.effective_period}>{revision.effective_period}</time>
              </h2>
              <div className="mt-4">
                <RevisionComparison object={revision} />
              </div>
              <p className="mt-6">
                <Link
                  to={intelligencePath(revision.id)}
                  className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
                >
                  Show the evidence →
                </Link>
              </p>
            </Card>
          ))}

        <WhyDataGetsRevised />
      </div>
    </div>
  );
}

/**
 * The empty state, which is the state this page is actually in.
 *
 * It has real work to do: explain what a revision is, what MacroChipz
 * will show when one arrives, since when it can truthfully track them,
 * and why it cannot reconstruct the ones that came before. A dead
 * "nothing here yet" panel would waste the only moment a reader is
 * curious about the feature.
 */
function WatchingForRevisions() {
  return (
    <section aria-labelledby="watching-heading">
      <Card as="article">
        <h2 id="watching-heading" className="type-section-heading">
          MacroChipz is watching for revisions
        </h2>

        <p className="mt-2 max-w-prose text-sm text-fg-secondary">
          No revision has been recorded yet. MacroChipz keeps a record of what it knew at each point in time, so when a
          published number changes, it can show you the change rather than quietly replacing the old value.
        </p>

        <h3 className="mt-6 type-label text-fg-muted">What you will see when one arrives</h3>
        <ol className="mt-2 max-w-prose space-y-1 text-sm text-fg-secondary">
          <li>1. What the number was when MacroChipz first recorded it.</li>
          <li>2. What it was revised to, and by how much.</li>
          <li>3. Whether MacroChipz&rsquo;s own conclusion changed as a result — or stayed the same.</li>
          <li>4. The evidence behind all of it: source, series, dates and methodology.</li>
        </ol>

        <div className="mt-6">
          <HistoricalBoundary />
        </div>
      </Card>
    </section>
  );
}

/**
 * THE HISTORICAL BOUNDARY (#43 §18) — mandatory, and reusable.
 *
 * #31 backfilled 1,072 existing observations when versioning was
 * introduced. Those values establish what MacroChipz held at import
 * time. They establish **nothing** about what providers had published
 * before then, and this component exists so no surface is ever tempted
 * to imply otherwise.
 *
 * It deliberately states no date. The stored `recorded_from` on a
 * backfilled row is the migration timestamp, not an economic boundary,
 * and printing it would dress a database event as a fact about the
 * economy.
 */
export function HistoricalBoundary() {
  return (
    <Disclosure summary="Why older revisions cannot be shown">
      <div className="max-w-prose space-y-2 text-sm text-fg-secondary">
        <p>
          MacroChipz can only prove a revision it watched happen — one where it had already recorded a value and then
          saw the provider publish a different one.
        </p>
        <p>
          Older observations were imported as a starting baseline when MacroChipz began keeping point-in-time history.
          For those, it knows the value it imported, but not what had been published for that period beforehand. Those
          earlier readings are not recoverable, so MacroChipz does not present them as originals.
        </p>
      </div>
    </Disclosure>
  );
}

/**
 * Curated, static education (#43 §16).
 *
 * Deliberately GENERIC. It describes mechanisms that cause revisions in
 * general and attributes none of them to a particular agency, because
 * MacroChipz holds no first-party documentation of any specific
 * provider's revision policy. Naming one would be inventing source
 * knowledge.
 */
function WhyDataGetsRevised() {
  return (
    <section aria-labelledby="why-revised-heading">
      <h2 id="why-revised-heading" className="type-section-heading">
        Why economic data gets revised
      </h2>

      <div className="mt-2 max-w-prose space-y-2 text-sm text-fg-secondary">
        <p>
          A first release is usually an estimate built from the reports that had arrived by the deadline. More complete
          information tends to turn up afterwards, and statistical agencies update their published figures to reflect
          it.
        </p>
        <p>
          Seasonal adjustment and periodic benchmarking can also change an estimate without anyone having made a
          mistake. <strong className="font-medium text-fg">A revision does not automatically mean the first number
          was wrong</strong> — it usually means more is now known.
        </p>
        <p>
          MacroChipz reports the change and whether its own conclusion moved with it. It does not claim to know why a
          provider revised a figure.
        </p>
      </div>

      <p className="mt-5 text-sm text-fg-muted">Explore the economy as it stands now:</p>
      <ul className="mt-2 flex flex-wrap gap-x-6 gap-y-2">
        {ECONOMIC_WORLDS.map((world) => (
          <li key={world.id}>
            <Link
              to={world.route}
              className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
            >
              {world.label} →
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
