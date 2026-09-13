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

from app.db.models import EconomicObservation, EconomicSeries
from app.models.series import SeriesResponse


class SeriesRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_series_by_series_id(self, series_id: str) -> EconomicSeries | None:
        """Look up a persisted series by its provider/business identifier."""
        return self._session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == series_id)
        ).scalar_one_or_none()

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

        return series

    def _upsert_observations(self, series: EconomicSeries, data: SeriesResponse) -> None:
        existing_by_date = {
            obs.observation_date: obs
            for obs in self._session.execute(
                select(EconomicObservation).where(EconomicObservation.economic_series_id == series.id)
            ).scalars()
        }

        for observation in data.observations:
            existing = existing_by_date.get(observation.date)
            if existing is not None:
                existing.value = observation.value
            else:
                self._session.add(
                    EconomicObservation(
                        economic_series_id=series.id,
                        observation_date=observation.date,
                        value=observation.value,
                    )
                )
