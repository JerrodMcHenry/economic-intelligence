"""Unit tests for Increment #25G's pure, deterministic categorization
module (`app.domain.since_last_visit`) -- no database, no FRED, no
FastAPI. Frozen contract: docs/product/since-last-visit-v1.md (#25F).

These are the PRIMARY, exhaustive tests of the algorithm's own
correctness -- hand-built input dataclasses let every branch (first
calculation, unchanged confirmation, changed-then-back, multi-period
current-result selection, deduplication, coverage) be proven exactly,
independent of any real economic fixture. Integration tests
(tests/integration/test_since_last_visit_service.py) prove the same
algorithm wired to a real database and real release-processing
fixtures, but do not re-derive branch coverage already proven here.
"""

from datetime import date, datetime, timezone

from app.domain.since_last_visit import (
    AnalysisChangeInput,
    ObservationChangeInput,
    RecordedResultInput,
    compute_coverage,
    resolve_window,
    select_recalculations,
    select_source_updates,
    select_structural_changes,
)

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 5, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 10, tzinfo=timezone.utc)
THROUGH = datetime(2026, 9, 15, tzinfo=timezone.utc)


# ---------------------------------------------------------------------
# resolve_window -- contract §7/§10-13/§50-51/§54
# ---------------------------------------------------------------------


class TestResolveWindow:
    def test_no_checkpoint_is_first_visit_but_still_bounded_to_the_default_window(self):
        """Contract §7/§49: even a genuine first visit is bounded to
        the default lookback window -- never an unbounded historical
        dump. `effective_after` (the real query boundary) is always a
        real value; `first_visit=True` is reported separately so the
        service can render `None` in the RESPONSE's own `after` field."""
        from datetime import timedelta

        effective_after, first_visit, clamped = resolve_window(None, THROUGH)
        assert effective_after == THROUGH - timedelta(days=90)
        assert first_visit is True
        assert clamped is False

    def test_future_checkpoint_is_treated_as_first_visit(self):
        from datetime import timedelta

        future = THROUGH.replace(year=2027)
        effective_after, first_visit, clamped = resolve_window(future, THROUGH)
        assert effective_after == THROUGH - timedelta(days=90)
        assert first_visit is True
        assert clamped is False

    def test_checkpoint_equal_to_through_is_treated_as_first_visit(self):
        effective_after, first_visit, clamped = resolve_window(THROUGH, THROUGH)
        assert first_visit is True

    def test_recent_valid_checkpoint_is_used_verbatim(self):
        recent = THROUGH.replace(day=THROUGH.day - 1)
        after, first_visit, clamped = resolve_window(recent, THROUGH)
        assert after == recent
        assert first_visit is False
        assert clamped is False

    def test_checkpoint_older_than_90_days_is_clamped(self):
        from datetime import timedelta

        old = THROUGH - timedelta(days=200)
        after, first_visit, clamped = resolve_window(old, THROUGH)
        assert after == THROUGH - timedelta(days=90)
        assert first_visit is False
        assert clamped is True

    def test_checkpoint_exactly_at_90_day_floor_is_not_clamped(self):
        from datetime import timedelta

        floor = THROUGH - timedelta(days=90)
        after, first_visit, clamped = resolve_window(floor, THROUGH)
        assert after == floor
        assert clamped is False

    def test_checkpoint_one_second_older_than_floor_is_clamped(self):
        from datetime import timedelta

        just_old = THROUGH - timedelta(days=90, seconds=1)
        after, first_visit, clamped = resolve_window(just_old, THROUGH)
        assert after == THROUGH - timedelta(days=90)
        assert clamped is True


# ---------------------------------------------------------------------
# select_structural_changes -- contract §20/§68-70
# ---------------------------------------------------------------------


class TestSelectStructuralChanges:
    def test_inflation_primary_momentum_state_change_is_tier_a(self):
        changes = [
            AnalysisChangeInput(
                release_check_run_id=1, component="PRIMARY_MOMENTUM", event_type="STATE_CHANGED", field="state",
                previous_value="COOLING", current_value="STABLE", evaluation_period=date(2026, 8, 1), methodology_id="inflation_v1.0",
            )
        ]
        items = select_structural_changes(changes, {1: T0})
        assert len(items) == 1
        assert items[0].monitor == "inflation"
        assert items[0].previous_value == "COOLING"
        assert items[0].current_value == "STABLE"

    def test_labor_component_any_field_is_tier_a(self):
        changes = [
            AnalysisChangeInput(
                release_check_run_id=1, component="LABOR", event_type="STATE_CHANGED", field="state",
                previous_value="STABLE", current_value="COOLING", evaluation_period=date(2026, 8, 1), methodology_id="labor_v1.0",
            )
        ]
        items = select_structural_changes(changes, {1: T0})
        assert len(items) == 1
        assert items[0].monitor == "labor"

    def test_confirmation_changed_is_never_tier_a(self):
        """Confirmation is deliberately excluded -- Since Last Visit
        V1's own narrower-than-Overview scope (contract §18/§20)."""
        changes = [
            AnalysisChangeInput(
                release_check_run_id=1, component="CONFIRMATION", event_type="CONFIRMATION_CHANGED", field="relationship",
                previous_value="CONFIRMS", current_value="DIVERGES", evaluation_period=date(2026, 8, 1), methodology_id="inflation_v1.0",
            )
        ]
        assert select_structural_changes(changes, {1: T0}) == []

    def test_headline_pce_state_change_is_never_tier_a(self):
        changes = [
            AnalysisChangeInput(
                release_check_run_id=1, component="HEADLINE_PCE", event_type="STATE_CHANGED", field="state",
                previous_value="COOLING", current_value="STABLE", evaluation_period=date(2026, 8, 1), methodology_id="inflation_v1.0",
            )
        ]
        assert select_structural_changes(changes, {1: T0}) == []

    def test_metric_changed_is_never_tier_a_even_on_primary_momentum(self):
        changes = [
            AnalysisChangeInput(
                release_check_run_id=1, component="PRIMARY_MOMENTUM", event_type="METRIC_CHANGED", field="r_3m_annualized",
                previous_value="2.1", current_value="2.3", evaluation_period=date(2026, 8, 1), methodology_id="inflation_v1.0",
            )
        ]
        assert select_structural_changes(changes, {1: T0}) == []

    def test_availability_lost_and_restored_are_tier_a(self):
        changes = [
            AnalysisChangeInput(
                release_check_run_id=1, component="PRIMARY_MOMENTUM", event_type="AVAILABILITY_LOST", field="state",
                previous_value="COOLING", current_value=None, evaluation_period=date(2026, 8, 1), methodology_id="inflation_v1.0",
            ),
            AnalysisChangeInput(
                release_check_run_id=2, component="LABOR", event_type="AVAILABILITY_RESTORED", field="state",
                previous_value=None, current_value="STABLE", evaluation_period=date(2026, 9, 1), methodology_id="labor_v1.0",
            ),
        ]
        items = select_structural_changes(changes, {1: T0, 2: T1})
        assert {i.event_type for i in items} == {"AVAILABILITY_LOST", "AVAILABILITY_RESTORED"}

    def test_changed_then_changed_back_preserves_both_transitions(self):
        """Contract §24-25: two genuine transitions within the window
        must both render, never collapsed to window-start-vs-end."""
        changes = [
            AnalysisChangeInput(
                release_check_run_id=1, component="LABOR", event_type="STATE_CHANGED", field="state",
                previous_value="STABLE", current_value="COOLING", evaluation_period=date(2026, 8, 1), methodology_id="labor_v1.0",
            ),
            AnalysisChangeInput(
                release_check_run_id=2, component="LABOR", event_type="STATE_CHANGED", field="state",
                previous_value="COOLING", current_value="STABLE", evaluation_period=date(2026, 9, 1), methodology_id="labor_v1.0",
            ),
        ]
        items = select_structural_changes(changes, {1: T0, 2: T1})
        assert len(items) == 2
        assert (items[0].previous_value, items[0].current_value) == ("STABLE", "COOLING")
        assert (items[1].previous_value, items[1].current_value) == ("COOLING", "STABLE")

    def test_multiple_evaluation_periods_in_one_run_select_only_the_max_period(self):
        """Contract §68-70: the exact scenario #25E's own test suite
        discovered empirically -- one run touching several propagated
        periods for the same monitor must surface only one item, the
        run's own latest-touched period."""
        changes = [
            AnalysisChangeInput(
                release_check_run_id=1, component="LABOR", event_type="STATE_CHANGED", field="state",
                previous_value="STABLE", current_value="COOLING", evaluation_period=date(2026, 5, 1), methodology_id="labor_v1.0",
            ),
            AnalysisChangeInput(
                release_check_run_id=1, component="LABOR", event_type="STATE_CHANGED", field="state",
                previous_value="STABLE", current_value="MIXED", evaluation_period=date(2026, 8, 1), methodology_id="labor_v1.0",
            ),
        ]
        items = select_structural_changes(changes, {1: T0})
        assert len(items) == 1
        assert items[0].evaluation_period == date(2026, 8, 1)
        assert items[0].current_value == "MIXED"

    def test_chronological_ordering_by_calculated_at(self):
        changes = [
            AnalysisChangeInput(
                release_check_run_id=2, component="LABOR", event_type="STATE_CHANGED", field="state",
                previous_value="COOLING", current_value="STABLE", evaluation_period=date(2026, 9, 1), methodology_id="labor_v1.0",
            ),
            AnalysisChangeInput(
                release_check_run_id=1, component="PRIMARY_MOMENTUM", event_type="STATE_CHANGED", field="state",
                previous_value="COOLING", current_value="STABLE", evaluation_period=date(2026, 8, 1), methodology_id="inflation_v1.0",
            ),
        ]
        items = select_structural_changes(changes, {1: T0, 2: T1})
        assert [i.release_check_run_id for i in items] == [1, 2]


# ---------------------------------------------------------------------
# select_recalculations -- contract §21-23/§68-70 (the central new capability)
# ---------------------------------------------------------------------


class TestSelectRecalculations:
    def test_first_ever_recorded_result_is_first_calculation_never_unchanged(self):
        results = [
            RecordedResultInput(id=100, release_check_run_id=1, monitor="inflation", evaluation_period=date(2026, 8, 1), state="COOLING", methodology_id="inflation_v1.0"),
        ]
        items = select_recalculations(results, {1: T0}, frozenset(), {"inflation": 100})
        assert len(items) == 1
        assert items[0].kind == "FIRST_CALCULATION"
        assert items[0].count == 1

    def test_a_later_result_with_an_earlier_sibling_is_unchanged_confirmation(self):
        results = [
            RecordedResultInput(id=105, release_check_run_id=2, monitor="inflation", evaluation_period=date(2026, 9, 1), state="COOLING", methodology_id="inflation_v1.0"),
        ]
        items = select_recalculations(results, {2: T1}, frozenset(), {"inflation": 100})
        assert len(items) == 1
        assert items[0].kind == "UNCHANGED_CONFIRMATION"
        assert items[0].count == 1

    def test_a_recorded_result_that_also_has_a_tier_a_row_is_suppressed_entirely(self):
        """Contract §21 branch 1: no double-reporting -- a genuine
        change is Tier A only, never ALSO an unchanged confirmation."""
        results = [
            RecordedResultInput(id=105, release_check_run_id=2, monitor="inflation", evaluation_period=date(2026, 9, 1), state="STABLE", methodology_id="inflation_v1.0"),
        ]
        changed_pairs = frozenset({(2, "inflation")})
        items = select_recalculations(results, {2: T1}, changed_pairs, {"inflation": 100})
        assert items == []

    def test_repeated_unchanged_confirmations_aggregate_to_one_item_with_a_count(self):
        results = [
            RecordedResultInput(id=101, release_check_run_id=2, monitor="inflation", evaluation_period=date(2026, 8, 1), state="COOLING", methodology_id="inflation_v1.0"),
            RecordedResultInput(id=102, release_check_run_id=3, monitor="inflation", evaluation_period=date(2026, 9, 1), state="COOLING", methodology_id="inflation_v1.0"),
            RecordedResultInput(id=103, release_check_run_id=4, monitor="inflation", evaluation_period=date(2026, 9, 1), state="COOLING", methodology_id="inflation_v1.0"),
        ]
        items = select_recalculations(results, {2: T0, 3: T1, 4: T2}, frozenset(), {"inflation": 100})
        assert len(items) == 1
        assert items[0].kind == "UNCHANGED_CONFIRMATION"
        assert items[0].count == 3
        assert items[0].calculated_at == T2  # the most recent of the three

    def test_first_calculation_and_subsequent_unchanged_confirmations_both_appear(self):
        """A brand-new deployment window can legitimately contain both
        the system-wide first calculation AND later, genuine
        re-confirmations -- both are real, distinct facts."""
        results = [
            RecordedResultInput(id=100, release_check_run_id=1, monitor="inflation", evaluation_period=date(2026, 7, 1), state="COOLING", methodology_id="inflation_v1.0"),
            RecordedResultInput(id=101, release_check_run_id=2, monitor="inflation", evaluation_period=date(2026, 8, 1), state="COOLING", methodology_id="inflation_v1.0"),
        ]
        items = select_recalculations(results, {1: T0, 2: T1}, frozenset(), {"inflation": 100})
        kinds = {item.kind for item in items}
        assert kinds == {"FIRST_CALCULATION", "UNCHANGED_CONFIRMATION"}
        first = next(i for i in items if i.kind == "FIRST_CALCULATION")
        unchanged = next(i for i in items if i.kind == "UNCHANGED_CONFIRMATION")
        assert first.count == 1
        assert unchanged.count == 1

    def test_insufficient_data_recorded_result_is_a_real_unchanged_confirmation(self):
        results = [
            RecordedResultInput(id=105, release_check_run_id=2, monitor="labor", evaluation_period=date(2026, 9, 1), state="INSUFFICIENT_DATA", methodology_id="labor_v1.0"),
        ]
        items = select_recalculations(results, {2: T1}, frozenset(), {"labor": 100})
        assert len(items) == 1
        assert items[0].state == "INSUFFICIENT_DATA"

    def test_domains_never_mix(self):
        results = [
            RecordedResultInput(id=105, release_check_run_id=2, monitor="inflation", evaluation_period=date(2026, 9, 1), state="COOLING", methodology_id="inflation_v1.0"),
            RecordedResultInput(id=205, release_check_run_id=2, monitor="labor", evaluation_period=date(2026, 9, 1), state="STABLE", methodology_id="labor_v1.0"),
        ]
        items = select_recalculations(results, {2: T1}, frozenset(), {"inflation": 100, "labor": 200})
        assert {i.monitor for i in items} == {"inflation", "labor"}
        assert len(items) == 2

    def test_multiple_evaluation_periods_one_run_selects_only_max_period_for_classification(self):
        """The same current-result-selection rule applies to Tier B."""
        results = [
            RecordedResultInput(id=101, release_check_run_id=1, monitor="labor", evaluation_period=date(2026, 5, 1), state="COOLING", methodology_id="labor_v1.0"),
            RecordedResultInput(id=102, release_check_run_id=1, monitor="labor", evaluation_period=date(2026, 8, 1), state="COOLING", methodology_id="labor_v1.0"),
        ]
        items = select_recalculations(results, {1: T0}, frozenset(), {"labor": 100})
        assert len(items) == 1
        assert items[0].evaluation_period == date(2026, 8, 1)


# ---------------------------------------------------------------------
# select_source_updates -- contract §28-30
# ---------------------------------------------------------------------


class TestSelectSourceUpdates:
    INFLATION_IDS = frozenset({"PCEPILFE", "CPILFESL", "PCEPI", "CPIAUCSL"})
    LABOR_IDS = frozenset({"PAYEMS", "UNRATE"})

    def test_a_change_with_no_top_level_recompute_becomes_a_source_update(self):
        changes = [ObservationChangeInput(release_check_run_id=1, series_id="CPILFESL", series_title="Core CPI", change_type="REVISED")]
        items = select_source_updates(changes, frozenset(), self.INFLATION_IDS, self.LABOR_IDS)
        assert len(items) == 1
        assert items[0].monitor == "inflation"
        assert items[0].change_type == "REVISED"

    def test_a_change_already_covered_by_a_top_level_recompute_is_not_duplicated(self):
        """Contract §66-67: no redundant cards for one fact."""
        changes = [ObservationChangeInput(release_check_run_id=1, series_id="PCEPILFE", series_title="Core PCE", change_type="NEW")]
        covered = frozenset({(1, "inflation")})
        items = select_source_updates(changes, covered, self.INFLATION_IDS, self.LABOR_IDS)
        assert items == []

    def test_an_unmapped_series_never_appears(self):
        changes = [ObservationChangeInput(release_check_run_id=1, series_id="FABRICATED_XYZ", series_title=None, change_type="NEW")]
        assert select_source_updates(changes, frozenset(), self.INFLATION_IDS, self.LABOR_IDS) == []

    def test_new_vs_revised_are_both_shown_and_distinguished(self):
        changes = [
            ObservationChangeInput(release_check_run_id=1, series_id="PAYEMS", series_title="PAYEMS", change_type="NEW"),
            ObservationChangeInput(release_check_run_id=1, series_id="UNRATE", series_title="UNRATE", change_type="REVISED"),
        ]
        items = select_source_updates(changes, frozenset(), self.INFLATION_IDS, self.LABOR_IDS)
        change_types = {(i.series_id, i.change_type) for i in items}
        assert change_types == {("PAYEMS", "NEW"), ("UNRATE", "REVISED")}

    def test_duplicate_series_change_type_pair_within_one_run_is_deduplicated(self):
        changes = [
            ObservationChangeInput(release_check_run_id=1, series_id="PAYEMS", series_title="PAYEMS", change_type="REVISED"),
            ObservationChangeInput(release_check_run_id=1, series_id="PAYEMS", series_title="PAYEMS", change_type="REVISED"),
        ]
        items = select_source_updates(changes, frozenset(), self.INFLATION_IDS, self.LABOR_IDS)
        assert len(items) == 1

    def test_missing_series_title_renders_as_none_never_fabricated(self):
        changes = [ObservationChangeInput(release_check_run_id=1, series_id="PAYEMS", series_title=None, change_type="NEW")]
        items = select_source_updates(changes, frozenset(), self.INFLATION_IDS, self.LABOR_IDS)
        assert items[0].series_title is None


# ---------------------------------------------------------------------
# compute_coverage -- contract §40-41
# ---------------------------------------------------------------------


class TestComputeCoverage:
    def test_all_relevant_releases_settled_is_checked(self):
        assert compute_coverage(frozenset({1, 2}), frozenset({1, 2}), any_sweep_in_window=False) == "CHECKED"

    def test_checked_does_not_require_sweep_evidence(self):
        """Contract §47: manual-only processing is honestly CHECKED."""
        assert compute_coverage(frozenset({1}), frozenset({1}), any_sweep_in_window=False) == "CHECKED"

    def test_missing_settlement_with_sweep_evidence_is_gap(self):
        assert compute_coverage(frozenset({1, 2}), frozenset({1}), any_sweep_in_window=True) == "GAP"

    def test_missing_settlement_with_no_sweep_evidence_is_unknown(self):
        assert compute_coverage(frozenset({1, 2}), frozenset({1}), any_sweep_in_window=False) == "UNKNOWN"

    def test_no_relevant_releases_is_vacuously_checked(self):
        assert compute_coverage(frozenset(), frozenset(), any_sweep_in_window=False) == "CHECKED"

    def test_zero_settled_and_zero_sweep_is_unknown(self):
        assert compute_coverage(frozenset({1}), frozenset(), any_sweep_in_window=False) == "UNKNOWN"
