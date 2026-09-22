"""The Housing read service against a real database (Increment #45).

The figures used throughout are the ones Census actually published for
June-August 2026 and August 2025, so the percentages asserted below are
the SAME percentages Census's own release text states. A sign error or an
inverted comparison therefore shows up as a disagreement with the
published source rather than as a self-consistently wrong answer.
"""

from datetime import date, datetime, timezone

import pytest

from app.models.housing import TREND_MONTHS
from app.repositories.housing_repository import HousingProvenanceRecord, HousingRepository
from app.services.housing import NEVER_INGESTED, NO_USABLE_VALUE, HousingReadService

pytestmark = pytest.mark.integration

PERMITS_SAAR = "us.housing.units-authorized.saar.monthly"
PERMITS_NSA = "us.housing.units-authorized.nsa.monthly"


def _seed(session, concept_id: str, values: dict[date, float | None], with_provenance: bool = True) -> None:
    """Write observations through the real repository, so versioning and
    provenance behave exactly as production does."""
    repo = HousingRepository(session)
    series = repo.ensure_series(
        storage_series_id=concept_id,
        concept_id=concept_id,
        title="Test housing series",
        units="Housing units",
        source="CENSUS",
    )
    retrieved_at = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    for period, value in sorted(values.items()):
        if value is None:
            # A month with no usable value is genuinely absent from
            # storage -- the ingestion service skips it entirely.
            continue
        repo.upsert_observation(
            series=series,
            observation_date=period,
            value=value,
            provenance=HousingProvenanceRecord(
                provider="CENSUS",
                dataset="timeseries/eits/resconst",
                source_series_field="APERMITS/TOTAL",
                source_url="https://www.census.gov/construction/nrc/",
                retrieved_at=retrieved_at,
            ),
            baseline=True,
        )
    session.flush()
    if not with_provenance:
        from sqlalchemy import text

        session.execute(text("DELETE FROM observation_provenance"))
        session.flush()


def _measure(session, stage: str = "PERMITS", which: str = "pace"):
    result = HousingReadService().get_result(session)
    entry = next(item for item in result.stages if item.stage == stage)
    return getattr(entry, which)


class TestShape:
    def test_an_empty_environment_reports_no_data_without_erroring(self, db_session) -> None:
        """Missing economic data is not an infrastructure failure."""
        result = HousingReadService().get_result(db_session)

        assert result.as_of_period is None
        assert len(result.stages) == 3
        for stage in result.stages:
            assert stage.pace.available is False
            assert stage.pace.unavailable_reason == NEVER_INGESTED
            assert stage.pace.value is None

    def test_the_stages_are_in_pipeline_order(self, db_session) -> None:
        """An order, not a ranking: it is a fact about construction."""
        result = HousingReadService().get_result(db_session)
        assert [stage.stage for stage in result.stages] == ["PERMITS", "STARTS", "COMPLETIONS"]

    def test_each_stage_carries_both_units(self, db_session) -> None:
        result = HousingReadService().get_result(db_session)
        for stage in result.stages:
            assert stage.pace.unit == "HOUSING_UNITS_ANNUAL_RATE"
            assert stage.pace.seasonal_adjustment == "SEASONALLY_ADJUSTED"
            assert stage.actual.unit == "HOUSING_UNITS"
            assert stage.actual.seasonal_adjustment == "NOT_SEASONALLY_ADJUSTED"

    def test_the_result_carries_no_state_field(self, db_session) -> None:
        result = HousingReadService().get_result(db_session)
        dumped = result.model_dump()
        assert "state" not in dumped
        assert "methodology_id" not in dumped

    def test_the_result_carries_the_required_census_attribution(self, db_session) -> None:
        result = HousingReadService().get_result(db_session)
        assert result.attribution == (
            "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau."
        )

    def test_the_result_carries_the_saar_explanation_and_the_limitations(self, db_session) -> None:
        result = HousingReadService().get_result(db_session)
        assert "not a count of homes" in result.saar_explanation
        assert len(result.limitations) >= 6


class TestComparisons:
    """Every number here is checked against the published release text."""

    def test_the_latest_value_and_period(self, db_session) -> None:
        _seed(db_session, PERMITS_SAAR, {date(2026, 7, 1): 1_433_000.0, date(2026, 8, 1): 1_394_000.0})

        measure = _measure(db_session)
        assert measure.available is True
        assert measure.period == date(2026, 8, 1)
        assert measure.value == 1_394_000.0

    def test_the_month_over_month_change_matches_the_release(self, db_session) -> None:
        _seed(db_session, PERMITS_SAAR, {date(2026, 7, 1): 1_433_000.0, date(2026, 8, 1): 1_394_000.0})

        measure = _measure(db_session)
        assert measure.previous_period == date(2026, 7, 1)
        assert measure.previous_value == 1_433_000.0
        assert measure.change_from_previous == -39_000.0
        # Census: "2.7 percent below the revised July rate of 1,433,000".
        assert round(measure.change_percent_from_previous, 1) == -2.7

    def test_the_year_over_year_change_matches_the_release(self, db_session) -> None:
        _seed(
            db_session,
            PERMITS_SAAR,
            {
                date(2025, 8, 1): 1_347_000.0,
                date(2026, 7, 1): 1_433_000.0,
                date(2026, 8, 1): 1_394_000.0,
            },
        )

        measure = _measure(db_session)
        assert measure.year_ago_period == date(2025, 8, 1)
        # Census: "3.5 percent above the August 2025 rate of 1,347,000".
        assert round(measure.change_percent_from_year_ago, 1) == 3.5

    def test_a_missing_year_ago_month_yields_no_comparison_rather_than_a_substitute(
        self, db_session
    ) -> None:
        _seed(db_session, PERMITS_SAAR, {date(2025, 9, 1): 1_347_000.0, date(2026, 8, 1): 1_394_000.0})

        measure = _measure(db_session)
        assert measure.year_ago_period is None
        assert measure.change_from_year_ago is None

    def test_a_single_observation_has_a_value_but_no_comparison(self, db_session) -> None:
        _seed(db_session, PERMITS_SAAR, {date(2026, 8, 1): 1_394_000.0})

        measure = _measure(db_session)
        assert measure.value == 1_394_000.0
        assert measure.change_from_previous is None
        assert measure.previous_value is None


class TestTrend:
    def test_the_trend_is_bounded_and_ascending(self, db_session) -> None:
        values = {date(2020 + (index // 12), (index % 12) + 1, 1): 1_000_000.0 + index for index in range(80)}
        _seed(db_session, PERMITS_SAAR, values)

        trend = _measure(db_session).trend
        assert trend.requested_months == TREND_MONTHS
        assert trend.available_months == TREND_MONTHS
        assert len(trend.points) == TREND_MONTHS
        dates = [point.observation_date for point in trend.points]
        assert dates == sorted(dates)

    def test_fewer_months_than_requested_is_reported_honestly(self, db_session) -> None:
        _seed(db_session, PERMITS_SAAR, {date(2026, 7, 1): 1_433_000.0, date(2026, 8, 1): 1_394_000.0})

        trend = _measure(db_session).trend
        assert trend.requested_months == TREND_MONTHS
        assert trend.available_months == 2

    def test_the_trend_ends_at_the_latest_observation(self, db_session) -> None:
        _seed(db_session, PERMITS_SAAR, {date(2026, 7, 1): 1_433_000.0, date(2026, 8, 1): 1_394_000.0})

        trend = _measure(db_session).trend
        assert trend.points[-1].observation_date == date(2026, 8, 1)
        assert trend.points[-1].value == 1_394_000.0

    def test_the_trend_carries_the_concepts_unit(self, db_session) -> None:
        _seed(db_session, PERMITS_SAAR, {date(2026, 8, 1): 1_394_000.0})
        assert _measure(db_session).trend.unit == "HOUSING_UNITS_ANNUAL_RATE"

    def test_a_gap_in_publication_is_not_filled(self, db_session) -> None:
        _seed(
            db_session,
            PERMITS_SAAR,
            {date(2026, 1, 1): 1_000_000.0, date(2026, 8, 1): 1_394_000.0},
        )

        trend = _measure(db_session).trend
        assert [point.observation_date.month for point in trend.points] == [1, 8]


class TestProvenance:
    def test_provenance_exposes_censuss_identifier_not_macrochipzs(self, db_session) -> None:
        _seed(db_session, PERMITS_SAAR, {date(2026, 8, 1): 1_394_000.0})

        provenance = _measure(db_session).provenance
        assert provenance is not None
        assert provenance.provider == "CENSUS"
        assert provenance.provider_series_id == "APERMITS/TOTAL"
        assert provenance.observation_date == date(2026, 8, 1)
        assert provenance.revision_count == 0

    def test_provenance_never_exposes_an_api_url(self, db_session) -> None:
        _seed(db_session, PERMITS_SAAR, {date(2026, 8, 1): 1_394_000.0})

        provenance = _measure(db_session).provenance
        assert "api.census.gov" not in provenance.source_url
        assert "key" not in provenance.source_url

    def test_missing_provenance_is_reported_as_absent_not_invented(self, db_session) -> None:
        _seed(db_session, PERMITS_SAAR, {date(2026, 8, 1): 1_394_000.0}, with_provenance=False)

        assert _measure(db_session).provenance is None


class TestAsOfPeriod:
    def test_it_is_the_newest_month_any_measure_has(self, db_session) -> None:
        """Not the newest month EVERY measure has: completions history
        begins in 1968 and permits in 1959, and requiring agreement would
        hide a perfectly good figure behind a series that starts later."""
        _seed(db_session, PERMITS_SAAR, {date(2026, 8, 1): 1_394_000.0})
        _seed(db_session, PERMITS_NSA, {date(2026, 7, 1): 128_900.0})

        result = HousingReadService().get_result(db_session)
        assert result.as_of_period == date(2026, 8, 1)


class TestUnavailability:
    def test_a_series_with_rows_but_no_values_is_distinguished_from_one_never_ingested(
        self, db_session
    ) -> None:
        """Two genuinely different conditions, so two reasons. Reporting
        both as "unavailable" would make a data problem look like an
        empty environment."""
        from sqlalchemy import text

        _seed(db_session, PERMITS_SAAR, {date(2026, 8, 1): 1_394_000.0})
        db_session.execute(text("UPDATE economic_observations SET value = NULL"))
        db_session.flush()

        measure = _measure(db_session)
        assert measure.available is False
        assert measure.unavailable_reason == NO_USABLE_VALUE

    def test_an_unavailable_measure_carries_no_figure_and_no_trend(self, db_session) -> None:
        measure = _measure(db_session)
        assert measure.value is None
        assert measure.trend is None
        assert measure.provenance is None


class TestReadPathIsReadOnly:
    def test_reading_writes_nothing(self, db_session) -> None:
        """A read must never be able to drive provider traffic or mutate
        canonical data -- verified behaviourally as well as structurally."""
        from sqlalchemy import func, select

        from app.db.models import EconomicObservation, ObservationVersion

        _seed(db_session, PERMITS_SAAR, {date(2026, 8, 1): 1_394_000.0})
        before = (
            db_session.execute(select(func.count()).select_from(EconomicObservation)).scalar_one(),
            db_session.execute(select(func.count()).select_from(ObservationVersion)).scalar_one(),
        )

        HousingReadService().get_result(db_session)
        HousingReadService().get_result(db_session)

        after = (
            db_session.execute(select(func.count()).select_from(EconomicObservation)).scalar_one(),
            db_session.execute(select(func.count()).select_from(ObservationVersion)).scalar_one(),
        )
        assert before == after

    def test_two_reads_of_unchanged_data_are_identical(self, db_session) -> None:
        _seed(db_session, PERMITS_SAAR, {date(2026, 7, 1): 1_433_000.0, date(2026, 8, 1): 1_394_000.0})

        first = HousingReadService().get_result(db_session)
        second = HousingReadService().get_result(db_session)
        assert first.model_dump() == second.model_dump()
