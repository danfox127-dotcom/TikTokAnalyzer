"""Which library file a command uses, and saying so out loud.

Found on a real library: a YouTube import went into a new file inside the
project folder while the museum kept reading the 844-item library in the home
folder. Every step reported success; the imported videos just never appeared.
"""

import json
import logging
import os

import pytest
from fastapi.testclient import TestClient

from favorites import backfill, db
from favorites.app import app
from favorites.importers import tiktok_export
from favorites.importers import youtube_takeout as yt


class TestResolvePath:
    def test_an_explicit_path_beats_the_environment(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "env.db"))
        assert db.resolve_path(tmp_path / "explicit.db") == str(tmp_path / "explicit.db")

    def test_the_environment_beats_the_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "env.db"))
        assert db.resolve_path() == str(tmp_path / "env.db")

    def test_the_default_is_the_file_beside_the_package(self, monkeypatch):
        monkeypatch.delenv("FAVORITES_DB", raising=False)
        assert db.resolve_path() == str(db.DEFAULT_DB)

    def test_a_relative_path_is_made_absolute(self, tmp_path, monkeypatch):
        # A relative FAVORITES_DB means a different file in every folder you
        # run a command from -- one way to end up with two libraries.
        monkeypatch.chdir(tmp_path)
        assert db.resolve_path("favorites.db") == str(tmp_path / "favorites.db")

    def test_a_home_folder_path_is_expanded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert db.resolve_path("~/favorites.db") == str(tmp_path / "favorites.db")


class TestAnnouncing:
    def test_a_new_file_says_so_loudly(self, tmp_path):
        conn, line = db.connect_announced(tmp_path / "fresh.db")
        conn.close()
        assert str(tmp_path / "fresh.db") in line
        assert "NEW" in line and "--db" in line and "FAVORITES_DB" in line

    def test_an_existing_file_says_how_much_is_in_it(self, tmp_path):
        path = tmp_path / "lib.db"
        conn = db.connect(path)
        db.upsert_item(conn, {"canonical_url": "u", "shared_url": "u", "platform": "tiktok"})
        conn.close()
        conn, line = db.connect_announced(path)
        conn.close()
        assert line.endswith("(1 item)")
        assert "NEW" not in line


def _takeout(tmp_path):
    folder = tmp_path / "Takeout 2" / "YouTube and YouTube Music" / "playlists"
    folder.mkdir(parents=True)
    (folder / "Watch later-videos.csv").write_text(
        "Video ID,Playlist Video Creation Timestamp\n"
        "aaaaaaaaaaa,2024-03-01T10:00:00+00:00\n")
    return tmp_path / "Takeout 2"


class TestTheCommandsSayWhichFile:
    def test_importing_into_a_fresh_file_is_flagged(self, tmp_path, capsys):
        """The exact thing that happened: an import quietly started a new library."""
        yt.main([str(_takeout(tmp_path)), "--db", str(tmp_path / "project" / "favorites.db")])
        out = capsys.readouterr().out
        assert "NEW -- created just now" in out
        assert str(tmp_path / "project" / "favorites.db") in out

    def test_importing_into_your_real_library_says_how_big_it_is(self, tmp_path, capsys):
        real = tmp_path / "favorites.db"
        conn = db.connect(real)
        for i in range(3):
            db.upsert_item(conn, {"canonical_url": f"u{i}", "shared_url": "u", "platform": "tiktok"})
        conn.close()
        yt.main([str(_takeout(tmp_path)), "--db", str(real)])
        out = capsys.readouterr().out
        assert f"library: {real}  (3 items)" in out
        assert "NEW" not in out

    def test_list_touches_no_library_and_names_none(self, tmp_path, capsys):
        yt.main([str(_takeout(tmp_path)), "--list", "--db", str(tmp_path / "x.db")])
        assert "library:" not in capsys.readouterr().out
        assert not (tmp_path / "x.db").exists()

    def test_the_tiktok_importer_says_too(self, tmp_path, capsys):
        export = tmp_path / "user_data_tiktok.json"
        export.write_text(json.dumps({"Likes and Favorites": {"Favorite Videos": {
            "FavoriteVideoList": []}}}))
        tiktok_export.main([str(export), "--db", str(tmp_path / "lib.db")])
        assert f"library: {tmp_path / 'lib.db'}" in capsys.readouterr().out

    def test_backfill_says_too(self, tmp_path, capsys):
        backfill.main(["--stats", "--db", str(tmp_path / "lib.db")])
        assert f"library: {tmp_path / 'lib.db'}" in capsys.readouterr().out


def test_the_museum_says_which_file_it_is_reading_when_it_starts(tmp_path, monkeypatch, caplog):
    path = tmp_path / "favorites.db"
    monkeypatch.setenv("FAVORITES_DB", str(path))
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        with TestClient(app):
            pass
    assert any(f"library: {path}" in r.getMessage() for r in caplog.records)
