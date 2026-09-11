"""Data-access layer for economic series and observations.

Owns all SQLAlchemy query/persistence operations against the
`economic_series` and `economic_observations` tables. Operates entirely
within a caller-provided `Session` and never calls `commit()` or
`rollback()` itself — the caller owns the transaction boundary (see
`app.db.session.session_scope`).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EconomicObservation, EconomicSeries
from app.models.series import SeriesResponse


class SeriesRepository:
    def __init__(self, session: Session):
        self._session = session

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
