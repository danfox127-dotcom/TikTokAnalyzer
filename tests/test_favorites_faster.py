"""Faster saves: a save does the quick part only (the name, who made it, the
picture), within a few seconds, and its length and a YouTube video's words
are fetched afterwards -- on the Mac straight after it answers, in the cloud
when you next open the save or Today, and by the Mac's minute loop."""

import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import db, thumbnails
from favorites.resolve import Resolved



def tiktok_page(video=26):
    return ('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
            '{"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": '
            '{"video": {"duration": %d}}}}}}</script>' % video)

VIDEO = "https://www.tiktok.com/@citydesk/video/7123"
KEY = "https://www.tiktok.com/video/7123"   # how Faves files it


@pytest.fixture(autouse=True)
def fresh_tries(monkeypatch):
    monkeypatch.setattr(web, "_tried", Counter())


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


def ago(**kw):
    return (datetime.now(timezone.utc) - timedelta(**kw)).isoformat()


def add(conn, url=KEY, platform="tiktok", status="ok", saved_at=None, **more):
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": url, "shared_url": url, "platform": platform, "resolve_status": status,
        "title": more.pop("title", "The zoning meeting" if status == "ok" else None),
        "creator_handle": "@citydesk", "saved_at": saved_at or ago(minutes=1), **more})
    return item_id


def oembed(title="zoning #localgov"):
    respx.get(host="www.tiktok.com", path="/oembed").mock(return_value=httpx.Response(
        200, json={"title": title, "author_name": "City Desk", "author_unique_id": "citydesk",
                   "thumbnail_url": "https://p.example/1.jpg"}))


class TestTheSaveItself:
    @respx.mock
    def test_no_length_is_looked_up_while_you_wait(self, client, conn):
        oembed()
        page = respx.get(VIDEO).mock(return_value=httpx.Response(200, text=tiktok_page(video=32)))
        respx.route().mock(return_value=httpx.Response(404))
        r = client.post("/save", json={"url": VIDEO})
        assert r.status_code == 201 and not page.called
        assert db.get_item(conn, r.json()["id"])["duration"] is None
        assert set(r.json()["took"]) == {"lookup", "picture", "keep"}

    def test_a_slow_lookup_keeps_the_bare_link(self, client, conn, monkeypatch):
        async def slow(shared, client):
            await asyncio.sleep(5)
        monkeypatch.setattr(web, "resolve", slow)
        monkeypatch.setattr(web, "QUICK", 0.05)
        r = client.post("/save", json={"url": f"Look {VIDEO}?is_from=x"})
        assert r.status_code == 201 and r.json()["took"]["lookup"] < 1
        row = db.get_item(conn, r.json()["id"])
        assert (row["canonical_url"], row["resolve_status"]) == (KEY, "pending")
        assert r.json()["said"].startswith("Saved ✓")

    def test_a_slow_lookup_never_undoes_an_earlier_one(self, client, conn, monkeypatch):
        item_id = add(conn, transcript="what was said", note="for the housing piece", saved_at=ago(days=30))
        thumbnails.store(conn, item_id, (b"\x89PNG", "image/png"), "https://p/1.png")

        async def slow(shared, client):
            await asyncio.sleep(5)
        monkeypatch.setattr(web, "resolve", slow)
        monkeypatch.setattr(web, "QUICK", 0.05)
        r = client.post("/save", json={"url": VIDEO, "note": "and the schools one"})
        assert r.json()["id"] == item_id and r.json()["said"].startswith("Already in Faves")
        row = db.get_item(conn, item_id)
        assert (row["title"], row["resolve_status"], row["transcript"], row["note"]) == (
            "The zoning meeting", "ok", "what was said", "and the schools one")

    def test_a_slow_picture_is_left_for_later(self, client, conn, monkeypatch):
        async def quick(shared, client):
            return Resolved(canonical_url=VIDEO, shared_url=VIDEO, platform="tiktok", title="Zoning",
                            thumbnail_url="https://p/slow.jpg", resolve_status="ok")

        async def slow(url, client):
            await asyncio.sleep(5)
        monkeypatch.setattr(web, "resolve", quick)
        monkeypatch.setattr(web.thumbnails, "fetch", slow)
        monkeypatch.setattr(web, "PICTURE", 0.05)
        r = client.post("/save", json={"url": VIDEO})
        assert r.status_code == 201 and r.json()["took"]["picture"] < 1
        assert web.lacks(conn, db.get_item(conn, r.json()["id"])) == ["picture", "length"]


class TestFinishing:
    @respx.mock
    def test_on_the_mac_straight_after_the_save(self, client, conn, monkeypatch):
        monkeypatch.setenv("FAVES_FINISH_LATER", "1")
        oembed()
        respx.get(VIDEO).mock(return_value=httpx.Response(200, text=tiktok_page(video=32)))
        respx.route().mock(return_value=httpx.Response(404))
        item_id = client.post("/save", json={"url": VIDEO}).json()["id"]
        assert db.get_item(conn, item_id)["duration"] == 32

    def test_not_in_the_cloud_where_nothing_runs_after_the_answer(self, client, monkeypatch):
        monkeypatch.setenv("FAVES_FINISH_LATER", "1")
        monkeypatch.setenv("FAVES_CLOUD", "1")
        monkeypatch.setenv("FAVORITES_TOKEN", "sesame")
        monkeypatch.setattr(web.cloud, "missing", lambda: [])
        later = []

        async def quick(shared, client):
            return Resolved(canonical_url=VIDEO, shared_url=VIDEO, platform="tiktok", title="Z",
                            resolve_status="ok")

        async def note(item_id):
            later.append(item_id)
        monkeypatch.setattr(web, "resolve", quick)
        monkeypatch.setattr(web, "finish_later", note)
        r = client.post("/save", json={"url": VIDEO}, headers={"authorization": "Bearer sesame"})
        assert r.status_code == 201 and later == []

    @respx.mock
    def test_the_saves_page_asks_and_redraws(self, client, conn, monkeypatch):
        item_id = add(conn)
        assert 'data-finish' not in client.get(f"/item/{item_id}").text   # off in tests
        monkeypatch.setenv("FAVES_FINISH_LATER", "1")
        assert f'data-finish="/item/{item_id}/finish"' in client.get(f"/item/{item_id}").text
        respx.route(host="www.tiktok.com", path__regex=r"video/7123$").mock(
            return_value=httpx.Response(200, text=tiktok_page(video=41)))
        assert client.post(f"/item/{item_id}/finish").json() == {"id": item_id, "filled": ["length", "labels"]}
        page = client.get(f"/item/{item_id}").text
        assert "0:41 long" in page and "data-finish" not in page
        js = client.get("/static/museum.js").text
        fn = js[js.index("function finishing(el)"):js.index("/* ---- Rewind")]
        assert "redraw()" in fn and "f.value !== f.defaultValue" in fn   # never over your typing

    def test_a_slow_save_gets_its_details(self, conn, monkeypatch):
        monkeypatch.setenv("FAVES_FINISH_LATER", "1")
        item_id = add(conn, url="https://vt.tiktok.com/ZSabc/", status="pending")

        async def found(shared, client):
            assert shared == "https://vt.tiktok.com/ZSabc/"
            return Resolved(canonical_url=KEY, shared_url=shared, platform="tiktok",
                            title="The zoning meeting", creator_handle="@citydesk", resolve_status="ok")

        async def length(item, client):
            return 26, None, "ok"
        monkeypatch.setattr(web, "resolve", found)
        monkeypatch.setattr(web.lengths, "page_facts", length)
        assert asyncio.run(web.finish(conn, item_id)) == {"id": item_id, "filled": ["details", "length"]}
        row = db.get_item(conn, item_id)
        assert (row["canonical_url"], row["title"], row["duration"]) == (KEY, "The zoning meeting", 26)

    def test_a_youtube_videos_words(self, conn, monkeypatch):
        item_id = add(conn, url="https://www.youtube.com/watch?v=abc", platform="youtube",
                      external_id="abc", duration=149, title="Housing, explained")
        monkeypatch.setattr(web.transcript, "fetch", lambda platform, vid: "rent control and zoning")
        assert asyncio.run(web.finish(conn, item_id))["filled"] == ["words"]
        assert db.get_item(conn, item_id)["transcript"] == "rent control and zoning"
        found = conn.execute("SELECT item_id FROM items_fts WHERE items_fts MATCH 'rent'").fetchall() \
            if not db.on_postgres() else [(item_id,)]
        assert [r[0] for r in found] == [item_id]

    def test_only_recent_saves_and_only_twice(self, conn, monkeypatch):
        old = add(conn, url="https://www.tiktok.com/@a/video/1", saved_at=ago(days=3))
        new = add(conn)
        assert web.unfinished(conn) == [new] and web.lacks(conn, db.get_item(conn, old)) == []
        calls = []

        async def nothing(item, client):
            calls.append(item["id"])
            return None, None, "not on the page"
        monkeypatch.setattr(web.lengths, "page_facts", nothing)
        for _ in range(3):
            asyncio.run(web.finish_recent(conn))
        assert calls == [new, new] and web.unfinished(conn) == []

    def test_today_catches_up_on_the_newest(self, client, conn, monkeypatch):
        add(conn)
        monkeypatch.setenv("FAVES_FINISH_LATER", "1")
        assert 'data-finish="/saves/finish"' in client.get("/").text

        async def length(item, client):
            return 26, None, "ok"
        monkeypatch.setattr(web.lengths, "page_facts", length)
        assert client.post("/saves/finish").json() == {"finished": 1}
        assert 'data-finish' not in client.get("/").text
