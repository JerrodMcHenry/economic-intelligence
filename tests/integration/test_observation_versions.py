"""Integration tests for system-time observation versioning
(Increment #31), against a real, isolated PostgreSQL test database.

These prove the properties the audit found missing: that history is no
longer path-dependent, that a revision preserves both values, that
as-of reads answer at exact interval boundaries, and that the database
itself -- not merely application code -- forbids two open versions.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.clients.treasury import NOMINAL_DATASET
from app.db.models import EconomicObservation, EconomicSeries, ObservationVersion
from app.models.rates import NOMINAL_10Y_SERIES_ID, PROVIDER, SERIES_TITLES, SERIES_UNITS
from app.models.series import Observation, SeriesResponse
from app.repositories.observation_versions import (
    ORIGIN_RATES_INGESTION,
    ORIGIN_RELEASE_PROCESSING,
    ORIGIN_SERIES_SYNC,
    ObservationVersionRepository,
    ObservationVersionWriter,
)
from app.repositories.rates_repository import ProvenanceRecord, RatesRepository
from app.repositories.release_processing_repository import ReleaseProcessingRepository
from app.repositories.series_repository import SeriesRepository

pytestmark = pytest.mark.integration

SERIES = "CPIAUCSL"
PERIOD = date(2026, 1, 1)

T1 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _series(session, series_id: str = SERIES) -> EconomicSeries:
    """Get-or-create: the shared test database may already carry this
    canonical series from another suite, and this test cares about
    versions, not about owning the series row."""
    existing = session.execute(select(EconomicSeries).where(EconomicSeries.series_id == series_id)).scalar_one_or_none()
    if existing is not None:
        return existing
    series = EconomicSeries(series_id=series_id, title=series_id, units="Index", source="FRED")
    session.add(series)
    session.flush()
    return series


def _write(session, series, value, at, origin=ORIGIN_SERIES_SYNC, period=PERIOD):
    return ObservationVersionWriter(session, recorded_at=at, origin=origin).apply(series, period, value)


def _versions(session, series_id: str = SERIES, period: date = PERIOD):
    return ObservationVersionRepository(session).list_versions(series_id, period)


class TestVersionStorage:
    def test_a_new_observation_opens_its_first_version(self, db_session):
        series = _series(db_session)
        assert _write(db_session, series, 100.0, T1) == "INSERTED"

        versions = _versions(db_session)
        assert len(versions) == 1
        assert versions[0].value == 100.0
        assert versions[0].recorded_from == T1
        assert versions[0].recorded_to is None
        assert versions[0].change_type == "NEW"
        assert versions[0].is_backfilled is False

    def test_an_unchanged_observation_creates_no_version(self, db_session):
        """A re-sync confirming what is already stored is not a new fact
        about the world; recording one would inflate history and blur
        genuine revisions."""
        series = _series(db_session)
        _write(db_session, series, 100.0, T1)

        assert _write(db_session, series, 100.0, T2) == "UNCHANGED"
        assert len(_versions(db_session)) == 1

    def test_a_revision_closes_the_old_version_and_opens_a_new_one(self, db_session):
        series = _series(db_session)
        _write(db_session, series, 100.0, T1)

        assert _write(db_session, series, 101.5, T2) == "REVISED"

        versions = _versions(db_session)
        assert [(v.value, v.recorded_from, v.recorded_to) for v in versions] == [
            (100.0, T1, T2),
            (101.5, T2, None),
        ]
        assert versions[1].change_type == "REVISED"

    def test_multiple_revisions_preserve_every_value(self, db_session):
        series = _series(db_session)
        _write(db_session, series, 100.0, T1)
        _write(db_session, series, 101.5, T2)
        _write(db_session, series, 99.25, T3)

        versions = _versions(db_session)
        assert [v.value for v in versions] == [100.0, 101.5, 99.25]
        assert [v.recorded_to for v in versions] == [T2, T3, None]

    def test_exactly_one_open_version_exists_at_all_times(self, db_session):
        series = _series(db_session)
        for value, at in ((100.0, T1), (101.0, T2), (102.0, T3)):
            _write(db_session, series, value, at)

        open_versions = [v for v in _versions(db_session) if v.recorded_to is None]
        assert len(open_versions) == 1
        assert open_versions[0].value == 102.0

    def test_a_transition_into_missing_is_a_revision_not_a_silent_drop(self, db_session):
        series = _series(db_session)
        _write(db_session, series, 100.0, T1)

        assert _write(db_session, series, None, T2) == "REVISED"
        assert [v.value for v in _versions(db_session)] == [100.0, None]

    def test_canonical_value_and_open_version_never_disagree(self, db_session):
        series = _series(db_session)
        _write(db_session, series, 100.0, T1)
        _write(db_session, series, 101.5, T2)
        db_session.flush()

        canonical = db_session.execute(
            select(EconomicObservation).where(
                EconomicObservation.economic_series_id == series.id,
                EconomicObservation.observation_date == PERIOD,
            )
        ).scalar_one()
        open_version = next(v for v in _versions(db_session) if v.recorded_to is None)
        assert canonical.value == open_version.value == 101.5

    def test_a_backwards_timestamp_is_refused_rather_than_corrupting_the_interval(self, db_session):
        series = _series(db_session)
        _write(db_session, series, 100.0, T2)
        with pytest.raises(ValueError, match="strictly after"):
            _write(db_session, series, 101.0, T1)


class TestDatabaseEnforcedInvariants:
    def test_the_database_rejects_a_second_open_version(self, db_session):
        """The partial unique index is the real guarantee -- application
        code could be wrong, and this would still hold."""
        series = _series(db_session)
        _write(db_session, series, 100.0, T1)
        db_session.flush()

        db_session.add(
            ObservationVersion(
                economic_series_id=series.id,
                observation_date=PERIOD,
                value=999.0,
                recorded_from=T2,
                recorded_to=None,
                change_type="REVISED",
                origin=ORIGIN_SERIES_SYNC,
                is_backfilled=False,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_the_database_rejects_a_backwards_closed_interval(self, db_session):
        series = _series(db_session)
        db_session.add(
            ObservationVersion(
                economic_series_id=series.id,
                observation_date=PERIOD,
                value=100.0,
                recorded_from=T2,
                recorded_to=T1,
                change_type="NEW",
                origin=ORIGIN_SERIES_SYNC,
                is_backfilled=False,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_the_database_rejects_duplicate_versions_starting_at_the_same_instant(self, db_session):
        series = _series(db_session)
        _write(db_session, series, 100.0, T1)
        _write(db_session, series, 101.0, T2)
        db_session.flush()

        db_session.add(
            ObservationVersion(
                economic_series_id=series.id,
                observation_date=PERIOD,
                value=555.0,
                recorded_from=T1,
                recorded_to=T2,
                change_type="REVISED",
                origin=ORIGIN_SERIES_SYNC,
                is_backfilled=False,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_a_rolled_back_transaction_leaves_no_version_behind(self, db_session):
        """Canonical write and version write share one unit of work, so
        they can never diverge across a rollback."""
        series = _series(db_session)
        _write(db_session, series, 100.0, T1)
        db_session.flush()

        savepoint = db_session.begin_nested()
        _write(db_session, series, 101.0, T2)
        db_session.flush()
        savepoint.rollback()

        versions = _versions(db_session)
        assert [v.value for v in versions] == [100.0]
        assert versions[0].recorded_to is None


class TestEveryWritePathVersions:
    def test_generic_series_sync_versions_a_revision(self, db_session):
        repo = SeriesRepository(db_session)
        repo.save_series(
            SeriesResponse(series_id=SERIES, title="CPI", units="Index", observations=[Observation(date=PERIOD, value=100.0)])
        )
        db_session.flush()
        repo.save_series(
            SeriesResponse(series_id=SERIES, title="CPI", units="Index", observations=[Observation(date=PERIOD, value=100.9)])
        )
        db_session.flush()

        assert [v.value for v in _versions(db_session)] == [100.0, 100.9]

    def test_generic_series_sync_of_identical_data_adds_no_version(self, db_session):
        repo = SeriesRepository(db_session)
        payload = SeriesResponse(
            series_id=SERIES, title="CPI", units="Index", observations=[Observation(date=PERIOD, value=100.0)]
        )
        repo.save_series(payload)
        db_session.flush()
        repo.save_series(payload)
        db_session.flush()

        assert len(_versions(db_session)) == 1

    def test_release_processing_versions_a_revision(self, db_session):
        series = _series(db_session)
        repo = ReleaseProcessingRepository(db_session)
        repo.write_observation(series.id, PERIOD, 100.0, recorded_at=T1)
        repo.write_observation(series.id, PERIOD, 102.0, recorded_at=T2)
        db_session.flush()

        versions = _versions(db_session)
        assert [(v.value, v.origin) for v in versions] == [
            (100.0, ORIGIN_RELEASE_PROCESSING),
            (102.0, ORIGIN_RELEASE_PROCESSING),
        ]
        assert versions[0].recorded_to == T2

    def test_rates_ingestion_versions_a_revision(self, db_session):
        """#29 recorded only a `revision_count`, which cannot
        reconstruct anything. A Treasury revision now preserves the
        previous value like every other path."""
        repo = RatesRepository(db_session)
        series = repo.ensure_series(NOMINAL_10Y_SERIES_ID, SERIES_TITLES[NOMINAL_10Y_SERIES_ID], SERIES_UNITS, PROVIDER)

        def provenance(at):
            return ProvenanceRecord(
                provider=PROVIDER,
                dataset=NOMINAL_DATASET,
                source_series_field="BC_10YEAR",
                source_url="https://home.treasury.gov/example",
                retrieved_at=at,
            )

        assert repo.upsert_observation(series, PERIOD, 5.01, provenance(T1)) == "INSERTED"
        assert repo.upsert_observation(series, PERIOD, 5.01, provenance(T2)) == "UNCHANGED"
        assert repo.upsert_observation(series, PERIOD, 5.07, provenance(T3)) == "REVISED"
        db_session.flush()

        versions = _versions(db_session, NOMINAL_10Y_SERIES_ID)
        assert [(v.value, v.origin) for v in versions] == [
            (5.01, ORIGIN_RATES_INGESTION),
            (5.07, ORIGIN_RATES_INGESTION),
        ]
        # #29's provenance is preserved alongside, not replaced.
        provenance_row = repo.get_provenance(NOMINAL_10Y_SERIES_ID, PERIOD)
        assert provenance_row.revision_count == 1
        assert provenance_row.last_revised_at == T3


class TestAsOfReads:
    @pytest.fixture
    def revised_series(self, db_session):
        series = _series(db_session)
        _write(db_session, series, 100.0, T1)
        _write(db_session, series, 101.5, T2)
        db_session.flush()
        return series

    def test_before_the_first_version_nothing_was_known(self, revised_series, db_session):
        """Never falls back to current values -- that substitution is
        exactly what makes a replay meaningless."""
        assert ObservationVersionRepository(db_session).get_observations_as_of(SERIES, T1 - timedelta(seconds=1)) == []

    def test_at_recorded_from_the_new_version_is_visible(self, revised_series, db_session):
        rows = ObservationVersionRepository(db_session).get_observations_as_of(SERIES, T1)
        assert [row.value for row in rows] == [100.0]

    def test_immediately_before_recorded_to_the_old_version_is_still_visible(self, revised_series, db_session):
        rows = ObservationVersionRepository(db_session).get_observations_as_of(SERIES, T2 - timedelta(microseconds=1))
        assert [row.value for row in rows] == [100.0]

    def test_at_recorded_to_the_new_version_is_visible(self, revised_series, db_session):
        """Half-open `[from, to)`: the boundary instant belongs to the
        NEW version, deterministically and without ambiguity."""
        rows = ObservationVersionRepository(db_session).get_observations_as_of(SERIES, T2)
        assert [row.value for row in rows] == [101.5]

    def test_now_returns_the_current_version(self, revised_series, db_session):
        rows = ObservationVersionRepository(db_session).get_observations_as_of(SERIES, datetime.now(timezone.utc))
        assert [row.value for row in rows] == [101.5]

    def test_an_unknown_series_is_empty_not_an_error(self, db_session):
        assert ObservationVersionRepository(db_session).get_observations_as_of("NOT_A_SERIES", T2) == []

    def test_multiple_observations_resolve_independently(self, db_session):
        series = _series(db_session)
        _write(db_session, series, 100.0, T1, period=date(2026, 1, 1))
        _write(db_session, series, 200.0, T1, period=date(2026, 2, 1))
        _write(db_session, series, 201.0, T2, period=date(2026, 2, 1))
        db_session.flush()

        repo = ObservationVersionRepository(db_session)
        assert [(r.observation_date, r.value) for r in repo.get_observations_as_of(SERIES, T1)] == [
            (date(2026, 1, 1), 100.0),
            (date(2026, 2, 1), 200.0),
        ]
        assert [(r.observation_date, r.value) for r in repo.get_observations_as_of(SERIES, T2)] == [
            (date(2026, 1, 1), 100.0),
            (date(2026, 2, 1), 201.0),
        ]


class TestBackfillSemantics:
    def test_a_backfilled_version_is_marked_and_a_later_revision_closes_it(self, db_session):
        """A backfilled row means "this value existed by then", never
        "this was the original publication" -- so it is flagged, and it
        behaves like any other open version from that point on."""
        series = _series(db_session)
        db_session.add(
            ObservationVersion(
                economic_series_id=series.id,
                observation_date=PERIOD,
                value=100.0,
                recorded_from=T1,
                recorded_to=None,
                change_type="BACKFILL",
                origin="BACKFILL",
                is_backfilled=True,
            )
        )
        db_session.add(EconomicObservation(economic_series_id=series.id, observation_date=PERIOD, value=100.0))
        db_session.flush()

        _write(db_session, series, 103.0, T2)
        db_session.flush()

        versions = _versions(db_session)
        assert [(v.value, v.is_backfilled, v.recorded_to) for v in versions] == [
            (100.0, True, T2),
            (103.0, False, None),
        ]

        rows = ObservationVersionRepository(db_session).get_observations_as_of(SERIES, T1)
        assert rows[0].is_backfilled is True

    def test_the_migration_backfilled_every_pre_existing_observation(self, db_session):
        """Whatever the test database already contained before this
        transaction, no observation may be left without history."""
        orphans = db_session.execute(
            text(
                """
                SELECT count(*) FROM economic_observations o
                WHERE NOT EXISTS (
                    SELECT 1 FROM observation_versions v
                    WHERE v.economic_series_id = o.economic_series_id
                      AND v.observation_date = o.observation_date
                )
                """
            )
        ).scalar_one()
        assert orphans == 0
