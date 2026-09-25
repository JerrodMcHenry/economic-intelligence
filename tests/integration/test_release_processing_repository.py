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

from datetime import date, datetime, timedelta, timezone

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
            sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "cpi")
        ).scalar_one()
        mappings = ReleaseProcessingRepository(db_session).get_active_mappings(release.id)
        assert sorted(m.series_id for m in mappings) == ["us.cpi.core.price-index.sa.monthly", "us.cpi.headline.price-index.sa.monthly"]

    def test_real_curated_personal_income_and_outlays_mapping_maps_to_pce_and_core_pce(self, db_session):
        release = db_session.execute(
            sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "pio")
        ).scalar_one()
        mappings = ReleaseProcessingRepository(db_session).get_active_mappings(release.id)
        assert sorted(m.series_id for m in mappings) == ["us.pce.core.price-index.sa.monthly", "us.pce.headline.price-index.sa.monthly"]

    def test_no_mapping_seeded_for_unrelated_release_families(self, db_session):
        """JOLTS, GDP, and Advance Retail Sales have no canonical
        monitor consumer yet -- deliberately no seeded mapping for
        them. Employment Situation (50) is NOT in this list as of
        Increment #20D.2 -- it now has a canonical Labor Monitor
        consumer (PAYEMS/UNRATE), seeded by migration 09f4c0959e9f
        per docs/architecture/labor-release-integration-v1.md §5 --
        see test_employment_situation_maps_exactly_payems_and_unrate
        below for its own positive assertion."""
        unmapped_provider_release_ids = ["192", "53", "9"]
        for provider_release_id in unmapped_provider_release_ids:
            release = db_session.execute(
                sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == provider_release_id)
            ).scalar_one()
            mappings = ReleaseProcessingRepository(db_session).get_active_mappings(release.id)
            assert mappings == [], f"provider_release_id {provider_release_id} unexpectedly has a mapping"

    def test_employment_situation_maps_exactly_payems_and_unrate(self, db_session):
        """Increment #20D.2: Employment Situation (FRED 50) maps
        exactly PAYEMS and UNRATE -- no CIVPART, no JOLTS, no wages/
        claims/hours/earnings/other CES series (per the frozen
        contract's own explicit exclusion list, §5)."""
        release = db_session.execute(
            sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "empsit")
        ).scalar_one()
        mappings = ReleaseProcessingRepository(db_session).get_active_mappings(release.id)
        assert sorted(m.series_id for m in mappings) == ["us.nonfarm.payroll-employment.sa.monthly", "us.unemployment-rate.sa.monthly"]

    def test_get_active_mappings_works_without_any_economic_series_row_existing(self, db_session):
        """The central design decision: a curated mapping is readable
        even though nothing has ever synced CPIAUCSL/CPILFESL as an
        EconomicSeries row -- there is no FK to EconomicSeries.id for
        this to depend on. Checks absence of THOSE specific rows
        (never asserts anything about global database state, which a
        long-lived shared test database cannot guarantee)."""
        assert (
            db_session.execute(sa.select(EconomicSeries).where(EconomicSeries.series_id.in_(["us.cpi.headline.price-index.sa.monthly", "us.cpi.core.price-index.sa.monthly"]))).first()
            is None
        )
        release = db_session.execute(
            sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "cpi")
        ).scalar_one()
        mappings = ReleaseProcessingRepository(db_session).get_active_mappings(release.id)
        assert len(mappings) == 2

    def test_inactive_mapping_is_excluded(self, db_session):
        release = _release(db_session)
        repo = ReleaseProcessingRepository(db_session)

        db_session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id="us.unemployment-rate.sa.monthly", active=False))
        db_session.flush()
        assert repo.get_active_mappings(release.id) == []

    def test_mapping_uniqueness_enforced_at_the_database_level(self, db_session):
        release = _release(db_session)
        db_session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id="us.unemployment-rate.sa.monthly", active=True))
        db_session.flush()
        db_session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id="us.unemployment-rate.sa.monthly", active=True))
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestSeriesAndObservationWrites:
    def test_create_series_then_get_by_series_id_round_trips(self, db_session):
        repo = ReleaseProcessingRepository(db_session)
        assert repo.get_series_by_series_id("us.unemployment-rate.sa.monthly") is None
        created = repo.create_series("us.unemployment-rate.sa.monthly", "Unemployment Rate", "Percent")
        found = repo.get_series_by_series_id("us.unemployment-rate.sa.monthly")
        assert found is not None and found.id == created.id

    def test_write_observation_inserts_when_absent(self, db_session):
        repo = ReleaseProcessingRepository(db_session)
        series = repo.create_series("us.unemployment-rate.sa.monthly", "Unemployment Rate", "Percent")
        repo.write_observation(series.id, date(2026, 1, 1), 4.1)
        assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): 4.1}

    def test_write_observation_overwrites_when_present(self, db_session):
        repo = ReleaseProcessingRepository(db_session)
        series = repo.create_series("us.unemployment-rate.sa.monthly", "Unemployment Rate", "Percent")
        repo.write_observation(series.id, date(2026, 1, 1), 4.1)
        repo.write_observation(series.id, date(2026, 1, 1), 4.2)
        assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): 4.2}

    def test_write_observation_can_write_and_overwrite_a_none_value(self, db_session):
        repo = ReleaseProcessingRepository(db_session)
        series = repo.create_series("us.unemployment-rate.sa.monthly", "Unemployment Rate", "Percent")
        repo.write_observation(series.id, date(2026, 1, 1), None)
        assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): None}
        repo.write_observation(series.id, date(2026, 1, 1), 4.1)
        assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): 4.1}

    def test_get_observations_by_date_returns_full_history(self, db_session):
        repo = ReleaseProcessingRepository(db_session)
        series = repo.create_series("us.unemployment-rate.sa.monthly", "Unemployment Rate", "Percent")
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
                series_id="us.unemployment-rate.sa.monthly", observation_date=date(2026, 1, 1), change_type="NEW", previous_value=None, new_value=4.1, detected_at=now
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


# ---------------------------------------------------------------------
# Due-work discovery (Increment #25C, frozen contract
# docs/product/automated-economic-maintenance-v1.md §8/§10/§14/§50)
# ---------------------------------------------------------------------

AS_OF = date(2026, 8, 15)


def _mapping(session, release, series_id="us.unemployment-rate.sa.monthly", active=True):
    session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id=series_id, active=active))
    session.flush()


class TestListDueOccurrenceIds:
    def test_unmapped_occurrence_is_never_due(self, db_session):
        """An occurrence whose release has no active mapping at all has
        nothing for release processing to check (frozen §8's own first
        rule) -- must never be surfaced, even though it is otherwise
        eligible."""
        release = _release(db_session, provider_release_id="9301")
        _occurrence(db_session, release, scheduled_date=AS_OF)
        due = ReleaseProcessingRepository(db_session).list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert due == []

    def test_future_scheduled_occurrence_is_never_due(self, db_session):
        release = _release(db_session, provider_release_id="9302")
        _mapping(db_session, release)
        _occurrence(db_session, release, scheduled_date=date(2099, 1, 1))
        due = ReleaseProcessingRepository(db_session).list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert due == []

    def test_unresolved_occurrence_with_no_check_run_at_all_is_due(self, db_session):
        release = _release(db_session, provider_release_id="9303")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, scheduled_date=AS_OF)
        due = ReleaseProcessingRepository(db_session).list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert due == [occurrence.id]

    def test_same_day_scheduled_occurrence_is_eligible_and_due(self, db_session):
        """Release times are unknown -- today's own scheduled date IS
        eligible (mirrors OccurrenceNotEligibleError's own boundary)."""
        release = _release(db_session, provider_release_id="9304")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, scheduled_date=AS_OF)
        due = ReleaseProcessingRepository(db_session).list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert occurrence.id in due

    def test_occurrence_settled_today_is_excluded(self, db_session):
        """A NO_CHANGE run completed TODAY means every currently-active
        mapped series was already successfully queried today (frozen
        §10's own settlement rule) -- excluded from today's due list."""
        release = _release(db_session, provider_release_id="9305")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, scheduled_date=AS_OF)
        repo = ReleaseProcessingRepository(db_session)
        today_midday = datetime(AS_OF.year, AS_OF.month, AS_OF.day, 12, tzinfo=timezone.utc)
        repo.add_check_run(occurrence.id, "NO_CHANGE", today_midday, today_midday)

        due = repo.list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert occurrence.id not in due

    def test_occurrence_settled_changed_today_is_also_excluded(self, db_session):
        """CHANGED counts as settled exactly like NO_CHANGE (frozen §10
        -- settlement is about "did we successfully ask everyone," not
        "did everyone answer with a change")."""
        release = _release(db_session, provider_release_id="9306")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, scheduled_date=AS_OF)
        repo = ReleaseProcessingRepository(db_session)
        today_midday = datetime(AS_OF.year, AS_OF.month, AS_OF.day, 12, tzinfo=timezone.utc)
        repo.add_check_run(occurrence.id, "CHANGED", today_midday, today_midday)

        due = repo.list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert occurrence.id not in due

    def test_occurrence_settled_yesterday_is_due_again_today(self, db_session):
        """Frozen §10's own conservative "small, bounded number of
        additional checks" for a genuinely late-arriving revision --
        a settled occurrence, still within its retry window, is due
        again exactly once per day, never permanently excluded."""
        release = _release(db_session, provider_release_id="9307")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, scheduled_date=AS_OF)
        repo = ReleaseProcessingRepository(db_session)
        yesterday_midday = datetime(AS_OF.year, AS_OF.month, AS_OF.day - 1, 12, tzinfo=timezone.utc)
        repo.add_check_run(occurrence.id, "NO_CHANGE", yesterday_midday, yesterday_midday)

        due = repo.list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert occurrence.id in due

    def test_partial_failure_today_does_not_count_as_settled_and_remains_due(self, db_session):
        """PARTIAL_FAILURE/FAILED_PROVIDER never count as a settled
        check (frozen §12) -- same-day retry remains available,
        bounded only by the external scheduler's own cadence (§14),
        never by this query."""
        release = _release(db_session, provider_release_id="9308")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, scheduled_date=AS_OF)
        repo = ReleaseProcessingRepository(db_session)
        today_midday = datetime(AS_OF.year, AS_OF.month, AS_OF.day, 12, tzinfo=timezone.utc)
        repo.add_check_run(occurrence.id, "PARTIAL_FAILURE", today_midday, today_midday)

        due = repo.list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert occurrence.id in due

    def test_failed_provider_today_does_not_count_as_settled_and_remains_due(self, db_session):
        release = _release(db_session, provider_release_id="9309")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, scheduled_date=AS_OF)
        repo = ReleaseProcessingRepository(db_session)
        today_midday = datetime(AS_OF.year, AS_OF.month, AS_OF.day, 12, tzinfo=timezone.utc)
        repo.add_check_run(occurrence.id, "FAILED_PROVIDER", today_midday, today_midday)

        due = repo.list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert occurrence.id in due

    def test_occurrence_older_than_retry_window_is_bounded_out(self, db_session):
        """Frozen §14/§50: bounded backfill -- automation never revisits
        ancient, permanently-unresolved history."""
        release = _release(db_session, provider_release_id="9310")
        _mapping(db_session, release)
        ancient = AS_OF - timedelta(days=30)
        occurrence = _occurrence(db_session, release, scheduled_date=ancient)
        due = ReleaseProcessingRepository(db_session).list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert occurrence.id not in due

    def test_occurrence_exactly_at_the_retry_window_boundary_is_still_due(self, db_session):
        release = _release(db_session, provider_release_id="9311")
        _mapping(db_session, release)
        boundary = date(AS_OF.year, AS_OF.month, AS_OF.day - 7)
        occurrence = _occurrence(db_session, release, scheduled_date=boundary)
        due = ReleaseProcessingRepository(db_session).list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert occurrence.id in due

    def test_inactive_mapping_does_not_make_an_occurrence_due(self, db_session):
        release = _release(db_session, provider_release_id="9312")
        _mapping(db_session, release, active=False)
        _occurrence(db_session, release, scheduled_date=AS_OF)
        due = ReleaseProcessingRepository(db_session).list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert due == []

    def test_deterministic_ordering_oldest_scheduled_date_first(self, db_session):
        release = _release(db_session, provider_release_id="9313")
        _mapping(db_session, release)
        newer = _occurrence(db_session, release, scheduled_date=AS_OF)
        older = _occurrence(db_session, release, scheduled_date=date(AS_OF.year, AS_OF.month, AS_OF.day - 2))
        middle = _occurrence(db_session, release, scheduled_date=date(AS_OF.year, AS_OF.month, AS_OF.day - 1))

        due = ReleaseProcessingRepository(db_session).list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert due == [older.id, middle.id, newer.id]

    def test_real_curated_cpi_release_occurrence_is_discoverable_as_due(self, db_session):
        """The real, migration-seeded CPI mapping (provider_release_id
        "10") is processable through this exact same due-work query
        with zero special-casing -- proving this isn't scoped to
        synthetic test releases only."""
        release = db_session.execute(sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "cpi")).scalar_one()
        occurrence = _occurrence(db_session, release, scheduled_date=AS_OF)
        due = ReleaseProcessingRepository(db_session).list_due_occurrence_ids(AS_OF, retry_window_days=7)
        assert occurrence.id in due
