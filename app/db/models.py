"""SQLAlchemy ORM models for persisted economic data.

Distinct from `app/models/series.py`, which defines the application's
*API* response contract (Pydantic). These classes define the *relational*
shape of the data as stored in PostgreSQL.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EconomicSeries(Base):
    """One economic data series (e.g. FRED's "UNRATE").

    `id` is the internal database identity; `series_id` is the external,
    provider-assigned business identifier. Keeping these distinct means the
    provider's identifier can be looked up, displayed, and referenced
    without ever standing in for the relational primary key.
    """

    __tablename__ = "economic_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    #: Which MacroChipz economic concept this series supplies (#38,
    #: ADR-034). Nullable by design and permanently so: the generic
    #: series-sync endpoint accepts arbitrary provider series, which are
    #: not canonical concepts. Canonical methodology paths require it
    #: and fail loudly without it; nothing infers it from a title.
    concept_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    units: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="FRED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    observations: Mapped[list["EconomicObservation"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )


class EconomicObservation(Base):
    """One dated data point belonging to an `EconomicSeries`.

    `economic_series_id` is the foreign key — named explicitly (rather than
    reusing "series_id") so it's never confused with the provider's string
    identifier on `EconomicSeries.series_id`.
    """

    __tablename__ = "economic_observations"
    __table_args__ = (
        UniqueConstraint("economic_series_id", "observation_date", name="uq_observation_series_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    economic_series_id: Mapped[int] = mapped_column(
        ForeignKey("economic_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    series: Mapped["EconomicSeries"] = relationship(back_populates="observations")


class EconomicRelease(Base):
    """One curated, recurring named release (e.g. FRED's "Consumer Price
    Index" release). Frozen contract: see
    docs/architecture/release-intelligence-v1.md #4.

    `id` is the internal database identity; `provider`+`provider_release_id`
    is the external, provider-assigned business identity -- kept distinct
    for the same reason `EconomicSeries.id` is kept distinct from
    `EconomicSeries.series_id` (see that class's docstring). The catalog
    itself is curated (seeded deliberately, never a wholesale sync of a
    provider's full release list) -- `active` is the toggle for that
    curation, not a general-purpose soft-delete flag.
    """

    __tablename__ = "economic_releases"
    __table_args__ = (
        UniqueConstraint("provider", "provider_release_id", name="uq_release_provider_provider_release_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, server_default="FRED")
    provider_release_id: Mapped[str] = mapped_column(String(64), nullable=False)
    official_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    occurrences: Mapped[list["ReleaseOccurrence"]] = relationship(
        back_populates="release", cascade="all, delete-orphan"
    )


class ReleaseOccurrence(Base):
    """One scheduled instance of an `EconomicRelease`, date-level only.
    Frozen contract: see docs/architecture/release-intelligence-v1.md #5.

    Deliberately does NOT carry a time-of-day, timezone, cancellation, or
    data/analysis-status field -- FRED's release-dates data cannot
    reliably source any of those (see the frozen spec's #3), and
    inventing one would violate this project's "missing precision stays
    explicit, never fabricated" invariant. `economic_release_id` is named
    explicitly (not reusing a provider-style identifier) for the same
    reason `EconomicObservation.economic_series_id` is -- never confused
    with `EconomicRelease.provider_release_id`.
    """

    __tablename__ = "release_occurrences"
    __table_args__ = (
        UniqueConstraint("economic_release_id", "scheduled_date", name="uq_occurrence_release_scheduled_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    economic_release_id: Mapped[int] = mapped_column(
        ForeignKey("economic_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    release: Mapped["EconomicRelease"] = relationship(back_populates="occurrences")


class ReleaseSeriesMapping(Base):
    """Increment #18: curated fact answering ONLY "which canonical
    series should EI inspect when processing this release?" -- never an
    economic-significance judgment (see
    docs/architecture/release-processing-v1.md and
    docs/adr/022-release-processing-audit-without-monitor-snapshots.md).

    `series_id` is deliberately a plain string, NOT a foreign key to
    `EconomicSeries.id` -- a curated mapping fact must exist
    independently of whether that series has ever actually been synced
    (see `app.repositories.release_processing_repository`, which
    creates the `EconomicSeries` row on first release-driven write if
    one doesn't already exist). No `role`/`importance`/`weight` column
    exists here and none should ever be added in this table -- that
    would encode economic meaning into a "what to check" lookup, which
    this table must never do.
    """

    __tablename__ = "release_series_mappings"
    __table_args__ = (
        UniqueConstraint("economic_release_id", "series_id", name="uq_release_series_mapping_release_series"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    economic_release_id: Mapped[int] = mapped_column(
        ForeignKey("economic_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReleaseCheckRun(Base):
    """Increment #18: one release-driven provider check attempt.

    `status` is one of exactly four values -- `NO_CHANGE`, `CHANGED`,
    `PARTIAL_FAILURE`, `FAILED_PROVIDER` -- deliberately no
    `NOT_CHECKED` (absence of a row already means that) and no
    persisted "DB failure" status: if the surrounding transaction
    itself fails, this row (and everything else written alongside it)
    never durably exists at all, which is accepted, documented
    behavior (see `app.services.release_processing`), not a gap to
    paper over with a second, separately-committed audit transaction.
    Retrying an occurrence is expected to create a NEW row -- "a check
    occurred" is itself a real, repeatable operational fact -- while
    `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` rows are NOT
    duplicated on a retry against unchanged provider data (see those
    classes below).
    """

    __tablename__ = "release_check_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    release_occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("release_occurrences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReleaseObservationUpdate(Base):
    """Increment #18: append-only audit fact -- "during this check, EI
    detected that this canonical provider observation was NEW or
    REVISED relative to EI's persisted current value." UNCHANGED
    observations are never written here (see
    `app.domain.release_processing.classify_observation_change`);
    "unchanged" is represented by a successful check plus the absence
    of a row for that observation, keeping audit volume proportional to
    actual change, not to check frequency.

    `previous_value`/`new_value` are both nullable -- `EconomicObservation.value`
    itself is nullable (a provider can return a missing "." observation),
    so a revision can legitimately transition into or out of `NULL`.
    `UNIQUE(release_check_run_id, series_id, observation_date)` prevents
    a bug from recording the same detected change twice within one run;
    the same observation changing again in a LATER run produces a new
    row in that later run's own `ReleaseCheckRun`, which is correct,
    not a duplicate.
    """

    __tablename__ = "release_observation_updates"
    __table_args__ = (
        UniqueConstraint(
            "release_check_run_id", "series_id", "observation_date", name="uq_release_observation_update_run_series_date"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    release_check_run_id: Mapped[int] = mapped_column(
        ForeignKey("release_check_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    change_type: Mapped[str] = mapped_column(String(16), nullable=False)
    previous_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReleaseAnalysisUpdate(Base):
    """Increment #18: structured, typed analytical consequence of one or
    more observation changes in a check run -- NOT a full
    `InflationMonitorResult` snapshot, and never arbitrary JSON. The
    field set mirrors `app.models.inflation_what_changed.ChangeEvent`
    (the frozen `inflation_what_changed_v1.0` event vocabulary --
    `METRIC_CHANGED`/`STATE_CHANGED`/`AVAILABILITY_LOST`/
    `AVAILABILITY_RESTORED`/`CONFIRMATION_CHANGED` -- reused, never
    duplicated) with ONE deliberate, honest adaptation:
    `ChangeEvent` carries separate `previous_period`/`current_period`
    fields because it compares two different calendar months; a
    release-scoped before/after comparison evaluates both snapshots at
    the exact SAME period (the observation write doesn't move which
    calendar month is being evaluated, only what value is at it), so
    this table has one `evaluation_period` column instead of two,
    rather than distorting the frozen contract's own period semantics
    to force a fit. `previous_value`/`current_value` are stored as
    `String` (nullable) because the frozen `ChangeEvent.previous_value`/
    `current_value` type is `float | str | None` (a state or
    relationship label, or a numeric metric) -- Python's `str(float)`
    round-trips exactly, so no precision is lost, and a single typed
    column avoids splitting one conceptual field across two nullable
    columns.

    A check run producing zero analytical consequences (data changed
    but no canonical Inflation evidence differed) simply has zero rows
    here -- never a synthetic "no change" row.
    """

    __tablename__ = "release_analysis_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    release_check_run_id: Mapped[int] = mapped_column(
        ForeignKey("release_check_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    field: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluation_period: Mapped[date] = mapped_column(Date, nullable=False)
    methodology_id: Mapped[str] = mapped_column(String(32), nullable=False)
    data_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaintenanceSweep(Base):
    """Increment #25C: one bounded automated-maintenance sweep attempt
    -- per-ORCHESTRATOR-RUN, operational-health-shaped data, deliberately
    NOT the same concept as `ReleaseCheckRun` (per-OCCURRENCE, economic-
    check-shaped) -- see
    docs/product/automated-economic-maintenance-v1.md §30/§53. Owned by
    `app.repositories.maintenance_repository.MaintenanceRepository`,
    never by `ReleaseProcessingRepository` (same "worker health and
    economic/domain freshness are two separate concepts, never
    conflated" reasoning that already keeps every other release-
    processing table separate from this one).

    `finished_at`/`status`/the three count columns are all nullable and
    written together, exactly once, at sweep completion
    (`MaintenanceRepository.finish_sweep`) -- a row with
    `finished_at IS NULL` means the sweep started and has not (yet, or
    ever) finished, the exact, intentional signal a future health
    check needs to distinguish a crashed/still-running sweep from "no
    sweep ran at all" (no row exists) -- see §52/§25 of the frozen
    contract. `status` is currently written as exactly one value,
    `"SUCCEEDED"`: reaching the finish step at all already means the
    orchestrator itself did not crash (frozen contract §30 -- sweep-
    level WORKER health is never conflated with any individual
    occurrence's own processing outcome, which `due_count`/
    `processed_count`/`failed_count` describe instead, independently).
    """

    __tablename__ = "maintenance_sweeps"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    due_count: Mapped[int | None] = mapped_column(nullable=True)
    processed_count: Mapped[int | None] = mapped_column(nullable=True)
    failed_count: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RecordedMonitorResult(Base):
    """Increment #25E: one immutable record proving that Economic
    Intelligence's own canonical monitor computation genuinely
    executed -- see docs/product/recorded-state-history-v1.md, the
    frozen #25D contract this table implements verbatim.

    Distinct from every other table in this schema: `ReleaseCheckRun`
    proves a check was ATTEMPTED (see that class's own docstring);
    `ReleaseAnalysisUpdate` proves a canonical fact CHANGED (change-
    only -- a check that recomputes and confirms the SAME state writes
    zero `ReleaseAnalysisUpdate` rows, by that class's own design).
    `RecordedMonitorResult` proves a canonical monitor result was
    genuinely CALCULATED, regardless of whether it changed -- the
    exact gap #24A/#25B/#25D each independently identified and this
    table exists to close (contract §4/§9).

    A row is written ONLY when the existing, unmodified
    `_evaluate_component_at`("PRIMARY_MOMENTUM")/`_evaluate_labor_at`
    AFTER-evidence call genuinely executes inside
    `ReleaseProcessingService._apply_changes_and_compute_analysis` --
    never synthesized, never backfilled, never written from a read
    path (contract §6/§51/§63). `release_check_run_id` is the row's
    sole source-event provenance (contract §24) -- the same
    `ReleaseCheckRun` row `ReleaseObservationUpdate`/
    `ReleaseAnalysisUpdate` already reference, created identically
    whether processing was triggered manually or by the automated
    maintenance orchestrator (contract §27).

    Append-only through normal application code: the repository
    exposes only `add_recorded_monitor_result`, never an update or
    delete method (contract §30). A later provider revision or
    methodology change never mutates an existing row -- it produces a
    NEW row, from a NEW `ReleaseCheckRun`, for the same
    `(monitor, evaluation_period)` (contract §12/§18/§82).

    `UNIQUE(release_check_run_id, monitor, evaluation_period)`
    deliberately does NOT include `methodology_id` -- identity is
    scoped to one genuine computation event, not to "this
    monitor/period pair, ever" (contract §13/§33), so the same period
    can legitimately be recorded again by a later, independent
    `ReleaseCheckRun` (a later release, a revision, a manual retry)
    without colliding. `state` is a plain string, never a database
    enum (contract §19/§71) -- it may legitimately be the literal
    `"INSUFFICIENT_DATA"` (contract §37), a real, successfully-
    computed classification, never a failure. `calculated_at` reuses
    the owning `ReleaseCheckRun.completed_at` value verbatim -- no
    independent clock read (contract §15).
    """

    __tablename__ = "recorded_monitor_results"
    __table_args__ = (
        UniqueConstraint(
            "release_check_run_id", "monitor", "evaluation_period", name="uq_recorded_monitor_result_run_monitor_period"
        ),
        Index("ix_recorded_monitor_results_monitor_calculated_at", "monitor", "calculated_at"),
        Index("ix_recorded_monitor_results_monitor_evaluation_period", "monitor", "evaluation_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    release_check_run_id: Mapped[int] = mapped_column(
        ForeignKey("release_check_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    monitor: Mapped[str] = mapped_column(String(16), nullable=False)
    evaluation_period: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    methodology_id: Mapped[str] = mapped_column(String(32), nullable=False)
    data_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ObservationProvenance(Base):
    """Increment #29: where one persisted `EconomicObservation` actually
    came from, and whether the provider has since revised it.

    Deliberately a SEPARATE table rather than columns on
    `economic_observations`: provenance is about the *retrieval event*,
    not about the economic fact, and every pre-#29 observation
    legitimately has none (backfilling a fabricated provider/URL for
    historical FRED rows would itself be a provenance lie). A missing
    provenance row therefore means "not recorded", never "unknown
    source silently assumed".

    One row per `(economic_series_id, observation_date)` -- the same
    grain as the observation itself. `revision_count` increments and
    `last_revised_at` is set only when a later ingestion genuinely
    changes the stored value; a re-ingestion that confirms the same
    value updates `retrieved_at` only, so revision history never
    inflates with routine idempotent syncs.
    """

    __tablename__ = "observation_provenance"
    __table_args__ = (
        UniqueConstraint("economic_series_id", "observation_date", name="uq_observation_provenance_series_date"),
        Index("ix_observation_provenance_provider_dataset", "provider", "dataset"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    economic_series_id: Mapped[int] = mapped_column(
        ForeignKey("economic_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    source_series_field: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_revised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RatesIngestionRun(Base):
    """Increment #29: one operator-invoked Rates ingestion attempt, for
    diagnosability.

    Mirrors `ReleaseCheckRun`'s role for release processing: it records
    that a sync was ATTEMPTED and how it ended, independent of whether
    any observation changed. Counts only -- never an upstream payload,
    never a URL with credentials (these feeds have none), never a stack
    trace. `error_class` holds an exception class name at most, so a
    failure is diagnosable without leaking response bodies.
    """

    __tablename__ = "rates_ingestion_runs"
    __table_args__ = (Index("ix_rates_ingestion_runs_started_at", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    datasets_requested: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    observations_received: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observations_inserted: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observations_revised: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    datasets_failed: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HousingIngestionRun(Base):
    """Increment #45: one operator-invoked Census ingestion attempt, for
    diagnosability.

    Mirrors `RatesIngestionRun`'s role exactly, and the two tables are
    structurally identical because ingesting one provider is structurally
    the same operation as ingesting another. They are kept separate
    rather than unified here for one reason: unifying them means
    migrating #29's existing rows into a renamed table, which is a
    refactor this increment has no reason to perform and every reason not
    to risk. A future provider-neutral `provider_ingestion_runs` is the
    right home for both -- recorded as deferred work, not done
    opportunistically.

    ONE COLUMN THAT MATTERS MORE THAN THE REST. `error_class` holds an
    exception CLASS NAME at most -- `CensusAuthError`, never a message,
    never a URL, never a response body. Census is the first provider here
    that requires a credential, and a request URL for it contains that
    credential, so "what went wrong" has to be diagnosable without
    recording anything that could carry one. A class name is enough to
    tell an expired key from a timeout from a schema change, which is
    every distinction an operator actually acts on.

    `rows_rejected` and `error_measure_rows_ignored` are recorded
    separately and deliberately. The first counts rows that failed
    validation -- a provider contract change, worth noticing. The second
    counts Census's own reliability statistics, which are expected on
    every run and are not a problem. Summing them into one number would
    make a normal run look degraded.
    """

    __tablename__ = "housing_ingestion_runs"
    __table_args__ = (Index("ix_housing_ingestion_runs_started_at", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    #: BASELINE_BACKFILL when this run performed the initial import of at
    #: least one series, INCREMENTAL otherwise. The persisted record of
    #: the #43 distinction, so "was that history imported or observed?"
    #: is answerable from the audit trail and not only from the version
    #: rows.
    import_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_received: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_measure_rows_ignored: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observations_inserted: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observations_revised: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observations_skipped_missing_value: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProviderIngestionRun(Base):
    """Increment #56A: one first-party (BLS or BEA) ingestion attempt.

    This is the provider-neutral run audit `HousingIngestionRun`'s
    docstring named as deferred work. It is used by the NEW providers
    only; Rates and Housing keep their own tables, because migrating
    their existing rows into this one is a refactor with no purpose here.

    As with every run table: counts, a status, modes and an exception
    CLASS NAME -- never a message, a URL, a response body or a key.

    `access_mode` records HOW the provider was reached (BLS keyless v1,
    BLS keyed v2, BEA flat file), because the limits and the verified
    status of each differ. `source_published_at` is the provider's own
    vintage instant where it states one (BEA's `Last-Modified`), and NULL
    where it does not -- never a guess.
    """

    __tablename__ = "provider_ingestion_runs"
    __table_args__ = (Index("ix_provider_ingestion_runs_provider_started_at", "provider", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    access_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    import_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    series_requested: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observations_received: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observations_inserted: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observations_revised: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observations_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observations_unavailable: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ObservationVersion(Base):
    """Increment #31: the append-only SYSTEM-TIME history of every value
    MacroChipz has held for one canonical observation.

    `economic_observations` remains the efficient CURRENT-state cache
    (one row per series/date, overwritten in place). This table answers
    the different question that cache structurally cannot: *what value
    did MacroChipz have recorded for this observation at time T?*

    NOT a generalized bitemporal store. `observation_date` remains the
    economic period; `recorded_from`/`recorded_to` are SYSTEM time --
    when MacroChipz considered a particular value current. Valid time in
    the source's own sense (when a value was true according to the
    provider, including publication time) is deliberately NOT modeled,
    because the providers this project uses do not publish it.

    Interval semantics are half-open, `[recorded_from, recorded_to)`:
    a version is live at T when `recorded_from <= T < recorded_to`, and
    an open version (`recorded_to IS NULL`) is live from
    `recorded_from` onward. A revision closes the open version at
    exactly the instant the new one opens, so the two never overlap and
    never leave a gap.

    Invariants enforced by the database, not merely by application code
    (see the migration): at most ONE open version per
    (series, observation_date); no two versions of the same
    (series, observation_date) sharing a `recorded_from`; and every
    closed interval strictly forward-going (`recorded_to > recorded_from`).

    `is_backfilled` marks the class of row this table cannot vouch for:
    a version whose value MacroChipz IMPORTED rather than watched
    arrive. It honestly means "this value existed in MacroChipz by this
    time" -- never "this was the value the source first published", and
    never evidence that no earlier revision occurred. Observed
    (non-backfilled) rows carry the real instant the write happened.

    Two write paths set it, and the meaning above covers both:

    - #31's migration, synthesizing versions from observations that
      predate point-in-time tracking. Their `recorded_from` is the
      observation row's own `created_at`.
    - #45's initial import of a NEW SOURCE's published history. A
      provider's 1959-2026 back history arriving in one request is
      structurally the same claim: MacroChipz knows those values as of
      the import, and knows nothing about earlier vintages of them.
      `ObservationVersionWriter(baseline=True)` writes these, and only
      for `NEW` versions -- a revision is always genuinely observed.

    `origin` records WHICH write path produced the version
    (`SERIES_SYNC`, `RELEASE_PROCESSING`, `RATES_INGESTION`,
    `HOUSING_INGESTION`, `BACKFILL`). A `release_check_run_id` FK is
    deliberately absent:
    release processing creates its check-run row only after the
    observation writes have already happened, so the id genuinely does
    not exist at write time, and restructuring that ordering purely to
    carry a nullable FK would change #18's own established sequence for
    no correctness gain. `release_observation_updates` already links a
    change to its run and remains the record for "what happened during
    this release-processing event".
    """

    __tablename__ = "observation_versions"
    __table_args__ = (
        UniqueConstraint(
            "economic_series_id", "observation_date", "recorded_from", name="uq_observation_version_series_date_from"
        ),
        Index(
            "uq_observation_version_one_open_per_series_date",
            "economic_series_id",
            "observation_date",
            unique=True,
            postgresql_where=text("recorded_to IS NULL"),
        ),
        Index("ix_observation_versions_as_of", "economic_series_id", "observation_date", "recorded_from"),
        CheckConstraint("recorded_to IS NULL OR recorded_to > recorded_from", name="ck_observation_version_interval"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    economic_series_id: Mapped[int] = mapped_column(
        ForeignKey("economic_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Nullable for the same reason `EconomicObservation.value` is: a
    # provider can legitimately publish a missing value, and a
    # transition into or out of missing is a real revision.
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_type: Mapped[str] = mapped_column(String(16), nullable=False)
    origin: Mapped[str] = mapped_column(String(24), nullable=False)
    is_backfilled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
