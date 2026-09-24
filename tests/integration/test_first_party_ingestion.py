"""Increment #56A: first-party BLS/BEA ingestion against a real database.

No network: stub clients return `FirstPartyObservation`s. The BLS stub
replays the REAL recorded BLS response through the real parser, so the
values reaching the database are exactly the published strings -- the
parity property #54B measured, proven here end to end.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.clients.bls import parse_response
from app.clients.bounded_http import ProviderUnavailableError
from app.clients.provider_observation import FirstPartyObservation
from app.concepts.bindings import active_binding
from app.db.models import (
    EconomicObservation,
    EconomicSeries,
    ObservationProvenance,
    ObservationVersion,
    ProviderIngestionRun,
)
from app.models.first_party import BEA_CONCEPT_IDS, BLS_CONCEPT_IDS, FIRST_PARTY_CONCEPT_IDS
from app.repositories.first_party_repository import FirstPartyRepository
from app.repositories.observation_versions import ORIGIN_FIRST_PARTY_INGESTION, ObservationVersionWriter
from app.services.first_party_ingestion import FirstPartyIngestionService

pytestmark = pytest.mark.integration

AS_OF = date(2026, 9, 24)
BLS_RESPONSE = json.loads((Path(__file__).parent.parent / "fixtures" / "bls_v1_2017_2026.json").read_text())
BLS_IDS = ["CUSR0000SA0", "CUSR0000SA0L1E", "CES0000000001", "LNS14000000"]
PAYROLLS = "us.nonfarm.payroll-employment.sa.monthly"
HEADLINE_CPI = "us.cpi.headline.price-index.sa.monthly"
PCE = "us.pce.headline.price-index.sa.monthly"


class StubBLS:
    api_version = "v1"
    max_years = 10

    def __init__(self, data=None, raises=None):
        self._data = data if data is not None else parse_response(BLS_RESPONSE, BLS_IDS)
        self._raises = raises
        self.calls = []

    def get_monthly(self, series_ids, start_year, end_year):
        self.calls.append((tuple(series_ids), start_year, end_year))
        if self._raises:
            raise self._raises
        return {series_id: list(self._data[series_id]) for series_id in series_ids}


class StubBEA:
    PUBLISHED = datetime(2026, 8, 26, 12, 30, 2, tzinfo=timezone.utc)

    def __init__(self, data=None, raises=None):
        self._data = data if data is not None else {
            "DPCERG": [FirstPartyObservation(date(2026, m, 1), 131.0 + m / 1000) for m in range(1, 8)],
            "DPCCRG": [FirstPartyObservation(date(2026, m, 1), 130.0 + m / 1000) for m in range(1, 8)],
        }
        self._raises = raises

    def get_nipa_monthly(self, codes, start):
        if self._raises:
            raise self._raises
        return {code: [o for o in self._data[code] if o.period >= start] for code in codes}, self.PUBLISHED


def _import(session, bls=None, bea=None, **kwargs):
    return FirstPartyIngestionService(bls or StubBLS(), bea or StubBEA()).import_history(session, as_of=AS_OF, **kwargs)


def _series(session, concept_id):
    return session.execute(select(EconomicSeries).where(EconomicSeries.series_id == concept_id)).scalar_one()


def _values(session, series_id):
    series = session.execute(select(EconomicSeries).where(EconomicSeries.series_id == series_id)).scalar_one()
    rows = session.execute(
        select(EconomicObservation.observation_date, EconomicObservation.value)
        .where(EconomicObservation.economic_series_id == series.id)
        .order_by(EconomicObservation.observation_date)
    ).all()
    return {row.observation_date: row.value for row in rows}


def _versions(session, concept_id):
    series = _series(session, concept_id)
    return session.execute(
        select(ObservationVersion).where(ObservationVersion.economic_series_id == series.id)
    ).scalars().all()


class TestTheInitialImport:
    def test_six_concept_keyed_rows_with_their_own_source_and_native_units(self, db_session):
        _import(db_session)
        for concept_id in FIRST_PARTY_CONCEPT_IDS:
            series = _series(db_session, concept_id)
            assert series.concept_id == concept_id
            assert series.source == ("BLS" if concept_id in BLS_CONCEPT_IDS else "BEA")
        assert _series(db_session, PAYROLLS).units == "Thousands of Persons"
        assert _series(db_session, PCE).units == "Index 2017=100"

    def test_values_are_the_published_strings_unconverted(self, db_session):
        _import(db_session)
        assert _values(db_session, HEADLINE_CPI)[date(2026, 8, 1)] == 334.131
        # Native thousands, exactly as the FRED row stores PAYEMS.
        assert _values(db_session, PAYROLLS)[date(2026, 8, 1)] == 159075.0

    def test_ten_calendar_years_are_imported(self, db_session):
        _import(db_session)
        dates = sorted(_values(db_session, HEADLINE_CPI))
        assert dates[0] == date(2017, 1, 1) and dates[-1] == date(2026, 8, 1) and len(dates) == 116

    def test_every_version_is_a_new_backfilled_baseline_and_none_is_a_revision(self, db_session):
        _import(db_session)
        for concept_id in FIRST_PARTY_CONCEPT_IDS:
            versions = _versions(db_session, concept_id)
            assert versions
            assert {v.change_type for v in versions} == {"NEW"}
            assert all(v.is_backfilled for v in versions)
            assert {v.origin for v in versions} == {ORIGIN_FIRST_PARTY_INGESTION}

    def test_unavailable_months_are_stored_as_null_never_zero(self, db_session):
        outcomes = _import(db_session)
        assert _values(db_session, HEADLINE_CPI)[date(2025, 10, 1)] is None
        assert _values(db_session, "us.unemployment-rate.sa.monthly")[date(2025, 10, 1)] is None
        assert _values(db_session, PAYROLLS)[date(2025, 10, 1)] == 158408.0
        bls = next(o for o in outcomes if o.provider == "BLS")
        assert {s.concept_id: s.unavailable for s in bls.series}[HEADLINE_CPI] == 1

    def test_provenance_names_the_agency_series_and_a_landing_page(self, db_session):
        _import(db_session)
        rows = db_session.execute(
            select(ObservationProvenance).where(ObservationProvenance.economic_series_id == _series(db_session, PAYROLLS).id)
        ).scalars().all()
        assert len(rows) == 116
        row = rows[0]
        assert (row.provider, row.dataset, row.source_series_field) == ("BLS", "CES", "CES0000000001")
        assert row.source_url == "https://data.bls.gov/timeseries/CES0000000001"
        assert "api." not in row.source_url
        assert len({r.retrieved_at for r in rows}) == 1
        assert row.first_seen_at == row.retrieved_at and row.revision_count == 0

    def test_provenance_and_versions_share_one_instant(self, db_session):
        _import(db_session)
        series = _series(db_session, PCE)
        instants = {v.recorded_from for v in _versions(db_session, PCE)}
        provenance = db_session.execute(
            select(ObservationProvenance.retrieved_at).where(ObservationProvenance.economic_series_id == series.id)
        ).scalars().all()
        assert len(instants) == 1 and set(provenance) == instants

    def test_one_run_row_per_provider(self, db_session):
        _import(db_session)
        runs = {r.provider: r for r in db_session.execute(select(ProviderIngestionRun)).scalars()}
        assert set(runs) == {"BLS", "BEA"}
        bls, bea = runs["BLS"], runs["BEA"]
        assert (bls.status, bls.import_mode, bls.access_mode) == ("SUCCEEDED", "BASELINE_BACKFILL", "KEYLESS_V1")
        assert (bls.window_start, bls.window_end) == (date(2017, 1, 1), AS_OF)
        assert bls.series_requested == 4 and bls.observations_inserted == 464 and bls.observations_unavailable == 3
        assert bls.source_published_at is None
        assert (bea.access_mode, bea.source_published_at) == ("FLAT_FILE", StubBEA.PUBLISHED)
        assert bls.error_class is None and bea.error_class is None

    def test_bls_is_asked_for_exactly_the_window_in_one_request(self, db_session):
        bls = StubBLS()
        _import(db_session, bls=bls)
        assert bls.calls == [(tuple(BLS_IDS), 2017, 2026)]


class TestNoFalseRevisions:
    def test_an_identical_rerun_writes_nothing(self, db_session):
        _import(db_session)
        before = db_session.execute(select(func.count()).select_from(ObservationVersion)).scalar_one()

        outcomes = _import(db_session)

        assert db_session.execute(select(func.count()).select_from(ObservationVersion)).scalar_one() == before
        for outcome in outcomes:
            assert outcome.import_mode == "INCREMENTAL"
            assert sum(s.inserted + s.revised for s in outcome.series) == 0

    def test_a_genuine_provider_revision_is_recorded_as_observed(self, db_session):
        _import(db_session)
        revised = StubBEA(data={
            "DPCERG": [FirstPartyObservation(date(2026, m, 1), 131.0 + m / 1000 + (0.25 if m == 3 else 0)) for m in range(1, 8)],
            "DPCCRG": [FirstPartyObservation(date(2026, m, 1), 130.0 + m / 1000) for m in range(1, 8)],
        })

        _import(db_session, bea=revised, providers=("BEA",))

        march = [v for v in _versions(db_session, PCE) if v.observation_date == date(2026, 3, 1)]
        assert sorted(v.change_type for v in march) == ["NEW", "REVISED"]
        assert not next(v for v in march if v.change_type == "REVISED").is_backfilled
        provenance = db_session.execute(
            select(ObservationProvenance).where(
                ObservationProvenance.economic_series_id == _series(db_session, PCE).id,
                ObservationProvenance.observation_date == date(2026, 3, 1),
            )
        ).scalar_one()
        assert provenance.revision_count == 1

    def test_a_genuinely_new_month_is_observed_not_backfilled(self, db_session):
        _import(db_session)
        later = StubBEA(data={
            code: [*obs, FirstPartyObservation(date(2026, 8, 1), 132.0)]
            for code, obs in StubBEA()._data.items()
        })
        _import(db_session, bea=later, providers=("BEA",))
        august = [v for v in _versions(db_session, PCE) if v.observation_date == date(2026, 8, 1)]
        assert [(v.change_type, v.is_backfilled) for v in august] == [("NEW", False)]


class TestFredHistoryIsNeverTouched:
    def _seed_fred_payems(self, session):
        series = EconomicSeries(series_id="PAYEMS", title="FRED payrolls", units="Thousands of Persons", source="FRED",
                                concept_id=PAYROLLS)
        session.add(series)
        session.flush()
        writer = ObservationVersionWriter(session)
        writer.apply(series, date(2026, 8, 1), 159075.0)
        writer.apply(series, date(2026, 7, 1), 158913.0)
        session.flush()
        return series

    def test_fred_rows_values_and_versions_are_unchanged(self, db_session):
        fred = self._seed_fred_payems(db_session)
        versions_before = db_session.execute(
            select(func.count()).select_from(ObservationVersion).where(ObservationVersion.economic_series_id == fred.id)
        ).scalar_one()

        _import(db_session)

        assert _values(db_session, "PAYEMS") == {date(2026, 7, 1): 158913.0, date(2026, 8, 1): 159075.0}
        assert db_session.execute(
            select(func.count()).select_from(ObservationVersion).where(ObservationVersion.economic_series_id == fred.id)
        ).scalar_one() == versions_before
        assert db_session.get(EconomicSeries, fred.id).source == "FRED"
        # A separate row holds the BLS data.
        assert _series(db_session, PAYROLLS).id != fred.id

    def test_readers_still_resolve_the_fred_row(self, db_session):
        self._seed_fred_payems(db_session)
        _import(db_session)
        assert active_binding(PAYROLLS).storage_series_id == "PAYEMS"

    def test_the_repository_refuses_to_write_into_a_row_owned_by_another_source(self, db_session):
        db_session.add(EconomicSeries(series_id=PAYROLLS, title="x", units="x", source="FRED", concept_id=PAYROLLS))
        db_session.flush()
        with pytest.raises(ValueError, match="refusing"):
            FirstPartyRepository(db_session).ensure_series(PAYROLLS, PAYROLLS, "t", "u", "BLS")

    def test_the_repository_refuses_a_non_first_party_source(self, db_session):
        with pytest.raises(ValueError):
            FirstPartyRepository(db_session).ensure_series("anything", PAYROLLS, "t", "u", "FRED")


class TestProviderFailureIsIsolated:
    def test_a_bls_outage_fails_bls_only(self, db_session):
        outcomes = _import(db_session, bls=StubBLS(raises=ProviderUnavailableError("BLS", "unreachable")))

        bls = next(o for o in outcomes if o.provider == "BLS")
        bea = next(o for o in outcomes if o.provider == "BEA")
        assert (bls.status, bls.error_class, bls.series) == ("FAILED", "ProviderUnavailableError", [])
        assert bea.status == "SUCCEEDED"
        for concept_id in BLS_CONCEPT_IDS:
            assert db_session.execute(
                select(EconomicSeries).where(EconomicSeries.series_id == concept_id)
            ).scalar_one_or_none() is None
        for concept_id in BEA_CONCEPT_IDS:
            assert _values(db_session, concept_id)

    def test_a_failed_run_is_recorded_with_a_class_name_only(self, db_session):
        _import(db_session, bea=StubBEA(raises=ProviderUnavailableError("BEA", "unreachable")))
        run = db_session.execute(select(ProviderIngestionRun).where(ProviderIngestionRun.provider == "BEA")).scalar_one()
        assert (run.status, run.error_class, run.observations_inserted) == ("FAILED", "ProviderUnavailableError", 0)

    def test_an_empty_series_is_partial_failure_not_success(self, db_session):
        empty = StubBEA(data={"DPCERG": [], "DPCCRG": StubBEA()._data["DPCCRG"]})
        (bea,) = _import(db_session, bea=empty, providers=("BEA",))
        assert bea.status == "PARTIAL_FAILURE"


class TestArguments:
    def test_keyless_bls_refuses_more_than_ten_years(self, db_session):
        with pytest.raises(ValueError, match="BLS_API_KEY"):
            _import(db_session, years=11)

    def test_bea_alone_may_import_more(self, db_session):
        (bea,) = _import(db_session, years=11, providers=("BEA",))
        assert bea.window_start == date(2016, 1, 1)

    def test_unknown_providers_are_refused(self, db_session):
        with pytest.raises(ValueError):
            _import(db_session, providers=("FRED",))
