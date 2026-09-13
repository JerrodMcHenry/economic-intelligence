"""seed curated v1 release catalog

Revision ID: fbbe6b1ab8d9
Revises: 42114760e4c8
Create Date: 2026-09-13 12:53:14.074811

Product-curation-only migration: seeds the six approved V1 curated
EconomicRelease rows (see docs/ENGINEERING_JOURNAL.md's Increment #17A
follow-up entry for how these provider_release_id values were
verified -- against official/current FRED release pages, not guessed
and not discovered dynamically). Deliberately kept separate from the
schema migration (42114760e4c8) that created
economic_releases/release_occurrences -- schema creation and product
curation are different kinds of change, so this one can be downgraded
(re-curated) without ever touching a table definition, and the schema
migration remains untouched, immutable history.

No FRED call, no dynamic discovery, no environment read -- every
seeded value below is a literal, reviewed constant. Creates no
ReleaseOccurrence rows (occurrences only ever come from an explicit
sync, never a migration) and touches no other table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbbe6b1ab8d9'
down_revision: Union[str, Sequence[str], None] = '42114760e4c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# A lightweight, migration-local table shim -- deliberately not the
# real ORM model (app.db.models.EconomicRelease). A data migration must
# stay correct even if that model's shape changes in the future; it
# describes only the columns this migration actually touches.
economic_releases = sa.table(
    "economic_releases",
    sa.column("name", sa.String),
    sa.column("provider", sa.String),
    sa.column("provider_release_id", sa.String),
    sa.column("official_url", sa.String),
    sa.column("active", sa.Boolean),
)

# The approved V1 curated catalog -- exactly these six, nothing else.
# FOMC, PPI, Industrial Production, housing releases, and Initial
# Claims are deliberately not included; they may be curated later in a
# separate migration.
CURATED_RELEASES = [
    {
        "name": "Consumer Price Index",
        "provider": "FRED",
        "provider_release_id": "10",
        "official_url": None,
        "active": True,
    },
    {
        "name": "Personal Income and Outlays",
        "provider": "FRED",
        "provider_release_id": "54",
        "official_url": None,
        "active": True,
    },
    {
        "name": "Employment Situation",
        "provider": "FRED",
        "provider_release_id": "50",
        "official_url": None,
        "active": True,
    },
    {
        "name": "Job Openings and Labor Turnover Survey",
        "provider": "FRED",
        "provider_release_id": "192",
        "official_url": None,
        "active": True,
    },
    {
        "name": "Gross Domestic Product",
        "provider": "FRED",
        "provider_release_id": "53",
        "official_url": None,
        "active": True,
    },
    {
        "name": "Advance Monthly Sales for Retail and Food Services",
        "provider": "FRED",
        "provider_release_id": "9",
        "official_url": None,
        "active": True,
    },
]


def upgrade() -> None:
    """Insert the six approved V1 curated releases. Relies on the
    existing UNIQUE(provider, provider_release_id) constraint (from
    42114760e4c8) to fail loudly rather than silently duplicate if this
    migration is ever mis-applied twice against the same database."""
    op.bulk_insert(economic_releases, CURATED_RELEASES)


def downgrade() -> None:
    """Remove ONLY the six rows this migration seeded, identified by
    their exact (provider, provider_release_id) pairs -- never a
    blanket DELETE FROM economic_releases, which could remove an
    unrelated release row created independently of this migration.

    If any release_occurrences rows exist for one of these releases by
    the time this runs, the existing ON DELETE CASCADE foreign key
    (from 42114760e4c8) removes them along with the release -- expected,
    documented behavior of that already-established constraint, not
    something this migration adds. Isolated verification of this
    migration is expected to run with zero occurrences present.
    """
    conn = op.get_bind()
    for release in CURATED_RELEASES:
        conn.execute(
            economic_releases.delete().where(
                economic_releases.c.provider == release["provider"],
                economic_releases.c.provider_release_id == release["provider_release_id"],
            )
        )
