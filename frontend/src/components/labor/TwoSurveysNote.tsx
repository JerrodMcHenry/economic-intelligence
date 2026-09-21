import { Disclosure } from "../Disclosure";

/**
 * Why payroll employment and unemployment can tell different stories
 * (Increment #41).
 *
 * THIS IS THE JOBS WORLD'S LOAD-BEARING DISTINCTION, and until #41 the
 * frontend did not show it at all. The backend has always been explicit
 * about it -- `app/concepts/registry.py` makes `universe` a REQUIRED
 * field precisely so this can never be lost:
 *
 *   NONFARM_PAYROLL_EMPLOYMENT  universe NONFARM_PAYROLL_JOBS
 *                               source program CES
 *   UNEMPLOYMENT_RATE           universe CIVILIAN_LABOR_FORCE_PERSONS
 *                               source program CPS
 *
 * Two different universes, counted by two different surveys. One counts
 * JOBS on employer payrolls; the other counts PEOPLE and asks whether
 * they have work. A person with two jobs is two payroll jobs and one
 * employed person. Someone who stops looking for work leaves the labour
 * force without ever appearing as a job lost.
 *
 * The consumer-facing job here is to make that difference
 * understandable WITHOUT erasing it -- #41's instruction is explicit:
 * "Do not present them as measurements of the exact same population."
 * So this is plain English about a real methodological boundary, not a
 * simplification of one.
 *
 * It states no economic conclusion, and deliberately does not say which
 * measure is "right" when they disagree. `labor_v1.0` answers that by
 * classifying the combination as MIXED; this component only explains
 * why disagreement is possible in the first place.
 */
export function TwoSurveysNote() {
  return (
    <Disclosure summary="Why these two can tell different stories">
      <div className="max-w-prose space-y-3 text-sm text-fg-secondary">
        <p>
          They count different things. Payroll employment counts <strong className="font-medium text-fg">jobs</strong>{" "}
          on employer payrolls. The unemployment rate counts{" "}
          <strong className="font-medium text-fg">people</strong> and asks whether they have work and are looking for
          it.
        </p>

        <dl className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-line p-3">
            <dt className="font-medium text-fg">Payroll employment</dt>
            <dd className="mt-1 text-fg-secondary">
              A survey of employers. Counts filled jobs, so one person holding two jobs counts twice.
            </dd>
            <dd className="mt-1 text-xs text-fg-muted">
              Establishment survey (CES) · measured in jobs
            </dd>
          </div>
          <div className="rounded-md border border-line p-3">
            <dt className="font-medium text-fg">Unemployment</dt>
            <dd className="mt-1 text-fg-secondary">
              A survey of households. Counts people, so someone who stops looking for work leaves the count entirely
              rather than appearing as a job lost.
            </dd>
            <dd className="mt-1 text-xs text-fg-muted">
              Household survey (CPS) · measured as a percentage of the labour force
            </dd>
          </div>
        </dl>

        <p>
          Because they measure different populations, they can move in different directions in the same month without
          either being wrong. MacroChipz keeps them separate for that reason, and reports the overall Jobs state as
          Mixed when its two components disagree — rather than averaging them into a single number that would describe
          neither.
        </p>
      </div>
    </Disclosure>
  );
}
