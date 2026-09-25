"""BLS and BEA as the observation source for release processing
(Increment #56B).

`ReleaseProcessingService` asks its source two questions -- "what are
this series' observations since D" and "what is this series called" --
in the shape FRED's client answers them. This adapter answers the first
from BLS or BEA and REFUSES the second, and that refusal is the point:

- **Observations** come from the ACTIVE binding for the mapped storage
  id, so release processing fetches exactly what every reader reads. One
  BLS query and at most one BEA download per adapter instance: the first
  request for a provider fetches every active series of that provider and
  is reused, so a sweep over several occurrences stays well inside BLS's
  keyless 25 queries a day.
- **Series creation is refused.** Release processing creates a series
  row it has never seen, and every observation it then writes is
  recorded as OBSERVED -- sixty "new data" events for a five-year window.
  A first-party row must start as a BASELINE, which only
  `python -m app.operations.import_first_party` writes. So an
  un-imported series fails that series' check with a message saying
  exactly what to run, instead of fabricating a history of arrivals.

Values are passed as `repr(float)`, which round-trips exactly, and a
period the agency published as unavailable becomes FRED's own `"."`, so
the service's existing parser stores it as NULL -- the #56A rule.
"""

from datetime import date, datetime, timezone

from app.clients.bea import BEAClient
from app.clients.bls import BLSClient
from app.clients.provider_observation import FirstPartyObservation
from app.concepts.bindings import BINDINGS, ProviderBinding, active_binding, concept_id_for_stored_series
from app.models.first_party import PROVIDER_BEA, PROVIDER_BLS


class SeriesNotInitializedError(Exception):
    """The first-party row has never been imported, so release processing
    must not create it (see the module docstring)."""


class FirstPartyObservationSource:
    def __init__(self, bls_client: BLSClient, bea_client: BEAClient, today: date | None = None):
        self._bls = bls_client
        self._bea = bea_client
        self._today = today
        self._fetched: dict[tuple[str, date], dict[str, list[FirstPartyObservation]]] = {}

    def get_observations(
        self,
        series_id: str,
        limit: int | None = None,
        observation_start: date | None = None,
        sort_order: str = "asc",
    ) -> list[dict[str, str]]:
        binding = _first_party_binding(series_id)
        start = observation_start or date(self._today_or_now().year - 4, 1, 1)
        batch = self._batch(binding.provider, start)
        observations = sorted(
            (item for item in batch[binding.provider_series_id] if item.period >= start),
            key=lambda item: item.period,
            reverse=sort_order == "desc",
        )
        if limit is not None:
            observations = observations[:limit]
        return [
            {"date": item.period.isoformat(), "value": "." if item.value is None else repr(item.value)}
            for item in observations
        ]

    def get_series_info(self, series_id: str) -> dict[str, str]:
        raise SeriesNotInitializedError(
            f"First-party series {series_id!r} has not been imported; run "
            "`python -m app.operations.import_first_party` before release processing."
        )

    def _batch(self, provider: str, start: date) -> dict[str, list[FirstPartyObservation]]:
        key = (provider, start)
        if key not in self._fetched:
            ids = [b.provider_series_id for b in BINDINGS if b.active and b.provider == provider]
            if provider == PROVIDER_BLS:
                self._fetched[key] = self._bls.get_monthly(ids, start.year, self._today_or_now().year)
            else:
                self._fetched[key], _ = self._bea.get_nipa_monthly(ids, start)
        return self._fetched[key]

    def _today_or_now(self) -> date:
        return self._today or datetime.now(timezone.utc).date()


def _first_party_binding(storage_series_id: str) -> ProviderBinding:
    binding = active_binding(concept_id_for_stored_series(storage_series_id))
    if binding.provider not in {PROVIDER_BLS, PROVIDER_BEA} or binding.storage_series_id != storage_series_id:
        raise ValueError(f"{storage_series_id!r} is not an active first-party series")
    return binding
