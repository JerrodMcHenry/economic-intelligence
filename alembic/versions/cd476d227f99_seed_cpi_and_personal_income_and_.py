"""seed CPI and Personal Income and Outlays release series mappings

Revision ID: cd476d227f99
Revises: dbd9a2889ef3
Create Date: 2026-09-13 15:36:39.409820

Product-curation-only migration, mirroring fbbe6b1ab8d9's own pattern:
deliberately separate from the schema migration (dbd9a2889ef3) that
created `release_series_mappings`, so this one can be downgraded
(re-curated) without ever touching a table definition.

Seeds ONLY the two curated V1 releases whose series already have a
deterministic canonical consumer in this repository -- Consumer Price
Index (CPIAUCSL, CPILFESL) and Personal Income and Outlays (PCEPI,
PCEPILFE), the exact four series `app/models/inflation.py` already
names as `HEADLINE_CPI_SERIES_ID`/`CONFIRMATION_SERIES_ID`/
`TARGET_SERIES_ID`/`PRIMARY_SERIES_ID`. Employment Situation, JOLTS,
GDP, and Advance Monthly Sales for Retail and Food Services are
deliberately NOT seeded here -- they have no canonical Inflation
Monitor (or any other deterministic monitor) consumer yet; seeding a
mapping for them now would mean release processing fetches and
persists observations with no deterministic analytical consequence
ever computed from them, exactly the "ingest arbitrary series merely
because their release exists" #18 V1 is scoped not to do.

Each release's real `economic_releases.id` is looked up by its stable
provider identity (`provider`, `provider_release_id`) at migration-run
time, never hardcoded/assumed -- correct regardless of a given
database's actual row-insertion history.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd476d227f99'
down_revision: Union[str, Sequence[str], None] = 'dbd9a2889ef3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Lightweight, migration-local table shims -- deliberately not the real
# ORM models (app.db.models), same discipline fbbe6b1ab8d9 already
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

# provider_release_id (FRED) -> the canonical series_id strings #18 V1
# checks for that release when it's processed.
CURATED_MAPPINGS: dict[str, list[str]] = {
    "10": ["CPIAUCSL", "CPILFESL"],  # Consumer Price Index
    "54": ["PCEPI", "PCEPILFE"],  # Personal Income and Outlays
}


def upgrade() -> None:
    """Insert the four approved V1 curated release->series mappings."""
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
