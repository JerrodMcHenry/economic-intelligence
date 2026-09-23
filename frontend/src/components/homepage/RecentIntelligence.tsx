import { Link } from "react-router-dom";

import type { IntelligenceObject } from "../../api/intelligence.types";
import { conceptShortName, typeLabel, worldLabel } from "../../lib/intelligenceLanguage";
import { intelligencePath } from "../../lib/siteUrl";
import { ECONOMIC_WORLDS } from "../../worlds/registry";

/**
 * Bounded recent intelligence (Increment #42).
 *
 * A short, finite list — never a feed. It shows what
 * `homepage_presentation_v1.0` selected after THE LEDE, capped at
 * `WHAT_CHANGED_LIMIT`, one object per concept so the same fact is not
 * repeated six times in six maturities.
 *
 * Every row states its world and the period the data describes. No row
 * claims novelty, urgency or importance: the honest time anchor is
 * `effective_period`, because `published_at` is null on every object
 * MacroChipz holds and `recorded_at` is a backfill timestamp.
 *
 * ================================================================
 * #48A: NESTED, NOT MERGED
 * ================================================================
 *
 * It now renders INSIDE the lede's card rather than as a section of
 * its own, because on this data it is always the same world and the
 * same period as the headline reading -- five Treasury maturities for
 * one date, split across two sections with two headings and two rules
 * between them.
 *
 * What did NOT change is the distinction the two make. THE LEDE is
 * chosen by `homepage_presentation_v1.0`; these are what
 * `selection.whatChanged` returned. So the heading stays, demoted to
 * `h3` because it is now inside the lede's `h2` -- one composition,
 * still two clearly separate claims. Merging the values into a single
 * undifferentiated list would have made the policy invisible, which is
 * the one thing this page may not do.
 */
export function RecentIntelligence({ objects }: { objects: IntelligenceObject[] }) {
  if (objects.length === 0) return null;

  return (
    <section aria-labelledby="recent-intelligence-heading">
      <h3 id="recent-intelligence-heading" className="type-label text-fg-muted">
        Also recorded
      </h3>
      <p className="mt-1.5 text-xs text-fg-muted">
        Other readings on file for the same period. Each one opens its own evidence.
      </p>

      <ul className="mt-3 grid gap-x-5 sm:grid-cols-2 lg:grid-cols-1">
        {objects.map((object) => {
          const world = ECONOMIC_WORLDS.find((entry) => entry.analyticsWorld === object.world);
          const name = conceptShortName(
            object.concepts[0],
            object.type === "RATES_MOVEMENT" ? object.payload.series_title : typeLabel(object.type),
          );
          return (
            <li key={object.id} className="border-t border-line-subtle py-2.5">
              <div className="flex items-baseline justify-between gap-x-3">
                <Link
                  to={intelligencePath(object.id)}
                  className="min-w-0 text-sm font-medium text-fg underline-offset-4 hover:underline"
                >
                  {name}
                </Link>
                {object.type === "RATES_MOVEMENT" && object.payload.latest_value !== null && (
                  <span className="type-numeric flex-none text-sm font-semibold text-fg">
                    {object.payload.latest_value.toFixed(2)}%
                  </span>
                )}
              </div>
              <p className="mt-0.5 type-meta text-fg-muted">
                {world?.label ?? worldLabel(object.world)} ·{" "}
                <time dateTime={object.effective_period}>{object.effective_period}</time>
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
