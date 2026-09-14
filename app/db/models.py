"""SQLAlchemy ORM models for persisted economic data.

Distinct from `app/models/series.py`, which defines the application's
*API* response contract (Pydantic). These classes define the *relational*
shape of the data as stored in PostgreSQL.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, UniqueConstraint, func
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
