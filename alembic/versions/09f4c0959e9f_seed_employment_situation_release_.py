"""seed employment situation release series mappings

Revision ID: 09f4c0959e9f
Revises: cd476d227f99
Create Date: 2026-09-14 09:35:01.608413

Product-curation-only migration, mirroring cd476d227f99's own pattern
exactly: deliberately separate from the schema migration
(dbd9a2889ef3) that created `release_series_mappings`, so this one can
be downgraded (re-curated) without ever touching a table definition.

Seeds the two curated V1 mappings that give Employment Situation a
deterministic canonical consumer -- PAYEMS and UNRATE, the exact two
series `app/models/labor.py` already names as `PAYEMS_SERIES_ID`/
`UNRATE_SERIES_ID`, per the frozen contract
docs/architecture/labor-release-integration-v1.md §5. No CIVPART, no
JOLTS, no wages/claims/hours/earnings/other CES series -- none is a
`labor_v1.0` dependency.

Employment Situation's own `economic_releases.id` is looked up by its
stable provider identity (`provider`, `provider_release_id`) at
migration-run time, never hardcoded/assumed -- correct regardless of a
given database's actual row-insertion history, the same discipline
cd476d227f99 already establishes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09f4c0959e9f'
down_revision: Union[str, Sequence[str], None] = 'cd476d227f99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Lightweight, migration-local table shims -- deliberately not the real
# ORM models (app.db.models), same discipline cd476d227f99 already
# established: a data migration must stay correct even if those
# models' shapes change in the future.
economic_releases = sa.table(
    "economic_releases",
    sa.column("id", sa.Integer),
    sa.column("provider", sa.String),
    sa.column("provider_release_id", sa.String),
)

release_series_mappings = sa.table(
    "release_series_mappings",
    sa.column("economic_release_id", sa.Integer),
    sa.column("series_id", sa.String),
    sa.column("active", sa.Boolean),
)

# provider_release_id (FRED) -> the canonical series_id strings #20D.2
# checks for that release when it's processed.
CURATED_MAPPINGS: dict[str, list[str]] = {
    "50": ["PAYEMS", "UNRATE"],  # Employment Situation
}


def upgrade() -> None:
    """Insert the two approved V1 curated release->series mappings."""
    conn = op.get_bind()
    rows_to_insert = []
    for provider_release_id, series_ids in CURATED_MAPPINGS.items():
        release_id = conn.execute(
            sa.select(economic_releases.c.id).where(
                economic_releases.c.provider == "FRED",
                economic_releases.c.provider_release_id == provider_release_id,
            )
        ).scalar_one()
        for series_id in series_ids:
            rows_to_insert.append({"economic_release_id": release_id, "series_id": series_id, "active": True})
    op.bulk_insert(release_series_mappings, rows_to_insert)


def downgrade() -> None:
    """Remove ONLY the mapping rows this migration seeded, identified by
    their exact (release provider identity, series_id) pairs -- never a
    blanket DELETE FROM release_series_mappings, which could remove an
    unrelated mapping created independently of this migration."""
    conn = op.get_bind()
    for provider_release_id, series_ids in CURATED_MAPPINGS.items():
        release_id = conn.execute(
            sa.select(economic_releases.c.id).where(
                economic_releases.c.provider == "FRED",
                economic_releases.c.provider_release_id == provider_release_id,
            )
        ).scalar_one()
        for series_id in series_ids:
            conn.execute(
                release_series_mappings.delete().where(
                    release_series_mappings.c.economic_release_id == release_id,
                    release_series_mappings.c.series_id == series_id,
                )
            )
