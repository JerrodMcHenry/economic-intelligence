import { explainersForConcept, explainersForWorld } from "../../explainers/registry";
import type { WorldId } from "../../worlds/registry";

/**
 * Restrained explainer entry points (Increment #44).
 *
 * A short list of questions, not a Learn section. World pages remain
 * intelligence products: the economic fact comes first, and this sits
 * beneath it as an offer rather than a syllabus.
 *
 * Plain anchors rather than router links, deliberately: these appear on
 * pages whose test harnesses render them without router context, and a
 * full navigation to a prerendered explainer is perfectly fine.
 */
export function UnderstandWorld({ world }: { world: WorldId }) {
  const explainers = explainersForWorld(world);
  if (explainers.length === 0) return null;

  return (
    <section aria-labelledby="understand-heading">
      <h2 id="understand-heading" className="type-section-heading">
        Understand this
      </h2>
      <ul className="mt-3 space-y-1.5">
        {explainers.map((explainer) => (
          <li key={explainer.id}>
            <a
              href={`/explain/${explainer.slug}`}
              className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
            >
              {explainer.question}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * The same offer on a permanent intelligence object, matched by
 * CONCEPT id (#38) rather than by title text.
 *
 * Placed after the fact, never before it: #40B's hierarchy puts the
 * number first, and education does not get to jump the queue.
 */
export function UnderstandConcept({ conceptId }: { conceptId: string | undefined }) {
  const explainers = conceptId ? explainersForConcept(conceptId) : [];
  if (explainers.length === 0) return null;

  return (
    <div className="mt-8">
      <h2 className="type-section-heading">Understand this</h2>
      <ul className="mt-2 space-y-1.5">
        {explainers.slice(0, 3).map((explainer) => (
          <li key={explainer.id}>
            <a
              href={`/explain/${explainer.slug}`}
              className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
            >
              {explainer.question}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
