"""Shared test setup."""

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
