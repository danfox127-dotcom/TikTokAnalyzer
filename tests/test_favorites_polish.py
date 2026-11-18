"""Everyday polish: a save that says what really happened, a save already kept
that says since when, several links pasted at once, edits that don't reload
the page, a player that shows the picture while it loads, and an extension
whose notifications still open the save a minute later."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import db


@pytest.fixture
def conn():
    c = db.connect()
    yield c
    c.close()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
    with TestClient(web.app) as c:
        yield c


@pytest.fixture
def no_lookups(monkeypatch):
    """capture() without the network: files the link under itself."""
    async def fake_capture(shared, note, conn, collection=None, saved_at=None):
        url = web.extract_url(shared)
        item_id, created = db.upsert_item(conn, {
            "canonical_url": url, "shared_url": url, "platform": "tiktok", "title": f"About {url[-4:]}",
            "resolve_status": "ok", "note": note, "saved_at": "2026-11-18T10:00:00+00:00"})
        return {"id": item_id, "created": created, "title": f"About {url[-4:]}", "platform": "tiktok",
                "canonical_url": url, "resolve_status": "ok", "has_transcript": False, "collection": None}
    monkeypatch.setattr(web, "capture", fake_capture)


def kept_before(conn, url="https://www.tiktok.com/video/7001", note="for the housing piece"):
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": url, "shared_url": url, "platform": "tiktok", "title": "The zoning meeting",
        "resolve_status": "ok", "note": note, "saved_at": "2024-05-03T10:00:00+00:00"})
    return item_id


class TestWhatASaveSays:
    def test_new(self, client, no_lookups):
        r = client.post("/save", json={"url": "https://www.tiktok.com/video/7002"})
        assert r.status_code == 201 and r.json()["said"] == "Saved ✓ About 7002"

    def test_already_kept_says_since_when_and_your_note(self, client, conn, no_lookups):
        kept_before(conn)
        r = client.post("/save", json={"url": "https://www.tiktok.com/video/7001"})
        assert r.json()["said"] == "Already in Faves since 3 May 2024. Your note: “for the housing piece”"

    def test_the_automatic_one_too(self, client, conn):
        kept_before(conn)
        r = client.post("/save?auto=1", json={"url": "https://www.tiktok.com/video/7001"})
        assert r.json()["already"] and r.json()["said"].startswith("Already in Faves since 3 May 2024")

    def test_a_refusal_says_why(self, client, monkeypatch):
        monkeypatch.setenv("FAVORITES_TOKEN", "sesame")
        r = client.post("/save", json={"url": "https://www.tiktok.com/video/7002"})
        assert r.status_code == 401 and "didn't accept the password" in r.json()["said"]
        r = client.post("/save", json={"url": "no link"}, headers={"Authorization": "Bearer sesame"})
        assert r.status_code == 400 and r.json()["said"].startswith("Nothing to keep")

    def test_other_pages_keep_their_usual_errors(self, client):
        r = client.get("/item/999")
        assert r.status_code == 404 and "said" not in r.text


class TestKeep:
    def test_a_link_already_kept(self, client, conn, no_lookups):
        item_id = kept_before(conn)
        r = client.post("/keep", data={"url": "https://www.tiktok.com/video/7001"}, follow_redirects=False)
        assert r.headers["location"] == f"/item/{item_id}?saved=2"
        page = client.get(r.headers["location"]).text
        assert "Already in Faves since 3 May 2024." in page and "for the housing piece" in page
        assert "Saved. Add a note" not in page

    def test_a_new_one(self, client, no_lookups):
        r = client.post("/keep", data={"url": "https://www.tiktok.com/video/7003"}, follow_redirects=False)
        assert r.headers["location"].endswith("?saved=1")
        assert "Saved. Add a note below" in client.get(r.headers["location"]).text

    def test_several_at_once(self, client, conn, no_lookups):
        kept_before(conn)
        pasted = ("https://www.tiktok.com/video/7101\nhttps://www.tiktok.com/video/7001\n"
                  "look: https://www.tiktok.com/video/7102.\nhttps://www.tiktok.com/video/7101")
        r = client.post("/keep", data={"url": pasted}, follow_redirects=False)
        page = client.get(r.headers["location"]).text
        assert "<b>Kept 2</b> · 1 already in Faves" in page
        assert "About 7101" in page and "About 7102" in page and "already kept, since 3 May 2024" in page
        assert conn.execute("SELECT count(*) FROM items").fetchone()[0] == 3

    def test_at_most_a_batch(self, client, no_lookups):
        pasted = "\n".join(f"https://www.tiktok.com/video/{7200 + n}" for n in range(web.BATCH + 3))
        page = client.get(client.post("/keep", data={"url": pasted}, follow_redirects=False).headers["location"]).text
        assert f"<b>Kept {web.BATCH}</b>" in page and f"3 more were left out: paste up to {web.BATCH}" in page

    def test_the_box_takes_several_lines(self, client):
        page = client.get("/keep").text
        assert '<textarea id="link" name="url"' in page and "(or several)" in page


class TestThePage:
    def test_edits_redraw_the_words_not_the_page(self, client):
        js = client.get("/static/museum.js").text
        inplace = js[js.index("function inplace(form)"):js.index("function moreResults")]
        assert "redraw()" in inplace and "location.reload()" in inplace   # reload only if the redraw fails
        redraw = js[js.index("function redraw()"):js.index("function inplace(form)")]
        assert "'.detail-body'" in redraw and "replaceWith" in redraw

    def test_the_player_shows_the_picture_while_it_loads(self, client):
        js = client.get("/static/museum.js").text
        play = js[js.index("function play(link)"):js.index("/* ---- a word after saving")]
        assert "'screen is-loading'" in play and "poster" in play and "'load'" in play and "is-slow" in play
        css = client.get("/static/style.css").text
        assert ".rr-playing .screen.is-loading iframe { opacity: 0; }" in css
        assert 'content: "Slow to load? "' in css


class TestTheExtension:
    def test_notifications_remember_their_save(self):
        js = (Path(web.__file__).parent / "extension" / "background.js").read_text()
        assert "chrome.storage.session" in js and "new Map()" not in js
