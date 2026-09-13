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
