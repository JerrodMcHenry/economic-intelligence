"""Add economic concept identity to persisted series (Increment #38, ADR-034).

One additive, nullable column. No observation value, observation date,
provenance row or version row is read or written by this migration --
it records which CONCEPT an already-persisted series belongs to, and
nothing else.

Why nullable, permanently:

`POST /api/v1/series/{series_id}/sync` accepts any FRED series a caller
names, and those are not canonical MacroChipz concepts. Forcing the
column NOT NULL would either break that endpoint or require inventing a
concept for every arbitrary series someone syncs -- which is exactly the
fabricated identity ADR-034 exists to prevent. So: canonical methodology
paths REQUIRE a concept and fail loudly without one; the generic series
endpoints neither require nor care.

Backfill is deterministic and refuses to guess. Each stored series is
mapped only where `app.concepts.bindings` declares an explicit binding
whose `equivalence_basis` cites the frozen methodology that already uses
that series for that role. A stored series with no binding is left NULL
-- never matched on a display label, never inferred from a title.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a2c19e37b5"
down_revision: Union[str, Sequence[str], None] = "c3f8a1d47b62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("economic_series", sa.Column("concept_id", sa.String(length=128), nullable=True))
    op.create_index("ix_economic_series_concept_id", "economic_series", ["concept_id"])

    # Imported inside the function so the module still imports in an
    # environment where the application package is unavailable, and so
    # the binding table is read at migration time rather than baked in.
    from app.concepts.bindings import BINDINGS

    connection = op.get_bind()
    for binding in BINDINGS:
        connection.execute(
            sa.text(
                "UPDATE economic_series SET concept_id = :concept_id "
                "WHERE series_id = :storage_series_id AND concept_id IS NULL"
            ),
            {"concept_id": binding.concept_id, "storage_series_id": binding.storage_series_id},
        )


def downgrade() -> None:
    op.drop_index("ix_economic_series_concept_id", table_name="economic_series")
    op.drop_column("economic_series", "concept_id")
