"""Housing ingestion against a real database (Increment #45).

No network: a stub client returns captured row shapes, so revision
sequences MacroChipz has never actually observed can be exercised
deterministically. That matters more here than anywhere else in this
increment -- **MacroChipz has never captured a genuine revision in its
entire history** (every one of the 1,072 pre-#45 version rows is
`is_backfilled = true`), so the only way to know the revision path works
before Census publishes one is to drive it here.

#45 section 15 asks for exactly that: prove a future real change to a
previously recorded value is representable, without manufacturing a
revision in the real data.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.clients.census import CensusAuthError, CensusRejectedRow, CensusResconstRow
from app.concepts.bindings import active_binding
from app.db.models import EconomicObservation, EconomicSeries, HousingIngestionRun, ObservationVersion
from app.models.housing import HOUSING_CONCEPT_IDS
from app.services.census_ingestion import HousingIngestionService

pytestmark = pytest.mark.integration

PERMITS_SAAR = "us.housing.units-authorized.saar.monthly"
STARTS_SAAR = "us.housing.units-started.saar.monthly"


class StubCensusClient:
    """Returns prepared rows. Deliberately NOT a `CensusClient` subclass:
    it holds no credential, so no test here can accidentally exercise a
    real request."""

    def __init__(self, rows, rejected=None, raises=None):
        self._rows = rows
        self._rejected = rejected or []
        self._raises = raises
        self.calls: list[str] = []

    def get_resconst(self, time_expression: str, dataset: str | None = None):
        self.calls.append(time_expression)
        if self._raises is not None:
            raise self._raises
        return list(self._rows), list(self._rejected)


def _row(
    period: date,
    value: float | None,
    category_code="APERMITS",
    data_type_code="TOTAL",
    seasonally_adjusted=True,
    is_error_measure=False,
) -> CensusResconstRow:
    return CensusResconstRow(
        period=period,
        category_code=category_code,
        data_type_code=data_type_code,
        seasonally_adjusted=seasonally_adjusted,
        is_error_measure=is_error_measure,
        value=value,
    )


def _sync(session, rows, rejected=None, raises=None, **kwargs):
    client = StubCensusClient(rows, rejected, raises)
    return HousingIngestionService(client).sync(session, **kwargs), client


def _observations(session, concept_id: str) -> list[EconomicObservation]:
    series = session.execute(
        select(EconomicSeries).where(EconomicSeries.series_id == concept_id)
    ).scalar_one_or_none()
    if series is None:
        return []
    return list(
        session.execute(
            select(EconomicObservation)
            .where(EconomicObservation.economic_series_id == series.id)
            .order_by(EconomicObservation.observation_date)
        )
        .scalars()
        .all()
    )


def _versions(session, concept_id: str, observation_date: date | None = None) -> list[ObservationVersion]:
    series = session.execute(
        select(EconomicSeries).where(EconomicSeries.series_id == concept_id)
    ).scalar_one()
    query = select(ObservationVersion).where(ObservationVersion.economic_series_id == series.id)
    if observation_date is not None:
        query = query.where(ObservationVersion.observation_date == observation_date)
    return list(session.execute(query.order_by(ObservationVersion.recorded_from)).scalars().all())


class TestBaselineImport:
    """#43's central rule, applied to a new source at the scale where
    breaking it would matter most."""

    def test_the_first_import_stores_the_history_with_the_unit_conversion_applied(self, db_session) -> None:
        result, _ = _sync(
            db_session,
            [_row(date(2026, 7, 1), 1433.0), _row(date(2026, 8, 1), 1394.0)],
        )

        assert result.status == "SUCCEEDED"
        observations = _observations(db_session, PERMITS_SAAR)
        # Census publishes 1394 thousands; MacroChipz stores units, and
        # the published release says 1,394,000.
        assert [item.value for item in observations] == [1_433_000.0, 1_394_000.0]

    def test_every_first_import_version_is_a_backfilled_baseline(self, db_session) -> None:
        """The whole point. MacroChipz did not watch these months arrive
        and cannot say what Census had published for them earlier."""
        _sync(db_session, [_row(date(1959, 1, 1), 1657.0), _row(date(2026, 8, 1), 1394.0)])

        versions = _versions(db_session, PERMITS_SAAR)
        assert len(versions) == 2
        assert all(version.is_backfilled for version in versions)
        assert all(version.change_type == "NEW" for version in versions)
        assert all(version.origin == "HOUSING_INGESTION" for version in versions)

    def test_the_run_is_recorded_as_a_baseline_backfill(self, db_session) -> None:
        result, _ = _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])

        assert result.series[0].import_mode == "BASELINE_BACKFILL"
        run = db_session.execute(select(HousingIngestionRun)).scalars().one()
        assert run.import_mode == "BASELINE_BACKFILL"

    def test_the_series_row_carries_its_concept_and_the_census_source(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])

        series = db_session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == PERMITS_SAAR)
        ).scalar_one()
        # Never NULL: a housing series must be impossible to mistake for
        # one of the arbitrary provider series the generic sync accepts.
        assert series.concept_id == PERMITS_SAAR
        assert series.source == "CENSUS"

    def test_one_clock_read_is_shared_by_the_whole_run(self, db_session) -> None:
        """So an as-of query never lands midway through a batch."""
        _sync(
            db_session,
            [_row(date(2026, 6, 1), 1400.0), _row(date(2026, 7, 1), 1433.0), _row(date(2026, 8, 1), 1394.0)],
        )

        assert len({version.recorded_from for version in _versions(db_session, PERMITS_SAAR)}) == 1


class TestIdempotency:
    def test_a_repeated_sync_writes_nothing_and_reports_nothing_revised(self, db_session) -> None:
        rows = [_row(date(2026, 7, 1), 1433.0), _row(date(2026, 8, 1), 1394.0)]
        _sync(db_session, rows)

        second, _ = _sync(db_session, rows)

        permits = next(item for item in second.series if item.concept_id == PERMITS_SAAR)
        assert (permits.observations_inserted, permits.observations_revised) == (0, 0)
        assert permits.observations_unchanged == 2

    def test_a_repeated_sync_adds_no_version_rows(self, db_session) -> None:
        """A re-sync that confirms what is stored is not a new fact about
        the world, and recording one would blur genuine revisions."""
        rows = [_row(date(2026, 8, 1), 1394.0)]
        _sync(db_session, rows)
        before = len(_versions(db_session, PERMITS_SAAR))

        _sync(db_session, rows)

        assert len(_versions(db_session, PERMITS_SAAR)) == before

    def test_the_second_run_is_reported_as_incremental(self, db_session) -> None:
        rows = [_row(date(2026, 8, 1), 1394.0)]
        _sync(db_session, rows)
        second, _ = _sync(db_session, rows)

        permits = next(item for item in second.series if item.concept_id == PERMITS_SAAR)
        assert permits.import_mode == "INCREMENTAL"


class TestFutureRevisions:
    """#45 section 15. Nothing here manufactures a revision in real data
    -- it proves the path works, so the first genuine Census revision
    needs no new code."""

    def test_a_changed_value_is_recorded_as_a_revision_that_preserves_the_original(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 7, 1), 1433.0)])

        # Census revises July, as it does in every monthly release.
        second, _ = _sync(db_session, [_row(date(2026, 7, 1), 1440.0)])

        permits = next(item for item in second.series if item.concept_id == PERMITS_SAAR)
        assert permits.observations_revised == 1

        versions = _versions(db_session, PERMITS_SAAR, date(2026, 7, 1))
        assert [version.value for version in versions] == [1_433_000.0, 1_440_000.0]
        assert [version.change_type for version in versions] == ["NEW", "REVISED"]

    def test_a_revision_is_never_marked_as_a_baseline(self, db_session) -> None:
        """Even though the value it replaced WAS an imported baseline.
        MacroChipz genuinely watched this change happen, and that is the
        one thing it can prove about a revision."""
        _sync(db_session, [_row(date(2026, 7, 1), 1433.0)])
        _sync(db_session, [_row(date(2026, 7, 1), 1440.0)])

        versions = _versions(db_session, PERMITS_SAAR, date(2026, 7, 1))
        assert versions[0].is_backfilled is True  # the imported baseline
        assert versions[1].is_backfilled is False  # the observed revision

    def test_the_previous_version_is_closed_at_the_instant_the_new_one_opens(self, db_session) -> None:
        """Half-open intervals: no overlap, no gap, so an as-of query at
        the boundary deterministically sees the new value."""
        _sync(db_session, [_row(date(2026, 7, 1), 1433.0)])
        _sync(db_session, [_row(date(2026, 7, 1), 1440.0)])

        first, second = _versions(db_session, PERMITS_SAAR, date(2026, 7, 1))
        assert first.recorded_to == second.recorded_from
        assert second.recorded_to is None

    def test_the_provenance_revision_counter_advances_only_on_a_real_change(self, db_session) -> None:
        from app.repositories.housing_repository import HousingRepository

        _sync(db_session, [_row(date(2026, 7, 1), 1433.0)])
        repo = HousingRepository(db_session)
        assert repo.get_provenance(PERMITS_SAAR, date(2026, 7, 1)).revision_count == 0

        _sync(db_session, [_row(date(2026, 7, 1), 1433.0)])  # unchanged
        assert repo.get_provenance(PERMITS_SAAR, date(2026, 7, 1)).revision_count == 0

        _sync(db_session, [_row(date(2026, 7, 1), 1440.0)])  # genuinely revised
        provenance = repo.get_provenance(PERMITS_SAAR, date(2026, 7, 1))
        assert provenance.revision_count == 1
        assert provenance.last_revised_at is not None

    def test_a_genuinely_new_month_is_observed_not_backfilled(self, db_session) -> None:
        """The other real future event: next month's release arriving.
        MacroChipz IS watching, so this is a real first observation."""
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0), _row(date(2026, 9, 1), 1410.0)])

        september = _versions(db_session, PERMITS_SAAR, date(2026, 9, 1))
        assert len(september) == 1
        assert september[0].change_type == "NEW"
        assert september[0].is_backfilled is False

    def test_filling_history_backwards_later_is_still_a_baseline(self, db_session) -> None:
        """A later sync reaching further back has not watched those months
        arrive either."""
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(1990, 3, 1), 1200.0), _row(date(2026, 8, 1), 1394.0)])

        old = _versions(db_session, PERMITS_SAAR, date(1990, 3, 1))
        assert old[0].is_backfilled is True


class TestMissingAndErrorData:
    """#45 section 6: unknown never becomes zero."""

    def test_a_row_with_no_value_is_skipped_never_stored_as_zero(self, db_session) -> None:
        result, _ = _sync(
            db_session,
            [_row(date(2026, 7, 1), 1433.0), _row(date(2026, 8, 1), None)],
        )

        permits = next(item for item in result.series if item.concept_id == PERMITS_SAAR)
        assert permits.observations_skipped_missing_value == 1
        assert [item.value for item in _observations(db_session, PERMITS_SAAR)] == [1_433_000.0]

    def test_a_skipped_month_is_not_carried_forward_from_the_previous_one(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 7, 1), 1433.0), _row(date(2026, 8, 1), None)])

        assert [item.observation_date for item in _observations(db_session, PERMITS_SAAR)] == [date(2026, 7, 1)]

    def test_an_error_measure_row_is_counted_and_never_ingested(self, db_session) -> None:
        """Census's relative standard errors are real output. Storing one
        as a housing count would publish a precision measure as a number
        of homes."""
        result, _ = _sync(
            db_session,
            [
                _row(date(2026, 8, 1), 1394.0),
                _row(date(2026, 8, 1), 6.0, data_type_code="E_TOTAL", is_error_measure=True),
            ],
        )

        assert result.error_measure_rows_ignored == 1
        assert [item.value for item in _observations(db_session, PERMITS_SAAR)] == [1_394_000.0]

    def test_out_of_scope_rows_are_counted_and_not_ingested(self, db_session) -> None:
        """Four fifths of this dataset is outside #45's scope -- units
        under construction, units authorized but not started, and the
        single- and multi-family breakdowns."""
        result, _ = _sync(
            db_session,
            [
                _row(date(2026, 8, 1), 1394.0),
                _row(date(2026, 8, 1), 668.0, category_code="UNDERCONST"),
                _row(date(2026, 8, 1), 878.0, data_type_code="SINGLE"),
            ],
        )

        assert result.rows_outside_scope == 2
        assert len(_observations(db_session, PERMITS_SAAR)) == 1

    def test_rejected_rows_are_reported_by_reason_and_degrade_the_status(self, db_session) -> None:
        result, _ = _sync(
            db_session,
            [_row(date(2026, 8, 1), 1394.0)],
            rejected=[CensusRejectedRow(reason="UNEXPECTED_PROGRAM", category_code="X", data_type_code="TOTAL")],
        )

        assert result.rows_rejected == 1
        assert result.rejected_reasons == {"UNEXPECTED_PROGRAM": 1}
        assert result.status == "PARTIAL_FAILURE"

    def test_a_zero_value_census_actually_published_is_preserved(self, db_session) -> None:
        """The complement of "never zero": a real zero must survive."""
        _sync(db_session, [_row(date(2026, 8, 1), 0.0)])

        assert [item.value for item in _observations(db_session, PERMITS_SAAR)] == [0.0]


class TestProvenance:
    def test_provenance_records_censuss_own_identifier_and_no_api_url(self, db_session) -> None:
        from app.repositories.housing_repository import HousingRepository

        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])

        provenance = HousingRepository(db_session).get_provenance(PERMITS_SAAR, date(2026, 8, 1))
        assert provenance.provider == "CENSUS"
        assert provenance.dataset == "timeseries/eits/resconst"
        assert provenance.source_series_field == "APERMITS/TOTAL"
        # A Census API URL carries the credential.
        assert "api.census.gov" not in provenance.source_url
        assert "key=" not in provenance.source_url

    def test_provenance_and_version_history_agree_on_the_instant(self, db_session) -> None:
        from app.repositories.housing_repository import HousingRepository

        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])

        provenance = HousingRepository(db_session).get_provenance(PERMITS_SAAR, date(2026, 8, 1))
        version = _versions(db_session, PERMITS_SAAR, date(2026, 8, 1))[0]
        assert provenance.retrieved_at == version.recorded_from


class TestProviderFailure:
    def test_an_authentication_failure_is_a_recorded_failed_run(self, db_session) -> None:
        """The run genuinely happened, so it is recorded rather than
        raised -- and reported with a class name only."""
        result, _ = _sync(db_session, [], raises=CensusAuthError("rejected"))

        assert result.status == "FAILED"
        assert result.error_class == "CensusAuthError"
        run = db_session.execute(select(HousingIngestionRun)).scalars().one()
        assert run.status == "FAILED"
        assert run.error_class == "CensusAuthError"

    def test_a_failed_run_stores_no_observations(self, db_session) -> None:
        _sync(db_session, [], raises=CensusAuthError("rejected"))

        assert _observations(db_session, PERMITS_SAAR) == []

    def test_a_recorded_failure_carries_no_credential_or_message_text(self, db_session) -> None:
        _sync(db_session, [], raises=CensusAuthError("key sentinel-leak-me was rejected"))

        run = db_session.execute(select(HousingIngestionRun)).scalars().one()
        # A class NAME, never the exception's message.
        assert run.error_class == "CensusAuthError"
        assert "sentinel-leak-me" not in str(run.error_class)

    def test_an_empty_response_is_partial_failure_not_success(self, db_session) -> None:
        """A sync that stored nothing should not read as healthy."""
        result, _ = _sync(db_session, [])
        assert result.status == "PARTIAL_FAILURE"


class TestRequestShape:
    def test_a_full_history_sync_asks_for_the_datasets_first_period(self, db_session) -> None:
        _, client = _sync(db_session, [_row(date(2026, 8, 1), 1394.0)], full_history=True)
        assert client.calls == ["from 1959-01"]

    def test_a_routine_sync_asks_for_a_bounded_recent_window(self, db_session) -> None:
        _, client = _sync(
            db_session,
            [_row(date(2026, 8, 1), 1394.0)],
            lookback_months=12,
            as_of=date(2026, 9, 21),
        )
        # Twelve months INCLUDING September, so October the previous year.
        assert client.calls == ["from 2025-10"]

    def test_exactly_one_request_is_made_per_sync(self, db_session) -> None:
        """Census answers an open-ended time expression in a single
        response, so a per-month loop would be needless authenticated
        traffic."""
        _, client = _sync(db_session, [_row(date(2026, 8, 1), 1394.0)], full_history=True)
        assert len(client.calls) == 1

    @pytest.mark.parametrize("months", [0, -1, 241])
    def test_an_out_of_range_lookback_is_refused(self, db_session, months: int) -> None:
        with pytest.raises(ValueError):
            _sync(db_session, [], lookback_months=months)


class TestSeriesRouting:
    def test_every_bound_concept_is_reported_even_when_census_returned_nothing_for_it(
        self, db_session
    ) -> None:
        """Six concepts are MacroChipz's declared scope, so all six are
        accounted for -- a silently absent series would look like a
        success."""
        result, _ = _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])

        assert {item.concept_id for item in result.series} == set(HOUSING_CONCEPT_IDS)

    def test_rows_are_routed_by_census_identity_not_by_name(self, db_session) -> None:
        _sync(
            db_session,
            [
                _row(date(2026, 8, 1), 1394.0, category_code="APERMITS"),
                _row(date(2026, 8, 1), 1275.0, category_code="ASTARTS"),
            ],
        )

        assert [item.value for item in _observations(db_session, PERMITS_SAAR)] == [1_394_000.0]
        assert [item.value for item in _observations(db_session, STARTS_SAAR)] == [1_275_000.0]

    def test_the_binding_table_is_the_work_list(self, db_session) -> None:
        """A new Census category must not quietly become a MacroChipz
        series just because it appeared in the response."""
        result, _ = _sync(
            db_session,
            [_row(date(2026, 8, 1), 999.0, category_code="ANEWCATEGORY")],
        )

        assert result.rows_outside_scope == 1
        assert all(item.observations_inserted == 0 for item in result.series)

    def test_the_adjusted_and_unadjusted_series_are_stored_separately(self, db_session) -> None:
        """The classic silent error this increment's concept design exists
        to prevent."""
        _sync(
            db_session,
            [
                _row(date(2026, 8, 1), 1394.0, category_code="APERMITS", seasonally_adjusted=True),
                _row(date(2026, 8, 1), 117.4, category_code="PERMITS", seasonally_adjusted=False),
            ],
        )

        assert [item.value for item in _observations(db_session, PERMITS_SAAR)] == [1_394_000.0]
        assert [item.value for item in _observations(db_session, "us.housing.units-authorized.nsa.monthly")] == [
            117_400.0
        ]

    def test_the_two_units_are_never_arithmetically_related(self, db_session) -> None:
        """1,394,000 / 12 is 116,167, and the real unadjusted August
        figure is 117,400. Close enough to look right, and wrong on
        principle -- so the stored values must be exactly what Census
        published, each in its own series."""
        _sync(
            db_session,
            [
                _row(date(2026, 8, 1), 1394.0, category_code="APERMITS"),
                _row(date(2026, 8, 1), 117.4, category_code="PERMITS", seasonally_adjusted=False),
            ],
        )

        pace = _observations(db_session, PERMITS_SAAR)[0].value
        actual = _observations(db_session, "us.housing.units-authorized.nsa.monthly")[0].value
        assert actual != pytest.approx(pace / 12)


class TestBindingsMatchTheIngestionPath:
    def test_every_housing_binding_stores_under_its_concept_id(self, db_session) -> None:
        """A provider added after #38 has no legacy rows to preserve, so it
        stores MacroChipz's own identity from the first write."""
        for concept_id in HOUSING_CONCEPT_IDS:
            assert active_binding(concept_id).storage_series_id == concept_id

    def test_the_recorded_run_counts_match_what_was_written(self, db_session) -> None:
        result, _ = _sync(
            db_session,
            [_row(date(2026, 7, 1), 1433.0), _row(date(2026, 8, 1), 1394.0)],
        )

        run = db_session.execute(select(HousingIngestionRun)).scalars().one()
        assert run.observations_inserted == sum(item.observations_inserted for item in result.series)
        assert run.observations_inserted == 2
        assert run.duration_ms >= 0
        assert run.started_at <= run.completed_at
        assert run.started_at.tzinfo is not None


class TestNoFabricatedTimestamps:
    def test_recorded_from_is_a_real_instant_close_to_now(self, db_session) -> None:
        before = datetime.now(timezone.utc)
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        after = datetime.now(timezone.utc)

        recorded = _versions(db_session, PERMITS_SAAR, date(2026, 8, 1))[0].recorded_from
        assert before <= recorded <= after

    def test_no_publication_time_is_invented_for_an_observation(self, db_session) -> None:
        """Census publishes a release TIME, but this dataset carries no
        per-observation publication instant. Stamping the release time onto
        812 months of history would be a fabrication."""
        _sync(db_session, [_row(date(1959, 1, 1), 1657.0)])

        version = _versions(db_session, PERMITS_SAAR, date(1959, 1, 1))[0]
        # The only timestamp is the system time MacroChipz recorded it.
        assert version.recorded_from.year >= 2026
