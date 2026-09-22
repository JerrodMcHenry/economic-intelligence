"""System-time observation versioning (Increment #31).

THE one algorithm that writes a canonical observation. Before #31 three
repositories each wrote `economic_observations` their own way, and only
one of them (release processing) preserved the previous value anywhere
-- so history was path-dependent, and 714 of 1,072 observations in the
development database had no recoverable history at all. This module
ends that: `SeriesRepository`, `ReleaseProcessingRepository` and
`RatesRepository` all delegate here, so there is exactly one place where
a canonical value changes and exactly one place where a version is
recorded. They cannot drift apart because they are the same code.

Two structures, deliberately separate:

- `economic_observations` remains the CURRENT-state cache: one row per
  (series, observation_date), overwritten in place, fast to read. Every
  existing read path keeps using it, unchanged.
- `observation_versions` is the append-only SYSTEM-TIME history: what
  value MacroChipz had recorded, and when it had it.

Interval semantics are half-open, `[recorded_from, recorded_to)`. A
version is live at T when `recorded_from <= T < recorded_to`; an open
version (`recorded_to IS NULL`) is live from `recorded_from` onward. A
revision closes the open version at exactly the instant the new one
opens, so successive versions neither overlap nor leave a gap, and an
as-of query at the boundary instant deterministically sees the NEW
value.

This is not a generalized bitemporal store, and this module never
pretends otherwise: `observation_date` is the economic period, system
time is when MacroChipz knew a value, and the source's own publication
time is not modeled because the providers used here do not publish it.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EconomicObservation, EconomicSeries, ObservationVersion

WriteOutcome = Literal["INSERTED", "REVISED", "UNCHANGED"]

#: Which write path produced a version. Recorded instead of a
#: `release_check_run_id` FK, which genuinely does not exist yet at the
#: moment release processing writes an observation.
ORIGIN_SERIES_SYNC = "SERIES_SYNC"
ORIGIN_RELEASE_PROCESSING = "RELEASE_PROCESSING"
ORIGIN_RATES_INGESTION = "RATES_INGESTION"
ORIGIN_HOUSING_INGESTION = "HOUSING_INGESTION"
ORIGIN_BACKFILL = "BACKFILL"

VALID_ORIGINS: frozenset[str] = frozenset(
    {
        ORIGIN_SERIES_SYNC,
        ORIGIN_RELEASE_PROCESSING,
        ORIGIN_RATES_INGESTION,
        ORIGIN_HOUSING_INGESTION,
        ORIGIN_BACKFILL,
    }
)


@dataclass(frozen=True)
class AsOfObservation:
    """One observation as MacroChipz knew it at a requested instant."""

    observation_date: date
    value: float | None
    is_backfilled: bool


class ObservationVersionWriter:
    """Applies canonical writes and their version history together.

    One writer is constructed per logical operation (one sync, one
    release-processing occurrence, one rates ingestion run) with ONE
    clock read, so every version that operation creates shares an exact
    `recorded_from`. That makes as-of boundaries crisp: a caller asking
    "what did we know at T" never lands midway through a batch.

    The caller owns the transaction (`session_scope()`), exactly as
    every other repository here does. Canonical mutation and version
    bookkeeping happen in the same unit of work, so a rollback discards
    both and the two can never disagree.
    """

    def __init__(
        self,
        session: Session,
        recorded_at: datetime | None = None,
        origin: str = ORIGIN_SERIES_SYNC,
        baseline: bool = False,
    ):
        """`baseline` marks FIRST observations written by this operation
        as an imported baseline rather than something MacroChipz watched
        arrive (Increment #45).

        WHY THIS FLAG EXISTS, AND WHAT IT IS NOT. `is_backfilled` was
        introduced by #31 for versions the MIGRATION synthesized from
        observations predating point-in-time tracking. #45 widens it, on
        purpose, to the structurally identical case: a provider's whole
        published history imported in one request. The flag's MEANING is
        unchanged and is exactly the meaning #31 documented -- "this
        value existed in MacroChipz by this time", never "this was the
        value the source first published, and no earlier revision
        occurred". A new source's 1959-2026 history is that case, and
        recording it as observed would claim MacroChipz watched sixty
        years of publication it did not see. #43's `BACKFILLED_BASELINE`
        is the revision-knowledge state that reads this flag.

        IT APPLIES ONLY TO `NEW` VERSIONS, and `_open_version` enforces
        that. A REVISION is always genuinely observed: reaching the
        revised branch at all means MacroChipz was holding an earlier
        value and saw the provider publish a different one, which is the
        one case where "originally reported" is provable. Marking a
        revision as baseline would throw away the only real revision
        evidence this system can ever collect.
        """
        if origin not in VALID_ORIGINS:
            raise ValueError(f"unknown observation-version origin: {origin!r}")
        self._session = session
        self._origin = origin
        self._baseline = baseline
        self._recorded_at = recorded_at or datetime.now(timezone.utc)

    @property
    def recorded_at(self) -> datetime:
        return self._recorded_at

    def apply(self, series: EconomicSeries, observation_date: date, value: float | None) -> WriteOutcome:
        """Write one observation, versioning it as required.

        - No current row: insert the observation and open its first
          version (`NEW`).
        - Same value as current: change nothing at all. No canonical
          write, and crucially no version -- a re-sync that confirms
          what is already stored is not a new fact about the world, and
          recording one would inflate history with noise and blur
          genuine revisions.
        - Different value: close the open version at `recorded_at`,
          open a new one, and update the canonical row (`REVISED`).

        `None` participates in plain equality, matching
        `app.domain.release_processing.classify_observation_change`: a
        transition into or out of missing is a genuine revision, never
        silently dropped.
        """
        existing = self._session.execute(
            select(EconomicObservation).where(
                EconomicObservation.economic_series_id == series.id,
                EconomicObservation.observation_date == observation_date,
            )
        ).scalar_one_or_none()

        if existing is None:
            self._session.add(
                EconomicObservation(
                    economic_series_id=series.id, observation_date=observation_date, value=value
                )
            )
            self._open_version(series.id, observation_date, value, change_type="NEW")
            self._session.flush()
            return "INSERTED"

        if existing.value == value:
            return "UNCHANGED"

        existing.value = value
        self._close_open_version(series.id, observation_date)
        self._open_version(series.id, observation_date, value, change_type="REVISED")
        self._session.flush()
        return "REVISED"

    def _close_open_version(self, economic_series_id: int, observation_date: date) -> None:
        """Close whichever version is currently open, if any.

        A missing open version is not an error: an observation that
        predates #31 and was never backfilled (or one whose history was
        legitimately absent) still gets a correct forward history from
        this point on. What must never happen is TWO open versions, and
        the database's partial unique index guarantees that even if this
        code were wrong.
        """
        open_version = self._session.execute(
            select(ObservationVersion).where(
                ObservationVersion.economic_series_id == economic_series_id,
                ObservationVersion.observation_date == observation_date,
                ObservationVersion.recorded_to.is_(None),
            )
        ).scalar_one_or_none()

        if open_version is None:
            return

        if open_version.recorded_from >= self._recorded_at:
            # Defensive: a zero-or-negative-length interval would break
            # the half-open semantics and violate the check constraint.
            # This can only happen with a caller-supplied timestamp that
            # moves backwards, which is a programming error, not data.
            raise ValueError(
                "recorded_at must be strictly after the open version's recorded_from "
                f"(open: {open_version.recorded_from!r}, incoming: {self._recorded_at!r})"
            )

        open_version.recorded_to = self._recorded_at

    def _open_version(
        self, economic_series_id: int, observation_date: date, value: float | None, change_type: str
    ) -> None:
        self._session.add(
            ObservationVersion(
                economic_series_id=economic_series_id,
                observation_date=observation_date,
                value=value,
                recorded_from=self._recorded_at,
                recorded_to=None,
                change_type=change_type,
                origin=self._origin,
                # `and change_type == "NEW"` is the whole guarantee, not
                # a defensive extra: a revision MacroChipz observed is
                # never a baseline, whatever the caller asked for. See
                # the constructor's docstring.
                is_backfilled=self._baseline and change_type == "NEW",
            )
        )


class ObservationVersionRepository:
    """Read side: what did MacroChipz know, and when.

    Never falls back to `economic_observations`. If no version was live
    at the requested instant, the honest answer is "nothing was known
    then", not "here is what we know now" -- silently substituting
    current values is exactly the contamination that makes a replay
    meaningless.
    """

    def __init__(self, session: Session):
        self._session = session

    def get_observations_as_of(self, series_id: str, at: datetime) -> list[AsOfObservation]:
        """Every observation of `series_id` whose version was live at
        `at`, ascending by observation date.

        Half-open: `recorded_from <= at < recorded_to`, with an open
        version live from `recorded_from` onward. An unknown series
        returns an empty list rather than raising -- the same
        missing-data-is-not-an-error discipline the monitors already
        follow.
        """
        series = self._session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == series_id)
        ).scalar_one_or_none()
        if series is None:
            return []

        rows = (
            self._session.execute(
                select(ObservationVersion)
                .where(
                    ObservationVersion.economic_series_id == series.id,
                    ObservationVersion.recorded_from <= at,
                    (ObservationVersion.recorded_to.is_(None)) | (ObservationVersion.recorded_to > at),
                )
                .order_by(ObservationVersion.observation_date.asc())
            )
            .scalars()
            .all()
        )
        return [
            AsOfObservation(
                observation_date=row.observation_date, value=row.value, is_backfilled=row.is_backfilled
            )
            for row in rows
        ]

    def list_observed_versions(
        self, series_ids: list[str], limit: int
    ) -> list[tuple[EconomicSeries, ObservationVersion]]:
        """The most recently recorded versions across `series_ids` that
        MacroChipz genuinely OBSERVED, newest first (Increment #45).

        "Observed" means `is_backfilled = false`: a value MacroChipz
        watched arrive or watched change, as opposed to one it imported.
        That filter is the whole reason this method exists. A new source's
        initial import writes its entire published history as baseline
        versions -- 4,644 rows for Housing's six series -- and projecting
        those into intelligence objects would report MacroChipz's own
        migration as economic news, which is precisely the manufactured
        activity `IntelligenceBuilder` is written to avoid.

        `limit` is required, not optional. A projection over an
        append-only table must be bounded at the query, because the
        alternative is a payload that grows with the database.

        Returns the series row alongside each version so the caller needs
        no second lookup for identity or display metadata.
        """
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if not series_ids:
            return []

        rows = self._session.execute(
            select(EconomicSeries, ObservationVersion)
            .join(ObservationVersion, ObservationVersion.economic_series_id == EconomicSeries.id)
            .where(
                EconomicSeries.series_id.in_(series_ids),
                ObservationVersion.is_backfilled.is_(False),
            )
            .order_by(
                ObservationVersion.recorded_from.desc(),
                ObservationVersion.observation_date.desc(),
                ObservationVersion.id.desc(),
            )
            .limit(limit)
        ).all()
        return [(series, version) for series, version in rows]

    def list_versions(self, series_id: str, observation_date: date) -> list[ObservationVersion]:
        """The full recorded timeline for one observation, oldest first
        -- the evidence behind any as-of answer."""
        series = self._session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == series_id)
        ).scalar_one_or_none()
        if series is None:
            return []

        rows = (
            self._session.execute(
                select(ObservationVersion)
                .where(
                    ObservationVersion.economic_series_id == series.id,
                    ObservationVersion.observation_date == observation_date,
                )
                .order_by(ObservationVersion.recorded_from.asc())
            )
            .scalars()
            .all()
        )
        return list(rows)

    def earliest_recorded_from(self, series_id: str) -> datetime | None:
        """When this series' version history begins. Used to decide
        whether a replay anchored before that instant has any real
        coverage at all, rather than quietly returning an empty
        dataset that the methodology would read as INSUFFICIENT_DATA."""
        series = self._session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == series_id)
        ).scalar_one_or_none()
        if series is None:
            return None

        return self._session.execute(
            select(ObservationVersion.recorded_from)
            .where(ObservationVersion.economic_series_id == series.id)
            .order_by(ObservationVersion.recorded_from.asc())
            .limit(1)
        ).scalar_one_or_none()
