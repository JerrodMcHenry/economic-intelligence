"""Increment #56A: imported BLS/BEA rows change no public response.

The strongest form of "API contracts unchanged": import real first-party
history into the test database while the FRED rows are EMPTY, then read
the Inflation and Jobs monitors. If any reader resolved the new rows,
these monitors would suddenly have data. They must still report exactly
what they reported before the import.
"""

from datetime import date

import pytest

from app.clients.provider_observation import FirstPartyObservation
from app.models.first_party import FIRST_PARTY_CONCEPT_IDS
from tests.integration.test_first_party_ingestion import StubBEA, StubBLS


def _full_bea_history():
    """115 months (2017-01..2026-07), enough for every Inflation window --
    so if a reader DID resolve these rows, the monitor would compute."""
    months = [date(year, month, 1) for year in range(2017, 2027) for month in range(1, 13)][:115]
    return {
        "DPCERG": [FirstPartyObservation(m, 100.0 + i * 0.2) for i, m in enumerate(months)],
        "DPCCRG": [FirstPartyObservation(m, 100.0 + i * 0.25) for i, m in enumerate(months)],
    }

pytestmark = pytest.mark.api

MONITOR_PATHS = [
    "/api/v1/monitors/inflation",
    "/api/v1/monitors/labor",
    "/api/v1/monitors/inflation/changes",
    "/api/v1/monitors/labor/changes",
    "/api/v1/monitors/inflation/state-duration",
    "/api/v1/monitors/labor/state-duration",
    "/api/v1/since-last-visit",
    "/api/v1/intelligence?limit=100",
]


def _stable(body):
    """Drop fields that legitimately differ between two reads (clock)."""
    if isinstance(body, dict):
        return {k: _stable(v) for k, v in body.items() if k not in {"generated_at", "as_of", "computed_at", "through"}}
    if isinstance(body, list):
        return [_stable(item) for item in body]
    return body


def test_monitors_and_intelligence_are_identical_before_and_after_an_import(client, seed_session):
    from app.services.first_party_ingestion import FirstPartyIngestionService

    before = {path: (client.get(path).status_code, _stable(client.get(path).json())) for path in MONITOR_PATHS}

    FirstPartyIngestionService(StubBLS(), StubBEA(data=_full_bea_history())).import_history(seed_session, as_of=date(2026, 9, 24))
    seed_session.commit()

    after = {path: (client.get(path).status_code, _stable(client.get(path).json())) for path in MONITOR_PATHS}
    assert after == before

    # And the rows really were there to be (wrongly) read.
    for concept_id in FIRST_PARTY_CONCEPT_IDS:
        assert client.get(f"/api/v1/series/{concept_id}/observations?limit=1").status_code == 200

    # `seed_session`'s cleanup truncates the series tables; the run audit
    # is this test's own to remove.
    from sqlalchemy import delete

    from app.db.models import ProviderIngestionRun

    seed_session.execute(delete(ProviderIngestionRun))
    seed_session.commit()
