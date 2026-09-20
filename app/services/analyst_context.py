"""Deterministic assembly of MacroChipz Analyst context (Increment #33).

This module is the reason the Analyst is safe. It turns canonical
intelligence into a typed, versioned `AnalystContextPacket`, and it is
the ONLY way economic facts ever reach the model.

Two structural properties, both enforced by
`tests/test_analyst_architecture.py` rather than by discipline:

1. **This module never imports OpenAI.** Context assembly is ordinary
   deterministic application code that would behave identically if no
   language model existed.

2. **The module that DOES talk to the model never imports this one's
   dependencies.** `app/services/analyst.py` receives a finished packet
   and is handed no `Session`, no repository and no client -- so "the
   model cannot reach the database" is a fact about the import graph,
   not a promise in a prompt.

Everything here reads through existing canonical services
(`InflationMonitorService`, `LaborMonitorService`, `RatesMonitorService`,
`MonitorHistoryService`), all of which are read-only. No new economic
calculation is performed, and none may be: if a number is worth telling
the model, some deterministic layer already computed it.

Values are formatted into strings WITH THEIR UNITS here, at the one
boundary that knows them. A model handed `158268000` cannot tell jobs
from thousands of persons; handed `"158,268,000 jobs"` it cannot get it
wrong.
"""

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.analyst import (
    ANALYST_CONTEXT_VERSION,
    AnalystContextPacket,
    AnalystContextRef,
    ContextFact,
    EvidenceItem,
    MethodologyRef,
    ReplayInformation,
)
from app.models.inflation import (
    CONFIRMATION_SERIES_ID,
    DATA_BASIS as INFLATION_DATA_BASIS,
    InflationMonitorResult,
    METHODOLOGY_ID as INFLATION_METHODOLOGY_ID,
    PRIMARY_SERIES_ID,
    SeriesMomentumResult,
)
from app.models.labor import (
    DATA_BASIS as LABOR_DATA_BASIS,
    LaborMonitorResult,
    METHODOLOGY_ID as LABOR_METHODOLOGY_ID,
)
from app.models.monitor_history import MonitorHistoryDetail
from app.models.rates import (
    DATA_BASIS as RATES_DATA_BASIS,
    METHODOLOGY_ID as RATES_METHODOLOGY_ID,
    PROVIDER as RATES_PROVIDER,
    RatesMonitorResult,
)
from app.services.inflation import InflationMonitorService
from app.services.labor import LaborMonitorService
from app.services.monitor_history import MonitorHistoryService, RecordedResultNotFoundError
from app.services.rates import RatesMonitorService

#: One sentence per methodology, written by MacroChipz. The model is
#: told what a methodology does rather than being left to characterise a
#: frozen specification it has never seen.
_METHODOLOGY_SUMMARY = {
    INFLATION_METHODOLOGY_ID: (
        "Classifies underlying inflation by comparing Core PCE's 3-month and 6-month annualized rates against "
        "its 12-month rate, using a fixed neutral band. Core CPI independently confirms or diverges."
    ),
    LABOR_METHODOLOGY_ID: (
        "Combines a payroll-employment condition and momentum reading with an unemployment-rate trend, each "
        "measured against fixed deadbands, into one labor state via a frozen agreement table."
    ),
    RATES_METHODOLOGY_ID: (
        "Reports U.S. Treasury par yields as published, plus derived curve spreads and inflation compensation, "
        "with changes measured over counted trading sessions rather than calendar days."
    ),
}


#: The unit and precision each change FIELD carries, keyed by the field
#: names `inflation_what_changed_v1.0` and `labor_what_changed_v1.0`
#: already freeze in their own `FIELD_ORDER` tuples.
#:
#: A unit lookup, not a second formatting implementation: rendering
#: still goes through `_fmt`. Coverage of both frozen vocabularies is
#: asserted by `tests/integration/test_analyst_context.py`, so a field
#: added to either contract cannot silently fall back to an unlabelled
#: number.
_CHANGE_FIELD_UNIT: dict[str, tuple[str, int]] = {
    # inflation_what_changed_v1.0
    "r_1m_annualized": ("%", 2),
    "r_3m_annualized": ("%", 2),
    "r_6m_annualized": ("%", 2),
    "r_12m": ("%", 2),
    "headline_pce_yoy": ("%", 2),
    "target_gap_pp": (" pp", 2),
    # labor_what_changed_v1.0. The PAYEMS-derived fields are already in
    # canonical jobs, matching `labor.metric.*` evidence exactly.
    "current_3m_avg_jobs": (" jobs", 0),
    "prior_3m_avg_jobs": (" jobs", 0),
    "momentum_delta_jobs": (" jobs", 0),
    "current_3m_avg": ("%", 1),
    "prior_year_3m_avg": ("%", 1),
    "delta_pp": (" pp", 2),
}

#: Change fields whose values are canonical NAMES rather than numbers.
#: They are passed through verbatim and need no unit.
_CHANGE_TEXT_FIELDS = frozenset({"state", "relationship", "condition", "momentum"})


class AnalystContextUnavailableError(Exception):
    """The requested context could not be assembled from canonical data.
    Distinct from "the provider failed" -- this one never involves the
    model at all."""


def _fmt(value: float | None, unit: str = "", digits: int = 2) -> str:
    """One number, formatted with its unit. `None` becomes an explicit
    phrase rather than a blank, so the model is told a value is missing
    instead of inferring it from silence."""
    if value is None:
        return "not available"
    return f"{value:,.{digits}f}{unit}"


def _pct(value: float | None) -> str:
    return "not available" if value is None else f"{value:.2f}%"


def _period(value: date | None) -> str:
    return "not available" if value is None else value.strftime("%B %Y")


def _momentum_evidence(momentum: SeriesMomentumResult, prefix: str, label_prefix: str) -> list[EvidenceItem]:
    """Each horizon the inflation methodology actually used, as citable
    evidence carrying the exact observations behind it."""
    items: list[EvidenceItem] = []
    for suffix, evidence in (
        ("1m_annualized", momentum.evidence_1m),
        ("3m_annualized", momentum.evidence_3m),
        ("6m_annualized", momentum.evidence_6m),
        ("12m", momentum.evidence_12m),
    ):
        if evidence is None:
            continue
        items.append(
            EvidenceItem(
                id=f"{prefix}.metric.{suffix}",
                kind="METRIC",
                label=f"{label_prefix} {suffix.replace('_', ' ')}",
                value=_pct(evidence.value),
                detail=(
                    f"{evidence.endpoint_date_past.isoformat()} index "
                    f"{_fmt(evidence.endpoint_value_past, digits=3)} to "
                    f"{evidence.endpoint_date_current.isoformat()} index "
                    f"{_fmt(evidence.endpoint_value_current, digits=3)}"
                ),
            )
        )
    return items


class AnalystContextBuilder:
    """Builds one packet per request. Read-only, no clock beyond the
    packet's own `generated_at`, and no branch anywhere that consults a
    model."""

    def build(self, session: Session, ref: AnalystContextRef) -> AnalystContextPacket:
        if ref.type == "INFLATION":
            return self._inflation(session)
        if ref.type == "LABOR":
            return self._labor(session)
        if ref.type == "RATES":
            return self._rates(session)
        return self._monitor_history(session, ref)

    # -----------------------------------------------------------------
    # Inflation
    # -----------------------------------------------------------------

    def _inflation(self, session: Session) -> AnalystContextPacket:
        service = InflationMonitorService()
        result: InflationMonitorResult = service.get_result(session)
        what_changed = service.get_what_changed_result(session)

        momentum = result.underlying_momentum
        evidence: list[EvidenceItem] = [
            EvidenceItem(
                id="inflation.state.core_pce",
                kind="STATE",
                label="Core PCE underlying momentum state",
                value=momentum.state,
                detail=f"Classified for {_period(momentum.calculation_period)} under {INFLATION_METHODOLOGY_ID}",
            ),
            EvidenceItem(
                id="inflation.state.core_cpi_confirmation",
                kind="STATE",
                label="Core CPI confirmation relationship",
                value=result.confirmation.relationship,
                detail=f"Core CPI state: {result.confirmation.confirmation_latest.state}",
            ),
        ]
        evidence.extend(_momentum_evidence(momentum, "inflation", "Core PCE"))

        if result.target.available:
            evidence.append(
                EvidenceItem(
                    id="inflation.metric.target_gap",
                    kind="METRIC",
                    label="Headline PCE gap to the 2% objective",
                    value=_fmt(result.target.target_gap_pp, " pp"),
                    detail=f"Headline PCE 12-month rate {_pct(result.target.headline_pce_yoy)}",
                )
            )

        metrics = [
            ContextFact(label="Core PCE 3-month annualized", value=_pct(momentum.r_3m_annualized)),
            ContextFact(label="Core PCE 6-month annualized", value=_pct(momentum.r_6m_annualized)),
            ContextFact(label="Core PCE 12-month", value=_pct(momentum.r_12m)),
            ContextFact(label="Neutral band", value=f"+/- {momentum.neutral_band_pp:.2f} pp around the 12-month rate"),
            ContextFact(
                label="Neutral band boundaries",
                value=f"{_pct(momentum.lower_boundary)} to {_pct(momentum.upper_boundary)}",
            ),
        ]

        changes = [
            ContextFact(label=f"{event.component} {event.field}", value=self._change_value(event))
            for event in what_changed.changes[:12]
        ]

        limitations = [
            "This context covers MacroChipz's inflation assessment only. It contains no market data, no forecast, "
            "and no information about other economic domains.",
            "Economic data is revised after publication; these values are the latest revised data MacroChipz holds.",
        ]
        if momentum.missing_required_metrics:
            limitations.append(
                "The methodology could not compute: " + ", ".join(momentum.missing_required_metrics) + "."
            )

        return AnalystContextPacket(
            context_version=ANALYST_CONTEXT_VERSION,
            context_type="INFLATION",
            generated_at=datetime.now(timezone.utc),
            subject="MacroChipz's inflation assessment (Core PCE underlying momentum, confirmed by Core CPI)",
            canonical_state=momentum.state,
            evaluation_period=momentum.calculation_period,
            methodology=MethodologyRef(
                methodology_id=INFLATION_METHODOLOGY_ID,
                data_basis=INFLATION_DATA_BASIS,
                summary=_METHODOLOGY_SUMMARY[INFLATION_METHODOLOGY_ID],
            ),
            deterministic_metrics=metrics,
            changes=changes,
            evidence=evidence,
            provenance=[
                ContextFact(label="Primary series", value=PRIMARY_SERIES_ID),
                ContextFact(label="Confirmation series", value=CONFIRMATION_SERIES_ID),
                ContextFact(label="Data through", value=_period(result.periods.data_through)),
            ],
            limitations=limitations,
        )

    @staticmethod
    def _change_endpoint(field: str, value: float | str | None) -> str:
        """One side of a change event, formatted exactly like every other
        value in the packet.

        The baseline live evaluation exposed this as the one real
        context defect: `changes[]` emitted `str(3.1127788466932538)`
        while the rest of the packet emitted `"3.11%"`. The model
        therefore had to round and infer a unit before it could say
        anything about a change -- precisely the work this packet exists
        to have already done. It rounded correctly, but asking a
        language model to do arithmetic the backend already owns is the
        habit this architecture exists to avoid.

        A `str` value is a canonical state or relationship name and is
        passed through untouched. Numbers reuse `_fmt`, the same helper
        every other value in the packet uses -- this adds a unit lookup,
        never a second formatting implementation.
        """
        if value is None:
            return "not available"
        if isinstance(value, str):
            return value
        unit, digits = _CHANGE_FIELD_UNIT.get(field, ("", 3))
        return _fmt(value, unit, digits)

    @classmethod
    def _change_value(cls, event) -> str:
        previous = cls._change_endpoint(event.field, event.previous_value)
        current = cls._change_endpoint(event.field, event.current_value)
        return f"{event.event_type}: {previous} to {current}"

    # -----------------------------------------------------------------
    # Labor
    # -----------------------------------------------------------------

    def _labor(self, session: Session) -> AnalystContextPacket:
        service = LaborMonitorService()
        result: LaborMonitorResult = service.get_result(session)
        what_changed = service.get_what_changed_result(session)

        employment = result.employment
        unemployment = result.unemployment

        evidence = [
            EvidenceItem(
                id="labor.state.combined",
                kind="STATE",
                label="Labor state",
                value=result.state,
                detail=f"Combines employment state {employment.state} with unemployment trend {unemployment.state}",
            ),
            EvidenceItem(
                id="labor.state.employment",
                kind="STATE",
                label="Employment state",
                value=employment.state,
                detail=f"Condition {employment.condition}, momentum {employment.momentum}",
            ),
            EvidenceItem(
                id="labor.state.unemployment",
                kind="STATE",
                label="Unemployment trend state",
                value=unemployment.state,
                detail=f"3-month average {_fmt(unemployment.current_3m_avg, '%', 1)} "
                f"versus {_fmt(unemployment.prior_year_3m_avg, '%', 1)} a year earlier",
            ),
            EvidenceItem(
                id="labor.metric.payroll_3m_average",
                kind="METRIC",
                label="Average monthly payroll change, latest 3 months",
                value=_fmt(employment.current_3m_avg_jobs, " jobs", 0),
                detail=f"Prior 3 months: {_fmt(employment.prior_3m_avg_jobs, ' jobs', 0)}",
            ),
            EvidenceItem(
                id="labor.metric.payroll_momentum",
                kind="METRIC",
                label="Change between those two 3-month averages",
                value=_fmt(employment.momentum_delta_jobs, " jobs", 0),
                detail=f"Deadband: +/- {employment.momentum_deadband_jobs:,.0f} jobs",
            ),
            EvidenceItem(
                id="labor.metric.unemployment_delta",
                kind="METRIC",
                label="Unemployment rate change versus a year earlier",
                value=_fmt(unemployment.delta_pp, " pp"),
                detail=f"Deadband: +/- {unemployment.unemployment_deadband_pp:.1f} pp",
            ),
        ]

        metrics = [
            ContextFact(label="Employment condition", value=employment.condition),
            ContextFact(label="Employment momentum", value=employment.momentum),
            ContextFact(label="Unemployment trend", value=unemployment.state),
            ContextFact(
                label="Condition deadband", value=f"+/- {employment.condition_deadband_jobs:,.0f} jobs per month"
            ),
        ]

        changes = [
            ContextFact(label=f"{event.component} {event.field}", value=self._change_value(event))
            for event in what_changed.changes[:12]
        ]

        return AnalystContextPacket(
            context_version=ANALYST_CONTEXT_VERSION,
            context_type="LABOR",
            generated_at=datetime.now(timezone.utc),
            subject="MacroChipz's labor market assessment (payroll employment and the unemployment trend)",
            canonical_state=result.state,
            evaluation_period=result.evaluation_period,
            methodology=MethodologyRef(
                methodology_id=LABOR_METHODOLOGY_ID,
                data_basis=LABOR_DATA_BASIS,
                summary=_METHODOLOGY_SUMMARY[LABOR_METHODOLOGY_ID],
            ),
            deterministic_metrics=metrics,
            changes=changes,
            evidence=evidence,
            provenance=[
                ContextFact(label="Employment series", value=employment.series_id),
                ContextFact(label="Unemployment series", value=unemployment.series_id),
            ],
            limitations=[
                "This context covers MacroChipz's labor assessment only. It contains no market data, no forecast, "
                "and no information about other economic domains.",
                "A MIXED state means the employment and unemployment readings do not agree; the frozen agreement "
                "table resolves only four combinations to a clean state.",
            ],
        )

    # -----------------------------------------------------------------
    # Rates
    # -----------------------------------------------------------------

    def _rates(self, session: Session) -> AnalystContextPacket:
        result: RatesMonitorResult = RatesMonitorService().get_result(session)

        evidence: list[EvidenceItem] = []
        for level in (*result.nominal_curve, *result.real_curve):
            if not level.available:
                continue
            evidence.append(
                EvidenceItem(
                    id=f"rates.level.{level.series_id}",
                    kind="OBSERVATION",
                    label=level.title,
                    value=_pct(level.latest_value),
                    detail=f"As published by {RATES_PROVIDER} for {level.latest_date}",
                )
            )
        for spread in result.curve_spreads:
            evidence.append(
                EvidenceItem(
                    id=f"rates.spread.{spread.spread_id}",
                    kind="METRIC",
                    label=spread.title,
                    value=_fmt(spread.spread_basis_points, " bp", 1) if spread.available else "not available",
                    detail=(
                        f"{spread.long_series_id} minus {spread.short_series_id}"
                        if spread.available
                        else f"Unavailable: {spread.unavailable_reason}"
                    ),
                )
            )
        for compensation in result.inflation_compensation:
            evidence.append(
                EvidenceItem(
                    id=f"rates.compensation.{compensation.maturity}",
                    kind="METRIC",
                    label=compensation.title,
                    value=_pct(compensation.compensation_percent) if compensation.available else "not available",
                    detail=(
                        f"{compensation.nominal_series_id} minus {compensation.real_series_id}"
                        if compensation.available
                        else f"Unavailable: {compensation.unavailable_reason}"
                    ),
                )
            )

        changes: list[ContextFact] = []
        for level in result.nominal_curve:
            for change in level.changes:
                if change.available:
                    changes.append(
                        ContextFact(
                            label=f"{level.title} over {change.sessions} sessions",
                            value=_fmt(change.change_basis_points, " bp", 1),
                        )
                    )

        historical: list[ContextFact] = []
        for level in result.nominal_curve:
            context = level.historical_context
            if context.available and context.percentile_rank is not None:
                historical.append(
                    ContextFact(
                        label=f"{level.title} {context.window} change, historical percentile",
                        value=f"{context.percentile_rank:.0f}th of {context.observation_count} observed changes",
                    )
                )

        return AnalystContextPacket(
            context_version=ANALYST_CONTEXT_VERSION,
            context_type="RATES",
            generated_at=datetime.now(timezone.utc),
            subject="MacroChipz's rates intelligence (U.S. Treasury par yields, curve spreads and inflation compensation)",
            # Rates deliberately has NO canonical classified state --
            # `rates_v1.0` publishes levels and derived metrics, and
            # inventing a state here would fabricate intelligence the
            # engine does not produce.
            canonical_state=None,
            evaluation_period=result.as_of_date,
            methodology=MethodologyRef(
                methodology_id=RATES_METHODOLOGY_ID,
                data_basis=RATES_DATA_BASIS,
                summary=_METHODOLOGY_SUMMARY[RATES_METHODOLOGY_ID],
            ),
            deterministic_metrics=[
                ContextFact(label="As-of date", value=str(result.as_of_date) if result.as_of_date else "not available")
            ],
            changes=changes[:12],
            evidence=evidence,
            provenance=[
                ContextFact(label="Provider", value=result.provider),
                ContextFact(label="Attribution", value=result.attribution),
            ],
            historical_context=historical,
            limitations=[
                "MacroChipz does not classify rates into a state the way it classifies inflation and labor. "
                "Rates intelligence reports published yields and values derived from them.",
                "Changes are measured over counted trading sessions, not calendar days.",
                "Historical percentiles describe the distribution of past changes MacroChipz has observed. "
                "They say nothing about what will happen next.",
            ],
        )

    # -----------------------------------------------------------------
    # Monitor history (#31/#32)
    # -----------------------------------------------------------------

    def _monitor_history(self, session: Session, ref: AnalystContextRef) -> AnalystContextPacket:
        if ref.recorded_result_id is None or ref.monitor is None:
            raise AnalystContextUnavailableError(
                "MONITOR_HISTORY requires both a recorded_result_id and a monitor."
            )
        try:
            detail: MonitorHistoryDetail = MonitorHistoryService().get_history_detail(
                session, ref.monitor, ref.recorded_result_id
            )
        except RecordedResultNotFoundError as exc:
            raise AnalystContextUnavailableError(str(exc)) from exc

        recorded = detail.recorded
        comparison = detail.current_comparison

        evidence: list[EvidenceItem] = [
            EvidenceItem(
                id="history.recorded_state",
                kind="STATE",
                label="What MacroChipz concluded at the time",
                value=recorded.state,
                detail=f"For {_period(recorded.evaluation_period)}, calculated {recorded.calculated_at.isoformat()} "
                f"under {recorded.methodology_id}",
            )
        ]
        for row in detail.historical_inputs:
            unit = {"INDEX": "", "JOBS": " jobs", "PERCENT": "%"}[row.value_unit]
            digits = 0 if row.value_unit == "JOBS" else (1 if row.value_unit == "PERCENT" else 3)
            evidence.append(
                EvidenceItem(
                    id=f"history.input.{row.series_id}.{row.observation_date.isoformat()}",
                    kind="OBSERVATION",
                    label=f"{row.series_id} for {_period(row.observation_date)}",
                    value=f"then {_fmt(row.value_then, unit, digits)}, today {_fmt(row.value_today, unit, digits)}",
                    detail=f"MacroChipz classifies this input as {row.comparison}"
                    + (" (value reconstructed at migration time)" if row.is_backfilled else ""),
                )
            )
        for change in detail.related_changes:
            evidence.append(
                EvidenceItem(
                    id=f"history.change.{change.series_id}.{change.observation_date.isoformat()}",
                    kind="CHANGE",
                    label=f"{change.change_type} observation for {change.series_id}, {_period(change.observation_date)}",
                    value=f"{change.previous_value} to {change.new_value}",
                    detail="Processed in the same run that produced this result",
                )
            )
        evidence.append(
            EvidenceItem(
                id="history.current_comparison",
                kind="COMPARISON",
                label="What today's revised data produces for the same period",
                value=comparison.current_state or "not computed",
                detail=f"MacroChipz classifies the input comparison as {comparison.status}"
                + (f" ({comparison.reason})" if comparison.reason else ""),
            )
        )

        limitations = [
            "Related data changes were processed in the same run that produced this result. MacroChipz records "
            "that they happened together; it does not record that one caused the other. Do not assert causation.",
        ]
        if recorded.replay.inputs_include_backfilled:
            limitations.append(
                "Some input values were reconstructed from data MacroChipz had already stored when it began "
                "tracking revisions. The result can be reproduced from that stored data, but MacroChipz cannot "
                "prove those were the provider's originally published figures."
            )
        if comparison.methodology_differs:
            limitations.append(
                f"This result used methodology {comparison.methodology_id_then} while MacroChipz now runs "
                f"{comparison.methodology_id_today}. Any difference may reflect changed data, changed methodology, "
                "or both."
            )
        if recorded.replay.outcome == "MISMATCH":
            limitations.append(
                "Replay MISMATCH: recalculating from the data available at the time does not reproduce the "
                "recorded result. This is a data-integrity issue and must be described as one, not explained away."
            )

        return AnalystContextPacket(
            context_version=ANALYST_CONTEXT_VERSION,
            context_type="MONITOR_HISTORY",
            generated_at=datetime.now(timezone.utc),
            subject=f"A recorded {ref.monitor} conclusion for {_period(recorded.evaluation_period)}, and how it "
            "compares with today's revised data",
            canonical_state=recorded.state,
            evaluation_period=recorded.evaluation_period,
            methodology=MethodologyRef(
                methodology_id=recorded.methodology_id,
                data_basis=recorded.data_basis,
                summary=_METHODOLOGY_SUMMARY.get(recorded.methodology_id, "A frozen MacroChipz methodology version."),
            ),
            deterministic_metrics=[
                ContextFact(label="Recorded state", value=recorded.state),
                ContextFact(label="Today's reconstruction", value=comparison.current_state or "not computed"),
                ContextFact(
                    label="Do the two differ?",
                    value="not comparable" if comparison.state_differs is None else str(comparison.state_differs),
                ),
                ContextFact(label="Inputs that changed since", value=str(comparison.changed_input_count)),
            ],
            changes=[
                ContextFact(
                    label="Other changes in the same run not used by this result",
                    value=str(detail.other_changes_in_same_run),
                )
            ],
            evidence=evidence,
            replay_information=ReplayInformation(
                outcome=recorded.replay.outcome,
                replayed_state=recorded.replay.replayed_state,
                reason=recorded.replay.reason,
                inputs_include_backfilled=recorded.replay.inputs_include_backfilled,
            ),
            limitations=limitations,
        )
