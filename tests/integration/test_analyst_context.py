"""Integration tests for deterministic Analyst context assembly
(Increment #33).

Deliberately imports NOTHING model-related -- not `openai`, not
`app.services.analyst`. That is both required
(`test_transaction_and_safety.py` forbids an integration test from
importing a provider) and exactly the point: context assembly is
ordinary deterministic application code, and proving it works does not
involve a language model at all.

What these establish is that the packet is a faithful, complete,
self-describing view of canonical intelligence -- because whatever ends
up here is the entire universe the model is permitted to reason about.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import (
    EconomicRelease,
    EconomicSeries,
    RecordedMonitorResult,
    ReleaseCheckRun,
    ReleaseOccurrence,
)
from app.models.analyst import ANALYST_CONTEXT_VERSION, AnalystContextRef
from app.models.inflation import METHODOLOGY_ID as INFLATION_METHODOLOGY_ID, PRIMARY_SERIES_ID
from app.models.labor import METHODOLOGY_ID as LABOR_METHODOLOGY_ID, PAYEMS_SERIES_ID, UNRATE_SERIES_ID
from app.repositories.observation_versions import ORIGIN_RELEASE_PROCESSING, ObservationVersionWriter
from app.services.analyst_context import AnalystContextBuilder, AnalystContextUnavailableError

pytestmark = pytest.mark.integration

CALCULATED_AT = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
BEFORE = CALCULATED_AT - timedelta(days=30)
PERIOD = date(2026, 3, 1)


def _month(anchor: date, months_back: int) -> date:
    year, month = anchor.year, anchor.month - months_back
    while month <= 0:
        year -= 1
        month += 12
    return date(year, month, 1)


def _series(session, series_id: str) -> EconomicSeries:
    existing = session.execute(select(EconomicSeries).where(EconomicSeries.series_id == series_id)).scalar_one_or_none()
    if existing is not None:
        return existing
    series = EconomicSeries(series_id=series_id, title=series_id, units="Index", source="FRED")
    session.add(series)
    session.flush()
    return series


def _seed(session, series_id: str, values: dict[date, float], at: datetime = BEFORE) -> None:
    writer = ObservationVersionWriter(session, recorded_at=at, origin=ORIGIN_RELEASE_PROCESSING)
    series = _series(session, series_id)
    for observation_date, value in sorted(values.items()):
        writer.apply(series, observation_date, value)
    session.flush()


def _core_pce(anchor: date, months: int = 14) -> dict[date, float]:
    return {_month(anchor, n): 120.0 * (1.002 ** (months - n)) for n in range(months)}


def _recorded(session, monitor: str, state: str, methodology_id: str) -> RecordedMonitorResult:
    release = session.execute(
        select(EconomicRelease).where(EconomicRelease.provider == "FRED", EconomicRelease.provider_release_id == "7777")
    ).scalar_one_or_none()
    if release is None:
        release = EconomicRelease(name="Analyst Test Release", provider="FRED", provider_release_id="7777", active=True)
        session.add(release)
        session.flush()
    occurrence = session.execute(
        select(ReleaseOccurrence).where(
            ReleaseOccurrence.economic_release_id == release.id,
            ReleaseOccurrence.scheduled_date == date(2026, 5, 1),
        )
    ).scalar_one_or_none()
    if occurrence is None:
        occurrence = ReleaseOccurrence(economic_release_id=release.id, scheduled_date=date(2026, 5, 1))
        session.add(occurrence)
        session.flush()
    run = ReleaseCheckRun(
        release_occurrence_id=occurrence.id, status="CHANGED", started_at=CALCULATED_AT, completed_at=CALCULATED_AT
    )
    session.add(run)
    session.flush()
    recorded = RecordedMonitorResult(
        release_check_run_id=run.id,
        monitor=monitor,
        evaluation_period=PERIOD,
        state=state,
        methodology_id=methodology_id,
        data_basis="latest_revised_data",
        calculated_at=CALCULATED_AT,
    )
    session.add(recorded)
    session.flush()
    return recorded


@pytest.fixture
def builder() -> AnalystContextBuilder:
    return AnalystContextBuilder()


class TestPacketShape:
    @pytest.mark.parametrize("context_type", ["INFLATION", "LABOR", "RATES"])
    def test_every_packet_is_versioned_and_names_its_methodology(self, db_session, builder, context_type):
        packet = builder.build(db_session, AnalystContextRef(type=context_type))

        assert packet.context_version == ANALYST_CONTEXT_VERSION
        assert packet.context_type == context_type
        assert packet.methodology.methodology_id
        assert packet.methodology.summary, "the model is told what a methodology does, never left to guess"
        assert packet.limitations, "every packet states what it does not establish"

    @pytest.mark.parametrize("context_type", ["INFLATION", "LABOR", "RATES"])
    def test_every_evidence_id_is_unique_and_non_empty(self, db_session, builder, context_type):
        """Ids are the model's only permitted citation vocabulary; a
        duplicate would make a reference ambiguous."""
        packet = builder.build(db_session, AnalystContextRef(type=context_type))
        ids = [item.id for item in packet.evidence]

        assert all(ids)
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize("context_type", ["INFLATION", "LABOR", "RATES"])
    def test_a_packet_carries_no_secret_or_infrastructure_detail(self, db_session, builder, context_type):
        packet = builder.build(db_session, AnalystContextRef(type=context_type))
        serialized = packet.model_dump_json().lower()

        for forbidden in ("api_key", "password", "postgresql://", "postgres://", "secret", "authorization", "bearer"):
            assert forbidden not in serialized

    @pytest.mark.parametrize("context_type", ["INFLATION", "LABOR", "RATES"])
    def test_numeric_values_carry_their_units_as_text(self, db_session, builder, context_type):
        """A bare number is a unit mistake waiting to happen -- the same
        class of error that produced a 1,000x defect inside #32's own
        deterministic code before it was caught."""
        packet = builder.build(db_session, AnalystContextRef(type=context_type))

        for fact in packet.deterministic_metrics:
            assert isinstance(fact.value, str)
        for item in packet.evidence:
            assert item.value is None or isinstance(item.value, str)


class TestChangeFormatting:
    """Regressions for the one real context defect the live baseline
    exposed (Increment #33).

    `changes[]` shipped `str(3.1127788466932538)` while every other
    value in the packet shipped `"3.11%"`. The model then had to round
    and infer a unit before it could describe a change -- work the
    packet exists to have already done. It rounded correctly, which is
    why this surfaced as an evaluation false positive rather than a
    wrong answer, but the architecture's whole premise is that the
    backend owns the arithmetic.
    """

    def test_every_frozen_change_field_has_a_unit_or_is_text(self):
        """A field added to either what-changed contract must not
        silently fall back to an unlabelled number."""
        from app.models.inflation_what_changed import FIELD_ORDER as INFLATION_FIELDS
        from app.models.labor_what_changed import FIELD_ORDER as LABOR_FIELDS
        from app.services.analyst_context import _CHANGE_FIELD_UNIT, _CHANGE_TEXT_FIELDS

        uncovered = [
            field
            for field in (*INFLATION_FIELDS, *LABOR_FIELDS)
            if field not in _CHANGE_FIELD_UNIT and field not in _CHANGE_TEXT_FIELDS
        ]
        assert uncovered == [], f"change fields with no declared unit: {uncovered}"

    @pytest.mark.parametrize(
        ("field", "value", "expected"),
        [
            # The exact values from the baseline failure.
            ("r_3m_annualized", 3.1127788466932538, "3.11%"),
            ("r_6m_annualized", 3.8714268926618223, "3.87%"),
            ("headline_pce_yoy", 3.71697056247684, "3.72%"),
            ("current_3m_avg", 4.133333333333334, "4.1%"),
            # And the rest of both vocabularies.
            ("r_1m_annualized", 1.7753701617267081, "1.78%"),
            ("r_12m", 3.343614465473621, "3.34%"),
            ("target_gap_pp", 1.71697056247684, "1.72 pp"),
            ("current_3m_avg_jobs", 38333.333333333336, "38,333 jobs"),
            ("prior_3m_avg_jobs", 141666.66666666666, "141,667 jobs"),
            ("momentum_delta_jobs", -70333.33333333333, "-70,333 jobs"),
            ("prior_year_3m_avg", 4.2333333333, "4.2%"),
            ("delta_pp", -0.1, "-0.10 pp"),
        ],
    )
    def test_each_numeric_change_field_is_formatted_with_its_unit(self, builder, field, value, expected):
        assert builder._change_endpoint(field, value) == expected

    def test_a_canonical_name_passes_through_untouched(self):
        """State and relationship values are names, not numbers."""
        from app.services.analyst_context import AnalystContextBuilder

        assert AnalystContextBuilder._change_endpoint("state", "COOLING") == "COOLING"
        assert AnalystContextBuilder._change_endpoint("condition", "EXPANDING") == "EXPANDING"

    def test_a_missing_endpoint_is_named_not_blank(self, builder):
        assert builder._change_endpoint("r_12m", None) == "not available"

    def test_inflation_changes_carry_no_raw_float(self, db_session, builder):
        """The packet-level assertion: no unformatted float survives
        anywhere in `changes[]`."""
        _seed(db_session, PRIMARY_SERIES_ID, _core_pce(PERIOD))

        packet = builder.build(db_session, AnalystContextRef(type="INFLATION"))

        for fact in packet.changes:
            for token in fact.value.split():
                # A bare number with more than 3 decimals is an
                # unformatted float that escaped.
                if "." in token and token.replace(".", "").replace("-", "").replace(",", "").isdigit():
                    decimals = len(token.split(".")[1])
                    assert decimals <= 3, f"unformatted float in changes[]: {fact.label} = {fact.value}"

    def test_labor_changes_carry_no_raw_float(self, db_session, builder):
        payems = {_month(PERIOD, n): 158_000.0 + 50.0 * (20 - n) for n in range(20)}
        _seed(db_session, PAYEMS_SERIES_ID, payems)
        _seed(db_session, UNRATE_SERIES_ID, {_month(PERIOD, n): 4.0 for n in range(20)})

        packet = builder.build(db_session, AnalystContextRef(type="LABOR"))

        for fact in packet.changes:
            for token in fact.value.split():
                if "." in token and token.replace(".", "").replace("-", "").replace(",", "").isdigit():
                    decimals = len(token.split(".")[1])
                    assert decimals <= 3, f"unformatted float in changes[]: {fact.label} = {fact.value}"

    def test_job_counts_in_changes_match_the_evidence_units_exactly(self, db_session, builder):
        """`changes[]` and `evidence[]` must not disagree about whether
        PAYEMS is jobs or thousands -- the 1,000x trap #32 already hit
        once inside deterministic code."""
        payems = {_month(PERIOD, n): 158_000.0 + 50.0 * (20 - n) for n in range(20)}
        _seed(db_session, PAYEMS_SERIES_ID, payems)
        _seed(db_session, UNRATE_SERIES_ID, {_month(PERIOD, n): 4.0 for n in range(20)})

        packet = builder.build(db_session, AnalystContextRef(type="LABOR"))
        job_changes = [f for f in packet.changes if "jobs" in f.label]
        evidence = next(i for i in packet.evidence if i.id == "labor.metric.payroll_3m_average")

        assert evidence.value is not None and evidence.value.endswith(" jobs")
        for fact in job_changes:
            assert " jobs" in fact.value, f"{fact.label} lost its unit: {fact.value}"


class TestInflationContext:
    def test_the_canonical_state_is_the_engines_state_verbatim(self, db_session, builder):
        _seed(db_session, PRIMARY_SERIES_ID, _core_pce(PERIOD))
        from app.services.inflation import InflationMonitorService

        expected = InflationMonitorService().get_result(db_session).underlying_momentum.state

        packet = builder.build(db_session, AnalystContextRef(type="INFLATION"))

        assert packet.canonical_state == expected

    def test_each_methodology_horizon_becomes_citable_evidence(self, db_session, builder):
        _seed(db_session, PRIMARY_SERIES_ID, _core_pce(PERIOD))

        packet = builder.build(db_session, AnalystContextRef(type="INFLATION"))
        ids = packet.evidence_ids()

        assert "inflation.state.core_pce" in ids
        assert {"inflation.metric.3m_annualized", "inflation.metric.6m_annualized", "inflation.metric.12m"} <= ids

    def test_evidence_details_name_the_exact_observations_behind_a_metric(self, db_session, builder):
        _seed(db_session, PRIMARY_SERIES_ID, _core_pce(PERIOD))

        packet = builder.build(db_session, AnalystContextRef(type="INFLATION"))
        twelve_month = next(i for i in packet.evidence if i.id == "inflation.metric.12m")

        assert twelve_month.detail is not None
        assert "index" in twelve_month.detail


class TestLaborContext:
    def test_payroll_evidence_is_expressed_in_jobs_not_native_thousands(self, db_session, builder):
        """`labor_v1.0` reports jobs; FRED publishes thousands. The
        packet must speak the methodology's unit and say so."""
        payems = {_month(PERIOD, n): 158_000.0 + 50.0 * (20 - n) for n in range(20)}
        _seed(db_session, PAYEMS_SERIES_ID, payems)
        _seed(db_session, UNRATE_SERIES_ID, {_month(PERIOD, n): 4.0 for n in range(20)})

        packet = builder.build(db_session, AnalystContextRef(type="LABOR"))
        average = next(i for i in packet.evidence if i.id == "labor.metric.payroll_3m_average")

        assert average.value is not None and average.value.endswith(" jobs")
        assert "," in average.value, "a jobs figure is grouped, so it cannot be misread as thousands"

    def test_the_combined_state_and_both_components_are_all_citable(self, db_session, builder):
        packet = builder.build(db_session, AnalystContextRef(type="LABOR"))
        ids = packet.evidence_ids()

        assert {"labor.state.combined", "labor.state.employment", "labor.state.unemployment"} <= ids


class TestRatesContext:
    def test_rates_has_no_canonical_state_and_says_so(self, db_session, builder):
        """`rates_v1.0` publishes levels and derived metrics, not a
        classification. Inventing one here would fabricate intelligence
        the engine does not produce."""
        packet = builder.build(db_session, AnalystContextRef(type="RATES"))

        assert packet.canonical_state is None
        assert any("does not classify rates into a state" in limit for limit in packet.limitations)

    def test_session_counted_windows_are_disclosed_as_such(self, db_session, builder):
        packet = builder.build(db_session, AnalystContextRef(type="RATES"))

        assert any("trading sessions, not calendar days" in limit for limit in packet.limitations)

    def test_historical_percentiles_are_disclaimed_as_backward_looking(self, db_session, builder):
        packet = builder.build(db_session, AnalystContextRef(type="RATES"))

        assert any("say nothing about what will happen next" in limit for limit in packet.limitations)


class TestMonitorHistoryContext:
    def test_the_recorded_state_and_todays_reconstruction_are_both_present_and_distinct(self, db_session, builder):
        _seed(db_session, PRIMARY_SERIES_ID, _core_pce(PERIOD))
        recorded = _recorded(db_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID)

        packet = builder.build(
            db_session,
            AnalystContextRef(type="MONITOR_HISTORY", monitor="inflation", recorded_result_id=recorded.id),
        )

        assert packet.canonical_state == "COOLING"
        labels = {fact.label for fact in packet.deterministic_metrics}
        assert {"Recorded state", "Today's reconstruction"} <= labels

    def test_replay_information_is_carried_verbatim(self, db_session, builder):
        _seed(db_session, PRIMARY_SERIES_ID, _core_pce(PERIOD))
        recorded = _recorded(db_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID)

        packet = builder.build(
            db_session,
            AnalystContextRef(type="MONITOR_HISTORY", monitor="inflation", recorded_result_id=recorded.id),
        )

        assert packet.replay_information is not None
        assert packet.replay_information.outcome in {"MATCH", "MISMATCH", "NOT_REPLAYABLE"}

    def test_a_replay_mismatch_is_escalated_into_an_explicit_limitation(self, db_session, builder):
        """The model must be told, in the context itself, that a
        mismatch is an integrity issue -- not left to infer it."""
        _seed(db_session, PRIMARY_SERIES_ID, _core_pce(PERIOD))
        from app.domain.inflation import compute_series_momentum_at
        from app.models.series import Observation

        history = _core_pce(PERIOD)
        genuine = compute_series_momentum_at(
            [Observation(date=d, value=v) for d, v in sorted(history.items())], PRIMARY_SERIES_ID, PERIOD
        ).state
        wrong = "HEATING" if genuine != "HEATING" else "COOLING"
        recorded = _recorded(db_session, "inflation", wrong, INFLATION_METHODOLOGY_ID)

        packet = builder.build(
            db_session,
            AnalystContextRef(type="MONITOR_HISTORY", monitor="inflation", recorded_result_id=recorded.id),
        )

        assert packet.replay_information is not None
        assert packet.replay_information.outcome == "MISMATCH"
        assert any("integrity" in limit and "explained away" in limit for limit in packet.limitations)

    def test_causation_is_forbidden_in_the_context_itself(self, db_session, builder):
        _seed(db_session, PRIMARY_SERIES_ID, _core_pce(PERIOD))
        recorded = _recorded(db_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID)

        packet = builder.build(
            db_session,
            AnalystContextRef(type="MONITOR_HISTORY", monitor="inflation", recorded_result_id=recorded.id),
        )

        assert any("does not record that one caused the other" in limit for limit in packet.limitations)

    def test_a_methodology_difference_becomes_an_explicit_limitation(self, db_session, builder):
        _seed(db_session, PRIMARY_SERIES_ID, _core_pce(PERIOD))
        recorded = _recorded(db_session, "inflation", "COOLING", "inflation_v0.9")

        packet = builder.build(
            db_session,
            AnalystContextRef(type="MONITOR_HISTORY", monitor="inflation", recorded_result_id=recorded.id),
        )

        assert any("inflation_v0.9" in limit and "changed methodology" in limit for limit in packet.limitations)

    def test_an_unknown_recorded_result_is_refused_not_invented(self, db_session, builder):
        with pytest.raises(AnalystContextUnavailableError):
            builder.build(
                db_session, AnalystContextRef(type="MONITOR_HISTORY", monitor="inflation", recorded_result_id=999_999)
            )

    def test_a_history_reference_without_an_identifier_is_refused(self, db_session, builder):
        with pytest.raises(AnalystContextUnavailableError):
            builder.build(db_session, AnalystContextRef(type="MONITOR_HISTORY"))

    def test_a_labor_result_cannot_be_loaded_under_the_inflation_monitor(self, db_session, builder):
        recorded = _recorded(db_session, "labor", "MIXED", LABOR_METHODOLOGY_ID)

        with pytest.raises(AnalystContextUnavailableError):
            builder.build(
                db_session,
                AnalystContextRef(type="MONITOR_HISTORY", monitor="inflation", recorded_result_id=recorded.id),
            )


class TestNoCanonicalSideEffects:
    def test_building_a_packet_writes_nothing(self, db_session, builder):
        """The Analyst's context is a pure read of canonical
        intelligence; asking a question must never alter history."""
        _seed(db_session, PRIMARY_SERIES_ID, _core_pce(PERIOD))
        from sqlalchemy import func

        from app.db.models import EconomicObservation, ObservationVersion

        def counts() -> tuple[int, int, int]:
            return (
                db_session.execute(select(func.count()).select_from(EconomicObservation)).scalar_one(),
                db_session.execute(select(func.count()).select_from(ObservationVersion)).scalar_one(),
                db_session.execute(select(func.count()).select_from(RecordedMonitorResult)).scalar_one(),
            )

        before = counts()
        for context_type in ("INFLATION", "LABOR", "RATES"):
            builder.build(db_session, AnalystContextRef(type=context_type))
        assert counts() == before
