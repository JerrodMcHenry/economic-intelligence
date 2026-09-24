"""Increment #54A: a platform-issued Postgres URL reaches the driver
this application actually installs.

Found by running the release command against a `postgresql://` URL --
the form Render's `connectionString` takes. SQLAlchemy resolved it to
psycopg2, which is not installed, so `release migrate` crashed and every
database route returned 500. `postgres://` failed differently: no such
dialect, misreported as DATABASE_UNAVAILABLE.

The dialect assertions below resolve the URL exactly as `create_engine`
would, without connecting, so they test the failure itself rather than
a string shape.
"""

import pytest
from sqlalchemy.engine import make_url

from app.core.config import _normalise_database_url


@pytest.mark.parametrize(
    "raw",
    [
        "postgresql://user:secret@db.internal:5432/macrochipz",
        "postgres://user:secret@db.internal:5432/macrochipz",
    ],
)
def test_driverless_platform_url_resolves_to_the_installed_psycopg_driver(raw):
    normalised = _normalise_database_url(raw)

    assert normalised == "postgresql+psycopg://user:secret@db.internal:5432/macrochipz"
    dialect = make_url(normalised).get_dialect()
    assert dialect.driver == "psycopg"


def test_the_rewrite_is_load_bearing_on_every_sqlalchemy_the_image_can_install():
    """The other direction: proves the rewrite is not cosmetic.

    #54A pinned "`postgresql://` resolves to psycopg2" and said the test
    would fail the day that stopped being true. It did: SQLAlchemy 2.1
    (installed by CI on 2026-09-24, dependencies being unpinned) defaults
    to psycopg 3, and `main` went red (#56A). The rewrite is still
    needed, for two reasons that hold on every version: `postgres://`
    has no dialect at all, and `postgresql://` means psycopg2 on any
    2.0 release -- which an unpinned build may still resolve to."""
    from sqlalchemy.exc import NoSuchModuleError

    with pytest.raises(NoSuchModuleError):
        make_url("postgres://u@h/db").get_dialect()
    assert make_url("postgresql://u@h/db").get_dialect().driver in {"psycopg2", "psycopg"}


@pytest.mark.parametrize(
    "raw",
    [
        "postgresql+psycopg://user@localhost:5432/economic_intelligence",
        "postgresql+psycopg2://user@localhost:5432/economic_intelligence",
        "sqlite:///local.db",
    ],
)
def test_url_that_already_names_a_driver_is_left_alone(raw):
    assert _normalise_database_url(raw) == raw


@pytest.mark.parametrize("raw", [None, ""])
def test_absent_url_stays_absent_so_configuration_missing_is_still_reported(raw):
    assert _normalise_database_url(raw) == raw


def test_only_the_scheme_is_rewritten_never_the_credentials_or_query():
    raw = "postgresql://user:p%40ss@db.internal:5432/macrochipz?sslmode=require"

    assert _normalise_database_url(raw) == "postgresql+psycopg://user:p%40ss@db.internal:5432/macrochipz?sslmode=require"
