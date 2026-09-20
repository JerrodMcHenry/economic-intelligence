"""Explicit, operator-invoked ingestion of the canonical Rates series
from the U.S. Treasury (Increment #29).

The write counterpart to `RatesMonitorService`, deliberately a separate
class rather than a mode on it -- the same structural separation
`app.services.releases` already uses (`ReleaseReadService` vs
`ReleaseSyncService`): the read path has no Treasury client parameter
anywhere on it, so it is *incapable* of calling upstream, not merely
discouraged from it.

Failure isolation: each dataset is fetched independently. One dataset
failing (timeout, malformed XML, upstream error) never discards the
other's successfully-ingested observations -- the run is recorded as
`PARTIAL_FAILURE` with the failed dataset named. Nothing upstream is
trusted to be well-formed; nothing missing is ever filled in.
"""

import logging
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.clients.treasury import TreasuryClient, TreasuryError, TreasuryRateRow
from app.models.rates import (
    NOMINAL_DATASET,
    NOMINAL_FIELD_MAP,
    PROVIDER,
    REAL_DATASET,
    REAL_FIELD_MAP,
    RatesSyncResponse,
    RatesSyncSeriesOutcome,
    SERIES_TITLES,
    SERIES_UNITS,
)
from app.repositories.rates_repository import ProvenanceRecord, RatesRepository

logger = logging.getLogger(__name__)

# One request per dataset per calendar month, so the default window is
# expressed in months. Twelve gives a new environment enough history for
# the 63-session window (~3 months) several times over, without pulling
# decades on every routine sync.
DEFAULT_LOOKBACK_MONTHS = 12
MAX_LOOKBACK_MONTHS = 240

_DATASETS: tuple[tuple[str, dict[str, str]], ...] = (
    (NOMINAL_DATASET, NOMINAL_FIELD_MAP),
    (REAL_DATASET, REAL_FIELD_MAP),
)


def _source_url(dataset: str) -> str:
    """The stable, human-resolvable reference for a dataset -- recorded
    as provenance so any stored observation can be traced back to the
    page that published it."""
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"pages/xml?data={dataset}"
    )


def _months_back(as_of: date, months: int) -> list[tuple[int, int]]:
    """The `(year, month)` pairs covering `months` months ending at
    `as_of`, oldest first. Exact calendar stepping -- never `30 * n`
    days, which would drift."""
    pairs: list[tuple[int, int]] = []
    year, month = as_of.year, as_of.month
    for _ in range(months):
        pairs.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(pairs))


class RatesIngestionService:
    """Requires a `TreasuryClient`: there is no meaningful
    database-only mode for an ingestion service, the same reasoning
    `ReleaseSyncService` already applies."""

    def __init__(self, treasury_client: TreasuryClient):
        self._client = treasury_client

    def sync(self, session: Session, lookback_months: int = DEFAULT_LOOKBACK_MONTHS, as_of: date | None = None) -> RatesSyncResponse:
        """Fetch, classify and persist the canonical Rates series.

        Idempotent: re-running over the same upstream data inserts
        nothing and reports zero revisions (see
        `RatesRepository.upsert_observation`). The caller owns the
        transaction boundary via `session_scope()`; this method never
        commits.
        """
        if not (1 <= lookback_months <= MAX_LOOKBACK_MONTHS):
            raise ValueError(f"lookback_months must be between 1 and {MAX_LOOKBACK_MONTHS}")

        started_at = datetime.now(timezone.utc)
        as_of_date = as_of or started_at.date()
        months = _months_back(as_of_date, lookback_months)

        repo = RatesRepository(session)
        counts: dict[str, dict[str, int]] = {}
        datasets_failed: list[str] = []
        error_class: str | None = None
        total_received = 0

        for dataset, field_map in _DATASETS:
            try:
                rows = self._fetch_dataset(dataset, months)
            except TreasuryError as exc:
                # Per-dataset isolation: record and continue, never
                # abort the other dataset's good work.
                datasets_failed.append(dataset)
                error_class = error_class or type(exc).__name__
                logger.warning(
                    "rates ingestion: dataset failed",
                    extra={"provider": PROVIDER, "dataset": dataset, "error_class": type(exc).__name__},
                )
                continue

            received, dataset_counts = self._persist_dataset(repo, dataset, field_map, rows)
            total_received += received
            counts.update(dataset_counts)

        completed_at = datetime.now(timezone.utc)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        inserted = sum(item["inserted"] for item in counts.values())
        revised = sum(item["revised"] for item in counts.values())
        status = self._status(datasets_failed)

        repo.add_ingestion_run(
            provider=PROVIDER,
            datasets_requested=[dataset for dataset, _ in _DATASETS],
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            observations_received=total_received,
            observations_inserted=inserted,
            observations_revised=revised,
            datasets_failed=datasets_failed,
            error_class=error_class,
        )

        logger.info(
            "rates ingestion complete",
            extra={
                "provider": PROVIDER,
                "status": status,
                "duration_ms": duration_ms,
                "observations_received": total_received,
                "observations_inserted": inserted,
                "observations_revised": revised,
                "datasets_failed": ",".join(datasets_failed) or None,
            },
        )

        return RatesSyncResponse(
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            datasets_requested=[dataset for dataset, _ in _DATASETS],
            datasets_failed=datasets_failed,
            series=[
                RatesSyncSeriesOutcome(
                    series_id=series_id,
                    dataset=item["dataset_name"],  # type: ignore[arg-type]
                    observations_received=item["received"],
                    observations_inserted=item["inserted"],
                    observations_revised=item["revised"],
                )
                for series_id, item in sorted(counts.items())
            ],
        )

    @staticmethod
    def _status(datasets_failed: list[str]) -> str:
        if not datasets_failed:
            return "SUCCEEDED"
        if len(datasets_failed) == len(_DATASETS):
            return "FAILED"
        return "PARTIAL_FAILURE"

    def _fetch_dataset(self, dataset: str, months: list[tuple[int, int]]) -> list[TreasuryRateRow]:
        rows: list[TreasuryRateRow] = []
        for year, month in months:
            rows.extend(self._client.get_month(dataset, year, month))
        return rows

    def _persist_dataset(
        self,
        repo: RatesRepository,
        dataset: str,
        field_map: dict[str, str],
        rows: list[TreasuryRateRow],
    ) -> tuple[int, dict[str, dict]]:
        counts: dict[str, dict] = {
            series_id: {"dataset_name": dataset, "received": 0, "inserted": 0, "revised": 0}
            for series_id in field_map.values()
        }
        retrieved_at = datetime.now(timezone.utc)
        source_url = _source_url(dataset)
        received = 0

        # Create the series rows once, not per observation.
        series_rows = {
            series_id: repo.ensure_series(
                series_id=series_id,
                title=SERIES_TITLES[series_id],
                units=SERIES_UNITS,
                source=PROVIDER,
            )
            for series_id in field_map.values()
        }

        for row in rows:
            for field, series_id in field_map.items():
                value = row.values.get(field)
                if value is None:
                    # The feed did not publish this maturity for this
                    # session. Skipped entirely -- never zero, never
                    # carried forward from the previous session.
                    continue

                received += 1
                counts[series_id]["received"] += 1
                outcome = repo.upsert_observation(
                    series=series_rows[series_id],
                    observation_date=row.observation_date,
                    value=value,
                    provenance=ProvenanceRecord(
                        provider=PROVIDER,
                        dataset=dataset,
                        source_series_field=field,
                        source_url=source_url,
                        retrieved_at=retrieved_at,
                    ),
                )
                if outcome == "INSERTED":
                    counts[series_id]["inserted"] += 1
                elif outcome == "REVISED":
                    counts[series_id]["revised"] += 1

        return received, counts
