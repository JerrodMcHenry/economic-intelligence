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
 */
export function RecentIntelligence({ objects }: { objects: IntelligenceObject[] }) {
  if (objects.length === 0) return null;

  return (
    <section aria-labelledby="recent-intelligence-heading">
      <h2 id="recent-intelligence-heading" className="type-section-heading">
        Also recorded
      </h2>
      <p className="mt-1 text-sm text-fg-muted">
        Other readings MacroChipz has on file for the same period. Each one opens its own evidence.
      </p>

      <ul className="mt-4 divide-y divide-line-subtle border-t border-line-subtle">
        {objects.map((object) => {
          const world = ECONOMIC_WORLDS.find((entry) => entry.analyticsWorld === object.world);
          const name = conceptShortName(
            object.concepts[0],
            object.type === "RATES_MOVEMENT" ? object.payload.series_title : typeLabel(object.type),
          );
          return (
            <li key={object.id} className="py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <Link
                  to={intelligencePath(object.id)}
                  className="text-sm font-medium text-fg underline-offset-4 hover:underline"
                >
                  {name}
                </Link>
                {object.type === "RATES_MOVEMENT" && object.payload.latest_value !== null && (
                  <span className="type-numeric text-sm text-fg">{object.payload.latest_value.toFixed(2)}%</span>
                )}
              </div>
              <p className="mt-0.5 text-xs text-fg-muted">
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
