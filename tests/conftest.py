"""Shared test setup."""

import os
import uuid

import pytest


@pytest.fixture(autouse=True)
def _never_the_real_library(tmp_path, monkeypatch):
    """Point every test at a throwaway library unless it chooses its own.

    The default library is ~/favorites.db -- a real person's only copy of
    their notes. A test that forgot to set FAVORITES_DB must write to a
    temporary file, never there.
    """
    monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "test-library.db"))


@pytest.fixture(autouse=True)
def _never_the_real_footprint(tmp_path, monkeypatch):
    """Footprint keeps its site lists and memory in ~/.footprint. Tests use a
    temporary folder instead, so they never read a real site list or overwrite
    what a real install has learned."""
    monkeypatch.setenv("FOOTPRINT_HOME", str(tmp_path / "footprint-home"))


@pytest.fixture(autouse=True)
def _never_the_real_inbox(tmp_path, monkeypatch):
    """Faves reads the phone's inbox file from iCloud Drive. Tests point it at
    a temporary file instead (missing unless a test writes it)."""
    monkeypatch.setenv("FAVORITES_INBOX", str(tmp_path / "Faves inbox.txt"))


@pytest.fixture(autouse=True)
def _a_fresh_postgres_library(monkeypatch):
    """With FAVES_TEST_DATABASE_URL set, every test's library is in Postgres:
    an empty schema of its own, dropped afterwards. The whole suite then runs
    against Postgres as well as SQLite -- the database the cloud museum uses.
    Without it, nothing changes."""
    url = os.environ.get("FAVES_TEST_DATABASE_URL")
    if not url:
        yield
        return
    from favorites import pg
    schema = "t_" + uuid.uuid4().hex[:16]
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("FAVORITES_PG_SCHEMA", schema)
    yield
    # By its address, not DATABASE_URL: a test may have undone its settings.
    pg.drop(schema, url)


def pytest_collection_modifyitems(config, items):
    """Tests about library *files* on disk -- where the default one is, how an
    old file is upgraded in place -- have no meaning for a Postgres library."""
    if not os.environ.get("FAVES_TEST_DATABASE_URL"):
        return
    skip = pytest.mark.skip(reason="about SQLite library files; the library is in Postgres here")
    for item in items:
        if item.get_closest_marker("sqlite_file"):
            item.add_marker(skip)


def pytest_configure(config):
    config.addinivalue_line("markers", "sqlite_file: a test about SQLite library files on disk")
