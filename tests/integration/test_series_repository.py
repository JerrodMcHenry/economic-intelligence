"""Integration tests for SeriesRepository against a real, isolated
PostgreSQL test database (see tests/integration/conftest.py for the
safety guard and transaction-rollback isolation this relies on).

No FastAPI, no OpenAI, no live FRED -- SeriesRepository has no
dependency on any of them; these tests exercise the real repository
against real PostgreSQL semantics (upsert, unique constraints,
pagination) that a mocked/in-memory substitute would not prove.

Covers only methods that actually exist on SeriesRepository today --
nothing here invents a hypothetical API.
"""

from datetime import date

from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository

JAN, FEB, MAR, APR, MAY = (date(2024, m, 1) for m in range(1, 6))


def _series_response(series_id="UNRATE", title="Unemployment Rate", units="Percent", observations=None):
    return SeriesResponse(
        series_id=series_id,
        title=title,
        units=units,
        source="FRED",
        observations=observations or [],
    )


class TestSeriesCreationAndLookup:
    def test_save_series_creates_new_series(self, db_session):
        repo = SeriesRepository(db_session)
        repo.save_series(_series_response())
        db_session.flush()

        found = repo.get_series_by_series_id("UNRATE")
        assert found is not None
        assert found.title == "Unemployment Rate"
        assert found.units == "Percent"
        assert found.source == "FRED"

    def test_unknown_series_lookup_returns_none(self, db_session):
        repo = SeriesRepository(db_session)
        assert repo.get_series_by_series_id("NOPE_NOT_REAL") is None

    def test_observation_persistence(self, db_session):
        repo = SeriesRepository(db_session)
        repo.save_series(
            _series_response(observations=[Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        )
        db_session.flush()

        series = repo.get_series_by_series_id("UNRATE")
        observations, total = repo.get_observations(series.id, None, None, limit=100, offset=0, order="asc")
        assert total == 2
        assert [(o.observation_date, o.value) for o in observations] == [(JAN, 100.0), (FEB, 110.0)]


class TestIdempotentUpsert:
    def test_saving_same_series_twice_does_not_duplicate_the_series_row(self, db_session):
        repo = SeriesRepository(db_session)
        repo.save_series(_series_response())
        db_session.flush()
        repo.save_series(_series_response(title="Unemployment Rate (revised)"))
        db_session.flush()

        # Still exactly one economic_series row for this series_id.
        found = repo.get_series_by_series_id("UNRATE")
        assert found is not None
        assert found.title == "Unemployment Rate (revised)"  # metadata updated in place

    def test_duplicate_dates_do_not_create_duplicate_observations(self, db_session):
        repo = SeriesRepository(db_session)
        repo.save_series(_series_response(observations=[Observation(date=JAN, value=100.0)]))
        db_session.flush()
        repo.save_series(_series_response(observations=[Observation(date=JAN, value=999.0)]))
        db_session.flush()

        series = repo.get_series_by_series_id("UNRATE")
        observations, total = repo.get_observations(series.id, None, None, limit=100, offset=0, order="asc")
        assert total == 1  # one canonical row per (series, date), not two

    def test_existing_observation_value_updates_in_place(self, db_session):
        """Current documented semantics (save_series's own docstring):
        an existing observation for the same date is updated, not left
        stale and not duplicated."""
        repo = SeriesRepository(db_session)
        repo.save_series(_series_response(observations=[Observation(date=JAN, value=100.0)]))
        db_session.flush()
        repo.save_series(_series_response(observations=[Observation(date=JAN, value=105.0)]))
        db_session.flush()

        series = repo.get_series_by_series_id("UNRATE")
        observations, _ = repo.get_observations(series.id, None, None, limit=100, offset=0, order="asc")
        assert observations[0].value == 105.0

    def test_upsert_never_deletes_observations_absent_from_the_new_data(self, db_session):
        """save_series's documented semantics: "Existing observations for
        dates not present in `data` are left untouched (no implicit
        deletion of history)." """
        repo = SeriesRepository(db_session)
        repo.save_series(
            _series_response(observations=[Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        )
        db_session.flush()
        # A later sync that only returns Feb (e.g. a narrower FRED response) must not remove Jan.
        repo.save_series(_series_response(observations=[Observation(date=FEB, value=111.0)]))
        db_session.flush()

        series = repo.get_series_by_series_id("UNRATE")
        observations, total = repo.get_observations(series.id, None, None, limit=100, offset=0, order="asc")
        assert total == 2
        assert observations[0].observation_date == JAN and observations[0].value == 100.0
        assert observations[1].observation_date == FEB and observations[1].value == 111.0


class TestObservationOrderingFilteringPagination:
    def _seeded_series(self, db_session):
        repo = SeriesRepository(db_session)
        repo.save_series(
            _series_response(
                observations=[
                    Observation(date=JAN, value=100.0),
                    Observation(date=FEB, value=110.0),
                    Observation(date=MAR, value=121.0),
                    Observation(date=APR, value=133.1),
                    Observation(date=MAY, value=146.41),
                ]
            )
        )
        db_session.flush()
        return repo, repo.get_series_by_series_id("UNRATE")

    def test_ascending_order(self, db_session):
        repo, series = self._seeded_series(db_session)
        observations, _ = repo.get_observations(series.id, None, None, limit=100, offset=0, order="asc")
        assert [o.observation_date for o in observations] == [JAN, FEB, MAR, APR, MAY]

    def test_descending_order(self, db_session):
        repo, series = self._seeded_series(db_session)
        observations, _ = repo.get_observations(series.id, None, None, limit=100, offset=0, order="desc")
        assert [o.observation_date for o in observations] == [MAY, APR, MAR, FEB, JAN]

    def test_start_date_filtering(self, db_session):
        repo, series = self._seeded_series(db_session)
        observations, total = repo.get_observations(series.id, MAR, None, limit=100, offset=0, order="asc")
        assert [o.observation_date for o in observations] == [MAR, APR, MAY]
        assert total == 3

    def test_end_date_filtering(self, db_session):
        repo, series = self._seeded_series(db_session)
        observations, total = repo.get_observations(series.id, None, MAR, limit=100, offset=0, order="asc")
        assert [o.observation_date for o in observations] == [JAN, FEB, MAR]
        assert total == 3

    def test_combined_date_range_filtering(self, db_session):
        repo, series = self._seeded_series(db_session)
        observations, total = repo.get_observations(series.id, FEB, APR, limit=100, offset=0, order="asc")
        assert [o.observation_date for o in observations] == [FEB, MAR, APR]
        assert total == 3

    def test_limit(self, db_session):
        repo, series = self._seeded_series(db_session)
        observations, total = repo.get_observations(series.id, None, None, limit=2, offset=0, order="asc")
        assert [o.observation_date for o in observations] == [JAN, FEB]
        assert total == 5  # total reflects the pre-pagination match count

    def test_offset(self, db_session):
        repo, series = self._seeded_series(db_session)
        observations, total = repo.get_observations(series.id, None, None, limit=100, offset=2, order="asc")
        assert [o.observation_date for o in observations] == [MAR, APR, MAY]
        assert total == 5

    def test_limit_and_offset_combined(self, db_session):
        repo, series = self._seeded_series(db_session)
        observations, total = repo.get_observations(series.id, None, None, limit=2, offset=1, order="asc")
        assert [o.observation_date for o in observations] == [FEB, MAR]
        assert total == 5

    def test_total_reflects_filter_before_pagination(self, db_session):
        """`total` must agree with the filtered (date-ranged) population,
        not the whole series -- verified by combining a date filter with
        a limit narrower than that filtered population."""
        repo, series = self._seeded_series(db_session)
        observations, total = repo.get_observations(series.id, FEB, MAY, limit=1, offset=0, order="asc")
        assert len(observations) == 1
        assert total == 4  # Feb..May inclusive, before limit=1 is applied


class TestPrecedingObservationRetrieval:
    def _seeded_series(self, db_session):
        repo = SeriesRepository(db_session)
        repo.save_series(
            _series_response(
                observations=[
                    Observation(date=JAN, value=100.0),
                    Observation(date=FEB, value=110.0),
                    Observation(date=MAR, value=121.0),
                ]
            )
        )
        db_session.flush()
        return repo, repo.get_series_by_series_id("UNRATE")

    def test_correct_number_of_preceding_observations(self, db_session):
        repo, series = self._seeded_series(db_session)
        preceding = repo.get_preceding_observations(series.id, before_date=MAR, count=2)
        assert [(o.observation_date, o.value) for o in preceding] == [(JAN, 100.0), (FEB, 110.0)]

    def test_preceding_observations_returned_in_ascending_order(self, db_session):
        repo, series = self._seeded_series(db_session)
        preceding = repo.get_preceding_observations(series.id, before_date=MAR, count=2)
        assert [o.observation_date for o in preceding] == sorted(o.observation_date for o in preceding)

    def test_count_caps_how_many_are_returned(self, db_session):
        repo, series = self._seeded_series(db_session)
        preceding = repo.get_preceding_observations(series.id, before_date=MAR, count=1)
        assert [o.observation_date for o in preceding] == [FEB]  # the single most recent before MAR

    def test_no_preceding_observation_when_none_exists(self, db_session):
        repo, series = self._seeded_series(db_session)
        preceding = repo.get_preceding_observations(series.id, before_date=JAN, count=5)
        assert preceding == []


class TestReadPathsDoNotMutate:
    def test_get_observations_does_not_change_row_count_or_values(self, db_session):
        repo = SeriesRepository(db_session)
        repo.save_series(
            _series_response(observations=[Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        )
        db_session.flush()
        series = repo.get_series_by_series_id("UNRATE")

        before, before_total = repo.get_observations(series.id, None, None, limit=100, offset=0, order="asc")
        before_values = [(o.observation_date, o.value) for o in before]

        # Call it again, and call the other read methods too -- none of them should change anything.
        repo.get_observations(series.id, None, None, limit=100, offset=0, order="desc")
        repo.get_observations_in_range(series.id, None, None)
        repo.get_preceding_observations(series.id, before_date=FEB, count=1)

        after, after_total = repo.get_observations(series.id, None, None, limit=100, offset=0, order="asc")
        after_values = [(o.observation_date, o.value) for o in after]

        assert before_total == after_total
        assert before_values == after_values
