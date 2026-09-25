"""first-party release catalog: BLS and BEA releases replace FRED's

Revision ID: b8d2e4f60a17
Revises: a6f1c3d95e20
Create Date: 2026-09-24 18:10:00.000000

Increment #56B. Release processing is triggered by release occurrences
and fetches the series MAPPED to each release. Until now both came from
FRED: FRED release ids 10/54/50 mapped to FRED series ids. With the
Inflation and Jobs bindings activated on the BLS and BEA rows, this
migration moves the catalog to match:

- three releases, named as their publishers name them, with the
  publisher as `provider`:
  - BLS `cpi` (Consumer Price Index);
  - BLS `empsit` (The Employment Situation);
  - BEA `pio` (Personal Income and Outlays);
- mappings from each to the concept-keyed storage ids, pairing exactly
  as FRED's did (CPI: headline + core CPI; Employment Situation:
  payrolls + unemployment; PIO: headline + core PCE);
- every FRED release and FRED-id mapping DEACTIVATED -- not deleted.
  Their occurrences, check runs and recorded results are history and
  stay exactly as they are; they simply stop being scheduled work.

Occurrence dates are NOT seeded here. They change every year, so they
live in `app/models/release_schedule.py` and are written by
`python -m app.operations.release_schedule` (and at the start of every
maintenance run), idempotently.

Concept ids are written as literals, not imported from the live binding
table: a migration must mean the same thing forever.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8d2e4f60a17"
down_revision: Union[str, Sequence[str], None] = "a6f1c3d95e20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RELEASES = (
    ("Consumer Price Index", "BLS", "cpi", "https://www.bls.gov/cpi/"),
    ("Employment Situation", "BLS", "empsit", "https://www.bls.gov/ces/"),
    ("Personal Income and Outlays", "BEA", "pio", "https://www.bea.gov/data/income-saving/personal-income"),
)

_MAPPINGS = {
    ("BLS", "cpi"): ("us.cpi.headline.price-index.sa.monthly", "us.cpi.core.price-index.sa.monthly"),
    ("BLS", "empsit"): ("us.nonfarm.payroll-employment.sa.monthly", "us.unemployment-rate.sa.monthly"),
    ("BEA", "pio"): ("us.pce.headline.price-index.sa.monthly", "us.pce.core.price-index.sa.monthly"),
}


def upgrade() -> None:
    connection = op.get_bind()
    for name, provider, provider_release_id, official_url in _RELEASES:
        connection.execute(
            sa.text(
                "INSERT INTO economic_releases (name, provider, provider_release_id, official_url, active) "
                "VALUES (:name, :provider, :pid, :url, true) "
                "ON CONFLICT (provider, provider_release_id) DO UPDATE SET active = true"
            ),
            {"name": name, "provider": provider, "pid": provider_release_id, "url": official_url},
        )
        release_id = connection.execute(
            sa.text("SELECT id FROM economic_releases WHERE provider = :provider AND provider_release_id = :pid"),
            {"provider": provider, "pid": provider_release_id},
        ).scalar_one()
        for series_id in _MAPPINGS[(provider, provider_release_id)]:
            connection.execute(
                sa.text(
                    "INSERT INTO release_series_mappings (economic_release_id, series_id, active) "
                    "VALUES (:release_id, :series_id, true) "
                    "ON CONFLICT (economic_release_id, series_id) DO UPDATE SET active = true"
                ),
                {"release_id": release_id, "series_id": series_id},
            )

    connection.execute(
        sa.text(
            "UPDATE release_series_mappings SET active = false WHERE economic_release_id IN "
            "(SELECT id FROM economic_releases WHERE provider = 'FRED')"
        )
    )
    connection.execute(sa.text("UPDATE economic_releases SET active = false WHERE provider = 'FRED'"))


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE economic_releases SET active = true WHERE provider = 'FRED'"))
    connection.execute(
        sa.text(
            "UPDATE release_series_mappings SET active = true WHERE economic_release_id IN "
            "(SELECT id FROM economic_releases WHERE provider = 'FRED')"
        )
    )
    # DEACTIVATE the first-party catalog, never delete it: deleting a
    # release cascades through its occurrences and check runs to
    # `recorded_monitor_results`, which are non-reconstructable history
    # (ADR-025). Re-upgrading reactivates the same rows via ON CONFLICT.
    connection.execute(
        sa.text(
            "UPDATE release_series_mappings SET active = false WHERE economic_release_id IN "
            "(SELECT id FROM economic_releases WHERE provider IN ('BLS', 'BEA'))"
        )
    )
    connection.execute(sa.text("UPDATE economic_releases SET active = false WHERE provider IN ('BLS', 'BEA')"))
