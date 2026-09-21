"""Golden-vector guards binding methodology VERSION to methodology
BEHAVIOR (Increment #31).

The pre-#31 audit found that `methodology_id` was a label, not a
binding: `inflation_v1.0` could have been changed to mean something
different without anything failing, which would silently invalidate
every historical `RecordedMonitorResult` carrying that identifier and
make deterministic replay a lie.

These vectors close that. Fixed canonical inputs produce fixed expected
outputs, asserted to many decimal places, for a named version. Changing
what `inflation_v1.0` or `labor_v1.0` computes now breaks CI, and the
only correct response is a NEW methodology version with NEW vectors --
never an edit to these numbers.

This is deliberately a test, not a runtime framework. No version
registry, no dispatch table, no plugin system: the guard belongs in CI,
where a silent behavioral change is caught, rather than in production
code that would have to carry every past methodology forever.

The expected values below were computed from the frozen specifications'
own formulas and cross-checked against the existing hand-computed
domain tests -- they are not snapshots of whatever the code happened to
return.
"""

from datetime import date

import pytest

from app.domain.inflation import compute_series_momentum_at
from app.domain.labor import compute_labor_monitor_result_at
from app.models.inflation import (
    METHODOLOGY_ID as INFLATION_METHODOLOGY_ID,
    NEUTRAL_BAND_PP,
    PRIMARY_SERIES_ID,
)
from app.models.labor import (
    CONDITION_DEADBAND_JOBS,
    METHODOLOGY_ID as LABOR_METHODOLOGY_ID,
    MOMENTUM_DEADBAND_JOBS,
    PAYEMS_SERIES_ID,
    UNEMPLOYMENT_DEADBAND_PP,
)
from app.models.series import Observation
from tests.identities import (
    CONFIRMATION_IDENTITY,
    EMPLOYMENT_IDENTITY,
    HEADLINE_CPI_IDENTITY,
    INFLATION_IDENTITIES,
    LABOR_IDENTITIES,
    PRIMARY_IDENTITY,
    TARGET_IDENTITY,
    UNEMPLOYMENT_IDENTITY,
)


def _month(anchor: date, months_back: int) -> date:
    year, month = anchor.year, anchor.month - months_back
    while month <= 0:
        year -= 1
        month += 12
    return date(year, month, 1)


class TestInflationV1GoldenVector:
    """`inflation_v1.0` -- frozen in docs/methodology/inflation-monitor-v1.0.md."""

    #: A Core PCE index rising exactly 0.2% per month for 13 months.
    #: Chosen because every horizon is then analytically known:
    #: 1.002^12 - 1 = 2.4266...% for every annualized horizon, so all
    #: three rates coincide and the state must be STABLE (every reading
    #: inside the 0.10pp neutral band around the 12-month rate).
    ANCHOR = date(2026, 6, 1)
    OBSERVATIONS = [
        Observation(date=_month(date(2026, 6, 1), 12 - n), value=100.0 * (1.002**n)) for n in range(13)
    ]

    def test_the_version_identifier_is_unchanged(self):
        assert INFLATION_METHODOLOGY_ID == "inflation_v1.0"

    def test_frozen_constants_are_unchanged(self):
        assert NEUTRAL_BAND_PP == 0.10

    def test_momentum_values_are_exactly_reproduced(self):
        result = compute_series_momentum_at(self.OBSERVATIONS, PRIMARY_IDENTITY, self.ANCHOR)

        # 1.002^12 - 1, expressed in percent.
        expected_rate = ((1.002**12) - 1) * 100
        assert result.r_1m_annualized == pytest.approx(expected_rate, rel=1e-12)
        assert result.r_3m_annualized == pytest.approx(expected_rate, rel=1e-12)
        assert result.r_6m_annualized == pytest.approx(expected_rate, rel=1e-12)
        assert result.r_12m == pytest.approx(expected_rate, rel=1e-12)
        # (1.002 ** 12 - 1) * 100, to full double precision.
        assert result.r_12m == pytest.approx(2.426576794540325, rel=1e-12)

    def test_the_classified_state_is_exactly_reproduced(self):
        result = compute_series_momentum_at(self.OBSERVATIONS, PRIMARY_IDENTITY, self.ANCHOR)

        assert result.state == "STABLE"
        assert result.calculation_period == self.ANCHOR
        assert result.lower_boundary == pytest.approx(result.r_12m - NEUTRAL_BAND_PP, rel=1e-12)
        assert result.upper_boundary == pytest.approx(result.r_12m + NEUTRAL_BAND_PP, rel=1e-12)

    def test_a_heating_vector_is_exactly_reproduced(self):
        """Short-horizon acceleration above the band must classify
        HEATING -- the boundary rule itself, pinned."""
        observations = [Observation(date=_month(self.ANCHOR, 12 - n), value=100.0 * (1.002**n)) for n in range(13)]
        # Lift only the latest reading, so 3M/6M exceed the 12M band.
        observations[-1] = Observation(date=self.ANCHOR, value=observations[-1].value * 1.01)

        result = compute_series_momentum_at(observations, PRIMARY_IDENTITY, self.ANCHOR)
        assert result.state == "HEATING"

    def test_insufficient_history_is_exactly_reproduced(self):
        result = compute_series_momentum_at(self.OBSERVATIONS[:3], PRIMARY_IDENTITY, self.ANCHOR)
        assert result.state == "INSUFFICIENT_DATA"


class TestLaborV1GoldenVector:
    """`labor_v1.0` -- frozen in research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md."""

    ANCHOR = date(2026, 6, 1)

    #: PAYEMS rising exactly 200k/month (well above the 50k deadband, so
    #: condition is EXPANDING) with identical 3-month averages before and
    #: after (so momentum is STEADY).
    PAYEMS = [Observation(date=_month(date(2026, 6, 1), 19 - n), value=150_000.0 + 200.0 * n) for n in range(20)]
    #: UNRATE flat, so the trailing-year comparison is exactly zero and
    #: the trend is STABLE inside the 0.2pp deadband.
    UNRATE = [Observation(date=_month(date(2026, 6, 1), 19 - n), value=4.0) for n in range(20)]

    def test_the_version_identifier_is_unchanged(self):
        assert LABOR_METHODOLOGY_ID == "labor_v1.0"

    def test_frozen_deadbands_are_unchanged(self):
        assert CONDITION_DEADBAND_JOBS == 50_000.0
        assert MOMENTUM_DEADBAND_JOBS == 50_000.0
        assert UNEMPLOYMENT_DEADBAND_PP == 0.2

    def test_the_combined_state_and_components_are_exactly_reproduced(self):
        result = compute_labor_monitor_result_at(
            self.PAYEMS,
            self.UNRATE,
            self.ANCHOR,
            CONDITION_DEADBAND_JOBS,
            MOMENTUM_DEADBAND_JOBS,
            UNEMPLOYMENT_DEADBAND_PP,
            identities=LABOR_IDENTITIES,
        )

        assert result.methodology_id == "labor_v1.0"
        assert result.evaluation_period == self.ANCHOR
        # PAYEMS is in thousands: +200 per month => 200k jobs/month.
        assert result.employment.current_3m_avg_jobs == pytest.approx(200_000.0, rel=1e-12)
        assert result.employment.prior_3m_avg_jobs == pytest.approx(200_000.0, rel=1e-12)
        assert result.employment.momentum_delta_jobs == pytest.approx(0.0, abs=1e-9)
        assert result.employment.condition == "EXPANDING"
        assert result.employment.momentum == "STEADY"
        assert result.unemployment.current_3m_avg == pytest.approx(4.0, rel=1e-12)
        assert result.unemployment.prior_year_3m_avg == pytest.approx(4.0, rel=1e-12)
        assert result.unemployment.delta_pp == pytest.approx(0.0, abs=1e-12)
        assert result.unemployment.state == "STABLE"
        # Frozen agreement table (LABOR_V1_FROZEN_METHODOLOGY.md §7):
        # EXPANDING x STABLE resolves to MIXED, not STRENGTHENING --
        # only four combinations produce a clean non-MIXED state, and
        # this is deliberately not one of them.
        assert result.state == "MIXED"

    def test_the_strengthening_combination_from_the_frozen_table_is_reproduced(self):
        """EXPANDING x IMPROVING is one of only four combinations the
        frozen agreement table resolves to a clean state."""
        improving_unrate = [
            Observation(date=_month(self.ANCHOR, 19 - n), value=5.0 - 0.05 * n) for n in range(20)
        ]

        result = compute_labor_monitor_result_at(
            self.PAYEMS,
            improving_unrate,
            self.ANCHOR,
            CONDITION_DEADBAND_JOBS,
            MOMENTUM_DEADBAND_JOBS,
            UNEMPLOYMENT_DEADBAND_PP,
            identities=LABOR_IDENTITIES,
        )

        assert result.employment.condition == "EXPANDING"
        assert result.unemployment.state == "IMPROVING"
        assert result.state == "STRENGTHENING"

    def test_a_contracting_vector_is_exactly_reproduced(self):
        payems = [Observation(date=_month(self.ANCHOR, 19 - n), value=150_000.0 - 200.0 * n) for n in range(20)]

        result = compute_labor_monitor_result_at(
            payems,
            self.UNRATE,
            self.ANCHOR,
            CONDITION_DEADBAND_JOBS,
            MOMENTUM_DEADBAND_JOBS,
            UNEMPLOYMENT_DEADBAND_PP,
            identities=LABOR_IDENTITIES,
        )

        assert result.employment.current_3m_avg_jobs == pytest.approx(-200_000.0, rel=1e-12)
        assert result.employment.condition == "CONTRACTING"

    def test_insufficient_history_is_exactly_reproduced(self):
        result = compute_labor_monitor_result_at(
            self.PAYEMS[-3:],
            self.UNRATE[-3:],
            self.ANCHOR,
            CONDITION_DEADBAND_JOBS,
            MOMENTUM_DEADBAND_JOBS,
            UNEMPLOYMENT_DEADBAND_PP,
            identities=LABOR_IDENTITIES,
        )
        assert result.state == "INSUFFICIENT_DATA"


def test_replay_only_covers_methodologies_that_have_golden_vectors():
    """If a monitor becomes replayable, its methodology must be pinned
    here first -- otherwise replay could silently validate against
    drifting behavior."""
    from app.services.replay import _MONITOR_METHODOLOGY

    assert set(_MONITOR_METHODOLOGY.values()) == {INFLATION_METHODOLOGY_ID, LABOR_METHODOLOGY_ID}
