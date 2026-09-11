"""SQLAlchemy ORM models for persisted economic data.

Distinct from `app/models/series.py`, which defines the application's
*API* response contract (Pydantic). These classes define the *relational*
shape of the data as stored in PostgreSQL.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint, func
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
