"""Integration tests for AnalysisService (compare + pipeline) against a
real, isolated PostgreSQL test database. No FastAPI, no OpenAI, no FRED
-- AnalysisService has no FRED dependency at all (see its own module
docstring), so nothing here needs to avoid instantiating one.

Expected values are independently hand-derived, never obtained by
calling app.domain.analysis/transformations functions directly and
asserting on their own output -- these tests exist to prove the SERVICE
composes persistence + domain math correctly, which a domain-level unit
test (Increment 010) cannot prove on its own.
"""

from datetime import date

import pytest

from app.models.analysis import PipelineRequest
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.analysis import AnalysisService
from app.services.economic_data import InvalidDateRangeError, SeriesNotFoundError

JAN, FEB, MAR, APR = (date(2024, m, 1) for m in range(1, 5))


def _seed(db_session, series_id, observations):
    SeriesRepository(db_session).save_series(
        SeriesResponse(series_id=series_id, title=series_id, units="Index", observations=observations)
    )
    db_session.flush()


class TestCompare:
    def test_exact_date_alignment_excludes_unmatched_dates(self, db_session):
        """A: Jan, Feb, Mar. B: Jan, Mar, Apr -- same canonical shape as
        the domain-level test. Expected matched dates: Jan, Mar only."""
        _seed(db_session, "A", [Observation(date=JAN, value=1.0), Observation(date=FEB, value=2.0), Observation(date=MAR, value=3.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=10.0), Observation(date=MAR, value=30.0), Observation(date=APR, value=40.0)])

        result = AnalysisService().compare("A", "B", db_session, analysis="aligned", start_date=None, end_date=None)
        assert [o.date for o in result.observations] == [JAN, MAR]
        assert result.matching_pairs == 2

    def test_spread(self, db_session):
        _seed(db_session, "A", [Observation(date=JAN, value=1.0), Observation(date=MAR, value=3.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=10.0), Observation(date=MAR, value=30.0)])

        result = AnalysisService().compare("A", "B", db_session, analysis="spread", start_date=None, end_date=None)
        assert [o.spread for o in result.observations] == [-9.0, -27.0]

    def test_correlation_perfectly_positive(self, db_session):
        """y = 2x for x=[1,2,3,4] -- hand-derived r = 1.0 (see
        tests/test_domain_analysis.py for the full derivation)."""
        _seed(db_session, "A", [Observation(date=date(2024, m, 1), value=float(m)) for m in range(1, 5)])
        _seed(db_session, "B", [Observation(date=date(2024, m, 1), value=float(2 * m)) for m in range(1, 5)])

        result = AnalysisService().compare("A", "B", db_session, analysis="correlation", start_date=None, end_date=None)
        assert result.correlation == 1.0

    def test_missing_null_value_on_a_matched_date_is_preserved(self, db_session):
        _seed(db_session, "A", [Observation(date=JAN, value=None), Observation(date=FEB, value=5.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=100.0), Observation(date=FEB, value=None)])

        result = AnalysisService().compare("A", "B", db_session, analysis="aligned", start_date=None, end_date=None)
        by_date = {o.date: o for o in result.observations}
        assert by_date[JAN].value_a is None and by_date[JAN].value_b == 100.0
        assert by_date[FEB].value_a == 5.0 and by_date[FEB].value_b is None
        assert result.matching_pairs == 2
        assert result.usable_pairs == 0  # neither date has both sides non-null

    def test_start_end_date_filtering(self, db_session):
        _seed(db_session, "A", [Observation(date=date(2024, m, 1), value=float(m)) for m in range(1, 5)])
        _seed(db_session, "B", [Observation(date=date(2024, m, 1), value=float(m)) for m in range(1, 5)])

        result = AnalysisService().compare("A", "B", db_session, analysis="aligned", start_date=FEB, end_date=MAR)
        assert [o.date for o in result.observations] == [FEB, MAR]

    def test_unknown_series_a_raises(self, db_session):
        _seed(db_session, "B", [Observation(date=JAN, value=1.0)])
        with pytest.raises(SeriesNotFoundError):
            AnalysisService().compare("NOPE", "B", db_session, analysis="aligned", start_date=None, end_date=None)

    def test_unknown_series_b_raises(self, db_session):
        _seed(db_session, "A", [Observation(date=JAN, value=1.0)])
        with pytest.raises(SeriesNotFoundError):
            AnalysisService().compare("A", "NOPE", db_session, analysis="aligned", start_date=None, end_date=None)

    def test_invalid_date_range_raises(self, db_session):
        _seed(db_session, "A", [Observation(date=JAN, value=1.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=1.0)])
        with pytest.raises(InvalidDateRangeError):
            AnalysisService().compare("A", "B", db_session, analysis="aligned", start_date=MAR, end_date=JAN)


def _pipeline_request(series_a_id, series_b_id, analysis="aligned", transform_a=None, transform_b=None, start_date=None, end_date=None):
    return PipelineRequest.model_validate(
        {
            "series_a": {"series_id": series_a_id, "transformation": transform_a},
            "series_b": {"series_id": series_b_id, "transformation": transform_b},
            "analysis": analysis,
            "start_date": start_date,
            "end_date": end_date,
        }
    )


class TestPipelineComposition:
    def test_raw_raw(self, db_session):
        _seed(db_session, "A", [Observation(date=JAN, value=1.0), Observation(date=MAR, value=3.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=10.0), Observation(date=MAR, value=30.0)])
        result = AnalysisService().pipeline(_pipeline_request("A", "B"), db_session)
        assert [(o.value_a, o.value_b) for o in result.observations] == [(1.0, 10.0), (3.0, 30.0)]
        assert result.series_a.transformation is None
        assert result.series_b.transformation is None

    def test_raw_transformed(self, db_session):
        """A raw, B percent_change. Growth series for B: Jan=100,Feb=110 -> 10.0 at Feb."""
        _seed(db_session, "A", [Observation(date=JAN, value=1.0), Observation(date=FEB, value=2.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        result = AnalysisService().pipeline(
            _pipeline_request("A", "B", transform_b={"type": "percent_change"}), db_session
        )
        by_date = {o.date: o for o in result.observations}
        assert by_date[JAN].value_a == 1.0 and by_date[JAN].value_b is None  # B's first obs has no predecessor
        assert by_date[FEB].value_a == 2.0 and by_date[FEB].value_b == 10.0

    def test_transformed_raw(self, db_session):
        _seed(db_session, "A", [Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=1.0), Observation(date=FEB, value=2.0)])
        result = AnalysisService().pipeline(
            _pipeline_request("A", "B", transform_a={"type": "percent_change"}), db_session
        )
        by_date = {o.date: o for o in result.observations}
        assert by_date[FEB].value_a == 10.0 and by_date[FEB].value_b == 2.0

    def test_transformed_transformed(self, db_session):
        _seed(db_session, "A", [Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=200.0), Observation(date=FEB, value=210.0)])
        result = AnalysisService().pipeline(
            _pipeline_request(
                "A", "B", transform_a={"type": "percent_change"}, transform_b={"type": "percent_change"}
            ),
            db_session,
        )
        by_date = {o.date: o for o in result.observations}
        assert by_date[FEB].value_a == 10.0  # (110-100)/100*100
        assert by_date[FEB].value_b == 5.0  # (210-200)/200*100

    def test_absolute_change_composition(self, db_session):
        _seed(db_session, "A", [Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=1.0), Observation(date=FEB, value=2.0)])
        result = AnalysisService().pipeline(
            _pipeline_request("A", "B", transform_a={"type": "absolute_change"}), db_session
        )
        by_date = {o.date: o for o in result.observations}
        assert by_date[FEB].value_a == 10.0

    def test_moving_average_composition(self, db_session):
        _seed(
            db_session,
            "A",
            [Observation(date=JAN, value=10.0), Observation(date=FEB, value=20.0), Observation(date=MAR, value=30.0)],
        )
        _seed(
            db_session,
            "B",
            [Observation(date=JAN, value=1.0), Observation(date=FEB, value=1.0), Observation(date=MAR, value=1.0)],
        )
        result = AnalysisService().pipeline(
            _pipeline_request("A", "B", transform_a={"type": "moving_average", "window": 2}), db_session
        )
        by_date = {o.date: o for o in result.observations}
        assert by_date[MAR].value_a == 25.0  # avg(20, 30)

    def test_transformation_happens_before_alignment_not_after(self, db_session):
        """The critical ordering test. A: Jan=100,Feb=110,Mar=121 (10%
        growth each month). B: Jan=10, Mar=30 -- deliberately MISSING
        Feb, so alignment (if it happened first) would reduce A to just
        [Jan, Mar] before any transformation ran.

        If transform-before-align (documented, correct): A's
        percent_change is computed against its OWN full [Jan,Feb,Mar]
        history first -> Mar = (121-110)/110*100 = 10.0. THEN alignment
        keeps only Jan/Mar (common with B) -> aligned Mar.value_a = 10.0.

        If align-before-transform (wrong): A would be reduced to
        [Jan, Mar] BEFORE transforming, making Mar's "previous" value
        Jan (100) instead of Feb (110) -> (121-100)/100*100 = 21.0.

        These two answers are different enough to unambiguously tell
        the two orderings apart.
        """
        _seed(db_session, "A", [Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0), Observation(date=MAR, value=121.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=10.0), Observation(date=MAR, value=30.0)])

        result = AnalysisService().pipeline(
            _pipeline_request("A", "B", transform_a={"type": "percent_change"}), db_session
        )
        by_date = {o.date: o for o in result.observations}
        assert by_date[MAR].value_a == 10.0  # NOT 21.0 -- proves transform-before-align

    def test_boundary_context_is_independent_per_series(self, db_session):
        """Both sides transformed with percent_change, start_date=Feb --
        each side must retrieve and use its OWN preceding (Jan) context,
        not share or confuse the other side's context.

        A: Jan=100, Feb=110 -> expected Feb = 10.0
        B: Jan=5,   Feb=8   -> expected Feb = 60.0 ((8-5)/5*100)
        """
        _seed(db_session, "A", [Observation(date=JAN, value=100.0), Observation(date=FEB, value=110.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=5.0), Observation(date=FEB, value=8.0)])

        result = AnalysisService().pipeline(
            _pipeline_request(
                "A", "B",
                transform_a={"type": "percent_change"}, transform_b={"type": "percent_change"},
                start_date=FEB,
            ),
            db_session,
        )
        assert len(result.observations) == 1
        assert result.observations[0].date == FEB
        assert result.observations[0].value_a == 10.0
        assert result.observations[0].value_b == 60.0
        assert JAN not in [o.date for o in result.observations]  # context not leaked

    def test_matching_pairs_and_usable_pairs(self, db_session):
        _seed(db_session, "A", [Observation(date=JAN, value=None), Observation(date=FEB, value=2.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=1.0), Observation(date=FEB, value=2.0)])
        result = AnalysisService().pipeline(_pipeline_request("A", "B"), db_session)
        assert result.matching_pairs == 2
        assert result.usable_pairs == 1  # only Feb has both sides non-null

    def test_correlation_behavior(self, db_session):
        _seed(db_session, "A", [Observation(date=date(2024, m, 1), value=float(m)) for m in range(1, 5)])
        _seed(db_session, "B", [Observation(date=date(2024, m, 1), value=float(2 * m)) for m in range(1, 5)])
        result = AnalysisService().pipeline(_pipeline_request("A", "B", analysis="correlation"), db_session)
        assert result.correlation == 1.0
        assert result.observations == []  # scalar result, no per-date rows

    def test_spread_behavior(self, db_session):
        _seed(db_session, "A", [Observation(date=JAN, value=10.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=4.0)])
        result = AnalysisService().pipeline(_pipeline_request("A", "B", analysis="spread"), db_session)
        assert result.observations[0].spread == 6.0


class TestReadPathsDoNotMutate:
    def test_compare_and_pipeline_do_not_change_persisted_data(self, db_session):
        _seed(db_session, "A", [Observation(date=JAN, value=1.0), Observation(date=FEB, value=2.0)])
        _seed(db_session, "B", [Observation(date=JAN, value=10.0), Observation(date=FEB, value=20.0)])
        repo = SeriesRepository(db_session)

        def snapshot(series_id):
            series = repo.get_series_by_series_id(series_id)
            rows, _ = repo.get_observations(series.id, None, None, limit=100, offset=0, order="asc")
            return [(r.observation_date, r.value) for r in rows]

        before_a, before_b = snapshot("A"), snapshot("B")

        AnalysisService().compare("A", "B", db_session, analysis="correlation", start_date=None, end_date=None)
        AnalysisService().pipeline(_pipeline_request("A", "B", transform_a={"type": "percent_change"}), db_session)

        after_a, after_b = snapshot("A"), snapshot("B")
        assert before_a == after_a
        assert before_b == after_b
