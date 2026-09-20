"""create observation_provenance and rates_ingestion_runs

Revision ID: b7c41d92e8a3
Revises: f5420059a092
Create Date: 2026-09-19 16:40:00.000000

Increment #29's Rates Intelligence foundation persistence (see
docs/methodology/rates-v1.0.md).

Two additive tables; no existing table, column, constraint, or row is
touched, so every pre-#29 observation keeps its exact current meaning
and the downgrade is a clean drop.

`observation_provenance` records where one persisted
`EconomicObservation` came from and whether the provider has since
revised it -- one row per (series, observation_date), the same grain as
the observation. It is deliberately NOT columns on
`economic_observations`: provenance describes the retrieval event, not
the economic fact, and pre-#29 rows legitimately have none. A missing
row means "not recorded", never a silently assumed source.

`rates_ingestion_runs` records that an ingestion was ATTEMPTED and how
it ended -- counts and an exception class name only, never an upstream
payload -- mirroring `release_check_runs`' role for release processing.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c41d92e8a3"
down_revision: Union[str, Sequence[str], None] = "f5420059a092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "observation_provenance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("economic_series_id", sa.Integer(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("dataset", sa.String(length=64), nullable=False),
        sa.Column("source_series_field", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_revised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["economic_series_id"], ["economic_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("economic_series_id", "observation_date", name="uq_observation_provenance_series_date"),
    )
    op.create_index(
        op.f("ix_observation_provenance_economic_series_id"),
        "observation_provenance",
        ["economic_series_id"],
        unique=False,
    )
    op.create_index(
        "ix_observation_provenance_provider_dataset",
        "observation_provenance",
        ["provider", "dataset"],
        unique=False,
    )

    op.create_table(
        "rates_ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("datasets_requested", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("observations_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observations_inserted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observations_revised", sa.Integer(), server_default="0", nullable=False),
        sa.Column("datasets_failed", sa.String(length=255), nullable=True),
        sa.Column("error_class", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rates_ingestion_runs_started_at", "rates_ingestion_runs", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rates_ingestion_runs_started_at", table_name="rates_ingestion_runs")
    op.drop_table("rates_ingestion_runs")
    op.drop_index("ix_observation_provenance_provider_dataset", table_name="observation_provenance")
    op.drop_index(op.f("ix_observation_provenance_economic_series_id"), table_name="observation_provenance")
    op.drop_table("observation_provenance")
