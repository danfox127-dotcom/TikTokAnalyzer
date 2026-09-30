"""The watched folder: exports import themselves."""

import json
import os
import time
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from favorites import db, watch
from favorites.importers import tiktok_export

OLD = time.time() - 3600  # settled an hour ago


def tiktok_payload(*videos):
    return json.dumps({"Likes and Favorites": {
        "Favorite Videos": {"FavoriteVideoList": [
            {"Date": "2024-05-01 10:00:00", "Link": f"https://www.tiktokv.com/share/video/{v}/"}
            for v in videos]},
        "Like List": {"ItemFavoriteList": [
            {"date": "2024-05-02 10:00:00", "link": "https://www.tiktokv.com/share/video/999/"}]}}})


def ig_post(code):
    url = f"https://www.instagram.com/p/{code}/"
    return {"timestamp": 1717243200, "media": [], "fbid": code, "label_values": [
        {"label": "URL", "value": url, "href": url},
        {"label": "Caption", "value": "Folding dumplings #cooking"},
        {"title": "Owner", "dict": [{"title": "", "dict": [
            {"label": "Name", "value": "Kitchen Desk"}, {"label": "Username", "value": "kitchendesk"}]}]},
    ]}


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    os.utime(path, (OLD, OLD))
    return path


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "lib.db"))
    yield c
    c.close()


@pytest.fixture
def downloads(tmp_path):
    d = tmp_path / "Downloads"
    d.mkdir()
    return d


def count(conn, where="1=1"):
    return conn.execute(f"SELECT count(*) FROM items WHERE {where}").fetchone()[0]


class TestRecognising:
    def test_each_kind_of_export(self, downloads):
        tt = make_zip(downloads / "TikTok_Data_1.zip", {"user_data_tiktok.json": tiktok_payload("1")})
        ig = make_zip(downloads / "instagram-me-2026.zip",
                      {"your_instagram_activity/saved/saved_posts.json": json.dumps([ig_post("A")])})
        yt = make_zip(downloads / "takeout-2026.zip", {
            "Takeout/YouTube and YouTube Music/playlists/Recipes-videos.csv":
                "Video ID,Playlist Video Creation Timestamp\naaaaaaaaaaa,2024-03-01T10:00:00+00:00\n"})
        other = make_zip(downloads / "photos.zip", {"a.jpg": "x"})
        assert [watch.detect(p) for p in (tt, ig, yt, other)] == ["tiktok", "instagram", "takeout", None]

    def test_loose_files_and_named_folders(self, downloads):
        (downloads / "user_data_tiktok.json").write_text(tiktok_payload("1"))
        assert watch.detect(downloads / "user_data_tiktok.json") == "tiktok"
        (downloads / "notes.json").write_text("{}")
        assert watch.detect(downloads / "notes.json") is None
        (downloads / "Takeout" / "YouTube and YouTube Music" / "playlists").mkdir(parents=True)
        (downloads / "Takeout" / "YouTube and YouTube Music" / "playlists" / "x-videos.csv").write_text("Video ID\n")
        assert watch.detect(downloads / "Takeout") == "takeout"
        # An ordinary folder is never walked, whatever is inside.
        (downloads / "Holiday").mkdir()
        (downloads / "Holiday" / "saved_posts.json").write_text("[]")
        assert watch.detect(downloads / "Holiday") is None

    def test_the_tiktok_importer_reads_the_zip(self, downloads):
        path = make_zip(downloads / "t.zip", {"TikTok/user_data_tiktok.json": tiktok_payload("1", "2")})
        assert len(tiktok_export.read_export(path)["favorites"]) == 2


class TestScanning:
    def test_imports_each_export_once_and_leaves_the_file_alone(self, conn, downloads):
        path = make_zip(downloads / "TikTok_Data.zip", {"user_data_tiktok.json": tiktok_payload("1", "2")})
        [found] = watch.scan(conn, [downloads])
        assert (found.kind, found.added, found.error) == ("tiktok", 2, None)
        assert count(conn) == 2  # favourites only: the like stays out
        assert watch.scan(conn, [downloads]) == []
        assert path.exists()

    def test_instagram_and_takeout(self, conn, downloads):
        make_zip(downloads / "instagram-me.zip", {"saved_posts.json": json.dumps([ig_post("A"), ig_post("B")])})
        make_zip(downloads / "takeout.zip", {
            "Takeout/YouTube and YouTube Music/playlists/Recipes-videos.csv":
                "Video ID,Playlist Video Creation Timestamp\naaaaaaaaaaa,2024-03-01T10:00:00+00:00\n",
            "Takeout/YouTube and YouTube Music/playlists/Liked videos-videos.csv":
                "Video ID,Playlist Video Creation Timestamp\nbbbbbbbbbbb,2024-03-01T10:00:00+00:00\n"})
        found = {f.kind: f.added for f in watch.scan(conn, [downloads])}
        assert found == {"instagram": 2, "takeout": 1}  # Liked videos stay out
        assert db.collections_for(conn, conn.execute(
            "SELECT id FROM items WHERE platform = 'youtube'").fetchone()[0]) == ["Recipes"]

    def test_a_file_still_downloading_waits(self, conn, downloads):
        path = make_zip(downloads / "TikTok_Data.zip", {"user_data_tiktok.json": tiktok_payload("1")})
        os.utime(path, None)  # changed just now
        assert watch.scan(conn, [downloads]) == []
        assert len(watch.scan(conn, [downloads], now=time.time() + 60)) == 1

    def test_a_broken_zip_is_tried_again_later(self, conn, downloads):
        (downloads / "TikTok_Data.zip").write_bytes(b"PK\x03\x04 not finished")
        os.utime(downloads / "TikTok_Data.zip", (OLD, OLD))
        assert watch.scan(conn, [downloads]) == []
        assert conn.execute("SELECT count(*) FROM imports").fetchone()[0] == 0

    def test_something_that_only_looked_like_an_export_is_noted_once(self, conn, downloads):
        make_zip(downloads / "x.zip", {"user_data_tiktok.json": "not json"})
        [found] = watch.scan(conn, [downloads])
        assert found.error and found.added == 0
        assert watch.scan(conn, [downloads]) == []

    def test_folders_from_the_setting(self, downloads, tmp_path, monkeypatch):
        monkeypatch.setenv("FAVORITES_WATCH", f"{downloads}{os.pathsep}{tmp_path / 'missing'}")
        assert watch.folders_from_env() == [downloads]
        monkeypatch.setenv("FAVORITES_WATCH", "")
        assert watch.folders_from_env() == []


class TestReminders:
    def test_due_after_sixty_days_and_snoozed_for_thirty(self, conn, downloads):
        make_zip(downloads / "TikTok_Data.zip", {"user_data_tiktok.json": tiktok_payload("1")})
        watch.scan(conn, [downloads])
        now = datetime.now(timezone.utc)
        assert watch.reminders(conn, now + timedelta(days=30)) == []
        [due] = watch.reminders(conn, now + timedelta(days=70))
        assert (due["platform"], due["name"], due["days"]) == ("tiktok", "TikTok", 70)
        watch.snooze(conn, "tiktok", now + timedelta(days=70))
        assert watch.reminders(conn, now + timedelta(days=80)) == []
        assert len(watch.reminders(conn, now + timedelta(days=101))) == 1

    def test_never_about_a_platform_you_have_not_used(self, conn):
        assert watch.reminders(conn, datetime.now(timezone.utc) + timedelta(days=400)) == []


def test_the_command(tmp_path, downloads, capsys):
    make_zip(downloads / "TikTok_Data.zip", {"user_data_tiktok.json": tiktok_payload("1")})
    assert watch.main([str(downloads), "--db", str(tmp_path / "lib.db")]) == 0
    out = capsys.readouterr().out
    assert "TikTok export" in out and "1 new" in out
