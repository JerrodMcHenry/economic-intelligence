"""Contract tests for the Pydantic models the tested domain functions
actually consume/produce: Observation, TransformedObservation
(app.models.series) and ComparisonObservation (app.models.analysis).

Deliberately narrow -- not full API testing (see Increment 010's scope).
Documents CURRENT contract behavior; does not change it. In particular,
none of these three models set `extra="forbid"` today (unlike the
AI-tool-facing models elsewhere in the app) -- the tests below assert
that as the current, documented behavior, not as something to fix here.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from app.models.analysis import ComparisonObservation
from app.models.series import Observation, TransformedObservation


class TestObservationContract:
    def test_date_and_value_are_required(self):
        with pytest.raises(ValidationError):
            Observation(value=1.0)  # missing date
        with pytest.raises(ValidationError):
            Observation(date=date(2024, 1, 1))  # missing value -- see note below

    def test_value_required_but_none_is_a_valid_value(self):
        """`value: float | None` with no default means the key must be
        present, but None is an accepted value for it -- required-but-
        nullable, not optional-to-omit. Both properties are asserted
        here since they're easy to conflate."""
        obs = Observation(date=date(2024, 1, 1), value=None)
        assert obs.value is None

    def test_extra_field_currently_silently_ignored(self):
        """Current behavior (no `extra="forbid"` on this model): an
        unexpected field does not raise. Documented, not endorsed."""
        obs = Observation(date=date(2024, 1, 1), value=1.0, unexpected_field="x")
        assert not hasattr(obs, "unexpected_field")


class TestTransformedObservationContract:
    def test_all_three_fields_required(self):
        with pytest.raises(ValidationError):
            TransformedObservation(original_value=1.0, value=1.0)  # missing date

    def test_original_value_and_value_independently_nullable(self):
        point = TransformedObservation(date=date(2024, 1, 1), original_value=None, value=None)
        assert point.original_value is None
        assert point.value is None

    def test_extra_field_currently_silently_ignored(self):
        point = TransformedObservation(date=date(2024, 1, 1), original_value=1.0, value=1.0, debug=True)
        assert not hasattr(point, "debug")


class TestComparisonObservationContract:
    def test_date_value_a_value_b_required(self):
        with pytest.raises(ValidationError):
            ComparisonObservation(value_a=1.0, value_b=2.0)  # missing date

    def test_value_a_and_value_b_required_but_nullable(self):
        point = ComparisonObservation(date=date(2024, 1, 1), value_a=None, value_b=None)
        assert point.value_a is None and point.value_b is None

    def test_spread_is_optional_unlike_value_a_and_value_b(self):
        """Asymmetry worth pinning down explicitly: spread has a default
        (None) and may be omitted entirely; value_a/value_b must be
        supplied (even if the supplied value is None itself)."""
        point = ComparisonObservation(date=date(2024, 1, 1), value_a=1.0, value_b=2.0)
        assert point.spread is None
        with pytest.raises(ValidationError):
            ComparisonObservation(date=date(2024, 1, 1), value_b=2.0)  # value_a omitted -> error

    def test_extra_field_currently_silently_ignored(self):
        point = ComparisonObservation(date=date(2024, 1, 1), value_a=1.0, value_b=2.0, url="http://example.com")
        assert not hasattr(point, "url")
