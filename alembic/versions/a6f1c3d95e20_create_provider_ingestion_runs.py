"""create provider_ingestion_runs

Revision ID: a6f1c3d95e20
Revises: e7b3d51c8a94
Create Date: 2026-09-24 16:40:00.000000

Increment #56A's first-party (BLS/BEA) ingestion persistence.

ONE additive table, and nothing else. First-party observations need no
new storage: they are dated observations of named series, written to
`economic_series` / `economic_observations` / `observation_provenance`
/ `observation_versions` through the shared version writer, exactly as
Rates and Housing are. No existing table, column, constraint or row is
touched -- in particular, no FRED-derived row is read, relabelled or
rewritten -- so the downgrade is a clean drop.

`provider_ingestion_runs` is the provider-neutral run audit #45 named
as deferred work. It records that an ingestion was attempted and how it
ended: counts, statuses, modes and an exception class name. Never a
payload, a response body, a URL or a credential.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a6f1c3d95e20"
down_revision: Union[str, Sequence[str], None] = "e7b3d51c8a94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("dataset", sa.String(length=64), nullable=False),
        sa.Column("access_mode", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("import_mode", sa.String(length=24), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("series_requested", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observations_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observations_inserted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observations_revised", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observations_unchanged", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observations_unavailable", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_class", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_ingestion_runs_provider_started_at",
        "provider_ingestion_runs",
        ["provider", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_provider_ingestion_runs_provider_started_at", table_name="provider_ingestion_runs")
    op.drop_table("provider_ingestion_runs")
