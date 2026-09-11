"""Application/use-case logic for retrieving economic data series.

Coordinates a data source client (currently just FRED), a persistence
repository, and normalizes raw provider data into our own response models.
HTTP-specific concerns (status codes, request/response objects) do not
belong here, and neither does raw SQL — that lives in
`app.repositories.series_repository`.
"""

from datetime import date
from typing import Literal

from sqlalchemy.orm import Session

from app.clients.fred import FREDClient, FREDUpstreamError
from app.models.series import Observation, PaginationMeta, SeriesObservationsResponse, SeriesResponse
from app.repositories.series_repository import SeriesRepository

DEFAULT_OBSERVATION_LIMIT = 10


class SeriesNotFoundError(Exception):
    """Raised when a requested series is not persisted in our database."""


class InvalidDateRangeError(Exception):
    """Raised when start_date is after end_date."""


class EconomicDataService:
    def __init__(self, fred_client: FREDClient | None = None):
        # Optional: only the FRED-backed methods (get_series, sync_series)
        # need a client. get_observations reads the database only and
        # never touches it.
        self._fred_client = fred_client

    def get_series(self, series_id: str, limit: int = DEFAULT_OBSERVATION_LIMIT) -> SeriesResponse:
        info = self._fred_client.get_series_info(series_id)
        raw_observations = self._fred_client.get_observations(series_id, limit=limit)

        try:
            observations = [
                Observation(date=obs["date"], value=_parse_value(obs["value"]))
                # FRED returns newest-first; present chronologically instead.
                for obs in reversed(raw_observations)
            ]
            return SeriesResponse(
                series_id=info["id"],
                title=info["title"],
                units=info["units"],
                observations=observations,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise FREDUpstreamError(
                f"Received malformed data from FRED for series '{series_id}'"
            ) from exc

    def sync_series(
        self, series_id: str, session: Session, limit: int = DEFAULT_OBSERVATION_LIMIT
    ) -> SeriesResponse:
        """Fetch a series from FRED and persist it within the given session's transaction.

        The caller (the route) owns `session`'s transaction boundary via
        `session_scope()` — this method performs writes on it but never
        commits or rolls back itself.
        """
        data = self.get_series(series_id, limit=limit)
        SeriesRepository(session).save_series(data)
        return data

    def get_observations(
        self,
        series_id: str,
        session: Session,
        start_date: date | None,
        end_date: date | None,
        limit: int,
        offset: int,
        order: Literal["asc", "desc"],
    ) -> SeriesObservationsResponse:
        """Query persisted historical observations for a series.

        Database-only: never calls FRED, never syncs, never mutates data.
        Raises `InvalidDateRangeError` if `start_date` is after `end_date`,
        and `SeriesNotFoundError` if the series isn't persisted.
        """
        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidDateRangeError("start_date must not be after end_date.")

        repo = SeriesRepository(session)
        series = repo.get_series_by_series_id(series_id)
        if series is None:
            raise SeriesNotFoundError(f"Series '{series_id}' is not persisted.")

        observations, total = repo.get_observations(
            economic_series_id=series.id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
            order=order,
        )

        return SeriesObservationsResponse(
            series_id=series.series_id,
            title=series.title,
            units=series.units,
            source=series.source,
            observations=[Observation(date=obs.observation_date, value=obs.value) for obs in observations],
            pagination=PaginationMeta(limit=limit, offset=offset, returned=len(observations), total=total),
        )


def _parse_value(raw: str) -> float | None:
    """FRED represents a missing observation with the literal string '.'."""
    if raw == ".":
        return None
    return float(raw)
