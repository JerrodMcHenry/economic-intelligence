"""Increment #56B: release processing on BLS/BEA, after a baseline import.

The #54B plan's hardest guarantees, exercised on the real release
processing service with the real `FirstPartyObservationSource` and stub
provider clients (no network):

- a genuine revision after a baseline import is recorded as OBSERVED and
  REVISED, and the baseline stays a baseline -- the two remain
  distinguishable;
- a genuinely new month is observed, not backfilled;
- a month the agency published as unavailable stays missing -- NULL,
  never zero, never a "change";
- release processing never creates a first-party row: an un-imported
  series fails with the command to run, and nothing is written;
- one BLS request serves every BLS series in a run.

And the calculation-parity property at the domain level: identical
values under the FRED identity and the BLS identity give identical
Labor results in every field except the provider identity.
"""

from dataclasses import replace
from datetime import date

import pytest
import sqlalchemy as sa

from app.clients.provider_observation import FirstPartyObservation
from app.concepts.bindings import bindings_for_concept
from app.db.models import EconomicRelease, EconomicSeries, ObservationVersion
from app.repositories.release_repository import ReleaseRepository
from app.services.first_party_ingestion import FirstPartyIngestionService
from app.services.first_party_source import FirstPartyObservationSource, SeriesNotInitializedError
from app.services.release_processing import ReleaseProcessingService
from tests.integration.test_first_party_ingestion import StubBEA, StubBLS

pytestmark = pytest.mark.integration

PAYROLLS = "us.nonfarm.payroll-employment.sa.monthly"
UNEMPLOYMENT = "us.unemployment-rate.sa.monthly"
AS_OF = date(2026, 9, 24)


class CountingBLS:
    """Serves a fixed monthly history for every requested series, counting requests."""

    api_version, max_years = "v1", 10

    def __init__(self, history: dict[str, list[FirstPartyObservation]]):
        self.history = history
        self.calls = 0

    def get_monthly(self, series_ids, start_year, end_year):
        self.calls += 1
        return {series_id: list(self.history.get(series_id, [])) for series_id in series_ids}


def _months(start: date, values: list[float | None]) -> list[FirstPartyObservation]:
    out, year, month = [], start.year, start.month
    for value in values:
        out.append(FirstPartyObservation(date(year, month, 1), value))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return out


class TestSource:
    def _source(self, bls):
        return FirstPartyObservationSource(bls, StubBEA(), today=AS_OF)

    def test_unavailable_becomes_freds_dot_so_it_is_stored_as_null(self):
        bls = CountingBLS({"LNS14000000": _months(date(2025, 9, 1), [4.4, None, 4.5])})
        rows = self._source(bls).get_observations(UNEMPLOYMENT, observation_start=date(2025, 1, 1))
        assert [row["value"] for row in rows] == ["4.4", ".", "4.5"]

    def test_values_round_trip_exactly(self):
        bls = CountingBLS({"CUSR0000SA0": _months(date(2026, 8, 1), [334.131])})
        (row,) = self._source(bls).get_observations("us.cpi.headline.price-index.sa.monthly", observation_start=date(2026, 1, 1))
        assert float(row["value"]) == 334.131

    def test_one_bls_request_serves_every_bls_series(self):
        bls = CountingBLS({"CES0000000001": _months(date(2026, 1, 1), [1.0]), "LNS14000000": _months(date(2026, 1, 1), [4.0])})
        source = self._source(bls)
        source.get_observations(PAYROLLS, observation_start=date(2021, 1, 1))
        source.get_observations(UNEMPLOYMENT, observation_start=date(2021, 1, 1))
        source.get_observations("us.cpi.core.price-index.sa.monthly", observation_start=date(2021, 1, 1))
        assert bls.calls == 1

    def test_it_never_creates_a_series(self):
        with pytest.raises(SeriesNotInitializedError, match="import_first_party"):
            self._source(CountingBLS({})).get_series_info(PAYROLLS)

    @pytest.mark.parametrize("storage_id", ["PAYEMS", "UST_NOMINAL_10Y", "us.housing.units-started.saar.monthly"])
    def test_it_serves_only_active_first_party_rows(self, storage_id):
        with pytest.raises(ValueError):
            self._source(CountingBLS({})).get_observations(storage_id)


def _empsit_occurrence(session, scheduled=date(2026, 9, 4)):
    release = session.execute(sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "empsit")).scalar_one()
    return ReleaseRepository(session).upsert_occurrence(release.id, scheduled)


def _versions(session, concept_id, observation_date):
    series = session.execute(sa.select(EconomicSeries).where(EconomicSeries.series_id == concept_id)).scalar_one()
    return session.execute(
        sa.select(ObservationVersion)
        .where(ObservationVersion.economic_series_id == series.id, ObservationVersion.observation_date == observation_date)
        .order_by(ObservationVersion.recorded_from)
    ).scalars().all()


class TestReleaseProcessingAfterABaseline:
    def _imported(self, session):
        FirstPartyIngestionService(StubBLS(), StubBEA()).import_history(session, as_of=date(2026, 8, 31))

    def _process(self, session, history):
        occurrence = _empsit_occurrence(session)
        source = FirstPartyObservationSource(CountingBLS(history), StubBEA(), today=AS_OF)
        return ReleaseProcessingService(source).process_occurrence(occurrence.id, session, AS_OF)

    def test_revision_new_month_and_unavailable_month_are_each_recorded_honestly(self, db_session):
        self._imported(db_session)
        from app.clients.bls import parse_response
        from tests.integration.test_first_party_ingestion import BLS_IDS, BLS_RESPONSE

        published = parse_response(BLS_RESPONSE, BLS_IDS)
        payrolls = [o for o in published["CES0000000001"] if o.period >= date(2021, 1, 1)]
        unemployment = [o for o in published["LNS14000000"] if o.period >= date(2021, 1, 1)]
        # BLS revises July payrolls and publishes September.
        payrolls = [replace(o, value=158950.0) if o.period == date(2026, 7, 1) else o for o in payrolls]
        payrolls.append(FirstPartyObservation(date(2026, 9, 1), 159200.0))

        result = self._process(db_session, {"CES0000000001": payrolls, "LNS14000000": unemployment})

        assert result.status == "CHANGED"
        changes = {(c.series_id, c.observation_date): c.change_type for c in result.observation_changes}
        assert changes == {(PAYROLLS, date(2026, 7, 1)): "REVISED", (PAYROLLS, date(2026, 9, 1)): "NEW"}

        july = _versions(db_session, PAYROLLS, date(2026, 7, 1))
        assert [(v.change_type, v.is_backfilled) for v in july] == [("NEW", True), ("REVISED", False)]
        assert july[1].origin == "RELEASE_PROCESSING"
        september = _versions(db_session, PAYROLLS, date(2026, 9, 1))
        assert [(v.change_type, v.is_backfilled) for v in september] == [("NEW", False)]

        # October 2025 CPS: unavailable at import, unavailable now -- still
        # NULL, and not reported as a change.
        october = _versions(db_session, UNEMPLOYMENT, date(2025, 10, 1))
        assert [(v.value, v.change_type) for v in october] == [(None, "NEW")]

    def test_an_identical_publication_changes_nothing(self, db_session):
        self._imported(db_session)
        from app.clients.bls import parse_response
        from tests.integration.test_first_party_ingestion import BLS_IDS, BLS_RESPONSE

        published = parse_response(BLS_RESPONSE, BLS_IDS)
        result = self._process(db_session, {k: v for k, v in published.items()})
        assert result.status == "NO_CHANGE"

    def test_an_unimported_series_fails_with_the_command_and_writes_nothing(self, db_session):
        result = self._process(db_session, {"CES0000000001": _months(date(2026, 1, 1), [1.0]), "LNS14000000": []})

        failed = [o for o in result.series_outcomes if not o.succeeded]
        assert [o.series_id for o in failed] == [PAYROLLS]
        assert "import_first_party" in failed[0].error
        assert db_session.execute(
            sa.select(EconomicSeries).where(EconomicSeries.series_id == PAYROLLS)
        ).scalar_one_or_none() is None


class TestCalculationParity:
    def test_identical_values_under_fred_and_bls_identities_give_identical_labor_results(self):
        from app.domain.labor import compute_labor_monitor_result_at
        from app.models.labor import (
            CONDITION_DEADBAND_JOBS,
            MOMENTUM_DEADBAND_JOBS,
            UNEMPLOYMENT_DEADBAND_PP,
            LaborSeriesIdentities,
        )
        from app.models.series import Observation, SeriesIdentity

        def identity(concept_id, provider):
            b = next(b for b in bindings_for_concept(concept_id) if b.provider == provider)
            return SeriesIdentity(concept_id=concept_id, provider=b.provider, provider_series_id=b.provider_series_id)

        payrolls = [Observation(date=o.period, value=o.value) for o in _months(date(2024, 1, 1), [157000.0 + 90 * i for i in range(30)])]
        unemployment = [Observation(date=o.period, value=o.value) for o in _months(date(2024, 1, 1), [3.8 + 0.02 * i for i in range(30)])]

        def compute(provider):
            return compute_labor_monitor_result_at(
                payrolls, unemployment, date(2026, 6, 1), CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS,
                UNEMPLOYMENT_DEADBAND_PP,
                identities=LaborSeriesIdentities(
                    employment=identity(PAYROLLS, provider), unemployment=identity(UNEMPLOYMENT, provider)
                ),
            ).model_dump()

        def without_identity(value):
            if isinstance(value, dict):
                return {k: without_identity(v) for k, v in value.items() if k not in {"provider", "series_id"}}
            if isinstance(value, list):
                return [without_identity(v) for v in value]
            return value

        fred, bls = compute("FRED"), compute("BLS")
        assert fred["state"] == bls["state"] and fred["state"] != "INSUFFICIENT_DATA"
        assert without_identity(fred) == without_identity(bls)
        assert fred != bls  # the identity really did differ
