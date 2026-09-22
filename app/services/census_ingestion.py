"""Explicit, operator-invoked ingestion of the canonical Housing series
from the U.S. Census Bureau (Increment #45).

The write counterpart to `HousingReadService`, and a separate class for
the reason that module's docstring gives. Modelled on
`RatesIngestionService` throughout; the two genuine differences are
documented below rather than left to be inferred.

DIFFERENCE 1 -- ONE REQUEST, NOT A LOOP
---------------------------------------
Treasury's feeds are paged by calendar month, so `RatesIngestionService`
issues one request per month. Census's `resconst` dataset accepts an
open-ended time expression and answers the ENTIRE history -- 1959-01
onward, 26,773 rows, ~1.5 MB -- in a single response. So the baseline
import is one request, and a routine sync is one request for a short
recent window. Fewer requests against an authenticated, rate-limited
endpoint is not an optimisation here; it is the shape the provider
offers.

DIFFERENCE 2 -- THE BASELINE DECISION
-------------------------------------
This is the part with no precedent in the codebase, and the part #43
constrains most tightly.

A first import of a new source is NOT a history of observed events.
MacroChipz learns sixty-seven years of published values at one instant;
it did not watch any of them arrive and cannot say what Census had
published for those months at any earlier time. Recording them as
observed would manufacture exactly the revision history #43 exists to
refuse -- and would do it at a scale that dwarfs anything in the
database, which is why it is decided per observation by a pure function
(`app.domain.housing.is_baseline_import`) rather than by a flag someone
remembers to pass.

The consequence, stated plainly: **the initial Housing import produces
zero Structured Intelligence objects.** Every version it writes is a
`BACKFILLED_BASELINE`, and `IntelligenceBuilder` emits Housing objects
only for versions MacroChipz genuinely observed. A page that showed
4,644 "new data point" entries after a backfill would be reporting its
own migration as economic news.

WHAT IS NOT FABRICATED
----------------------
No timestamp is invented. `retrieved_at` is one real clock read per run,
shared by every provenance row and every version `recorded_from` in that
run, so an as-of query never lands midway through a batch. `published_at`
is not recorded at all: Census publishes a release TIME (8:30 a.m. ET),
but this dataset does not carry a per-observation publication instant,
and stamping the release time onto every row of a sixty-seven-year
history would be a fabrication on 812 months' worth of data.

Nothing missing is filled in. A row Census published without a usable
number is skipped and counted, never stored as zero and never carried
forward from the previous month. A row Census published as a reliability
statistic rather than an estimate is recognised and set aside, never
ingested as a housing count.
"""

import logging
from collections import Counter
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.clients.census import CensusClient, CensusError, CensusResconstRow
from app.concepts.bindings import active_binding
from app.domain.housing import is_baseline_import
from app.models.housing import (
    DATASET,
    HOUSING_CONCEPT_IDS,
    PROVIDER,
    SERIES_TITLES,
    SERIES_UNITS,
    SOURCE_URL,
    HousingImportMode,
    HousingSyncResponse,
    HousingSyncSeriesOutcome,
)
from app.repositories.housing_repository import HousingProvenanceRecord, HousingRepository

logger = logging.getLogger(__name__)

#: The dataset's own earliest period (housing starts and permits,
#: 1959-01; completions begin 1968-01 and simply have no earlier rows).
#: Verified against the live dataset, not assumed.
DATASET_FIRST_PERIOD = "1959-01"

#: The default routine-sync window, in months back from `as_of`. Twelve,
#: because Census revises recent months in every release and a
#: year-over-year comparison needs the month twelve back to exist. Not
#: used for a baseline import, which asks for everything.
DEFAULT_LOOKBACK_MONTHS = 12
MAX_LOOKBACK_MONTHS = 240

#: Data type code for the total across structure types. #45's scope is
#: the pipeline total; the single-family and multi-family breakdowns
#: Census also publishes are deliberately not ingested.
TOTAL_DATA_TYPE_CODE = "TOTAL"


class HousingIngestionService:
    """Requires a `CensusClient`: there is no meaningful database-only
    mode for an ingestion service, the same reasoning
    `RatesIngestionService` applies."""

    def __init__(self, census_client: CensusClient):
        self._client = census_client

    def sync(
        self,
        session: Session,
        lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
        full_history: bool = False,
        as_of: date | None = None,
    ) -> HousingSyncResponse:
        """Fetch, validate, classify and persist the canonical Housing
        series.

        `full_history=True` requests every period the dataset publishes
        -- what a new environment needs once. Otherwise a bounded recent
        window is fetched.

        Idempotent: re-running over the same upstream data inserts
        nothing, revises nothing, and writes no version rows (see
        `HousingRepository.upsert_observation`). The caller owns the
        transaction boundary via `session_scope()`; this method never
        commits.
        """
        if not (1 <= lookback_months <= MAX_LOOKBACK_MONTHS):
            raise ValueError(f"lookback_months must be between 1 and {MAX_LOOKBACK_MONTHS}")

        started_at = datetime.now(timezone.utc)
        as_of_date = as_of or started_at.date()
        time_expression = (
            f"from {DATASET_FIRST_PERIOD}"
            if full_history
            else f"from {_months_before(as_of_date, lookback_months - 1)}"
        )

        repo = HousingRepository(session)
        error_class: str | None = None
        rows: list[CensusResconstRow] = []
        rejected_reasons: Counter[str] = Counter()

        try:
            accepted, rejected = self._client.get_resconst(time_expression)
            rows = accepted
            rejected_reasons.update(item.reason for item in rejected)
        except CensusError as exc:
            # A single-request provider has no partial success to
            # preserve, so a failed fetch is a FAILED run -- recorded,
            # because the attempt genuinely happened, and reported with a
            # class name only.
            error_class = type(exc).__name__
            logger.warning(
                "housing ingestion: census fetch failed",
                extra={"provider": PROVIDER, "dataset": DATASET, "error_class": error_class},
            )

        outcomes, counts = self._persist(repo, rows, retrieved_at=started_at) if rows else ([], _empty_counts())

        completed_at = datetime.now(timezone.utc)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        status = self._status(error_class, rejected_reasons.total(), len(rows))
        import_mode = self._import_mode(outcomes)

        repo.add_ingestion_run(
            provider=PROVIDER,
            dataset=DATASET,
            status=status,
            import_mode=import_mode,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            rows_received=len(rows),
            rows_rejected=rejected_reasons.total(),
            error_measure_rows_ignored=counts["error_measure_rows"],
            observations_inserted=sum(item.observations_inserted for item in outcomes),
            observations_revised=sum(item.observations_revised for item in outcomes),
            observations_skipped_missing_value=sum(
                item.observations_skipped_missing_value for item in outcomes
            ),
            error_class=error_class,
        )

        logger.info(
            "housing ingestion complete",
            extra={
                "provider": PROVIDER,
                "dataset": DATASET,
                "status": status,
                "import_mode": import_mode,
                "duration_ms": duration_ms,
                "rows_received": len(rows),
                "rows_rejected": rejected_reasons.total(),
                "observations_inserted": sum(item.observations_inserted for item in outcomes),
                "observations_revised": sum(item.observations_revised for item in outcomes),
                # No credential, no URL, no upstream body. Every field
                # here is a count, a status, or a constant.
            },
        )

        return HousingSyncResponse(
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            rows_received=len(rows),
            error_measure_rows_ignored=counts["error_measure_rows"],
            rows_rejected=rejected_reasons.total(),
            rejected_reasons=dict(sorted(rejected_reasons.items())),
            rows_outside_scope=counts["out_of_scope_rows"],
            series=outcomes,
            error_class=error_class,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(
        self, repo: HousingRepository, rows: list[CensusResconstRow], retrieved_at: datetime
    ) -> tuple[list[HousingSyncSeriesOutcome], dict[str, int]]:
        """Route validated provider rows to canonical series and write them.

        Provider rows are grouped by Census's own identity
        (`category_code/data_type_code`) and matched against the BINDING
        table -- never against a name, a label, or a guess. A row whose
        identity matches no binding is out of scope and counted; that is
        the normal case for four fifths of this dataset, which also
        publishes units under construction, units authorized but not
        started, and single- and multi-family breakdowns that #45
        deliberately does not ingest.
        """
        counts = _empty_counts()

        by_provider_series: dict[str, list[CensusResconstRow]] = {}
        for row in rows:
            if row.is_error_measure:
                # Census's own reliability statistics. Real output, but
                # not an economic observation: ingesting a relative
                # standard error as a housing count would publish a
                # precision measure as a number of homes.
                counts["error_measure_rows"] += 1
                continue
            if row.data_type_code != TOTAL_DATA_TYPE_CODE:
                counts["out_of_scope_rows"] += 1
                continue
            by_provider_series.setdefault(f"{row.category_code}/{row.data_type_code}", []).append(row)

        # Bindings first, so the work list is MacroChipz's declared scope
        # and the provider's response is matched into it -- not the other
        # way round, which would let a new Census category quietly become
        # a MacroChipz series.
        wanted = {active_binding(concept_id).provider_series_id: concept_id for concept_id in HOUSING_CONCEPT_IDS}

        for provider_series_id, series_rows in by_provider_series.items():
            if provider_series_id not in wanted:
                counts["out_of_scope_rows"] += len(series_rows)

        outcomes: list[HousingSyncSeriesOutcome] = []
        for concept_id in HOUSING_CONCEPT_IDS:
            binding = active_binding(concept_id)
            series_rows = by_provider_series.get(binding.provider_series_id, [])
            outcomes.append(
                self._persist_series(repo, concept_id, series_rows, retrieved_at)
            )

        return outcomes, counts

    def _persist_series(
        self,
        repo: HousingRepository,
        concept_id: str,
        rows: list[CensusResconstRow],
        retrieved_at: datetime,
    ) -> HousingSyncSeriesOutcome:
        binding = active_binding(concept_id)
        storage_series_id = binding.storage_series_id

        # Read the baseline inputs ONCE, before any write: after the
        # first insert the series is no longer empty, and a per-row
        # re-read would classify row two as incremental against row one.
        had_observations = repo.has_observations(storage_series_id)
        latest_stored = repo.latest_observation_date(storage_series_id)

        inserted = revised = unchanged = skipped_missing = 0
        periods: list[date] = []

        if rows:
            series = repo.ensure_series(
                storage_series_id=storage_series_id,
                concept_id=concept_id,
                title=SERIES_TITLES[concept_id],
                units=SERIES_UNITS[concept_id],
                source=PROVIDER,
            )
            provenance = HousingProvenanceRecord(
                provider=PROVIDER,
                dataset=DATASET,
                source_series_field=binding.provider_series_id,
                source_url=SOURCE_URL,
                retrieved_at=retrieved_at,
            )

            for row in sorted(rows, key=lambda item: item.period):
                if row.value is None:
                    # Census published this month with no usable number.
                    # Skipped entirely -- never zero, never carried
                    # forward from the preceding month.
                    skipped_missing += 1
                    continue

                periods.append(row.period)
                outcome = repo.upsert_observation(
                    series=series,
                    observation_date=row.period,
                    # The ONE conversion, applied at the binding that
                    # declares it: Census publishes thousands of units,
                    # MacroChipz stores units.
                    value=row.value * binding.canonical_unit_factor,
                    provenance=provenance,
                    baseline=is_baseline_import(had_observations, latest_stored, row.period),
                )
                if outcome == "INSERTED":
                    inserted += 1
                elif outcome == "REVISED":
                    revised += 1
                else:
                    unchanged += 1

        return HousingSyncSeriesOutcome(
            concept_id=concept_id,
            provider_series_id=binding.provider_series_id,
            import_mode="BASELINE_BACKFILL" if not had_observations else "INCREMENTAL",
            observations_received=len(rows),
            observations_inserted=inserted,
            observations_revised=revised,
            observations_unchanged=unchanged,
            observations_skipped_missing_value=skipped_missing,
            first_period=min(periods) if periods else None,
            last_period=max(periods) if periods else None,
        )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    @staticmethod
    def _status(error_class: str | None, rejected: int, received: int) -> str:
        if error_class is not None:
            return "FAILED"
        if received == 0:
            # Reached Census, parsed the response, and it contained no
            # usable rows. Not an exception -- but not a success either,
            # because a sync that stored nothing should not read as
            # healthy.
            return "PARTIAL_FAILURE"
        if rejected:
            # Some rows failed validation. The rest were stored, so this
            # is genuinely partial rather than failed.
            return "PARTIAL_FAILURE"
        return "SUCCEEDED"

    @staticmethod
    def _import_mode(outcomes: list[HousingSyncSeriesOutcome]) -> HousingImportMode:
        """`BASELINE_BACKFILL` if ANY series was importing for the first
        time. Deliberately not "if all were": a run that backfills one
        new series alongside five existing ones has performed a baseline
        import, and reporting it as incremental would understate what it
        did."""
        return (
            "BASELINE_BACKFILL"
            if any(outcome.import_mode == "BASELINE_BACKFILL" for outcome in outcomes)
            else "INCREMENTAL"
        )


def _empty_counts() -> dict[str, int]:
    return {"error_measure_rows": 0, "out_of_scope_rows": 0}


def _months_before(as_of: date, months: int) -> str:
    """`YYYY-MM` for the month `months` before `as_of`.

    Exact calendar stepping -- never `30 * n` days, which would drift.
    """
    year, month = as_of.year, as_of.month
    for _ in range(months):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return f"{year:04d}-{month:02d}"
