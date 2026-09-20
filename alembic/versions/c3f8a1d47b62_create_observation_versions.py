"""create observation_versions and backfill current observations

Revision ID: c3f8a1d47b62
Revises: b7c41d92e8a3
Create Date: 2026-09-20 09:10:00.000000

Increment #31's system-time observation versioning (see
docs/methodology/observation-versioning-v1.md and ADR-030).

Additive: `economic_observations` is untouched and remains the current-
state cache. This table records every value MacroChipz has held for an
observation over SYSTEM time, with half-open `[recorded_from,
recorded_to)` intervals.

Three invariants are enforced by PostgreSQL rather than by application
code alone:

- a partial unique index gives AT MOST ONE open version per
  (series, observation_date);
- a unique constraint forbids two versions of the same
  (series, observation_date) starting at the same instant;
- a check constraint forbids a closed interval that does not move
  forward in time.

The data migration backfills one OPEN version per existing observation,
with `recorded_from = economic_observations.created_at` and
`is_backfilled = true`. That timestamp honestly means "this value
existed in MacroChipz by then". It is NOT evidence that the value was
the source's first publication, and NOT evidence that no earlier
revision occurred -- `economic_observations` has no `updated_at`, so a
pre-#31 in-place revision left no trace anywhere except (for FRED series
processed through release processing) `release_observation_updates`.
This migration deliberately does not attempt to reconstruct vintages
from that log: a partial reconstruction presented as history would be
worse than an honestly-marked backfill.

Downgrade drops the table outright, which loses version history but
restores the pre-#31 schema exactly; no other table is modified, so
nothing else is affected.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3f8a1d47b62"
down_revision: Union[str, Sequence[str], None] = "b7c41d92e8a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "observation_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("economic_series_id", sa.Integer(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("recorded_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_type", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=24), nullable=False),
        sa.Column("is_backfilled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["economic_series_id"], ["economic_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "economic_series_id", "observation_date", "recorded_from", name="uq_observation_version_series_date_from"
        ),
        sa.CheckConstraint("recorded_to IS NULL OR recorded_to > recorded_from", name="ck_observation_version_interval"),
    )
    op.create_index(
        op.f("ix_observation_versions_economic_series_id"), "observation_versions", ["economic_series_id"], unique=False
    )
    op.create_index(
        "ix_observation_versions_as_of",
        "observation_versions",
        ["economic_series_id", "observation_date", "recorded_from"],
        unique=False,
    )
    # The invariant that matters most: one open version per observation.
    op.create_index(
        "uq_observation_version_one_open_per_series_date",
        "observation_versions",
        ["economic_series_id", "observation_date"],
        unique=True,
        postgresql_where=sa.text("recorded_to IS NULL"),
    )

    # Backfill: one open, explicitly-marked version per existing
    # observation. `created_at` is the most defensible timestamp the
    # current schema offers -- see this migration's own docstring for
    # exactly what it does and does not prove.
    op.execute(
        sa.text(
            """
            INSERT INTO observation_versions (
                economic_series_id, observation_date, value,
                recorded_from, recorded_to, change_type, origin, is_backfilled
            )
            SELECT
                economic_series_id, observation_date, value,
                created_at, NULL, 'BACKFILL', 'BACKFILL', true
            FROM economic_observations
            """
        )
    )


def downgrade() -> None:
    op.drop_index("uq_observation_version_one_open_per_series_date", table_name="observation_versions")
    op.drop_index("ix_observation_versions_as_of", table_name="observation_versions")
    op.drop_index(op.f("ix_observation_versions_economic_series_id"), table_name="observation_versions")
    op.drop_table("observation_versions")
