"""Data-access layer for economic series and observations.

Owns all SQLAlchemy query/persistence operations against the
`economic_series` and `economic_observations` tables. Operates entirely
within a caller-provided `Session` and never calls `commit()` or
`rollback()` itself — the caller owns the transaction boundary (see
`app.db.session.session_scope`).
"""

from datetime import date
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.concepts.bindings import BINDINGS, AmbiguousBindingError, UnknownBindingError, concept_id_for_stored_series
from app.db.models import EconomicObservation, EconomicSeries
from app.models.series import SeriesIdentity, SeriesResponse
from app.repositories.observation_versions import ORIGIN_SERIES_SYNC, ObservationVersionWriter


#: Providers whose rows are keyed by MacroChipz's concept id rather than
#: by the provider's own identifier (#56B). Treasury and Census rows are
#: concept-keyed too, but their evidence contracts predate this and name
#: the storage id; changing them is not #56B's business.
_CONCEPT_KEYED_AGENCY_PROVIDERS = frozenset({"BLS", "BEA"})


def provider_series_id_for(series: EconomicSeries) -> str:
    """The identifier the PROVIDER uses for this row's series.

    For FRED rows the storage id IS the provider id (`PAYEMS`). For BLS
    and BEA rows the storage id is a concept id, so the agency's own
    identifier (`CES0000000001`) comes from the binding registered for
    exactly this row -- matched on storage id AND the row's own source,
    so it can never name another provider's series (#56B: without this,
    evidence would print a concept id where the agency series id
    belongs).
    """
    if series.source not in _CONCEPT_KEYED_AGENCY_PROVIDERS:
        return series.series_id
    matches = [
        binding.provider_series_id
        for binding in BINDINGS
        if binding.storage_series_id == series.series_id and binding.provider == series.source
    ]
    if len(matches) != 1:
        raise MissingConceptIdentityError(
            f"Stored {series.source} series {series.series_id!r} has {len(matches)} matching bindings; expected one."
        )
    return matches[0]


def _concept_id_or_none(storage_series_id: str) -> str | None:
    """The concept a stored series supplies, or `None` for an arbitrary
    provider series (#38, ADR-034).

    The SAME deterministic rule the backfill migration uses: an explicit
    registered binding, or nothing. `None` is the correct, expected
    answer for a series synced through the generic endpoint -- those are
    not canonical MacroChipz concepts, and inferring one from a title is
    exactly what ADR-034 forbids.
    """
    try:
        return concept_id_for_stored_series(storage_series_id)
    except (UnknownBindingError, AmbiguousBindingError):
        return None


class MissingConceptIdentityError(LookupError):
    """A persisted series that canonical code reads carries no
    `concept_id`. A configuration error, never missing data."""


class SeriesRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_series_by_series_id(self, series_id: str) -> EconomicSeries | None:
        """Look up a persisted series by its provider/business identifier."""
        return self._session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == series_id)
        ).scalar_one_or_none()

    def get_identity(self, series_id: str) -> SeriesIdentity | None:
        """Who a persisted series actually is (#38, ADR-034).

        All three fields are read from the stored row -- the concept it
        supplies, the provider that supplied it, and that provider's own
        identifier. This is the function that makes evidence honest:
        before #38 a methodology stamped its evidence from a module
        constant, so a provider cutover would have left old evidence
        naming a provider that no longer supplied anything.

        Returns `None` when the series is not persisted at all, matching
        `get_series_by_series_id`'s own missing-series semantics.

        Raises `MissingConceptIdentityError` when the series EXISTS but
        carries no concept. That is deliberately not `None`: a series
        the canonical methodologies read must have a registered concept,
        and silently treating it as absent would turn a configuration
        error into a confident `INSUFFICIENT_DATA` that looks like an
        economic finding.
        """
        series = self.get_series_by_series_id(series_id)
        if series is None:
            return None

        # `concept_id` is a denormalization of a deterministic mapping,
        # so a row that predates the column -- or one written by a path
        # that does not set it -- still resolves, by the SAME rule the
        # backfill used. Only a series with no registered binding at all
        # is genuinely unidentifiable, and that raises.
        concept_id = series.concept_id or _concept_id_or_none(series.series_id)
        if concept_id is None:
            raise MissingConceptIdentityError(
                f"Persisted series {series_id!r} has no concept_id and no registered binding. "
                f"It is not a MacroChipz economic concept; see app/concepts/bindings.py."
            )

        # The PROVIDER always comes from the row, never from whichever
        # binding is active -- that is what keeps historical evidence
        # honest after a provider cutover (ADR-034, Invariant D): a FRED
        # row keeps naming FRED after #56B, because it is a different row.
        return SeriesIdentity(
            concept_id=concept_id,
            provider=series.source,
            provider_series_id=provider_series_id_for(series),
        )

    def search_series(self, query: str, limit: int) -> list[EconomicSeries]:
        """Case-insensitive substring match against persisted series'
        `series_id` or `title` -- discovery only, no judgment about which
        match is economically "best" (that's the caller's/model's job).

        Deterministic ordering: an exact `series_id` match (case-
        insensitive) first, then alphabetically by `series_id` -- there is
        no local popularity/relevance signal to rank by, unlike FRED's
        `search_rank`.
        """
        pattern = f"%{query}%"
        is_exact_id = func.lower(EconomicSeries.series_id) == query.lower()
        rows = (
            self._session.execute(
                select(EconomicSeries)
                .where(or_(EconomicSeries.series_id.ilike(pattern), EconomicSeries.title.ilike(pattern)))
                .order_by(is_exact_id.desc(), EconomicSeries.series_id.asc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return list(rows)

    def get_observations(
        self,
        economic_series_id: int,
        start_date: date | None,
        end_date: date | None,
        limit: int,
        offset: int,
        order: Literal["asc", "desc"],
    ) -> tuple[list[EconomicObservation], int]:
        """Query a series' observations, filtered/ordered/paginated.

        Returns `(page, total)`, where `total` is the count of observations
        matching `economic_series_id`/`start_date`/`end_date` *before*
        `limit`/`offset` are applied — the count query and the page query
        share the same filter conditions so the two always agree.
        """
        conditions = [EconomicObservation.economic_series_id == economic_series_id]
        if start_date is not None:
            conditions.append(EconomicObservation.observation_date >= start_date)
        if end_date is not None:
            conditions.append(EconomicObservation.observation_date <= end_date)

        total = self._session.execute(
            select(func.count()).select_from(EconomicObservation).where(*conditions)
        ).scalar_one()

        # observation_date is unique per series (see uq_observation_series_date),
        # so ordering by it alone is already deterministic -- no tiebreaker needed.
        order_by = (
            EconomicObservation.observation_date.asc()
            if order == "asc"
            else EconomicObservation.observation_date.desc()
        )
        observations = (
            self._session.execute(
                select(EconomicObservation).where(*conditions).order_by(order_by).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )

        return list(observations), total

    def get_observations_in_range(
        self,
        economic_series_id: int,
        start_date: date | None,
        end_date: date | None,
    ) -> list[EconomicObservation]:
        """Return ALL observations for a series matching the optional date
        filters, in ascending chronological order -- unpaginated.

        Used by the transformation endpoint, which needs the complete
        requested range at once (a transformation can't be computed
        correctly one page at a time -- see app.services.economic_data).
        """
        conditions = [EconomicObservation.economic_series_id == economic_series_id]
        if start_date is not None:
            conditions.append(EconomicObservation.observation_date >= start_date)
        if end_date is not None:
            conditions.append(EconomicObservation.observation_date <= end_date)

        observations = (
            self._session.execute(
                select(EconomicObservation).where(*conditions).order_by(EconomicObservation.observation_date.asc())
            )
            .scalars()
            .all()
        )
        return list(observations)

    def get_preceding_observations(
        self,
        economic_series_id: int,
        before_date: date,
        count: int,
    ) -> list[EconomicObservation]:
        """Return up to `count` observations for a series strictly before
        `before_date` -- the `count` most recent such observations,
        returned in ascending chronological order so they can be
        prepended directly to a later range.

        Used to give the transformation engine enough leading context
        (e.g. the one prior observation a change calculation needs, or a
        moving average's `window - 1` prior points) to compute correct
        values at the start of a date-filtered request, without that
        context itself appearing in the response.
        """
        rows = (
            self._session.execute(
                select(EconomicObservation)
                .where(
                    EconomicObservation.economic_series_id == economic_series_id,
                    EconomicObservation.observation_date < before_date,
                )
                .order_by(EconomicObservation.observation_date.desc())
                .limit(count)
            )
            .scalars()
            .all()
        )
        return list(reversed(rows))

    def save_series(self, data: SeriesResponse) -> EconomicSeries:
        """Upsert series metadata and its observations.

        Existing series/observation rows are updated in place; new ones are
        inserted. Existing observations for dates not present in `data` are
        left untouched (no implicit deletion of history).
        """
        series = self._upsert_series(data)
        self._upsert_observations(series, data)
        return series

    def _upsert_series(self, data: SeriesResponse) -> EconomicSeries:
        series = self._session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == data.series_id)
        ).scalar_one_or_none()

        if series is None:
            series = EconomicSeries(
                series_id=data.series_id,
                concept_id=_concept_id_or_none(data.series_id),
                title=data.title,
                units=data.units,
                source=data.source,
            )
            self._session.add(series)
            self._session.flush()  # assigns series.id for the observations below
        else:
            series.title = data.title
            series.units = data.units
            series.source = data.source
            # Backfill a row that predates concept identity (#38), or one
            # created before its binding was registered. Never CLEARED
            # here: an existing concept is not un-set by a re-sync.
            if series.concept_id is None:
                series.concept_id = _concept_id_or_none(data.series_id)

        return series

    def _upsert_observations(self, series: EconomicSeries, data: SeriesResponse) -> None:
        """Delegates every canonical write to the one shared versioning
        writer (Increment #31), so a sync-path revision preserves its
        previous value exactly as a release-processing revision does.
        Before #31 this path overwrote values silently and history was
        path-dependent.

        One writer, one clock read, for the whole series: every version
        this sync creates shares an exact `recorded_from`.
        """
        writer = ObservationVersionWriter(self._session, origin=ORIGIN_SERIES_SYNC)
        for observation in data.observations:
            writer.apply(series, observation.date, observation.value)
