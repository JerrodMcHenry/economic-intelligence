"""Integration tests for EconomicDataService's database-backed behavior
against a real, isolated PostgreSQL test database. No live FRED: every
service under test here is constructed with NO FREDClient
(`EconomicDataService()`), and none of the methods exercised
(`get_observations`, `get_transformed_observations`) ever reference a
FRED client at all -- see app/services/economic_data.py.

The boundary-context tests are the important ones in this file: they
prove Increment 005/007's documented "retrieve preceding observations so
a transformation at the start of the requested range is mathematically
correct, then trim them back out" behavior end-to-end against a real
database, with independently hand-computed expected values.
"""

from datetime import date

import pytest

from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.economic_data import (
    EconomicDataService,
    InvalidDateRangeError,
    InvalidWindowError,
    SeriesNotFoundError,
)

JAN, FEB, MAR, APR = (date(2024, m, 1) for m in range(1, 5))


def _seed(db_session, series_id="UNRATE", observations=None):
    SeriesRepository(db_session).save_series(
        SeriesResponse(series_id=series_id, title="Unemployment Rate", units="Percent", observations=observations or [])
    )
    db_session.flush()


class TestGetObservations:
    def test_reads_persisted_data(self, db_session):
        _seed(db_session, observations=[Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        service = EconomicDataService()
        result = service.get_observations("UNRATE", db_session, start_date=None, end_date=None, limit=100, offset=0, order="asc")
        assert [(o.date, o.value) for o in result.observations] == [(JAN, 100.0), (FEB, 110.0)]

    def test_date_filtering(self, db_session):
        _seed(
            db_session,
            observations=[Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0), Observation(date=MAR, value=121.0)],
        )
        service = EconomicDataService()
        result = service.get_observations("UNRATE", db_session, start_date=FEB, end_date=None, limit=100, offset=0, order="asc")
        assert [o.date for o in result.observations] == [FEB, MAR]

    def test_pagination_metadata(self, db_session):
        _seed(
            db_session,
            observations=[Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0), Observation(date=MAR, value=121.0)],
        )
        service = EconomicDataService()
        result = service.get_observations("UNRATE", db_session, start_date=None, end_date=None, limit=2, offset=0, order="asc")
        assert result.pagination.limit == 2
        assert result.pagination.offset == 0
        assert result.pagination.returned == 2
        assert result.pagination.total == 3

    def test_ordering_desc(self, db_session):
        _seed(db_session, observations=[Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        service = EconomicDataService()
        result = service.get_observations("UNRATE", db_session, start_date=None, end_date=None, limit=100, offset=0, order="desc")
        assert [o.date for o in result.observations] == [FEB, JAN]

    def test_unknown_series_raises(self, db_session):
        service = EconomicDataService()
        with pytest.raises(SeriesNotFoundError):
            service.get_observations("NOPE", db_session, start_date=None, end_date=None, limit=100, offset=0, order="asc")

    def test_invalid_date_range_raises(self, db_session):
        _seed(db_session, observations=[Observation(date=JAN, value=100.0)])
        service = EconomicDataService()
        with pytest.raises(InvalidDateRangeError):
            service.get_observations("UNRATE", db_session, start_date=MAR, end_date=JAN, limit=100, offset=0, order="asc")


class TestTransformedObservations:
    def test_absolute_change_through_service(self, db_session):
        _seed(db_session, observations=[Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        service = EconomicDataService()
        result = service.get_transformed_observations(
            "UNRATE", db_session, transformation="absolute_change", start_date=None, end_date=None, window=None
        )
        assert [(o.date, o.value) for o in result.observations] == [(JAN, None), (FEB, 10.0)]

    def test_percent_change_through_service(self, db_session):
        _seed(db_session, observations=[Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        service = EconomicDataService()
        result = service.get_transformed_observations(
            "UNRATE", db_session, transformation="percent_change", start_date=None, end_date=None, window=None
        )
        assert result.observations[1].value == 10.0

    def test_moving_average_through_service(self, db_session):
        _seed(
            db_session,
            observations=[Observation(date=JAN, value=10.0), Observation(date=FEB, value=20.0), Observation(date=MAR, value=30.0)],
        )
        service = EconomicDataService()
        result = service.get_transformed_observations(
            "UNRATE", db_session, transformation="moving_average", start_date=None, end_date=None, window=2
        )
        assert [o.value for o in result.observations] == [None, 15.0, 25.0]

    def test_window_required_for_moving_average(self, db_session):
        _seed(db_session, observations=[Observation(date=JAN, value=10.0)])
        service = EconomicDataService()
        with pytest.raises(InvalidWindowError):
            service.get_transformed_observations(
                "UNRATE", db_session, transformation="moving_average", start_date=None, end_date=None, window=None
            )

    def test_window_inapplicable_to_other_transformations(self, db_session):
        _seed(db_session, observations=[Observation(date=JAN, value=10.0)])
        service = EconomicDataService()
        with pytest.raises(InvalidWindowError):
            service.get_transformed_observations(
                "UNRATE", db_session, transformation="percent_change", start_date=None, end_date=None, window=3
            )


class TestBoundaryContextGoldenBehavior:
    """The important tests in this file. Persisted: Jan=100, Feb=110,
    Mar=121 -- a clean 10%-compounding series chosen specifically so
    expected values are trivial to verify independently by hand.
    """

    def _seed_growth_series(self, db_session):
        _seed(
            db_session,
            observations=[
                Observation(date=JAN, value=100.0),
                Observation(date=FEB, value=110.0),
                Observation(date=MAR, value=121.0),
            ],
        )

    def test_percent_change_uses_preceding_context_not_null(self, db_session):
        """Requesting start_date=Feb must NOT produce a null at Feb --
        the service must fetch Jan as context first. Expected Feb:
        (110-100)/100*100 = 10.0. Expected Mar: (121-110)/110*100 = 10.0."""
        self._seed_growth_series(db_session)
        service = EconomicDataService()
        result = service.get_transformed_observations(
            "UNRATE", db_session, transformation="percent_change", start_date=FEB, end_date=None, window=None
        )
        assert [(o.date, o.value) for o in result.observations] == [(FEB, 10.0), (MAR, 10.0)]

    def test_absolute_change_uses_preceding_context_not_null(self, db_session):
        """Expected Feb: 110-100=10.0. Expected Mar: 121-110=11.0."""
        self._seed_growth_series(db_session)
        service = EconomicDataService()
        result = service.get_transformed_observations(
            "UNRATE", db_session, transformation="absolute_change", start_date=FEB, end_date=None, window=None
        )
        assert [(o.date, o.value) for o in result.observations] == [(FEB, 10.0), (MAR, 11.0)]

    def test_moving_average_uses_preceding_context_not_null(self, db_session):
        """window=2, start_date=Mar: context = [Feb]. Expected Mar
        average = (110+121)/2 = 115.5, computed independently, not by
        calling moving_average() first."""
        self._seed_growth_series(db_session)
        service = EconomicDataService()
        result = service.get_transformed_observations(
            "UNRATE", db_session, transformation="moving_average", start_date=MAR, end_date=None, window=2
        )
        assert [(o.date, o.value) for o in result.observations] == [(MAR, 115.5)]

    def test_context_observations_are_not_leaked_into_the_response(self, db_session):
        """Jan is needed as context for Feb's percent_change, but must
        never appear in the returned observations list itself."""
        self._seed_growth_series(db_session)
        service = EconomicDataService()
        result = service.get_transformed_observations(
            "UNRATE", db_session, transformation="percent_change", start_date=FEB, end_date=None, window=None
        )
        assert JAN not in [o.date for o in result.observations]
        assert len(result.observations) == 2  # exactly Feb, Mar -- not Jan too

    def test_no_context_needed_when_start_date_is_the_beginning(self, db_session):
        """Without a start_date truncating the series, there's nothing
        earlier to borrow from -- the very first point is still null,
        same as the pure-domain-function behavior."""
        self._seed_growth_series(db_session)
        service = EconomicDataService()
        result = service.get_transformed_observations(
            "UNRATE", db_session, transformation="percent_change", start_date=None, end_date=None, window=None
        )
        assert result.observations[0].value is None  # Jan: no predecessor at all


class TestReadPathsDoNotMutate:
    def test_get_observations_and_transform_do_not_change_persisted_data(self, db_session):
        self_seed_values = [Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)]
        _seed(db_session, observations=self_seed_values)
        service = EconomicDataService()

        before, _ = SeriesRepository(db_session).get_observations(
            SeriesRepository(db_session).get_series_by_series_id("UNRATE").id, None, None, limit=100, offset=0, order="asc"
        )
        before_values = [(o.observation_date, o.value) for o in before]

        service.get_observations("UNRATE", db_session, start_date=None, end_date=None, limit=100, offset=0, order="asc")
        service.get_transformed_observations(
            "UNRATE", db_session, transformation="percent_change", start_date=None, end_date=None, window=None
        )

        after, _ = SeriesRepository(db_session).get_observations(
            SeriesRepository(db_session).get_series_by_series_id("UNRATE").id, None, None, limit=100, offset=0, order="asc"
        )
        after_values = [(o.observation_date, o.value) for o in after]

        assert before_values == after_values
