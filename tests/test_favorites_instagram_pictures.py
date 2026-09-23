"""Instagram pictures, by way of the link-preview route.

Found on a real library: asked as a browser, Instagram sent 20 of 20 pages (and
20 of 20 embed pages) with no picture tag at all. Asked as a link previewer --
the way iMessage asks when you paste a link -- 5 of 5 came back with one, and
every picture downloaded. The export itself carries no pictures, so this is the
only way an imported Instagram save gets one.
"""

import asyncio

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from favorites import db, platforms, thumbnails
from favorites.app import app
from favorites.resolve import USER_AGENT, resolve

JPEG = b"\xff\xd8\xff\xe0" + b"picture" * 50
PIC = "https://scontent.cdninstagram.com/v/t51/pic.jpg?stp=dst&_nc_ht=x"
PAGE = (
    '<html><head>'
    '<meta property="og:title" content="Kitchen Desk on Instagram: &quot;Folding dumplings&quot;">'
    '<meta property="og:image" content="https://scontent.cdninstagram.com/v/t51/pic.jpg?stp=dst&amp;_nc_ht=x">'
    '</head><body></body></html>'
)
BARE = "<html><head><title>Instagram</title></head><body></body></html>"


def previewer_only(request):
    """Instagram as observed: the picture tag goes to link previewers only."""
    if "facebookexternalhit" in request.headers.get("user-agent", ""):
        return httpx.Response(200, text=PAGE, headers={"content-type": "text/html"})
    return httpx.Response(200, text=BARE, headers={"content-type": "text/html"})


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "lib.db"))
    yield c
    c.close()


@pytest.fixture
def no_waiting(monkeypatch):
    pauses = []

    async def fake(seconds):
        pauses.append(seconds)
        await asyncio.sleep(0)

    monkeypatch.setattr(thumbnails, "_sleep", fake)
    return pauses


def imported(conn, code="C1abcDEF", thumb=None, platform="instagram"):
    """An Instagram save as the export importer leaves it: caption, no picture."""
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": f"https://www.instagram.com/p/{code}", "shared_url": "x",
        "platform": platform, "external_id": code,
        "title": "Folding dumplings #dumplings", "creator_handle": "@kitchendesk",
        "thumbnail_url": thumb, "resolve_status": "ok",
        "saved_at": "2024-06-01T12:00:00+00:00",
    })
    return item_id


def run(conn, **kw):
    return asyncio.run(thumbnails.run(conn, quiet=True, **kw))


class TestWhoIsAsking:
    def test_only_instagram_asks_as_a_link_previewer(self):
        askers = [p.name for p in platforms.PLATFORMS if p.preview_agent]
        assert askers == ["instagram"]
        assert "facebookexternalhit" in platforms.LINK_PREVIEW_AGENT

    @respx.mock
    def test_an_instagram_share_gets_its_picture_link(self):
        page = respx.get(host="www.instagram.com", path="/p/C1abcDEF").mock(side_effect=previewer_only)
        respx.route().mock(return_value=httpx.Response(404))

        async def go():
            async with httpx.AsyncClient() as c:
                return await resolve("https://www.instagram.com/p/C1abcDEF/?igsh=abc", c)
        item = asyncio.run(go())
        assert item.thumbnail_url == PIC
        assert "facebookexternalhit" in page.calls.last.request.headers["user-agent"]

    @respx.mock
    def test_everywhere_else_still_asks_as_a_browser(self):
        page = respx.get("https://example.com/post").mock(return_value=httpx.Response(
            200, text=PAGE, headers={"content-type": "text/html"}))

        async def go():
            async with httpx.AsyncClient() as c:
                return await resolve("https://example.com/post", c)
        asyncio.run(go())
        assert page.calls.last.request.headers["user-agent"] == USER_AGENT


class TestCatchingUpInstagram:
    def test_imported_saves_with_no_link_are_asked(self, conn):
        ig = imported(conn)
        thumbnails.store(conn, imported(conn, code="kept"), (JPEG, "image/jpeg"), PIC)
        assert [i["id"] for i in thumbnails.missing(conn)] == [ig]

    def test_other_platforms_with_no_link_are_not_asked_again(self, conn):
        # A resolved TikTok with no picture link was asked once and had none.
        imported(conn, code="7001", platform="tiktok")
        assert thumbnails.missing(conn) == []

    @respx.mock
    def test_an_imported_save_gets_its_picture(self, conn, no_waiting):
        item_id = imported(conn)
        respx.get(host="www.instagram.com", path="/p/C1abcDEF").mock(side_effect=previewer_only)
        respx.get(PIC).mock(return_value=httpx.Response(
            200, content=JPEG, headers={"content-type": "image/jpeg"}))
        respx.route().mock(return_value=httpx.Response(404))

        r = run(conn)
        assert r == {"attempted": 1, "kept": 1, "refreshed": 0, "found": 1, "failed": 0, "why": {}}
        assert thumbnails.get(conn, item_id)["data"] == JPEG
        item = db.get_item(conn, item_id)
        assert item["thumbnail_url"] == PIC
        # Only the picture link is taken from the page; the export's caption
        # stays, rather than the page's "X on Instagram: ..." rewording of it.
        assert item["title"] == "Folding dumplings #dumplings"

    @respx.mock
    def test_a_post_that_offers_no_picture_is_named(self, conn, no_waiting):
        imported(conn)
        respx.get(host="www.instagram.com", path="/p/C1abcDEF").mock(
            return_value=httpx.Response(404))
        respx.route().mock(return_value=httpx.Response(404))
        r = run(conn)
        assert r["why"] == {"no picture offered (deleted, private, or refused)": 1}

    def test_instagram_is_asked_slowly_and_nothing_else_is(self, conn, no_waiting, monkeypatch):
        for code in ("one", "two", "three"):
            imported(conn, code=code)
        for vid in ("7001", "7002", "7003"):
            db.upsert_item(conn, {
                "canonical_url": f"https://www.tiktok.com/video/{vid}", "shared_url": "x",
                "platform": "tiktok", "external_id": vid, "title": "t",
                "thumbnail_url": f"https://p16.tiktokcdn.com/{vid}.jpg", "resolve_status": "ok"})

        busy = {"instagram": 0, "tiktok": 0}
        most = {"instagram": 0, "tiktok": 0}

        async def attempt(item, client):
            name = item["platform"]
            busy[name] += 1
            most[name] = max(most[name], busy[name])
            for _ in range(5):  # stay "in flight" long enough to overlap if allowed
                await asyncio.sleep(0)
            busy[name] -= 1
            return item, None, None, False, "unavailable"
        monkeypatch.setattr(thumbnails, "_attempt", attempt)

        run(conn)
        pause = platforms.get("instagram").bulk_pause
        assert pause > 0
        assert no_waiting == [pause] * 3  # one pause per Instagram post, none for TikTok
        assert most["instagram"] == 1     # one at a time...
        assert most["tiktok"] > 1         # ...while the rest keep their usual pace

    @respx.mock
    def test_the_command_reports_pictures_by_platform(self, tmp_path, capsys, no_waiting):
        path = tmp_path / "lib.db"
        c = db.connect(str(path))
        imported(c)
        imported(c, code="gone")
        c.close()
        respx.get(host="www.instagram.com", path="/p/C1abcDEF").mock(side_effect=previewer_only)
        respx.get(PIC).mock(return_value=httpx.Response(
            200, content=JPEG, headers={"content-type": "image/jpeg"}))
        respx.route().mock(return_value=httpx.Response(404))

        thumbnails.main(["--db", str(path), "--quiet"])
        out = capsys.readouterr().out
        assert "kept 1 of 2 (1 got a picture for the first time)" in out
        assert "Instagram         : 1 of 2" in out

    def test_the_app_shows_the_kept_picture(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "favorites.db"))
        monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
        c = db.connect(str(tmp_path / "favorites.db"))
        item_id = imported(c, thumb=PIC)
        thumbnails.store(c, item_id, (JPEG, "image/jpeg"), PIC)
        c.close()
        with TestClient(app) as client:
            assert f'src="/thumb/{item_id}"' in client.get(f"/item/{item_id}").text
            assert client.get(f"/thumb/{item_id}").content == JPEG
