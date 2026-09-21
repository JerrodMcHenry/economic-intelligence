"""Revision knowledge states (Increment #43).

MacroChipz may only claim to know an "original value" when it actually
recorded one BEFORE the change. These tests hold that line, because the
alternative -- presenting a migration baseline as economic history --
is the single most damaging thing this feature could do.

MEASURED BEFORE IMPLEMENTATION, and the reason the conservative default
exists: the local database holds 1,072 versioned observation rows, and
every one is `change_type=BACKFILL, origin=BACKFILL, is_backfilled=true`.
Zero observations have a second version. Zero rows are superseded.
**There is not one genuine captured revision.**
"""

from datetime import date

import pytest

from app.models.intelligence import ObservationChangePayload


def payload(**overrides) -> ObservationChangePayload:
    base = dict(
        change_type="NEW",
        previous_value=None,
        new_value=4.1,
        delta=None,
        observation_date=date(2026, 8, 1),
        provider="FRED",
        provider_series_id="UNRATE",
        series_title="Unemployment Rate",
        units="Percent",
    )
    base.update(overrides)
    return ObservationChangePayload(**base)


class TestConservativeDefault:
    def test_an_object_built_before_43_never_claims_a_known_original(self):
        """The field is additive with a default, so every pre-#43
        object parses -- and defaults to the state that claims least."""
        assert payload().revision_knowledge == "BACKFILLED_BASELINE"
        assert payload().original_value_known is False

    def test_a_first_observation_is_not_a_revision(self):
        observation = payload(change_type="NEW", revision_knowledge="FIRST_OBSERVATION")
        assert observation.change_type == "NEW"
        assert observation.original_value_known is False
        assert observation.previous_value is None


class TestTheThreeStatesAreDistinct:
    """Collapsing these would let one sentence stand in for three very
    different truths."""

    def test_prospective_revision_is_the_only_provable_original(self):
        revision = payload(
            change_type="REVISED",
            revision_knowledge="PROSPECTIVE_REVISION",
            original_value_known=True,
            previous_value=3.1,
            new_value=3.0,
            delta=-0.1,
        )
        assert revision.original_value_known is True
        assert revision.previous_value == 3.1

    def test_a_backfilled_baseline_is_not_a_provable_original(self):
        # The value exists, but it is what MacroChipz imported -- not
        # what the provider first published.
        baseline = payload(
            change_type="REVISED",
            revision_knowledge="BACKFILLED_BASELINE",
            original_value_known=False,
            previous_value=3.1,
        )
        assert baseline.previous_value == 3.1
        assert baseline.original_value_known is False, (
            "a value imported at migration time must never be presented as an original reading"
        )

    def test_the_three_states_are_the_whole_vocabulary(self):
        for state in ("FIRST_OBSERVATION", "PROSPECTIVE_REVISION", "BACKFILLED_BASELINE"):
            assert payload(revision_knowledge=state).revision_knowledge == state

    def test_an_unknown_state_is_rejected_rather_than_coerced(self):
        with pytest.raises(Exception):
            payload(revision_knowledge="PROBABLY_A_REVISION")


class TestNothingIsInvented:
    def test_no_publication_timestamp_exists_on_this_payload(self):
        # MacroChipz does not know when a provider published a value.
        # `published_at` lives on the envelope and is null; nothing here
        # may stand in for it.
        assert "published_at" not in payload().model_dump()
        assert "publication" not in str(payload().model_dump()).lower()

    def test_delta_is_absent_rather_than_zero_when_uncomputable(self):
        assert payload(change_type="NEW", previous_value=None, delta=None).delta is None

    def test_no_significance_or_magnitude_field_exists(self):
        fields = set(payload().model_dump())
        for forbidden in ("significance", "importance", "score", "magnitude", "severity", "rank"):
            assert forbidden not in fields
