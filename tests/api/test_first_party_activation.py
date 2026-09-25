"""Increment #56B: the public monitors read BLS and BEA, and say so.

The #56A version of this file proved the imported rows were INERT. #56B
activated them, so it now proves the opposite, end to end through the
HTTP API: with only first-party data in the database, the Inflation and
Jobs monitors compute, and every evidence item names the AGENCY's own
series id and provider -- never FRED, never a storage key.
"""

from datetime import date

import pytest

from app.clients.provider_observation import FirstPartyObservation
from tests.integration.test_first_party_ingestion import StubBEA, StubBLS

pytestmark = pytest.mark.api

AGENCY_SERIES_IDS = {"CUSR0000SA0", "CUSR0000SA0L1E", "CES0000000001", "LNS14000000", "DPCERG", "DPCCRG"}


def _full_bea_history():
    """115 months (2017-01..2026-07), enough for every Inflation window."""
    months = [date(year, month, 1) for year in range(2017, 2027) for month in range(1, 13)][:115]
    return {
        "DPCERG": [FirstPartyObservation(m, 100.0 + i * 0.2) for i, m in enumerate(months)],
        "DPCCRG": [FirstPartyObservation(m, 100.0 + i * 0.25) for i, m in enumerate(months)],
    }


def _evidence(body, found=None):
    """Every (provider, series_id) pair anywhere in a response."""
    found = set() if found is None else found
    if isinstance(body, dict):
        if "provider" in body and "series_id" in body:
            found.add((body["provider"], body["series_id"]))
        for value in body.values():
            _evidence(value, found)
    elif isinstance(body, list):
        for item in body:
            _evidence(item, found)
    return found


def test_the_monitors_compute_from_bls_and_bea_and_name_the_agency_series(client, seed_session):
    from sqlalchemy import delete

    from app.db.models import ProviderIngestionRun
    from app.services.first_party_ingestion import FirstPartyIngestionService

    before = {path: client.get(path).json() for path in ("/api/v1/monitors/inflation", "/api/v1/monitors/labor")}

    FirstPartyIngestionService(StubBLS(), StubBEA(data=_full_bea_history())).import_history(
        seed_session, as_of=date(2026, 9, 24)
    )
    seed_session.commit()
    try:
        inflation = client.get("/api/v1/monitors/inflation").json()
        labor = client.get("/api/v1/monitors/labor").json()

        # They compute now -- the imported rows are what they read.
        assert inflation != before["/api/v1/monitors/inflation"]
        assert labor != before["/api/v1/monitors/labor"]

        evidence = _evidence(inflation) | _evidence(labor)
        assert evidence, "the monitors returned no evidence at all"
        assert {provider for provider, _ in evidence} <= {"BLS", "BEA"}
        assert {series_id for _, series_id in evidence} <= AGENCY_SERIES_IDS
        assert ("BLS", "CES0000000001") in evidence and ("BEA", "DPCCRG") in evidence
    finally:
        seed_session.execute(delete(ProviderIngestionRun))
        seed_session.commit()
