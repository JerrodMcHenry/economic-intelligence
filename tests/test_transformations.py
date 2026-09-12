"""Golden tests for app.domain.transformations -- pure, deterministic,
zero-I/O functions. No network, no database, no OpenAI, no FRED: these
tests run completely offline.

Expected values are independently hand-computed from the documented
algorithm in app/domain/transformations.py's own docstrings, never
derived by calling the implementation and asserting on whatever it
returns. These tests document CURRENT canonical behavior -- if a result
here looks surprising, that is a finding to report, not a reason to
change the fixture or the production code.
"""

from datetime import date

from app.domain.transformations import absolute_change, moving_average, percent_change
from app.models.series import Observation, TransformedObservation

# Shared fixture for absolute_change: covers positive change, negative
# change, unchanged value, first-observation, null current value, null
# previous value (the observation right after a null), and recovery
# after a null.
ABS_CHANGE_OBSERVATIONS = [
    Observation(date=date(2024, 1, 1), value=100.0),
    Observation(date=date(2024, 2, 1), value=110.0),  # positive: +10
    Observation(date=date(2024, 3, 1), value=95.0),  # negative: -15
    Observation(date=date(2024, 4, 1), value=95.0),  # unchanged: 0
    Observation(date=date(2024, 5, 1), value=None),  # null current
    Observation(date=date(2024, 6, 1), value=120.0),  # null previous (prior was None)
    Observation(date=date(2024, 7, 1), value=130.0),  # recovery: +10
]
ABS_CHANGE_EXPECTED = [None, 10.0, -15.0, 0.0, None, None, 10.0]


def _assert_matches(actual: list[TransformedObservation], expected_values, source: list[Observation]) -> None:
    assert len(actual) == len(expected_values) == len(source)
    for i, (point, expected_value, original) in enumerate(zip(actual, expected_values, source)):
        assert point.date == original.date, f"index {i}: date not preserved"
        assert point.original_value == original.value, f"index {i}: original_value mismatch"
        if expected_value is None:
            assert point.value is None, f"index {i}: expected None, got {point.value}"
        else:
            assert point.value == expected_value, f"index {i}: expected {expected_value}, got {point.value}"


class TestAbsoluteChange:
    def test_golden_sequence(self):
        """One fixture covering: positive change, negative change,
        unchanged value, first-observation null, null-current-value,
        null-previous-value, and date/order preservation in one pass."""
        result = absolute_change(ABS_CHANGE_OBSERVATIONS)
        _assert_matches(result, ABS_CHANGE_EXPECTED, ABS_CHANGE_OBSERVATIONS)

    def test_first_observation_is_always_none(self):
        result = absolute_change([Observation(date=date(2024, 1, 1), value=42.0)])
        assert len(result) == 1
        assert result[0].value is None
        assert result[0].original_value == 42.0

    def test_date_order_preserved_exactly(self):
        result = absolute_change(ABS_CHANGE_OBSERVATIONS)
        assert [r.date for r in result] == [o.date for o in ABS_CHANGE_OBSERVATIONS]

    def test_input_not_mutated(self):
        snapshot = [Observation(date=o.date, value=o.value) for o in ABS_CHANGE_OBSERVATIONS]
        absolute_change(ABS_CHANGE_OBSERVATIONS)
        assert ABS_CHANGE_OBSERVATIONS == snapshot

    def test_repeated_execution_identical(self):
        first = absolute_change(ABS_CHANGE_OBSERVATIONS)
        second = absolute_change(ABS_CHANGE_OBSERVATIONS)
        assert first == second


# Separate fixture for percent_change: shares the positive/negative/
# unchanged/first-obs/null-current/null-previous shape above, plus an
# explicit previous-value-is-zero case (not exercised by absolute_change,
# which has no division).
PCT_CHANGE_OBSERVATIONS = [
    Observation(date=date(2024, 1, 1), value=50.0),
    Observation(date=date(2024, 2, 1), value=75.0),  # (75-50)/50*100 = 50.0
    Observation(date=date(2024, 3, 1), value=60.0),  # (60-75)/75*100 = -20.0
    Observation(date=date(2024, 4, 1), value=60.0),  # unchanged: 0.0
    Observation(date=date(2024, 5, 1), value=0.0),  # (0-60)/60*100 = -100.0
    Observation(date=date(2024, 6, 1), value=30.0),  # previous == 0 -> None
    Observation(date=date(2024, 7, 1), value=None),  # null current -> None
    Observation(date=date(2024, 8, 1), value=40.0),  # null previous -> None
]
PCT_CHANGE_EXPECTED = [None, 50.0, -20.0, 0.0, -100.0, None, None, None]


class TestPercentChange:
    def test_golden_sequence(self):
        """Covers: positive change, negative change, unchanged value,
        first-observation, previous value == 0 (never divides by zero),
        null current value, and null previous value."""
        result = percent_change(PCT_CHANGE_OBSERVATIONS)
        _assert_matches(result, PCT_CHANGE_EXPECTED, PCT_CHANGE_OBSERVATIONS)

    def test_previous_value_zero_never_divides(self):
        obs = [Observation(date=date(2024, 1, 1), value=0.0), Observation(date=date(2024, 2, 1), value=10.0)]
        result = percent_change(obs)
        assert result[1].value is None  # never inf, never a substituted 0

    def test_date_order_preserved_exactly(self):
        result = percent_change(PCT_CHANGE_OBSERVATIONS)
        assert [r.date for r in result] == [o.date for o in PCT_CHANGE_OBSERVATIONS]

    def test_input_not_mutated(self):
        snapshot = [Observation(date=o.date, value=o.value) for o in PCT_CHANGE_OBSERVATIONS]
        percent_change(PCT_CHANGE_OBSERVATIONS)
        assert PCT_CHANGE_OBSERVATIONS == snapshot

    def test_repeated_execution_identical(self):
        first = percent_change(PCT_CHANGE_OBSERVATIONS)
        second = percent_change(PCT_CHANGE_OBSERVATIONS)
        assert first == second


# window=2 fixture: covers a null appearing inside the window (both as
# the newest and as a prior point), and recovery afterward.
MA2_OBSERVATIONS = [
    Observation(date=date(2024, 1, 1), value=10.0),  # insufficient history (need 2)
    Observation(date=date(2024, 2, 1), value=20.0),  # avg(10,20) = 15.0
    Observation(date=date(2024, 3, 1), value=30.0),  # avg(20,30) = 25.0
    Observation(date=date(2024, 4, 1), value=None),  # window has a null -> None
    Observation(date=date(2024, 5, 1), value=50.0),  # window=[None,50] -> None
    Observation(date=date(2024, 6, 1), value=70.0),  # avg(50,70) = 60.0
]
MA2_EXPECTED = [None, 15.0, 25.0, None, None, 60.0]

# window=3 fixture, no nulls: isolates "insufficient initial history"
# (two leading Nones, since 3 points are required) from null-handling.
MA3_OBSERVATIONS = [
    Observation(date=date(2024, 1, 1), value=10.0),
    Observation(date=date(2024, 2, 1), value=20.0),
    Observation(date=date(2024, 3, 1), value=30.0),  # avg(10,20,30) = 20.0
    Observation(date=date(2024, 4, 1), value=40.0),  # avg(20,30,40) = 30.0
    Observation(date=date(2024, 5, 1), value=50.0),  # avg(30,40,50) = 40.0
]
MA3_EXPECTED = [None, None, 20.0, 30.0, 40.0]


class TestMovingAverage:
    def test_window_2_golden_sequence(self):
        """Covers: valid window=2, a null inside the averaging window
        (both as the newest point and as a prior point), and recovery."""
        result = moving_average(MA2_OBSERVATIONS, window=2)
        _assert_matches(result, MA2_EXPECTED, MA2_OBSERVATIONS)

    def test_window_3_insufficient_initial_history(self):
        """Covers: a larger window, and the documented rule that a
        result is null until at least `window` points have been seen."""
        result = moving_average(MA3_OBSERVATIONS, window=3)
        _assert_matches(result, MA3_EXPECTED, MA3_OBSERVATIONS)

    def test_chronological_order_preserved(self):
        result = moving_average(MA3_OBSERVATIONS, window=3)
        assert [r.date for r in result] == [o.date for o in MA3_OBSERVATIONS]

    def test_input_not_mutated(self):
        snapshot = [Observation(date=o.date, value=o.value) for o in MA2_OBSERVATIONS]
        moving_average(MA2_OBSERVATIONS, window=2)
        assert MA2_OBSERVATIONS == snapshot

    def test_repeated_execution_identical(self):
        first = moving_average(MA2_OBSERVATIONS, window=2)
        second = moving_average(MA2_OBSERVATIONS, window=2)
        assert first == second
