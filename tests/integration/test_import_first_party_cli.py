"""Increment #56A: `python -m app.operations.import_first_party`.

Called as `main(argv)` against the isolated test database through the
REAL `session_scope()` (the `process_release` CLI tests' pattern), with
the provider clients patched at their method boundary -- never a live
request. Rows are committed for real, so each test removes what it wrote.
"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import delete, select

from app.clients.bea import BEAClient
from app.clients.bls import BLSClient, parse_response
from app.clients.bounded_http import ProviderTimeoutError
from app.clients.provider_observation import FirstPartyObservation
from app.db.models import EconomicSeries, ProviderIngestionRun
from app.models.first_party import FIRST_PARTY_CONCEPT_IDS
from app.operations.import_first_party import main

pytestmark = pytest.mark.integration

BLS_RESPONSE = json.loads((Path(__file__).parent.parent / "fixtures" / "bls_v1_2017_2026.json").read_text())
BLS_IDS = ["CUSR0000SA0", "CUSR0000SA0L1E", "CES0000000001", "LNS14000000"]
BEA_DATA = {
    "DPCERG": [FirstPartyObservation(date(2026, 7, 1), 131.659)],
    "DPCCRG": [FirstPartyObservation(date(2026, 7, 1), 130.658)],
}


@pytest.fixture
def configured(monkeypatch, test_database_url):
    from app.core.config import settings
    from app.db import session as session_module

    monkeypatch.setattr(settings, "database_url", test_database_url)
    monkeypatch.setattr(settings, "bls_api_key", None)
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()
    yield
    from app.db.session import session_scope

    with session_scope() as session:
        session.execute(delete(ProviderIngestionRun))
        session.execute(delete(EconomicSeries).where(EconomicSeries.series_id.in_(FIRST_PARTY_CONCEPT_IDS)))
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()


def _providers(bls_raises=None):
    def get_monthly(self, series_ids, start_year, end_year):
        if bls_raises:
            raise bls_raises
        return parse_response(BLS_RESPONSE, list(series_ids))

    return (
        patch.object(BLSClient, "get_monthly", get_monthly),
        patch.object(BEAClient, "get_nipa_monthly", lambda self, codes, start: (BEA_DATA, None)),
    )


def test_a_successful_import_exits_zero_and_commits(configured, capsys):
    bls_patch, bea_patch = _providers()
    with bls_patch, bea_patch:
        assert main(["--as-of-date", "2026-09-24"]) == 0

    out = capsys.readouterr().out
    assert "BLS [KEYLESS_V1] SUCCEEDED BASELINE_BACKFILL 2017-01-01..2026-09-24" in out
    assert "CES0000000001" in out and "DPCERG" in out

    from app.db.session import session_scope

    with session_scope() as session:
        stored = session.execute(
            select(EconomicSeries.series_id).where(EconomicSeries.series_id.in_(FIRST_PARTY_CONCEPT_IDS))
        ).scalars().all()
        assert sorted(stored) == sorted(FIRST_PARTY_CONCEPT_IDS)


def test_a_rerun_is_incremental_and_changes_nothing(configured, capsys):
    bls_patch, bea_patch = _providers()
    with bls_patch, bea_patch:
        assert main(["--as-of-date", "2026-09-24"]) == 0
        capsys.readouterr()
        assert main(["--as-of-date", "2026-09-24"]) == 0

    out = capsys.readouterr().out
    assert "INCREMENTAL" in out and "BASELINE_BACKFILL" not in out
    assert "inserted=0 revised=0" in out


def test_a_provider_failure_exits_one_and_keeps_the_other(configured, capsys):
    bls_patch, bea_patch = _providers(bls_raises=ProviderTimeoutError("BLS", "timed out"))
    with bls_patch, bea_patch:
        assert main(["--as-of-date", "2026-09-24"]) == 1

    out = capsys.readouterr().out
    assert "BLS [KEYLESS_V1] FAILED" in out and "error=ProviderTimeoutError" in out
    assert "BEA [FLAT_FILE] SUCCEEDED" in out


def test_keyless_more_than_ten_years_is_refused_before_any_request(configured, capsys):
    bls_patch, bea_patch = _providers()
    with bls_patch as bls_mock, bea_patch:
        assert main(["--years", "11"]) == 2
    assert "BLS_API_KEY" in capsys.readouterr().err
    del bls_mock


def test_no_database_is_an_operational_failure(monkeypatch, capsys):
    from app.core.config import settings

    monkeypatch.setattr(settings, "database_url", None)
    assert main([]) == 2
    assert "database is not configured" in capsys.readouterr().err


def test_the_key_is_never_printed(configured, monkeypatch, capsys):
    from app.core.config import settings

    sentinel = "synthetic-bls-key-0000000000000000"
    monkeypatch.setattr(settings, "bls_api_key", sentinel)
    bls_patch, bea_patch = _providers()
    with bls_patch, bea_patch:
        assert main(["--as-of-date", "2026-09-24"]) == 0
    captured = capsys.readouterr()
    assert sentinel not in captured.out + captured.err
    assert "BLS [KEYED_V2]" in captured.out
