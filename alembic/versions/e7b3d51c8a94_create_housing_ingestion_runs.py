"""create housing_ingestion_runs

Revision ID: e7b3d51c8a94
Revises: d4a2c19e37b5
Create Date: 2026-09-21 18:05:00.000000

Increment #45's Housing World foundation persistence.

ONE additive table, and nothing else. No existing table, column,
constraint or row is touched, so every pre-#45 observation keeps its
exact current meaning and the downgrade is a clean drop.

Housing needs NO new observation storage. A Census New Residential
Construction figure is a dated observation of a named series, which is
precisely what `economic_series` / `economic_observations` already
model; its retrieval facts go in `observation_provenance` and its
system-time history in `observation_versions`, both unchanged. That is
the point of #31's shared writer -- a new provider joins the existing
versioning rather than building its own history, so Housing
participates in point-in-time replay and Revision Intelligence on day
one without a single Housing-specific history table.

`housing_ingestion_runs` records that an ingestion was ATTEMPTED and
how it ended -- counts, a status, an import mode and an exception class
name only. Never an upstream payload, never a response body, and never
a request URL: Census is the first provider here whose request URL
carries a credential, so this table is deliberately incapable of
holding one.

`import_mode` persists the #43 distinction. `BASELINE_BACKFILL` means
this run imported a series' published history at one instant and
therefore cannot speak to earlier provider vintages of those months;
`INCREMENTAL` means the series already existed and the run observed
what changed. Without this column, "was that sixty years of history
watched or imported?" would be answerable only by inspecting individual
version rows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7b3d51c8a94"
down_revision: Union[str, Sequence[str], None] = "d4a2c19e37b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "housing_ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("dataset", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("import_mode", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("rows_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_rejected", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_measure_rows_ignored", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observations_inserted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observations_revised", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observations_skipped_missing_value", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_class", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_housing_ingestion_runs_started_at", "housing_ingestion_runs", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_housing_ingestion_runs_started_at", table_name="housing_ingestion_runs")
    op.drop_table("housing_ingestion_runs")
