import { getEmploymentSituationProcessingStatus, getLaborMonitor, getLaborStateDuration, getLaborWhatChanged } from "../api/labor";
import { getAnalystAvailability } from "../api/analyst";
import { getPayrollObservations, getUnemploymentObservations } from "../api/series";
import { getLaborHistory } from "../api/monitorHistory";
import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import { useApiResource } from "../api/useApiResource";
import { AskMacroChipz } from "../components/analyst/AskMacroChipz";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { IntelligenceHistorySection } from "../components/history/IntelligenceHistorySection";
import { DataBasisNote } from "../components/inflation/DataBasisNote";
import { EmploymentSection } from "../components/labor/EmploymentSection";
import { LaborHero } from "../components/labor/LaborHero";
import { LatestDataDetected } from "../components/labor/LatestDataDetected";
import { MethodologyDisclosure } from "../components/labor/MethodologyDisclosure";
import { RelevantRelease } from "../components/labor/RelevantRelease";
import { SurveyThreshold } from "../components/labor/SurveyThreshold";
import { UnemploymentSection } from "../components/labor/UnemploymentSection";
import { Disclosure } from "../components/Disclosure";
import { WhatChangedSection } from "../components/labor/WhatChangedSection";
import { UnderstandWorld } from "../components/explainers/UnderstandLinks";
import { laborStateLabelOrRaw, laborStateToneOrNeutral } from "../lib/laborLabels";
import { formatPeriod } from "../lib/format";

const MONITOR_ERROR_MESSAGE = "Jobs data could not be loaded.";
const CHANGES_ERROR_MESSAGE = "What changed could not be loaded.";
const PROCESSING_STATUS_ERROR_MESSAGE = "Release-processing status is temporarily unavailable.";
const UPCOMING_ERROR_MESSAGE = "Upcoming releases could not be loaded.";
const RECENT_ERROR_MESSAGE = "Recent releases could not be loaded.";
const OBSERVATIONS_ERROR_MESSAGE = "Published observations could not be loaded.";

/**
 * The Labor Market Monitor product page (Increment #20E.2). Loads
 * `GET /api/v1/monitors/labor`, `GET /api/v1/monitors/labor/changes`,
 * `GET /api/v1/monitors/labor/state-duration` (Increment #24D),
 * Upcoming/Recent releases, and Employment Situation's own scoped
 * processing-status evidence -- six completely independent resources
 * (see useApiResource), each with its own loading/error UI; one
 * failing never blanks, blocks, or fabricates any other section, the
 * same discipline /inflation and / already establish. `stateDuration`
 * is fetched here (the page), not inside `LaborHero`, matching this
 * page's own established "page owns every resource, components stay
 * dumb" convention -- one clear owner per resource.
 *
 * Section hierarchy (docs/architecture/labor-ui-v1.md §7, extended by
 * Increment #32): Current State -> Employment -> Unemployment -> What
 * Changed -> Latest Data Detected -> Relevant Release -> Intelligence
 * History -> Evidence & methodology. #32 inserts its section at
 * position 7 rather than anywhere earlier specifically to preserve
 * §7's own deliberate adjacencies -- "Latest Data Detected" must stay
 * next to "Relevant Release" because they concern the same release --
 * and because recorded history reads naturally just before the
 * page-level methodology disclosure.
 * State Duration V1 is a new line inside the existing Current State
 * (Hero) section, not an eighth section (frozen contract
 * docs/product/state-duration-v1.md §40). Every economic value, state,
 * and relationship rendered below is exactly what those endpoints
 * returned; this page composes and formats, it does not calculate.
 */
export function JobsPage() {
  const monitor = useApiResource(getLaborMonitor);
  const whatChanged = useApiResource(getLaborWhatChanged);
  const stateDuration = useApiResource(getLaborStateDuration);
  const processingStatus = useApiResource(getEmploymentSituationProcessingStatus);
  const upcoming = useApiResource(fetchUpcomingReleases);
  const recent = useApiResource(fetchRecentReleases);
  const history = useApiResource(getLaborHistory);
  const analyst = useApiResource(getAnalystAvailability);
  /* #51B: the two published series, each an INDEPENDENT resource.
     Either failing leaves the other, and the monitor's own
     classification, rendered exactly as before. */
  const payroll = useApiResource(getPayrollObservations);
  const unemploymentSeries = useApiResource(getUnemploymentObservations);

  return (
    <div>
      {/*
       * THE HERO (#51B), replacing `PageHeader`.
       *
       * The standfirst is VERBATIM from `explain.jobs-two-surveys`.
       * The old one described the page rather than the subject, and
       * #51A measured four state words reaching the reader before any
       * sentence they could use.
       */}
      <header>
        <p className="type-label text-fg-muted">Jobs</p>
        <h1 className="type-page-title mt-2 max-w-3xl text-balance">Two surveys. Two answers.</h1>
        <p className="mt-3 max-w-prose text-fg-secondary">
          One counts jobs on employer payrolls, the other counts people and asks whether they have work. They measure
          different populations, so they can disagree without either being wrong.
        </p>

        {monitor.status === "success" && (
          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-fg-muted">
            <span className="inline-flex items-center gap-2 rounded-full border border-line px-3 py-1">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-brand" />
              Both surveys through {formatPeriod(monitor.data.evaluation_period)}
            </span>
            <span>Published by the U.S. Bureau of Labor Statistics</span>
          </div>
        )}
        <div className="mt-3">
          <DataBasisNote />
        </div>
      </header>

      <div className="mt-8 space-y-8">
        {/* 1. THE TWO SURVEYS, AND THE THRESHOLD THAT CLASSIFIED EACH. */}
        <section aria-labelledby="jobs-surveys-heading">
          <h2 id="jobs-surveys-heading" className="text-sm font-medium text-fg-muted">
            Two surveys, side by side
          </h2>
          <div className="mt-3">
            {monitor.status === "loading" && <LoadingSkeleton label="Loading the two surveys" heightClassName="h-80" />}
            {monitor.status === "error" && <ErrorMessage message={MONITOR_ERROR_MESSAGE} onRetry={monitor.reload} />}
            {monitor.status === "success" && (
              <SurveyThreshold
                result={monitor.data}
                payroll={payroll.status === "success" ? payroll.data : null}
                unemployment={unemploymentSeries.status === "success" ? unemploymentSeries.data : null}
              />
            )}
            {monitor.status === "success" && (payroll.status === "error" || unemploymentSeries.status === "error") && (
              <div className="mt-3">
                <ErrorMessage
                  message={OBSERVATIONS_ERROR_MESSAGE}
                  onRetry={payroll.status === "error" ? payroll.reload : unemploymentSeries.reload}
                />
              </div>
            )}
          </div>
        </section>

        {/* 2. WHAT THE TWO SURVEYS ADD UP TO.
               #51B refinement 1: the disagreement is stated in plain
               English, and the formal classification is retained
               rather than replaced by it. */}
        {monitor.status === "success" && (
          <section aria-labelledby="jobs-conclusion-heading">
            <h2 id="jobs-conclusion-heading" className="text-sm font-medium text-fg-muted">
              What MacroChipz concludes
            </h2>
            <div className="lx-card mt-3 rounded-xl p-5 sm:p-6">
              <p className="max-w-prose text-base text-fg-secondary sm:text-lg">
                The two surveys are pointing different ways this month. Payroll employment is{" "}
                <span className="font-semibold text-fg">{laborStateLabelOrRaw(monitor.data.employment.state)}</span> and
                the unemployment trend is{" "}
                <span className="font-semibold text-fg">{laborStateLabelOrRaw(monitor.data.unemployment.state)}</span>.
                Neither is overridden and no average is taken between them.
              </p>
              <p className="mt-3 max-w-prose text-sm text-fg-muted">
                {monitor.data.methodology_id} records that disagreement under one formal name, shown below.
              </p>
              <div className="mt-4">
                <LaborHero result={monitor.data} stateDuration={stateDuration} />
              </div>
            </div>
          </section>
        )}

        {/* 3. The two surveys' own detail, behind a disclosure.
               #51A measured these as two full-width sections totalling
               1,230px on a phone. Nothing is removed or summarised —
               the whole of both, plus the note explaining why they are
               two things rather than one, is one tap away. */}
        {monitor.status === "success" && (
          <section aria-labelledby="jobs-detail-heading">
            <h2 id="jobs-detail-heading" className="text-sm font-medium text-fg-muted">
              Each survey in full
            </h2>
            <div className="mt-3 max-w-3xl">
              <Disclosure summary="Every figure behind both classifications" summaryClassName="min-h-11">
                <div className="space-y-8 pb-2 pt-2">
                  <EmploymentSection
                    employment={monitor.data.employment}
                    methodologyId={monitor.data.methodology_id}
                    dataBasis={monitor.data.data_basis}
                  />
                  <UnemploymentSection
                    unemployment={monitor.data.unemployment}
                    methodologyId={monitor.data.methodology_id}
                    dataBasis={monitor.data.data_basis}
                  />
                </div>
              </Disclosure>
            </div>
          </section>
        )}

        {/* 4. WHAT THIS PAGE DOES NOT HAVE (#51B).
               Participation, U-6, job openings and initial claims all
               404 from this API today — so the page says so rather
               than letting a reader assume the unemployment rate
               measures the experience of looking for work. */}
        {monitor.status === "success" && (
          <section aria-labelledby="jobs-limits-heading">
            <h2 id="jobs-limits-heading" className="text-sm font-medium text-fg-muted">
              What this page does not have
            </h2>
            <ul className="lx-card mt-3 list-disc space-y-2.5 rounded-xl p-5 pl-9 sm:p-6 sm:pl-10">
              <li className="max-w-prose text-sm text-fg-secondary">
                No measure of how hard it is to find a job. Job openings, labour-force participation, the broader
                underemployment rate and new claims for unemployment insurance are not available here, and MacroChipz
                does not estimate them.
              </li>
              <li className="max-w-prose text-sm text-fg-secondary">
                The unemployment rate counts people who are out of work and looking for it. This is why the rate alone
                does not tell you whether the jobs picture improved.
              </li>
              <li className="max-w-prose text-sm text-fg-secondary">
                No industry, state or demographic breakdown, and no wages. Both surveys are published here as one
                national number each.
              </li>
              <li className="max-w-prose text-sm text-fg-secondary">
                Values are the latest revised data, so a figure can change after it is first published. What changed is
                recorded rather than overwritten.
              </li>
            </ul>
          </section>
        )}
        {/* 4. What Changed */}
        {whatChanged.status === "loading" && <LoadingSkeleton label="Loading what changed" heightClassName="h-48" />}
        {whatChanged.status === "error" && <ErrorMessage message={CHANGES_ERROR_MESSAGE} onRetry={whatChanged.reload} />}
        {whatChanged.status === "success" && <WhatChangedSection whatChanged={whatChanged.data} />}

        {/* 5. Latest Data Detected */}
        {processingStatus.status === "loading" && (
          <LoadingSkeleton label="Loading latest data detected" heightClassName="h-32" />
        )}
        {processingStatus.status === "error" && (
          <ErrorMessage message={PROCESSING_STATUS_ERROR_MESSAGE} onRetry={processingStatus.reload} />
        )}
        {processingStatus.status === "success" && <LatestDataDetected items={processingStatus.data.occurrences} />}

        {/* 6. Relevant Release -- upcoming/recent load and fail independently;
            RelevantRelease itself shows whichever side is available. */}
        <div>
          {upcoming.status === "loading" && <LoadingSkeleton label="Loading upcoming releases" heightClassName="h-24" />}
          {upcoming.status === "error" && <ErrorMessage message={UPCOMING_ERROR_MESSAGE} onRetry={upcoming.reload} />}

          {recent.status === "loading" && <LoadingSkeleton label="Loading recent releases" heightClassName="h-8" />}
          {recent.status === "error" && <ErrorMessage message={RECENT_ERROR_MESSAGE} onRetry={recent.reload} />}

          <RelevantRelease
            upcoming={upcoming.status === "success" ? upcoming.data.releases : null}
            recent={recent.status === "success" ? recent.data.releases : null}
          />
        </div>

        {/* 7. Intelligence History (Increment #32), behind a
               disclosure (#51B). #51A measured it at 1,413px — 31% of
               the phone page — for twelve recorded states. Nothing is
               removed or summarised: the whole section, replay
               outcomes included, is one tap away. */}
        <div className="max-w-3xl">
          <Disclosure summary="Recorded conclusions, and whether they still reproduce" summaryClassName="min-h-11">
            <div className="pt-2">
              <IntelligenceHistorySection
                monitor="labor"
                history={history}
                headingId="labor-intelligence-history-heading"
                analystAvailable={analyst.status === "success" && analyst.data.available}
                stateLabel={laborStateLabelOrRaw}
                stateTone={laborStateToneOrNeutral}
              />
            </div>
          </Disclosure>
        </div>

        {/* 8. Ask MacroChipz (Increment #33) -- optional interpretive
            layer; unconfigured or failing, it renders a short note and
            changes nothing else on the page. */}
        <AskMacroChipz
          contextType="LABOR"
          contextRef={{ type: "LABOR" }}
          available={analyst.status === "success" && analyst.data.available}
          headingId="labor-analyst-heading"
        />

        {/* 9. Evidence & methodology */}
        {(monitor.status === "success" || whatChanged.status === "success") && (
          <MethodologyDisclosure
            monitor={monitor.status === "success" ? monitor.data : null}
            whatChanged={whatChanged.status === "success" ? whatChanged.data : null}
          />
        )}
      </div>

      <div className="mt-10 border-t border-line pt-8">
        <UnderstandWorld world="JOBS" />
      </div>

      {/* #43. A plain anchor rather than a router Link: this is a
          cross-capability jump out of a world, and it keeps the page
          renderable without router context. */}
      <p className="mt-6">
        <a
          href="/revisions"
          className="inline-flex min-h-11 items-center text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
        >
          Revision history →
        </a>
      </p>
    </div>
  );
}
