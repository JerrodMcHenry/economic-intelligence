"""Integration tests for ReleaseProcessingRepository against a real,
isolated PostgreSQL test database (see tests/conftest.py). No FastAPI,
no OpenAI, no FRED -- this repository has no dependency on any of them.

The four release_series_mappings rows seeded by
alembic/versions/cd476d227f99_seed_cpi_and_personal_income_and_.py
(CPIAUCSL/CPILFESL under release provider_release_id "10",
PCEPI/PCEPILFE under "54") are real, persistent, active data in the
isolated test database this file runs against -- tests that need their
OWN synthetic mapping use a provider_release_id well outside the real
curated range ("9001"+), the same discipline
tests/integration/test_release_repository.py already establishes.
"""

from datetime import date, datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.db.models import EconomicRelease, EconomicSeries, ReleaseSeriesMapping
from app.models.release_processing import AnalysisChangeRecord, ObservationChangeRecord
from app.repositories.release_processing_repository import ReleaseProcessingRepository
from app.repositories.release_repository import ReleaseRepository


def _release(session, name="Test Release", provider_release_id="9001", active=True):
    release = EconomicRelease(name=name, provider="FRED", provider_release_id=provider_release_id, active=active)
    session.add(release)
    session.flush()
    return release


class TestMappings:
    def test_real_curated_cpi_mapping_maps_to_headline_and_core_cpi(self, db_session):
        release = db_session.execute(
            sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "10")
        ).scalar_one()
        mappings = ReleaseProcessingRepository(db_session).get_active_mappings(release.id)
        assert sorted(m.series_id for m in mappings) == ["CPIAUCSL", "CPILFESL"]

    def test_real_curated_personal_income_and_outlays_mapping_maps_to_pce_and_core_pce(self, db_session):
        release = db_session.execute(
            sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "54")
        ).scalar_one()
        mappings = ReleaseProcessingRepository(db_session).get_active_mappings(release.id)
        assert sorted(m.series_id for m in mappings) == ["PCEPI", "PCEPILFE"]

    def test_no_mapping_seeded_for_unrelated_release_families(self, db_session):
        """Employment Situation, JOLTS, GDP, and Advance Retail Sales
        have no canonical Inflation Monitor consumer yet -- #18 V1
        deliberately does not seed a mapping for them."""
        unmapped_provider_release_ids = ["50", "192", "53", "9"]
        for provider_release_id in unmapped_provider_release_ids:
            release = db_session.execute(
                sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == provider_release_id)
            ).scalar_one()
            mappings = ReleaseProcessingRepository(db_session).get_active_mappings(release.id)
            assert mappings == [], f"provider_release_id {provider_release_id} unexpectedly has a mapping"

    def test_get_active_mappings_works_without_any_economic_series_row_existing(self, db_session):
        """The central design decision: a curated mapping is readable
        even though nothing has ever synced CPIAUCSL/CPILFESL as an
        EconomicSeries row -- there is no FK to EconomicSeries.id for
        this to depend on. Checks absence of THOSE specific rows
        (never asserts anything about global database state, which a
        long-lived shared test database cannot guarantee)."""
        assert (
            db_session.execute(sa.select(EconomicSeries).where(EconomicSeries.series_id.in_(["CPIAUCSL", "CPILFESL"]))).first()
            is None
        )
        release = db_session.execute(
            sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "10")
        ).scalar_one()
        mappings = ReleaseProcessingRepository(db_session).get_active_mappings(release.id)
        assert len(mappings) == 2

    def test_inactive_mapping_is_excluded(self, db_session):
        release = _release(db_session)
        repo = ReleaseProcessingRepository(db_session)

        db_session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id="UNRATE", active=False))
        db_session.flush()
        assert repo.get_active_mappings(release.id) == []

    def test_mapping_uniqueness_enforced_at_the_database_level(self, db_session):
        release = _release(db_session)
        db_session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id="UNRATE", active=True))
        db_session.flush()
        db_session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id="UNRATE", active=True))
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestSeriesAndObservationWrites:
    def test_create_series_then_get_by_series_id_round_trips(self, db_session):
        repo = ReleaseProcessingRepository(db_session)
        assert repo.get_series_by_series_id("UNRATE") is None
        created = repo.create_series("UNRATE", "Unemployment Rate", "Percent")
        found = repo.get_series_by_series_id("UNRATE")
        assert found is not None and found.id == created.id

    def test_write_observation_inserts_when_absent(self, db_session):
        repo = ReleaseProcessingRepository(db_session)
        series = repo.create_series("UNRATE", "Unemployment Rate", "Percent")
        repo.write_observation(series.id, date(2026, 1, 1), 4.1)
        assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): 4.1}

    def test_write_observation_overwrites_when_present(self, db_session):
        repo = ReleaseProcessingRepository(db_session)
        series = repo.create_series("UNRATE", "Unemployment Rate", "Percent")
        repo.write_observation(series.id, date(2026, 1, 1), 4.1)
        repo.write_observation(series.id, date(2026, 1, 1), 4.2)
        assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): 4.2}

    def test_write_observation_can_write_and_overwrite_a_none_value(self, db_session):
        repo = ReleaseProcessingRepository(db_session)
        series = repo.create_series("UNRATE", "Unemployment Rate", "Percent")
        repo.write_observation(series.id, date(2026, 1, 1), None)
        assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): None}
        repo.write_observation(series.id, date(2026, 1, 1), 4.1)
        assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): 4.1}

    def test_get_observations_by_date_returns_full_history(self, db_session):
        repo = ReleaseProcessingRepository(db_session)
        series = repo.create_series("UNRATE", "Unemployment Rate", "Percent")
        repo.write_observation(series.id, date(2026, 1, 1), 4.0)
        repo.write_observation(series.id, date(2026, 2, 1), 4.1)
        assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): 4.0, date(2026, 2, 1): 4.1}


class TestCheckRunAndUpdatePersistence:
    def test_add_check_run_persists_and_assigns_an_id(self, db_session):
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        repo = ReleaseProcessingRepository(db_session)
        now = datetime.now(timezone.utc)
        run = repo.add_check_run(occurrence.id, "NO_CHANGE", now, now)
        assert run.id is not None
        assert run.status == "NO_CHANGE"

    def test_add_observation_update_persists_a_new_change(self, db_session):
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        repo = ReleaseProcessingRepository(db_session)
        now = datetime.now(timezone.utc)
        run = repo.add_check_run(occurrence.id, "CHANGED", now, now)
        repo.add_observation_update(
            run.id,
            ObservationChangeRecord(
                series_id="UNRATE", observation_date=date(2026, 1, 1), change_type="NEW", previous_value=None, new_value=4.1, detected_at=now
            ),
        )
        updates = repo.list_observation_updates_for_run(run.id)
        assert len(updates) == 1
        assert updates[0].change_type == "NEW"
        assert updates[0].previous_value is None
        assert updates[0].new_value == 4.1

    def test_add_analysis_update_persists_a_new_analytical_consequence(self, db_session):
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        repo = ReleaseProcessingRepository(db_session)
        now = datetime.now(timezone.utc)
        run = repo.add_check_run(occurrence.id, "CHANGED", now, now)
        repo.add_analysis_update(
            run.id,
            AnalysisChangeRecord(
                component="PRIMARY_MOMENTUM",
                event_type="STATE_CHANGED",
                field="state",
                previous_value="STABLE",
                current_value="MIXED",
                delta=None,
                evaluation_period=date(2026, 7, 1),
                methodology_id="inflation_v1.0",
                data_basis="latest_revised_data",
            ),
        )
        updates = repo.list_analysis_updates_for_run(run.id)
        assert len(updates) == 1
        assert updates[0].previous_value == "STABLE"
        assert updates[0].current_value == "MIXED"

    def test_analysis_update_round_trips_a_numeric_value_as_string_exactly(self, db_session):
        """str(float) round-trips exactly -- proven directly, not
        assumed (see ReleaseAnalysisUpdate's own docstring)."""
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        repo = ReleaseProcessingRepository(db_session)
        now = datetime.now(timezone.utc)
        run = repo.add_check_run(occurrence.id, "CHANGED", now, now)
        repo.add_analysis_update(
            run.id,
            AnalysisChangeRecord(
                component="TARGET",
                event_type="METRIC_CHANGED",
                field="target_gap_pp",
                previous_value=1.7011657214870874,
                current_value=1.7011657214870875,
                delta=1e-16,
                evaluation_period=date(2026, 7, 1),
                methodology_id="inflation_v1.0",
                data_basis="latest_revised_data",
            ),
        )
        stored = repo.list_analysis_updates_for_run(run.id)[0]
        assert float(stored.previous_value) == 1.7011657214870874
        assert float(stored.current_value) == 1.7011657214870875

    def test_list_check_runs_for_occurrence_returns_every_run_including_retries(self, db_session):
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        repo = ReleaseProcessingRepository(db_session)
        now = datetime.now(timezone.utc)
        repo.add_check_run(occurrence.id, "NO_CHANGE", now, now)
        repo.add_check_run(occurrence.id, "NO_CHANGE", now, now)
        runs = repo.list_check_runs_for_occurrence(occurrence.id)
        assert len(runs) == 2


def _occurrence(session, release, scheduled_date=date(2026, 7, 15)):
    return ReleaseRepository(session).upsert_occurrence(release.id, scheduled_date)
