"""The phone's inbox: links shared while Faves was away are saved later."""

import asyncio

import httpx
import pytest
import respx

from favorites import app as app_module
from favorites import db, inbox

OEMBED = {
    "title": "the zoning meeting went sideways #localgov",
    "author_name": "City Desk",
    "author_unique_id": "citydesk",
    "author_url": "https://www.tiktok.com/@citydesk",
    "thumbnail_url": "https://p16.tiktokcdn.com/thumb.jpg",
}


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "lib.db"))
    inbox.STATUS.rescued, inbox.STATUS.recent = 0, []
    conn = db.connect()
    yield conn
    conn.close()


@pytest.fixture
def tiktok_ok():
    with respx.mock:
        lookups = respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=OEMBED))
        respx.route().mock(return_value=httpx.Response(404))
        yield lookups


def write(lines):
    inbox.path().write_text("\n".join(lines) + "\n")


def read_now():
    return asyncio.run(app_module._read_inbox())


class TestLines:
    def test_the_shortcuts_line_dated_and_with_a_note(self):
        line = inbox.parse("2026-10-22T13:48:00-04:00\thttps://www.tiktok.com/@a/video/1\tfor the newsletter")
        assert (line.link, line.saved_at, line.note) == (
            "https://www.tiktok.com/@a/video/1", "2026-10-22T17:48:00+00:00", "for the newsletter")

    def test_a_bare_link_or_a_caption_with_one(self):
        assert inbox.parse("https://vm.tiktok.com/ZT1/").saved_at is None
        line = inbox.parse("Check this out! https://www.instagram.com/reel/XYZ/?igsh=1")
        assert line.link == "https://www.instagram.com/reel/XYZ/?igsh=1" and line.note is None

    def test_lines_without_a_link_are_ignored(self):
        assert inbox.parse("") is None and inbox.parse("just some words") is None


class TestRescue:
    def test_a_link_that_never_arrived_is_saved_with_its_real_date(self, library, tiktok_ok):
        write(["2026-10-20T09:15:00Z\thttps://www.tiktok.com/@citydesk/video/7123\tzoning"])
        assert read_now() == 1
        row = library.execute("SELECT saved_at, note, title FROM items").fetchone()
        assert row["saved_at"].startswith("2026-10-20T09:15") and row["note"] == "zoning"
        assert inbox.STATUS.rescued == 1 and inbox.STATUS.found

    def test_each_line_is_dealt_with_once(self, library, tiktok_ok):
        write(["https://www.tiktok.com/@citydesk/video/7123"])
        assert read_now() == 1
        assert read_now() == 0
        assert tiktok_ok.call_count == 1

    def test_links_that_reached_faves_directly_are_not_looked_up_again(self, library, tiktok_ok):
        db.upsert_item(library, {"canonical_url": "https://www.tiktok.com/@citydesk/video/7123",
                                 "shared_url": "https://vm.tiktok.com/ZT1/", "platform": "tiktok"})
        write(["2026-10-20T09:15:00Z\thttps://vm.tiktok.com/ZT1/"])
        assert read_now() == 0
        assert tiktok_ok.call_count == 0
        assert library.execute("SELECT count(*) FROM items").fetchone()[0] == 1

    def test_a_line_with_nothing_to_save_is_not_tried_forever(self, library, tiktok_ok, monkeypatch):
        async def refuse(*args, **kwargs):
            raise app_module.HTTPException(status_code=400, detail="no URL found")
        monkeypatch.setattr(app_module, "capture", refuse)
        write(["https://example.com/broken"])
        assert read_now() == 0
        assert library.execute("SELECT count(*) FROM inbox_seen").fetchone()[0] == 1

    def test_no_inbox_yet_is_fine(self, library):
        assert read_now() == 0 and not inbox.STATUS.found

    def test_an_inbox_icloud_has_moved_off_the_mac_is_asked_for(self, library, monkeypatch):
        calls = []
        monkeypatch.setattr(inbox.subprocess, "run", lambda args, **kw: calls.append(args))
        p = inbox.path()
        (p.parent / f".{p.name}.icloud").write_text("placeholder")
        assert read_now() == 0
        assert calls == [["brctl", "download", str(p)]] and inbox.STATUS.found
