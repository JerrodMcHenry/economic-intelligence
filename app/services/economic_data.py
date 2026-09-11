"""Application/use-case logic for retrieving economic data series.

Coordinates a data source client (currently just FRED), a persistence
repository, and normalizes raw provider data into our own response models.
HTTP-specific concerns (status codes, request/response objects) do not
belong here, and neither does raw SQL — that lives in
`app.repositories.series_repository`.
"""

from sqlalchemy.orm import Session

from app.clients.fred import FREDClient, FREDUpstreamError
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository

DEFAULT_OBSERVATION_LIMIT = 10


class EconomicDataService:
    def __init__(self, fred_client: FREDClient):
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


def _parse_value(raw: str) -> float | None:
    """FRED represents a missing observation with the literal string '.'."""
    if raw == ".":
        return None
    return float(raw)
