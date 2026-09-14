"""Tests for the pure What Changed comparator
(app.domain.labor_what_changed), contract `labor_what_changed_v1.0` --
frozen and normative in
research/labor_momentum/LABOR_WHAT_CHANGED_V1_FROZEN_METHODOLOGY.md.
Pure, offline, deterministic: no database, no network, no FRED, no
OpenAI.

Historical regression fixtures use REAL PAYEMS/UNRATE values (FRED's
native units), taken directly from the cached research data that
validated `labor_v1.0` (research/labor_momentum/data/PAYEMS.csv,
UNRATE.csv) -- not fabricated numbers. Real `EmploymentResult`/
`UnemploymentResult` evidence objects for these fixtures are built by
CALLING `app.domain.labor`'s own already-frozen, already-tested
`compute_employment_result`/`compute_unemployment_result` primitives
(exactly like tests/integration/test_labor_service.py already does) --
this is test-fixture construction, not a violation of the comparator's
own "never imports app.domain.labor" architectural guard (checked
separately, statically, in tests/test_labor_architecture.py and
tests/test_domain_architectural_independence.py against the PRODUCTION
module, not this test file).
"""

from datetime import date

import pytest

from app.domain.labor import combine_labor_state, compute_employment_result, compute_unemployment_result, month_before
from app.domain.labor_what_changed import (
    assemble_labor_what_changed_result,
    compare_employment_section,
    compare_labor_state,
    compare_unemployment_section,
)
from app.models.labor import CONDITION_DEADBAND_JOBS, EmploymentResult, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP, UnemploymentResult

# ---------------------------------------------------------------------
# Real historical PAYEMS values (FRED native "Thousands of Persons"),
# taken directly from research/labor_momentum/data/PAYEMS.csv -- the
# exact data that validated labor_v1.0. Spans late 2007 through late
# 2009 (Great Recession/early recovery), 2019-2020 (COVID collapse/
# snapback), 2020-2021 (2021 recovery), and 2021-2024 (post-recovery
# normal growth) -- enough contiguous real months to compute
# compute_employment_result at every anchor used below.
# ---------------------------------------------------------------------

_PAYEMS_THOUSANDS: dict[date, float] = {
    date(2008, 1, 1): 138391, date(2008, 2, 1): 138329, date(2008, 3, 1): 138259, date(2008, 4, 1): 138040,
    date(2008, 5, 1): 137851, date(2008, 6, 1): 137700, date(2008, 7, 1): 137497, date(2008, 8, 1): 137211,
    date(2008, 9, 1): 136760, date(2008, 10, 1): 136291, date(2008, 11, 1): 135541, date(2008, 12, 1): 134847,
    date(2009, 1, 1): 134079, date(2009, 2, 1): 133318, date(2009, 3, 1): 132494, date(2009, 4, 1): 131822,
    date(2009, 5, 1): 131466, date(2009, 6, 1): 131008, date(2009, 7, 1): 130662, date(2009, 8, 1): 130472,
    date(2009, 9, 1): 130246,
    date(2019, 10, 1): 151460, date(2019, 11, 1): 151667, date(2019, 12, 1): 151794,
    date(2020, 1, 1): 152031, date(2020, 2, 1): 152293, date(2020, 3, 1): 150895, date(2020, 4, 1): 130426,
    date(2020, 5, 1): 133040, date(2020, 6, 1): 137671, date(2020, 7, 1): 139255, date(2020, 8, 1): 140821,
    date(2020, 9, 1): 141770, date(2020, 10, 1): 142460, date(2020, 11, 1): 142733, date(2020, 12, 1): 142548,
    date(2021, 1, 1): 142863, date(2021, 2, 1): 143380, date(2021, 3, 1): 144232, date(2021, 4, 1): 144587,
    date(2021, 5, 1): 145065, date(2021, 6, 1): 145820,
    date(2022, 1, 1): 150006, date(2022, 2, 1): 150825, date(2022, 3, 1): 151315, date(2022, 4, 1): 151623,
    date(2022, 5, 1): 151924, date(2022, 6, 1): 152358, date(2022, 7, 1): 153072, date(2022, 8, 1): 153362,
    date(2022, 9, 1): 153582,
    date(2023, 4, 1): 155375, date(2023, 5, 1): 155655, date(2023, 6, 1): 155880, date(2023, 7, 1): 156043,
    date(2023, 8, 1): 156261, date(2023, 9, 1): 156417,
    date(2024, 1, 1): 157032, date(2024, 2, 1): 157238, date(2024, 3, 1): 157466, date(2024, 4, 1): 157530,
    date(2024, 5, 1): 157608, date(2024, 6, 1): 157695, date(2024, 7, 1): 157748, date(2024, 8, 1): 157757,
    date(2024, 9, 1): 157912,
}
_PAYEMS_JOBS: dict[date, float] = {d: v * 1000 for d, v in _PAYEMS_THOUSANDS.items()}

_UNRATE_PERCENT: dict[date, float] = {
    date(2008, 1, 1): 5.0, date(2008, 2, 1): 4.9, date(2008, 3, 1): 5.1, date(2008, 4, 1): 5.0,
    date(2008, 5, 1): 5.4, date(2008, 6, 1): 5.6, date(2008, 7, 1): 5.8, date(2008, 8, 1): 6.1,
    date(2008, 9, 1): 6.1, date(2008, 10, 1): 6.5, date(2008, 11, 1): 6.8, date(2008, 12, 1): 7.3,
    date(2009, 1, 1): 7.8, date(2009, 2, 1): 8.3, date(2009, 3, 1): 8.7, date(2009, 4, 1): 9.0,
    date(2009, 5, 1): 9.4, date(2009, 6, 1): 9.5, date(2009, 7, 1): 9.5, date(2009, 8, 1): 9.6,
    date(2009, 9, 1): 9.8,
    date(2019, 1, 1): 4.0, date(2019, 2, 1): 3.8, date(2019, 3, 1): 3.8, date(2019, 4, 1): 3.6,
    date(2019, 5, 1): 3.6, date(2019, 6, 1): 3.6, date(2019, 7, 1): 3.7, date(2019, 8, 1): 3.7,
    date(2019, 9, 1): 3.5,
    date(2020, 1, 1): 3.6, date(2020, 2, 1): 3.5, date(2020, 3, 1): 4.4, date(2020, 4, 1): 14.8,
    date(2020, 5, 1): 13.2, date(2020, 6, 1): 11.0, date(2020, 7, 1): 10.2, date(2020, 8, 1): 8.4,
    date(2020, 9, 1): 7.8,
    date(2021, 1, 1): 6.4, date(2021, 2, 1): 6.2, date(2021, 3, 1): 6.1, date(2021, 4, 1): 6.1,
    date(2021, 5, 1): 5.8, date(2021, 6, 1): 5.9, date(2021, 7, 1): 5.4, date(2021, 8, 1): 5.1,
    date(2022, 1, 1): 4.0, date(2022, 2, 1): 3.9, date(2022, 3, 1): 3.7, date(2022, 4, 1): 3.7,
    date(2022, 5, 1): 3.6, date(2022, 6, 1): 3.6, date(2022, 7, 1): 3.5, date(2022, 8, 1): 3.6,
    date(2022, 9, 1): 3.5,
    date(2023, 4, 1): 3.4, date(2023, 5, 1): 3.6, date(2023, 6, 1): 3.6, date(2023, 7, 1): 3.5,
    date(2023, 8, 1): 3.7, date(2023, 9, 1): 3.7,
    date(2024, 5, 1): 3.9, date(2024, 6, 1): 4.1, date(2024, 7, 1): 4.2, date(2024, 8, 1): 4.2,
    date(2024, 9, 1): 4.1,
}


def _employment(period: date) -> EmploymentResult:
    return compute_employment_result(_PAYEMS_JOBS, period, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)


def _unemployment(period: date) -> UnemploymentResult:
    return compute_unemployment_result(_UNRATE_PERCENT, period, UNEMPLOYMENT_DEADBAND_PP)


def _labor_state(period: date) -> str:
    return combine_labor_state(_employment(period).state, _unemployment(period).state)


# Sanity-check the fixture data itself reproduces the exact facts
# #20B's own regression suite already pinned, before building What
# Changed assertions on top of it -- if the shared fixture data ever
# drifts, THIS fails first, with an unambiguous message, rather than
# a confusing downstream comparator assertion.
class TestFixtureSanity:
    def test_fixture_reproduces_the_20b_pinned_facts(self):
        assert _employment(date(2009, 8, 1)).state == "RECOVERING"
        assert _employment(date(2021, 4, 1)).state == "EXPANDING"
        assert _employment(date(2021, 4, 1)).momentum == "IMPROVING"
        assert _employment(date(2021, 6, 1)).momentum == "STEADY"


# ---------------------------------------------------------------------
# EMPLOYMENT section: state/condition/momentum transitions, using real
# 2009 (Great Recession -> recovery), 2020 (COVID collapse -> snapback),
# 2021, and 2022-2024 data.
# ---------------------------------------------------------------------


class TestEmploymentStateAndMomentumChangeTogether:
    """2009-04 -> 2009-05: the exact real month labor_v1.0 first
    classifies the labor market as RECOVERING -- condition stays
    CONTRACTING (payrolls still falling), momentum flips STEADY ->
    IMPROVING, and EMPLOYMENT.state flips CONTRACTING -> RECOVERING."""

    PREV, CURR = date(2009, 4, 1), date(2009, 5, 1)

    def test_condition_unchanged_momentum_and_state_changed(self):
        result = compare_employment_section(self.PREV, self.CURR, _employment(self.PREV), _employment(self.CURR))
        assert result.state_changed is True
        fields_changed = {e.field for e in result.changes if e.event_type == "STATE_CHANGED"}
        assert fields_changed == {"state", "momentum"}
        assert "condition" not in fields_changed

        state_event = next(e for e in result.changes if e.field == "state")
        assert (state_event.previous_value, state_event.current_value) == ("CONTRACTING", "RECOVERING")
        momentum_event = next(e for e in result.changes if e.field == "momentum")
        assert (momentum_event.previous_value, momentum_event.current_value) == ("STEADY", "IMPROVING")

    def test_metrics_also_changed(self):
        result = compare_employment_section(self.PREV, self.CURR, _employment(self.PREV), _employment(self.CURR))
        assert result.metric_changed is True


class TestEmploymentMetricsOnlyNoCategoricalChange:
    """2009-07 -> 2009-08: both RECOVERING throughout -- the recovery
    is real and ongoing (metrics keep improving) but the categorical
    picture (condition/momentum/state) is already stable, so only
    METRIC_CHANGED events fire."""

    PREV, CURR = date(2009, 7, 1), date(2009, 8, 1)

    def test_no_state_condition_or_momentum_change(self):
        result = compare_employment_section(self.PREV, self.CURR, _employment(self.PREV), _employment(self.CURR))
        assert result.state_changed is False
        assert {e.field for e in result.changes if e.event_type == "STATE_CHANGED"} == set()

    def test_all_three_numeric_metrics_changed(self):
        result = compare_employment_section(self.PREV, self.CURR, _employment(self.PREV), _employment(self.CURR))
        assert result.metric_changed is True
        changed_fields = {e.field for e in result.changes if e.event_type == "METRIC_CHANGED"}
        assert changed_fields == {"current_3m_avg_jobs", "prior_3m_avg_jobs", "momentum_delta_jobs"}


class TestEmploymentCovidSnapback:
    """2020-06 -> 2020-07: condition, momentum, AND state all flip at
    once -- CONTRACTING/WORSENING/CONTRACTING to EXPANDING/IMPROVING/
    EXPANDING, the single largest real month-over-month swing in the
    validated history. Proves the comparator handles a fully
    simultaneous multi-field transition correctly, not just isolated
    single-field ones."""

    PREV, CURR = date(2020, 6, 1), date(2020, 7, 1)

    def test_condition_momentum_and_state_all_changed(self):
        result = compare_employment_section(self.PREV, self.CURR, _employment(self.PREV), _employment(self.CURR))
        fields_changed = {e.field for e in result.changes if e.event_type == "STATE_CHANGED"}
        assert fields_changed == {"state", "condition", "momentum"}

        condition_event = next(e for e in result.changes if e.field == "condition")
        assert (condition_event.previous_value, condition_event.current_value) == ("CONTRACTING", "EXPANDING")
        state_event = next(e for e in result.changes if e.field == "state")
        assert (state_event.previous_value, state_event.current_value) == ("CONTRACTING", "EXPANDING")


class TestEmploymentMomentumChangeIndependentOfState:
    """2021-05 -> 2021-06: momentum decelerates IMPROVING -> STEADY,
    but condition (EXPANDING) and therefore EMPLOYMENT.state
    (EXPANDING) are both unaffected -- proving `momentum` is reported
    independently of `state`, never suppressed just because the
    top-level state didn't move (frozen contract §6)."""

    PREV, CURR = date(2021, 5, 1), date(2021, 6, 1)

    def test_momentum_changed_state_did_not(self):
        result = compare_employment_section(self.PREV, self.CURR, _employment(self.PREV), _employment(self.CURR))
        fields_changed = {e.field for e in result.changes if e.event_type == "STATE_CHANGED"}
        assert fields_changed == {"momentum"}
        assert result.state_changed is False  # top-level EMPLOYMENT.state event specifically

        momentum_event = next(e for e in result.changes if e.field == "momentum")
        assert (momentum_event.previous_value, momentum_event.current_value) == ("IMPROVING", "STEADY")


class TestEmploymentConditionAndStateChangeWithoutMomentumChange:
    """2024-07 -> 2024-08: condition slips EXPANDING -> FLAT and state
    follows COOLING -> STABLE, but momentum stays WORSENING both
    months -- unaffected. The mirror image of the test above: proves
    `condition` and `state` can change while `momentum` independently
    does not."""

    PREV, CURR = date(2024, 7, 1), date(2024, 8, 1)

    def test_condition_and_state_changed_momentum_did_not(self):
        result = compare_employment_section(self.PREV, self.CURR, _employment(self.PREV), _employment(self.CURR))
        fields_changed = {e.field for e in result.changes if e.event_type == "STATE_CHANGED"}
        assert fields_changed == {"condition", "state"}
        assert "momentum" not in fields_changed

        condition_event = next(e for e in result.changes if e.field == "condition")
        assert (condition_event.previous_value, condition_event.current_value) == ("EXPANDING", "FLAT")
        state_event = next(e for e in result.changes if e.field == "state")
        assert (state_event.previous_value, state_event.current_value) == ("COOLING", "STABLE")


class TestEmploymentFullReversalOverTwoConsecutiveMonths:
    """2024-08 -> 2024-09: condition, momentum, AND state all flip
    back the other way (FLAT/WORSENING/STABLE -> EXPANDING/STEADY/
    EXPANDING) -- while the top-level LABOR.state stays MIXED both
    months (see TestLaborStateComparison below), proving EMPLOYMENT
    can swing completely while LABOR.state does not move at all."""

    PREV, CURR = date(2024, 8, 1), date(2024, 9, 1)

    def test_all_three_fields_changed(self):
        result = compare_employment_section(self.PREV, self.CURR, _employment(self.PREV), _employment(self.CURR))
        fields_changed = {e.field for e in result.changes if e.event_type == "STATE_CHANGED"}
        assert fields_changed == {"condition", "momentum", "state"}

    def test_labor_state_unaffected(self):
        assert _labor_state(self.PREV) == _labor_state(self.CURR) == "MIXED"


# ---------------------------------------------------------------------
# UNEMPLOYMENT section
# ---------------------------------------------------------------------


class TestUnemploymentMetricsOnlyThroughoutRecession:
    """2009-04 -> 2009-05 and 2009-07 -> 2009-08: DETERIORATING
    throughout the Great Recession -- no state change, but the
    magnitude keeps growing (metrics changed)."""

    @pytest.mark.parametrize("prev,curr", [(date(2009, 4, 1), date(2009, 5, 1)), (date(2009, 7, 1), date(2009, 8, 1))])
    def test_deteriorating_throughout_metrics_changed(self, prev, curr):
        result = compare_unemployment_section(prev, curr, _unemployment(prev), _unemployment(curr))
        assert result.state_changed is False
        assert result.metric_changed is True


class TestUnemploymentImprovingThroughout2021Recovery:
    @pytest.mark.parametrize("prev,curr", [(date(2021, 4, 1), date(2021, 5, 1)), (date(2021, 5, 1), date(2021, 6, 1))])
    def test_improving_throughout_metrics_changed(self, prev, curr):
        result = compare_unemployment_section(prev, curr, _unemployment(prev), _unemployment(curr))
        assert result.state_changed is False
        assert result.metric_changed is True
        assert _unemployment(prev).state == _unemployment(curr).state == "IMPROVING"


class TestUnemploymentStableQuietEconomy2023:
    PREV, CURR = date(2023, 6, 1), date(2023, 7, 1)

    def test_stable_throughout_metrics_still_changed(self):
        result = compare_unemployment_section(self.PREV, self.CURR, _unemployment(self.PREV), _unemployment(self.CURR))
        assert _unemployment(self.PREV).state == _unemployment(self.CURR).state == "STABLE"
        assert result.state_changed is False
        assert result.metric_changed is True


class TestUnemploymentCovidStillDeterioratingDespitePayrollSnapback:
    """2020-06 -> 2020-07: even as PAYEMS posted its biggest gain on
    record (TestEmploymentCovidSnapback above), UNRATE's own
    prior-year-relative trend is still DETERIORATING both months
    (unemployment remains historically far above its year-ago level)
    -- proving UNEMPLOYMENT is judged entirely on its own terms, never
    inferred from EMPLOYMENT's direction."""

    PREV, CURR = date(2020, 6, 1), date(2020, 7, 1)

    def test_still_deteriorating_both_months(self):
        assert _unemployment(self.PREV).state == _unemployment(self.CURR).state == "DETERIORATING"
        result = compare_unemployment_section(self.PREV, self.CURR, _unemployment(self.PREV), _unemployment(self.CURR))
        assert result.state_changed is False
        assert result.metric_changed is True


# ---------------------------------------------------------------------
# Top-level LABOR.state comparison
# ---------------------------------------------------------------------


class TestLaborStateComparison:
    def test_2009_04_to_05_cooling_to_mixed(self):
        """CONTRACTING+DETERIORATING (COOLING) -> RECOVERING+DETERIORATING
        (no table cell -> MIXED, per the frozen default): the exact
        real month the top-level state stops being a clean COOLING
        read as soon as EMPLOYMENT enters RECOVERING -- the frozen
        table has no RECOVERING+anything cell other than MIXED, by
        design (RECOVERING never resolves to STRENGTHENING)."""
        prev, curr = date(2009, 4, 1), date(2009, 5, 1)
        assert _labor_state(prev) == "COOLING"
        assert _labor_state(curr) == "MIXED"
        events = compare_labor_state(prev, curr, _labor_state(prev), _labor_state(curr))
        assert len(events) == 1
        assert events[0].component == "LABOR"
        assert events[0].event_type == "STATE_CHANGED"
        assert (events[0].previous_value, events[0].current_value) == ("COOLING", "MIXED")

    def test_2020_06_to_07_cooling_to_mixed_despite_huge_payroll_gain(self):
        prev, curr = date(2020, 6, 1), date(2020, 7, 1)
        assert _labor_state(prev) == "COOLING"
        assert _labor_state(curr) == "MIXED"
        events = compare_labor_state(prev, curr, _labor_state(prev), _labor_state(curr))
        assert events[0].event_type == "STATE_CHANGED"

    def test_2022_07_to_08_mixed_to_strengthening(self):
        prev, curr = date(2022, 7, 1), date(2022, 8, 1)
        assert _labor_state(prev) == "MIXED"
        assert _labor_state(curr) == "STRENGTHENING"
        events = compare_labor_state(prev, curr, _labor_state(prev), _labor_state(curr))
        assert (events[0].previous_value, events[0].current_value) == ("MIXED", "STRENGTHENING")

    def test_2021_04_to_05_strengthening_confirmed_no_change(self):
        prev, curr = date(2021, 4, 1), date(2021, 5, 1)
        assert _labor_state(prev) == _labor_state(curr) == "STRENGTHENING"
        events = compare_labor_state(prev, curr, _labor_state(prev), _labor_state(curr))
        assert events == []

    def test_2021_05_to_06_strengthening_confirmed_even_as_momentum_decelerates(self):
        """Companion to TestEmploymentMomentumChangeIndependentOfState:
        LABOR.state stays STRENGTHENING even though EMPLOYMENT.momentum
        changed underneath it."""
        prev, curr = date(2021, 5, 1), date(2021, 6, 1)
        assert _labor_state(prev) == _labor_state(curr) == "STRENGTHENING"
        events = compare_labor_state(prev, curr, _labor_state(prev), _labor_state(curr))
        assert events == []

    def test_insufficient_data_never_counts_as_a_valid_transition_endpoint(self):
        events = compare_labor_state(date(2020, 1, 1), date(2020, 2, 1), "INSUFFICIENT_DATA", "INSUFFICIENT_DATA")
        assert events == []


# ---------------------------------------------------------------------
# Availability transitions (synthetic gaps, built the same way #20B's
# own missing-month tests build them: deleting a required month from a
# real, otherwise-complete index).
# ---------------------------------------------------------------------


class TestAvailabilityTransitions:
    def test_employment_availability_lost_when_a_required_month_disappears(self):
        """Deleting the ANCHOR month itself (offset 0, not just one of
        the older required months) guarantees BOTH `current_3m_avg_jobs`
        (needs t) and `prior_3m_avg_jobs` (needs t-3..t-6, unaffected)
        -- specifically `current_3m_avg_jobs` becomes unavailable,
        which is what drives both `condition` and `momentum` (and
        therefore `state`) to INSUFFICIENT_DATA together."""
        anchor = date(2009, 8, 1)
        complete = dict(_PAYEMS_JOBS)
        gapped = dict(complete)
        del gapped[anchor]

        previous_evidence = compute_employment_result(complete, anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        current_evidence = compute_employment_result(gapped, anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        assert previous_evidence.state != "INSUFFICIENT_DATA"
        assert current_evidence.state == "INSUFFICIENT_DATA"

        result = compare_employment_section(anchor, anchor, previous_evidence, current_evidence)
        assert result.availability_lost is True
        assert result.availability_restored is False
        # state/condition/momentum all lose availability together (all derived from the same computation):
        lost_fields = {e.field for e in result.changes if e.event_type == "AVAILABILITY_LOST"}
        assert {"state", "condition", "momentum"} <= lost_fields

    def test_employment_availability_restored_is_the_mirror_image(self):
        anchor = date(2009, 8, 1)
        complete = dict(_PAYEMS_JOBS)
        gapped = dict(complete)
        del gapped[anchor]

        previous_evidence = compute_employment_result(gapped, anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        current_evidence = compute_employment_result(complete, anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        result = compare_employment_section(anchor, anchor, previous_evidence, current_evidence)
        assert result.availability_restored is True
        assert result.availability_lost is False

    def test_employment_and_labor_availability_loss_co_occur_from_one_gap(self):
        """A single PAYEMS gap makes EMPLOYMENT unavailable, and since
        LABOR.state depends on EMPLOYMENT.state, LABOR.state ALSO
        becomes INSUFFICIENT_DATA from the exact same root cause --
        both sections legitimately report AVAILABILITY_LOST
        independently (never suppressed into one event), while
        UNEMPLOYMENT (an entirely different series) is completely
        unaffected."""
        anchor = date(2009, 8, 1)
        complete = dict(_PAYEMS_JOBS)
        gapped = dict(complete)
        del gapped[month_before(anchor, 6)]

        prev_employment = compute_employment_result(complete, anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        curr_employment = compute_employment_result(gapped, anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        unemployment_evidence = _unemployment(anchor)  # same both sides -- UNRATE untouched
        prev_labor_state = combine_labor_state(prev_employment.state, unemployment_evidence.state)
        curr_labor_state = combine_labor_state(curr_employment.state, unemployment_evidence.state)
        assert curr_labor_state == "INSUFFICIENT_DATA"

        employment_changes = compare_employment_section(anchor, anchor, prev_employment, curr_employment)
        unemployment_changes = compare_unemployment_section(anchor, anchor, unemployment_evidence, unemployment_evidence)
        labor_changes = compare_labor_state(anchor, anchor, prev_labor_state, curr_labor_state)

        assert employment_changes.availability_lost is True
        assert any(e.event_type == "AVAILABILITY_LOST" for e in labor_changes)
        assert unemployment_changes.changes == []  # completely unaffected by the PAYEMS-only gap

    def test_unemployment_availability_lost_and_restored(self):
        anchor = date(2020, 6, 1)
        complete = dict(_UNRATE_PERCENT)
        gapped = dict(complete)
        del gapped[month_before(anchor, 13)]

        lost_prev = compute_unemployment_result(complete, anchor, UNEMPLOYMENT_DEADBAND_PP)
        lost_curr = compute_unemployment_result(gapped, anchor, UNEMPLOYMENT_DEADBAND_PP)
        lost_result = compare_unemployment_section(anchor, anchor, lost_prev, lost_curr)
        assert lost_result.availability_lost is True

        restored_result = compare_unemployment_section(anchor, anchor, lost_curr, lost_prev)
        assert restored_result.availability_restored is True

    def test_both_sides_insufficient_produces_no_event(self):
        anchor = date(2009, 8, 1)
        insufficient = compute_employment_result({}, anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        assert insufficient.state == "INSUFFICIENT_DATA"
        result = compare_employment_section(anchor, anchor, insufficient, insufficient)
        assert result.changes == []
        assert result.availability_lost is False
        assert result.availability_restored is False


# ---------------------------------------------------------------------
# Real UNRATE 2025-10 gap -- fixture-based (not live FRED), proving
# exact-t-1/never-skip using the SAME production `compute_unemployment_result`
# #20A.1's own research first found this gap against, and #20B's own
# test_known_real_historical_gap_shape_2025_10_unrate already pins the
# single-period shape of. Here it's exercised at the What Changed
# layer: a real availability transition caused entirely by which
# EXACT calendar month happens to fall in the required window.
# ---------------------------------------------------------------------


class TestRealUnrate202510GapAtTheWhatChangedLayer:
    def _index(self) -> dict[date, float]:
        # A synthetic-but-realistic UNRATE index, constant except for
        # the real 2025-10 gap -- deliberately NOT a live FRED call
        # (per the increment's explicit fixture-based requirement).
        months = {month_before(date(2026, 10, 1), n) for n in range(-3, 18)}
        index = {m: 4.0 for m in months}
        del index[date(2025, 10, 1)]
        return index

    def test_september_to_october_2026_availability_lost_exactly_when_the_gap_enters_the_window(self):
        """2026-09's required window is {2026-09,08,07} current /
        {2025-09,08,07} prior-year -- the 2025-10 gap falls in
        NEITHER, so 2026-09 is fully available. 2026-10's required
        window is {2026-10,09,08} current / {2025-10,09,08} prior-year
        -- the gap IS now inside the prior-year window, so 2026-10
        alone becomes INSUFFICIENT_DATA. previous_period is EXACTLY
        2026-09 (never searched further back, never skipped to a
        "better" month)."""
        index = self._index()
        previous_period, current_period = month_before(date(2026, 10, 1), 1), date(2026, 10, 1)
        assert previous_period == date(2026, 9, 1)

        previous_evidence = compute_unemployment_result(index, previous_period, UNEMPLOYMENT_DEADBAND_PP)
        current_evidence = compute_unemployment_result(index, current_period, UNEMPLOYMENT_DEADBAND_PP)
        assert previous_evidence.state != "INSUFFICIENT_DATA"
        assert current_evidence.state == "INSUFFICIENT_DATA"

        result = compare_unemployment_section(previous_period, current_period, previous_evidence, current_evidence)
        assert result.availability_lost is True
        state_event = next(e for e in result.changes if e.field == "state")
        assert state_event.previous_period == date(2026, 9, 1)
        assert state_event.current_period == date(2026, 10, 1)

    def test_december_2026_to_january_2027_availability_restored_exactly_when_the_gap_exits_the_window(self):
        """The gap stays inside the prior-year window for THREE
        consecutive anchors (2026-10, -11, -12 all have `2025-10`
        as one of t-12/t-13/t-14 respectively) -- it only rolls fully
        out once the anchor reaches 2027-01 (prior-year window
        {2025-11,12, 2026-01}). previous_period is EXACTLY 2026-12,
        never searched further forward looking for "the next good
        month.\""""
        index = self._index()
        previous_period, current_period = date(2026, 12, 1), date(2027, 1, 1)

        previous_evidence = compute_unemployment_result(index, previous_period, UNEMPLOYMENT_DEADBAND_PP)
        current_evidence = compute_unemployment_result(index, current_period, UNEMPLOYMENT_DEADBAND_PP)
        assert previous_evidence.state == "INSUFFICIENT_DATA"
        assert current_evidence.state != "INSUFFICIENT_DATA"

        result = compare_unemployment_section(previous_period, current_period, previous_evidence, current_evidence)
        assert result.availability_restored is True


# ---------------------------------------------------------------------
# Numeric metric exact-inequality proofs (no epsilon, no rounding)
# ---------------------------------------------------------------------


class TestNumericMetricExactInequality:
    def _employment_with(self, current_3m: float | None) -> EmploymentResult:
        return EmploymentResult(
            current_3m_avg_jobs=current_3m, prior_3m_avg_jobs=100_000.0, momentum_delta_jobs=0.0,
            condition_deadband_jobs=CONDITION_DEADBAND_JOBS, momentum_deadband_jobs=MOMENTUM_DEADBAND_JOBS,
            condition="EXPANDING", momentum="STEADY", state="EXPANDING", observations=[],
        )

    def test_unrounded_change_hidden_by_display_rounding_still_reported(self):
        previous = self._employment_with(2.849999)
        current = self._employment_with(2.850001)
        result = compare_employment_section(date(2020, 1, 1), date(2020, 2, 1), previous, current)
        event = next(e for e in result.changes if e.field == "current_3m_avg_jobs")
        assert event.event_type == "METRIC_CHANGED"
        # both round to the same 2-decimal display value -- canonical unrounded values still differ:
        assert round(event.previous_value, 2) == round(event.current_value, 2) == 2.85
        assert event.previous_value != event.current_value
        assert event.delta == pytest.approx(0.000002)

    def test_exactly_equal_values_produce_no_event(self):
        previous = self._employment_with(100_000.0)
        current = self._employment_with(100_000.0)
        result = compare_employment_section(date(2020, 1, 1), date(2020, 2, 1), previous, current)
        assert result.changes == []

    def test_delta_is_current_minus_previous(self):
        previous = self._employment_with(80_000.0)
        current = self._employment_with(50_000.0)
        result = compare_employment_section(date(2020, 1, 1), date(2020, 2, 1), previous, current)
        event = next(e for e in result.changes if e.field == "current_3m_avg_jobs")
        assert event.delta == pytest.approx(-30_000.0)

    def test_both_none_produces_no_event(self):
        previous = self._employment_with(None)
        current = self._employment_with(None)
        result = compare_employment_section(date(2020, 1, 1), date(2020, 2, 1), previous, current)
        assert not any(e.field == "current_3m_avg_jobs" for e in result.changes)


# ---------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------


class TestDeterministicOrdering:
    def test_component_then_event_type_then_field_ordering(self):
        prev, curr = date(2020, 6, 1), date(2020, 7, 1)
        employment_changes = compare_employment_section(prev, curr, _employment(prev), _employment(curr))
        unemployment_changes = compare_unemployment_section(prev, curr, _unemployment(prev), _unemployment(curr))
        labor_changes = compare_labor_state(prev, curr, _labor_state(prev), _labor_state(curr))
        result = assemble_labor_what_changed_result(
            prev, curr, _labor_state(prev), _labor_state(curr), labor_changes, employment_changes, unemployment_changes
        )

        component_priority = {"LABOR": 0, "EMPLOYMENT": 1, "UNEMPLOYMENT": 2}
        priorities = [component_priority[e.component] for e in result.changes]
        assert priorities == sorted(priorities)

        employment_events = [e for e in result.changes if e.component == "EMPLOYMENT"]
        event_type_priority = {"STATE_CHANGED": 0, "AVAILABILITY_LOST": 1, "AVAILABILITY_RESTORED": 2, "METRIC_CHANGED": 3}
        employment_priorities = [event_type_priority[e.event_type] for e in employment_events]
        assert employment_priorities == sorted(employment_priorities)

        state_events = [e for e in employment_events if e.event_type == "STATE_CHANGED"]
        field_priority = {"state": 0, "condition": 1, "momentum": 2}
        assert [field_priority[e.field] for e in state_events] == sorted(field_priority[e.field] for e in state_events)

    def test_ordering_is_stable_across_repeated_calls(self):
        prev, curr = date(2020, 6, 1), date(2020, 7, 1)
        result_1 = compare_employment_section(prev, curr, _employment(prev), _employment(curr)).changes
        result_2 = compare_employment_section(prev, curr, _employment(prev), _employment(curr)).changes
        assert [e.field for e in result_1] == [e.field for e in result_2]


# ---------------------------------------------------------------------
# No-change result semantics
# ---------------------------------------------------------------------


class TestNoChangeResult:
    def test_fully_identical_comparison_yields_empty_changes_and_false_flags(self):
        prev, curr = date(2021, 4, 1), date(2021, 5, 1)
        employment_evidence = _employment(prev)  # same object both sides -- nothing at all differs
        unemployment_evidence = _unemployment(prev)

        employment_changes = compare_employment_section(prev, curr, employment_evidence, employment_evidence)
        unemployment_changes = compare_unemployment_section(prev, curr, unemployment_evidence, unemployment_evidence)
        labor_state = combine_labor_state(employment_evidence.state, unemployment_evidence.state)
        labor_changes = compare_labor_state(prev, curr, labor_state, labor_state)

        result = assemble_labor_what_changed_result(
            prev, curr, labor_state, labor_state, labor_changes, employment_changes, unemployment_changes
        )
        assert result.changes == []
        assert result.any_state_changed is False
        assert result.any_metric_changed is False
        assert result.any_availability_changed is False


# ---------------------------------------------------------------------
# Same-period revision support -- the comparator must work identically
# whether previous_period != current_period (month-over-month) or
# previous_period == current_period (a future release-processing
# before/after-revision comparison). No ordering assertion exists
# anywhere in the comparator.
# ---------------------------------------------------------------------


class TestSamePeriodRevisionSupport:
    def test_identical_period_before_and_after_a_revision_still_produces_correct_events(self):
        same_period = date(2009, 8, 1)
        before_revision = _employment(date(2009, 7, 1))  # stand-in "before" snapshot
        after_revision = _employment(date(2009, 8, 1))  # stand-in "after" snapshot
        result = compare_employment_section(same_period, same_period, before_revision, after_revision)
        # Same assertions as the ordinary month-over-month metrics-only case --
        # the comparator does not care that previous_period == current_period:
        assert result.metric_changed is True
        for event in result.changes:
            assert event.previous_period == event.current_period == same_period

    def test_labor_state_comparator_also_accepts_identical_periods(self):
        same_period = date(2009, 5, 1)
        events = compare_labor_state(same_period, same_period, "COOLING", "MIXED")
        assert len(events) == 1
        assert events[0].previous_period == events[0].current_period == same_period

    def test_no_function_anywhere_compares_previous_period_to_current_period(self):
        """A direct, explicit proof (not just an absence of a crash):
        passing previous_period > current_period (backwards in time)
        is accepted without complaint -- there is no ordering
        assertion to trip."""
        later, earlier = date(2020, 6, 1), date(2015, 1, 1)
        result = compare_employment_section(later, earlier, _employment(date(2020, 5, 1)), _employment(date(2020, 6, 1)))
        # Merely raising no exception on a "backwards in time" period pair
        # already proves there is no ordering assertion -- the labels
        # below confirm they are still echoed back exactly as given.
        assert all(e.previous_period == later and e.current_period == earlier for e in result.changes)


# ---------------------------------------------------------------------
# Period passthrough -- the comparator never computes or substitutes a
# period; it reports exactly whatever it is given.
# ---------------------------------------------------------------------


class TestPeriodPassthrough:
    def test_exact_periods_are_reported_verbatim(self):
        prev, curr = date(2009, 4, 1), date(2009, 5, 1)
        result = compare_employment_section(prev, curr, _employment(prev), _employment(curr))
        for event in result.changes:
            assert event.previous_period == prev
            assert event.current_period == curr

    def test_non_adjacent_periods_accepted_verbatim(self):
        """Period SELECTION is entirely the caller's responsibility --
        passing a non-adjacent pair (skipping months) is accepted
        without any adjustment."""
        prev, curr = date(2009, 4, 1), date(2009, 8, 1)
        result = compare_employment_section(prev, curr, _employment(prev), _employment(curr))
        for event in result.changes:
            assert event.previous_period == prev
            assert event.current_period == curr


# ---------------------------------------------------------------------
# comparison_available semantics
# ---------------------------------------------------------------------


class TestAssembleComparisonAvailable:
    def test_no_current_period_is_comparison_unavailable(self):
        insufficient_employment = compute_employment_result({}, date(2020, 1, 1), CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        insufficient_unemployment = compute_unemployment_result({}, date(2020, 1, 1), UNEMPLOYMENT_DEADBAND_PP)
        employment_changes = compare_employment_section(None, None, insufficient_employment, insufficient_employment)
        unemployment_changes = compare_unemployment_section(None, None, insufficient_unemployment, insufficient_unemployment)
        labor_changes = compare_labor_state(None, None, "INSUFFICIENT_DATA", "INSUFFICIENT_DATA")

        result = assemble_labor_what_changed_result(
            None, None, "INSUFFICIENT_DATA", "INSUFFICIENT_DATA", labor_changes, employment_changes, unemployment_changes
        )
        assert result.comparison_available is False
        assert result.previous_period is None
        assert result.current_period is None
        assert result.changes == []

    def test_current_period_present_is_comparison_available(self):
        prev, curr = date(2021, 4, 1), date(2021, 5, 1)
        employment_changes = compare_employment_section(prev, curr, _employment(prev), _employment(curr))
        unemployment_changes = compare_unemployment_section(prev, curr, _unemployment(prev), _unemployment(curr))
        labor_changes = compare_labor_state(prev, curr, _labor_state(prev), _labor_state(curr))
        result = assemble_labor_what_changed_result(
            prev, curr, _labor_state(prev), _labor_state(curr), labor_changes, employment_changes, unemployment_changes
        )
        assert result.comparison_available is True

    def test_current_labor_result_is_attached_when_provided(self):
        from app.domain.labor import compute_labor_monitor_result_at

        prev, curr = date(2021, 4, 1), date(2021, 5, 1)
        current_result = compute_labor_monitor_result_at(
            [], [], curr, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP
        )
        employment_changes = compare_employment_section(prev, curr, _employment(prev), _employment(curr))
        unemployment_changes = compare_unemployment_section(prev, curr, _unemployment(prev), _unemployment(curr))
        labor_changes = compare_labor_state(prev, curr, _labor_state(prev), _labor_state(curr))
        result = assemble_labor_what_changed_result(
            prev, curr, _labor_state(prev), _labor_state(curr), labor_changes, employment_changes, unemployment_changes,
            current_labor_result=current_result,
        )
        assert result.current_labor_result is current_result

    def test_current_labor_result_defaults_to_none(self):
        prev, curr = date(2021, 4, 1), date(2021, 5, 1)
        employment_changes = compare_employment_section(prev, curr, _employment(prev), _employment(curr))
        unemployment_changes = compare_unemployment_section(prev, curr, _unemployment(prev), _unemployment(curr))
        labor_changes = compare_labor_state(prev, curr, _labor_state(prev), _labor_state(curr))
        result = assemble_labor_what_changed_result(
            prev, curr, _labor_state(prev), _labor_state(curr), labor_changes, employment_changes, unemployment_changes
        )
        assert result.current_labor_result is None


# ---------------------------------------------------------------------
# Determinism / non-mutation
# ---------------------------------------------------------------------


class TestDeterminismAndNonMutation:
    def test_repeated_calls_produce_identical_results(self):
        prev, curr = date(2009, 4, 1), date(2009, 5, 1)
        previous_evidence, current_evidence = _employment(prev), _employment(curr)
        result_1 = compare_employment_section(prev, curr, previous_evidence, current_evidence)
        result_2 = compare_employment_section(prev, curr, previous_evidence, current_evidence)
        assert result_1 == result_2

    def test_input_evidence_objects_not_mutated(self):
        prev, curr = date(2009, 4, 1), date(2009, 5, 1)
        previous_evidence, current_evidence = _employment(prev), _employment(curr)
        previous_snapshot = previous_evidence.model_copy(deep=True)
        current_snapshot = current_evidence.model_copy(deep=True)
        compare_employment_section(prev, curr, previous_evidence, current_evidence)
        assert previous_evidence == previous_snapshot
        assert current_evidence == current_snapshot
