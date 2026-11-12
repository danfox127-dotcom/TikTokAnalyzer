"""Missing details: the saves Faves couldn't identify. A short TikTok share
link is followed to its video; the rest you check yourself, one at a time --
name the ones that are still there, mark the ones that are gone."""

import re

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import backfill, db, museum, platforms
from favorites.resolve import expand, resolve

OEMBED = {
    "title": "the zoning meeting went sideways #localgov",
    "author_name": "City Desk",
    "author_unique_id": "citydesk",
    "author_url": "https://www.tiktok.com/@citydesk",
    "thumbnail_url": "https://p16.tiktokcdn.com/thumb.jpg",
}


@pytest.fixture
def conn():
    c = db.connect()
    yield c
    c.close()


@pytest.fixture
def client():
    with TestClient(web.app) as c:
        yield c


def unidentified(conn, vid, saved, source="export", note=None, canonical=None, platform="tiktok"):
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": canonical or f"https://www.tiktok.com/video/{vid}",
        "shared_url": canonical or f"https://www.tiktokv.com/share/video/{vid}/",
        "platform": platform, "external_id": vid if not canonical else None,
        "resolve_status": "unresolved", "resolve_attempts": 3, "source": source,
        "saved_at": saved, "note": note})
    return item_id


@pytest.fixture
def three(conn):
    return [unidentified(conn, "7001", "2024-01-01T10:00:00+00:00"),
            unidentified(conn, "7002", "2026-01-13T10:00:00+00:00"),
            unidentified(conn, None, "2026-10-12T16:45:23+00:00", source="share",
                         note="Timothy Dexter's successful failures",
                         canonical="https://www.tiktok.com/t/ZPLBwef2g")]


class TestShortLinks:
    def test_tiktok_t_links_are_short_links(self):
        assert platforms.is_short_link("https://www.tiktok.com/t/ZPLBwef2g/")
        assert platforms.is_short_link("https://vm.tiktok.com/ZMabc/")
        assert not platforms.is_short_link("https://www.tiktok.com/@citydesk/video/7123")
        assert not platforms.is_short_link("https://www.youtube.com/t/abc")   # only TikTok's own

    @pytest.mark.asyncio
    @respx.mock
    async def test_one_is_followed_to_its_video(self):
        respx.head("https://www.tiktok.com/t/ZPLBwef2g/").mock(
            return_value=httpx.Response(301, headers={"location": "https://www.tiktok.com/@citydesk/video/7123?_r=1"}))
        respx.head("https://www.tiktok.com/@citydesk/video/7123?_r=1").mock(return_value=httpx.Response(200))
        respx.get(host="www.tiktok.com", path="/oembed").mock(return_value=httpx.Response(200, json=OEMBED))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://www.tiktok.com/t/ZPLBwef2g/", client)
        assert (item.canonical_url, item.external_id) == ("https://www.tiktok.com/video/7123", "7123")
        assert item.resolve_status == "ok" and item.creator_handle == "@citydesk"

    @pytest.mark.asyncio
    @respx.mock
    async def test_a_bounce_to_a_page_that_isnt_the_video_is_not_followed(self):
        respx.head("https://www.tiktok.com/t/ZPLBwef2g/").mock(
            return_value=httpx.Response(302, headers={"location": "https://www.tiktok.com/login"}))
        respx.get("https://www.tiktok.com/t/ZPLBwef2g/").mock(
            return_value=httpx.Response(302, headers={"location": "https://www.tiktok.com/login"}))
        respx.route(host="www.tiktok.com", path="/login").mock(return_value=httpx.Response(200))
        async with httpx.AsyncClient() as client:
            assert await expand("https://www.tiktok.com/t/ZPLBwef2g/", client) == "https://www.tiktok.com/t/ZPLBwef2g/"

    @pytest.mark.asyncio
    @respx.mock
    async def test_looking_it_up_again_files_it_under_its_video(self, conn, three):
        respx.head("https://www.tiktok.com/t/ZPLBwef2g").mock(
            return_value=httpx.Response(301, headers={"location": "https://www.tiktok.com/@citydesk/video/7123"}))
        respx.head("https://www.tiktok.com/@citydesk/video/7123").mock(return_value=httpx.Response(200))
        respx.get(host="www.tiktok.com", path="/oembed", params={"url": "https://www.tiktok.com/video/7123"}).mock(
            return_value=httpx.Response(200, json=OEMBED))
        respx.route().mock(return_value=httpx.Response(404))
        conn.execute("UPDATE items SET resolve_attempts = 0 WHERE id = ?", (three[2],))
        conn.commit()
        await backfill.run(conn, limit=10, quiet=True)
        row = db.rows_to_dicts([db.get_item(conn, three[2])])[0]          # the same save, not a copy
        assert row["canonical_url"] == "https://www.tiktok.com/video/7123" and row["resolve_status"] == "ok"
        assert row["note"] == "Timothy Dexter's successful failures"
        assert conn.execute("SELECT count(*) FROM items WHERE canonical_url LIKE '%7123%'").fetchone()[0] == 1

    def test_a_video_already_saved_is_one_save_not_two(self, conn, three):
        kept, _ = db.upsert_item(conn, {
            "canonical_url": "https://www.tiktok.com/video/7123", "shared_url": "x", "platform": "tiktok",
            "external_id": "7123", "title": "already here", "resolve_status": "ok",
            "saved_at": "2026-11-01T10:00:00+00:00"})
        assert db.rekey(conn, three[2], "https://www.tiktok.com/video/7123") == kept
        conn.commit()
        assert db.get_item(conn, three[2]) is None
        row = db.get_item(conn, kept)
        assert row["note"] == "Timothy Dexter's successful failures"
        assert row["saved_at"] == "2026-10-12T16:45:23+00:00"                  # the earlier date


class TestTheScreen:
    def test_every_missing_save_newest_first(self, client, three):
        page = client.get("/missing").text
        ids = re.findall(r'<article class="rr-deckcard tone-peach is-naming" data-id="(\d+)"', page)
        assert ids == [str(three[2]), str(three[1]), str(three[0])]
        assert "3 left" in page and 'id="name-sheet"' in page
        # A TikTok with its number has a player to check it with; the short link opens in TikTok.
        assert page.count('data-embed="https://www.tiktok.com/player/v1/') == 2
        assert "Open it in TikTok to see if it&#39;s still there." in page or "Open it in TikTok to see if it's still there." in page
        assert "Shared from your phone" in page and "From your TikTok export" in page
        assert "Timothy Dexter" in page

    def test_it_can_start_where_you_left_off(self, client, three):
        page = client.get(f"/missing?at={three[1]}").text
        assert re.findall(r'is-naming" data-id="(\d+)"', page) == [str(three[1]), str(three[0])]

    def test_nothing_missing(self, client):
        assert "Every save has its details." in client.get("/missing").text

    def test_the_way_in(self, client, three):
        page = client.get("/sync").text
        assert 'href="/missing"' in page and "Check them one by one" in page


class TestNamingOne:
    def test_it_joins_the_library(self, client, conn, three):
        r = client.post(f"/item/{three[0]}/name", data={"title": "Orzo with brown butter and sage", "creator": "@cassie"},
                        headers={"Accept": "application/json"})
        assert r.status_code == 200 and r.json()["title"] == "Orzo with brown butter and sage"
        row = db.get_item(conn, three[0])
        assert (row["resolve_status"], row["resolve_error"]) == ("ok", "named by you")
        assert row["creator_handle"] == "@cassie" and row["creator_name"] is None
        assert [r["id"] for r in db.search(conn, "orzo")] == [three[0]]
        assert museum.pending_count(conn) == 2

    def test_a_creator_by_name(self, client, conn, three):
        client.post(f"/item/{three[0]}/name", data={"title": "A thing", "creator": "Cassie Brim"})
        assert db.get_item(conn, three[0])["creator_name"] == "Cassie Brim"

    def test_it_needs_a_title(self, client, conn, three):
        assert client.post(f"/item/{three[0]}/name", data={"title": "  "}).status_code == 400
        assert db.get_item(conn, three[0])["resolve_status"] == "unresolved"

    def test_no_such_save(self, client):
        assert client.post("/item/999/name", data={"title": "x"}).status_code == 404
        assert client.post("/item/999/gone").status_code == 404

    def test_the_script_names_and_moves_on(self, client):
        js = client.get("/static/museum.js").text
        assert "getElementById('name-sheet')" in js and "closest('.goner')" in js and "/name'" in js


class TestGone:
    def test_kept_out_of_the_way(self, client, conn, three):
        r = client.post(f"/item/{three[1]}/gone", headers={"Accept": "application/json"})
        assert r.json() == {"gone": True}
        assert db.get_item(conn, three[1])["resolve_status"] == db.GONE
        assert museum.pending_count(conn) == 2
        assert f'data-id="{three[1]}"' not in client.get("/missing").text
        gone_page = client.get("/missing/gone").text
        assert "1 video you found gone" in gone_page and "Put it back" in gone_page
        assert "1 you marked gone" in client.get("/sync").text

    def test_never_looked_up_again(self, conn, three):
        db.mark_gone(conn, three[1])
        web._look_again()                                   # "Look them up again" resets the tries ...
        assert three[1] not in [i["id"] for i in backfill.pending(conn)]   # ... but not for a gone one
        assert db.get_item(conn, three[1])["resolve_attempts"] == 3

    def test_put_back(self, client, conn, three):
        db.mark_gone(conn, three[1])
        r = client.post(f"/item/{three[1]}/gone", data={"back": "1"}, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/missing/gone"
        assert db.get_item(conn, three[1])["resolve_status"] == "unresolved"
        assert museum.pending_count(conn) == 3

    def test_never_deleted(self, client, conn, three):
        client.post(f"/item/{three[1]}/gone")
        assert db.count(conn) == 3
