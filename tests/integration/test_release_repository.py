"""Integration tests for ReleaseRepository against a real, isolated
PostgreSQL test database (see tests/conftest.py for the safety guard
and rollback-isolated `db_session` fixture this relies on).

No FastAPI, no OpenAI, no live FRED -- ReleaseRepository has no
dependency on any of them (checked structurally by
tests/integration/test_transaction_and_safety.py). Curated releases are
created directly via the ORM here (there is no repository "create
release" method -- the frozen catalog is meant to be migration-seeded,
not written by application code).

The six releases seeded by
alembic/versions/fbbe6b1ab8d9_seed_curated_v1_release_catalog.py
(provider_release_id 9/10/50/53/54/192) are real, persistent, *active*
data in the isolated test database this file runs against -- every
release this file creates uses a provider_release_id well outside that
range ("9001"+) so it never collides with the real
UNIQUE(provider, provider_release_id) constraint, and any test that
calls `get_active_releases()` explicitly deactivates the curated
catalog first (safe: `db_session` rolls the whole transaction back at
teardown, so this never leaks into another test).
"""

from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.db.models import EconomicRelease, ReleaseOccurrence
from app.repositories.release_repository import ReleaseRepository

JAN, FEB, MAR = (date(2026, m, 1) for m in range(1, 4))


def _release(session, name="Test Release", provider="FRED", provider_release_id="9001", active=True):
    release = EconomicRelease(name=name, provider=provider, provider_release_id=provider_release_id, active=active)
    session.add(release)
    session.flush()
    return release


def _deactivate_curated_releases(session):
    """See this module's docstring: isolates a `get_active_releases()`
    test from the real, migration-seeded curated catalog, which is
    active by default."""
    session.execute(update(EconomicRelease).values(active=False))
    session.flush()


class TestActiveReleaseCatalog:
    def test_returns_only_active_releases_in_deterministic_name_order(self, db_session):
        _deactivate_curated_releases(db_session)
        _release(db_session, name="Zeta Release", provider_release_id="9101")
        _release(db_session, name="Alpha Release", provider_release_id="9102")
        _release(db_session, name="Inactive Release", provider_release_id="9103", active=False)

        active = ReleaseRepository(db_session).get_active_releases()

        assert [r.name for r in active] == ["Alpha Release", "Zeta Release"]

    def test_no_active_releases_returns_empty_list(self, db_session):
        _deactivate_curated_releases(db_session)
        assert ReleaseRepository(db_session).get_active_releases() == []

    def test_the_active_catalog_is_the_publishers_own_releases(self, db_session):
        """#56B: BLS CPI, BLS Employment Situation and BEA Personal Income
        and Outlays are the active catalog; the six FRED rows the
        original migration seeded are kept -- their occurrences are
        history -- but INACTIVE."""
        active = ReleaseRepository(db_session).get_active_releases()
        assert sorted((r.provider, r.provider_release_id, r.name) for r in active) == [
            ("BEA", "pio", "Personal Income and Outlays"),
            ("BLS", "cpi", "Consumer Price Index"),
            ("BLS", "empsit", "Employment Situation"),
        ]
        fred = db_session.execute(sa.select(EconomicRelease).where(EconomicRelease.provider == "FRED")).scalars().all()
        assert sorted(r.provider_release_id for r in fred) == sorted(["9", "10", "50", "53", "54", "192"])
        assert not any(r.active for r in fred)


class TestProviderIdentityLookup:
    def test_finds_release_by_provider_identity(self, db_session):
        _release(db_session, name="Custom Release", provider_release_id="9001")
        found = ReleaseRepository(db_session).get_release_by_provider_identity("FRED", "9001")
        assert found is not None
        assert found.name == "Custom Release"

    def test_finds_a_real_curated_release_by_provider_identity(self, db_session):
        found = ReleaseRepository(db_session).get_release_by_provider_identity("BLS", "cpi")
        assert found is not None
        assert found.name == "Consumer Price Index"
        assert found.active is True
        retired = ReleaseRepository(db_session).get_release_by_provider_identity("FRED", "10")
        assert retired is not None and retired.active is False

    def test_unknown_provider_identity_returns_none(self, db_session):
        assert ReleaseRepository(db_session).get_release_by_provider_identity("FRED", "999999") is None

    def test_unique_provider_identity_is_enforced_at_the_db_level(self, db_session):
        _release(db_session, provider_release_id="9001")
        db_session.add(EconomicRelease(name="Duplicate", provider="FRED", provider_release_id="9001"))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_unique_provider_identity_is_enforced_against_the_curated_catalog_too(self, db_session):
        """The constraint doesn't distinguish "migration-seeded" from
        "application-inserted" -- a duplicate of a real curated
        identity is rejected exactly the same way."""
        db_session.add(EconomicRelease(name="Duplicate CPI", provider="FRED", provider_release_id="10"))
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestOccurrenceUpsert:
    def test_inserts_new_occurrence_with_matching_first_and_last_seen_at(self, db_session):
        release = _release(db_session)
        occurrence = ReleaseRepository(db_session).upsert_occurrence(release.id, JAN)
        assert occurrence.scheduled_date == JAN
        assert occurrence.first_seen_at == occurrence.last_seen_at

    def test_duplicate_upsert_is_idempotent_no_new_row(self, db_session):
        release = _release(db_session)
        repo = ReleaseRepository(db_session)
        repo.upsert_occurrence(release.id, JAN)
        repo.upsert_occurrence(release.id, JAN)
        db_session.flush()

        _, total = repo.list_occurrences(start_date=None, end_date=None, limit=100, offset=0, order="asc")
        assert total == 1

    def test_first_seen_at_is_preserved_across_repeated_upserts(self, db_session):
        release = _release(db_session)
        repo = ReleaseRepository(db_session)
        first = repo.upsert_occurrence(release.id, JAN)
        first_seen = first.first_seen_at

        again = repo.upsert_occurrence(release.id, JAN)
        assert again.first_seen_at == first_seen

    def test_last_seen_at_is_refreshed_on_repeated_upsert(self, db_session):
        release = _release(db_session)
        repo = ReleaseRepository(db_session)
        first = repo.upsert_occurrence(release.id, JAN)
        # Roll the timestamp backward so the refresh is unambiguously
        # observable, rather than depending on real wall-clock
        # granularity between two calls in the same test.
        first.last_seen_at = first.last_seen_at - timedelta(hours=1)
        db_session.flush()
        stale_last_seen = first.last_seen_at

        again = repo.upsert_occurrence(release.id, JAN)
        assert again.last_seen_at > stale_last_seen

    def test_different_releases_can_share_the_same_scheduled_date(self, db_session):
        release_a = _release(db_session, name="Release A", provider_release_id="9001")
        release_b = _release(db_session, name="Release B", provider_release_id="9002")
        repo = ReleaseRepository(db_session)
        repo.upsert_occurrence(release_a.id, JAN)
        repo.upsert_occurrence(release_b.id, JAN)
        db_session.flush()

        _, total = repo.list_occurrences(start_date=None, end_date=None, limit=100, offset=0, order="asc")
        assert total == 2

    def test_same_release_and_date_duplicate_is_forbidden_at_the_db_level(self, db_session):
        """The real UNIQUE(economic_release_id, scheduled_date)
        constraint, enforced by PostgreSQL itself -- bypassing the
        repository's own upsert-checking logic via a raw duplicate
        insert, the same style already used for
        uq_observation_series_date in test_transaction_and_safety.py."""
        release = _release(db_session)
        db_session.add(ReleaseOccurrence(economic_release_id=release.id, scheduled_date=JAN))
        db_session.flush()
        db_session.add(ReleaseOccurrence(economic_release_id=release.id, scheduled_date=JAN))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_provider_omission_does_not_delete_a_historical_occurrence(self, db_session):
        """An occurrence persisted once and never upserted again on a
        later sync (a provider that stops returning that date) remains
        fully intact and readable -- nothing removes it."""
        release = _release(db_session)
        repo = ReleaseRepository(db_session)
        repo.upsert_occurrence(release.id, JAN)
        repo.upsert_occurrence(release.id, FEB)  # a later sync that no longer mentions JAN
        db_session.flush()

        rows, total = repo.list_occurrences(start_date=None, end_date=None, limit=100, offset=0, order="asc")
        assert total == 2
        assert {row[1].scheduled_date for row in rows} == {JAN, FEB}

    def test_repository_exposes_no_delete_method(self):
        assert not hasattr(ReleaseRepository, "delete_occurrence")
        assert not hasattr(ReleaseRepository, "delete_release")


class TestListOccurrencesFilteringOrderingPagination:
    def test_ordering_ascending(self, db_session):
        release = _release(db_session)
        repo = ReleaseRepository(db_session)
        for d in (MAR, JAN, FEB):
            repo.upsert_occurrence(release.id, d)
        db_session.flush()

        rows, _ = repo.list_occurrences(start_date=None, end_date=None, limit=100, offset=0, order="asc")
        assert [row[1].scheduled_date for row in rows] == [JAN, FEB, MAR]

    def test_ordering_descending(self, db_session):
        release = _release(db_session)
        repo = ReleaseRepository(db_session)
        for d in (JAN, MAR, FEB):
            repo.upsert_occurrence(release.id, d)
        db_session.flush()

        rows, _ = repo.list_occurrences(start_date=None, end_date=None, limit=100, offset=0, order="desc")
        assert [row[1].scheduled_date for row in rows] == [MAR, FEB, JAN]

    def test_filtering_by_start_and_end_date(self, db_session):
        release = _release(db_session)
        repo = ReleaseRepository(db_session)
        for d in (JAN, FEB, MAR):
            repo.upsert_occurrence(release.id, d)
        db_session.flush()

        rows, total = repo.list_occurrences(start_date=FEB, end_date=FEB, limit=100, offset=0, order="asc")
        assert total == 1
        assert rows[0][1].scheduled_date == FEB

    def test_pagination_limit_and_offset(self, db_session):
        release = _release(db_session)
        repo = ReleaseRepository(db_session)
        for d in (JAN, FEB, MAR):
            repo.upsert_occurrence(release.id, d)
        db_session.flush()

        rows, total = repo.list_occurrences(start_date=None, end_date=None, limit=1, offset=1, order="asc")
        assert total == 3
        assert len(rows) == 1
        assert rows[0][1].scheduled_date == FEB

    def test_total_count_reflects_all_matches_not_just_the_page(self, db_session):
        release = _release(db_session)
        repo = ReleaseRepository(db_session)
        for d in (JAN, FEB, MAR):
            repo.upsert_occurrence(release.id, d)
        db_session.flush()

        _, total = repo.list_occurrences(start_date=None, end_date=None, limit=1, offset=0, order="asc")
        assert total == 3


class TestTransactionOwnership:
    def test_repository_never_commits_or_rolls_back_itself(self, db_session):
        """Writes are visible within the same, still-open session
        without an explicit commit -- and this test never commits;
        db_session's own fixture teardown rolls the whole transaction
        back, which every other test in this file implicitly relies on
        starting from a clean slate."""
        release = _release(db_session)
        ReleaseRepository(db_session).upsert_occurrence(release.id, JAN)

        _, total = ReleaseRepository(db_session).list_occurrences(
            start_date=None, end_date=None, limit=10, offset=0, order="asc"
        )
        assert total == 1
