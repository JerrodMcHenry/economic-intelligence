"""Application/use-case logic for discovering candidate economic series.

This is the DISCOVERY PLANE: "what series exist" -- coordinating local
PostgreSQL metadata search and FRED catalog search (metadata only, never
observations), then merging and deterministically ranking the results
into one deduplicated candidate list. Deliberately distinct from
`EconomicDataService`/`AnalysisService`'s ANALYSIS PLANE ("what does the
persisted data say"), which this service never touches -- it has no
notion of transformations, alignment, or correlation, and never queries
`economic_observations`.

Every `SeriesCandidate` this service returns is verified: it came from an
actual row in `economic_series`, or an actual FRED `series/search`
response. Nothing here ever fabricates a candidate from the search query
text itself.
"""

from sqlalchemy.orm import Session

from app.clients.fred import FREDClient, FREDError
from app.db.models import EconomicSeries
from app.models.discovery import SeriesCandidate, SeriesSearchResponse
from app.repositories.series_repository import SeriesRepository


class SeriesDiscoveryService:
    def __init__(self, fred_client: FREDClient | None = None):
        # Optional: local-only search still works with no FRED client at
        # all (e.g. FRED_API_KEY unconfigured) -- degrades gracefully
        # rather than failing the whole search.
        self._fred_client = fred_client

    def search(self, query: str, limit: int, session: Session) -> SeriesSearchResponse:
        """Search local persisted metadata and (if configured) FRED's
        catalog for series matching `query`, merged into one deduplicated,
        deterministically ranked list of at most `limit` candidates.

        Never raises for a FRED-side failure (timeout, auth, malformed
        response) -- that degrades to `external_search_available=False`
        with local results still returned. A local (database) failure is
        not caught here and propagates to the caller, the same "only
        handle the failures that are actually this layer's to handle"
        discipline used everywhere else in this project.
        """
        repo = SeriesRepository(session)
        local_rows = repo.search_series(query, limit)
        local_by_id = {row.series_id: row for row in local_rows}

        external_search_available = self._fred_client is not None
        fred_rows: list[dict] = []
        if self._fred_client is not None:
            try:
                fred_rows = self._fred_client.search_series(query, limit=limit)
            except FREDError:
                external_search_available = False

        candidates_by_id = self._merge(local_by_id, fred_rows)
        ranked = self._rank(candidates_by_id, query, fred_rows, limit)

        return SeriesSearchResponse(
            query=query,
            candidates=ranked,
            external_search_available=external_search_available,
        )

    @staticmethod
    def _merge(local_by_id: dict[str, EconomicSeries], fred_rows: list[dict]) -> dict[str, SeriesCandidate]:
        """Build the deduplicated candidate map, keyed by series_id.

        A series present in both sources is returned once, `persisted=True`,
        with FRED's richer metadata (frequency, seasonal adjustment,
        observation range, popularity -- none of which our local schema
        persists) layered onto the local match.
        """
        candidates: dict[str, SeriesCandidate] = {
            row.series_id: SeriesCandidate(
                series_id=row.series_id,
                title=row.title,
                units=row.units,
                persisted=True,
                discovery_source="local",
            )
            for row in local_by_id.values()
        }

        for row in fred_rows:
            series_id = row.get("id")
            if not series_id:
                continue  # malformed entry; skip rather than fabricate a candidate

            fred_metadata = {
                "units": row.get("units"),
                "frequency": row.get("frequency"),
                "seasonal_adjustment": row.get("seasonal_adjustment"),
                "observation_start": row.get("observation_start"),
                "observation_end": row.get("observation_end"),
                "popularity": row.get("popularity"),
            }

            if series_id in candidates:
                existing = candidates[series_id]
                candidates[series_id] = existing.model_copy(
                    update={**fred_metadata, "discovery_source": "local_and_fred"}
                )
            else:
                candidates[series_id] = SeriesCandidate(
                    series_id=series_id,
                    title=row.get("title", ""),
                    persisted=False,
                    discovery_source="fred",
                    **fred_metadata,
                )

        return candidates

    @staticmethod
    def _rank(
        candidates_by_id: dict[str, SeriesCandidate],
        query: str,
        fred_rows: list[dict],
        limit: int,
    ) -> list[SeriesCandidate]:
        """Deterministic ranking, simplest rule that satisfies all four
        stated preferences:

        1. An exact `series_id` match (case-insensitive) always surfaces first.
        2. Among non-exact matches, persisted (locally analyzable) candidates
           rank ahead of FRED-only ones -- a modest, deliberate preference,
           not a claim that they're a "better" match for the query.
        3. Within each of those two tiers, FRED's own `search_rank` order
           is preserved (candidates with no FRED signal at all sort last
           within their tier, since there's no relevance score to rank
           them by).

        No ML/embedding/LLM-generated relevance score -- three plain,
        explainable comparison keys.
        """
        fred_rank_by_id = {row.get("id"): position for position, row in enumerate(fred_rows) if row.get("id")}
        query_lower = query.lower()

        def sort_key(candidate: SeriesCandidate) -> tuple[int, int, int]:
            is_exact = candidate.series_id.lower() == query_lower
            return (
                0 if is_exact else 1,
                0 if candidate.persisted else 1,
                fred_rank_by_id.get(candidate.series_id, len(fred_rows)),
            )

        ordered = sorted(candidates_by_id.values(), key=sort_key)
        return ordered[:limit]
