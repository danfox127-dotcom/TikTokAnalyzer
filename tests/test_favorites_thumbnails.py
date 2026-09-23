"""Keeping the picture, because the platform's link to it expires.

Found on a real library: all 738 TikTok thumbnails carried an x-expires
timestamp, every one of them lapsing on the same day. Once a link lapses the
card just goes blank -- so the image itself is kept, inside the library file.
"""

import asyncio

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from favorites import backfill, db, thumbnails
from favorites.app import app

JPEG = b"\xff\xd8\xff\xe0" + b"picture" * 50
OLD = "https://p16.tiktokcdn.com/old.jpg?x-expires=1&x-signature=a"
NEW = "https://p16.tiktokcdn.com/new.jpg?x-expires=9999999999&x-signature=b"

OEMBED = {
    "title": "the zoning meeting went sideways #localgov",
    "author_name": "City Desk", "author_unique_id": "citydesk",
    "thumbnail_url": NEW,
}


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "lib.db"))
    yield c
    c.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "favorites.db"))
    monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
    with TestClient(app) as c:
        yield c


def resolved_item(conn, vid="7001", thumb=OLD):
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": f"https://www.tiktok.com/video/{vid}", "shared_url": "x",
        "platform": "tiktok", "external_id": vid, "title": "a video",
        "thumbnail_url": thumb, "resolve_status": "ok",
    })
    return item_id


def fetch(url):
    async def go():
        async with httpx.AsyncClient() as c:
            return await thumbnails.fetch(url, c)
    return asyncio.run(go())


class TestFetch:
    @respx.mock
    def test_an_image_comes_back_with_its_type(self):
        respx.get(NEW).mock(return_value=httpx.Response(
            200, content=JPEG, headers={"content-type": "image/jpeg; charset=binary"}))
        assert fetch(NEW) == (JPEG, "image/jpeg")

    @pytest.mark.parametrize("response", [
        httpx.Response(403, content=b"expired"),                                   # lapsed link
        httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"}),
        httpx.Response(200, content=b"<svg onload=alert(1)>",
                       headers={"content-type": "image/svg+xml"}),                 # can carry script
        httpx.Response(200, content=b"", headers={"content-type": "image/jpeg"}),
        httpx.Response(200, content=b"x" * (thumbnails.MAX_BYTES + 1),
                       headers={"content-type": "image/jpeg"}),                    # not a thumbnail
    ])
    @respx.mock
    def test_anything_but_a_modest_raster_image_is_refused(self, response):
        respx.get(NEW).mock(return_value=response)
        assert fetch(NEW) is None

    @respx.mock
    def test_a_network_error_is_just_no_picture(self):
        respx.get(NEW).mock(side_effect=httpx.ConnectError("offline"))
        assert fetch(NEW) is None

    def test_no_link_is_no_picture(self):
        assert fetch(None) is None and fetch("") is None


class TestServing:
    def test_a_kept_picture_is_served_from_the_library(self, client, tmp_path):
        c = db.connect(str(tmp_path / "favorites.db"))
        item_id = resolved_item(c)
        thumbnails.store(c, item_id, (JPEG, "image/jpeg"), OLD)
        c.close()
        resp = client.get(f"/thumb/{item_id}", follow_redirects=False)
        assert resp.status_code == 200
        assert resp.content == JPEG
        assert resp.headers["content-type"] == "image/jpeg"
        assert resp.headers["content-security-policy"] == "default-src 'none'"
        assert resp.headers["x-content-type-options"] == "nosniff"

    def test_without_a_kept_copy_it_falls_back_to_the_platform_link(self, client, tmp_path):
        c = db.connect(str(tmp_path / "favorites.db"))
        item_id = resolved_item(c)
        c.close()
        resp = client.get(f"/thumb/{item_id}", follow_redirects=False)
        assert resp.status_code == 302 and resp.headers["location"] == OLD

    def test_nothing_at_all_is_a_404(self, client, tmp_path):
        c = db.connect(str(tmp_path / "favorites.db"))
        item_id = resolved_item(c, thumb=None)
        c.close()
        assert client.get(f"/thumb/{item_id}").status_code == 404
        assert client.get("/thumb/99999").status_code == 404

    def test_pages_ask_the_library_for_pictures(self, client, tmp_path):
        c = db.connect(str(tmp_path / "favorites.db"))
        item_id = resolved_item(c)
        c.close()
        page = client.get(f"/item/{item_id}").text
        assert f'src="/thumb/{item_id}"' in page
        assert OLD not in page  # the expiring link is no longer in the page at all


class TestKeptAsYouGo:
    @respx.mock
    def test_a_share_keeps_its_picture(self, client):
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=OEMBED))
        respx.get(NEW).mock(return_value=httpx.Response(
            200, content=JPEG, headers={"content-type": "image/jpeg"}))
        respx.route().mock(return_value=httpx.Response(404))
        item_id = client.post("/save", json={
            "url": "https://www.tiktok.com/@citydesk/video/7123"}).json()["id"]
        assert client.get(f"/thumb/{item_id}", follow_redirects=False).content == JPEG

    @respx.mock
    def test_a_backfill_keeps_its_picture(self, conn):
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=OEMBED))
        respx.get(NEW).mock(return_value=httpx.Response(
            200, content=JPEG, headers={"content-type": "image/jpeg"}))
        respx.route().mock(return_value=httpx.Response(404))
        item_id, _ = db.upsert_item(conn, {
            "canonical_url": "https://www.tiktok.com/video/7123", "shared_url": "x",
            "platform": "tiktok", "external_id": "7123", "resolve_status": "pending",
            "saved_at": "2024-01-01T00:00:00+00:00"})
        asyncio.run(backfill.run(conn, None, quiet=True))
        assert thumbnails.get(conn, item_id)["data"] == JPEG

    @respx.mock
    def test_a_picture_that_fails_to_download_does_not_fail_the_save(self, client):
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=OEMBED))
        respx.route().mock(return_value=httpx.Response(404))
        resp = client.post("/save", json={"url": "https://www.tiktok.com/@citydesk/video/7123"})
        assert resp.status_code == 201
        assert resp.json()["resolve_status"] == "ok"


class TestCatchingUp:
    """``python -m favorites.thumbnails`` for a library resolved before this existed."""

    @respx.mock
    def test_a_live_link_is_kept_directly(self, conn):
        item_id = resolved_item(conn, thumb=NEW)
        respx.get(NEW).mock(return_value=httpx.Response(
            200, content=JPEG, headers={"content-type": "image/jpeg"}))
        r = asyncio.run(thumbnails.run(conn, quiet=True))
        assert r == {"attempted": 1, "kept": 1, "refreshed": 0, "found": 0, "failed": 0, "why": {}}
        assert thumbnails.get(conn, item_id)["data"] == JPEG

    @respx.mock
    def test_an_expired_link_is_replaced_by_asking_the_platform_again(self, conn):
        """Missing the deadline is recoverable for any video that still exists."""
        item_id = resolved_item(conn, thumb=OLD)
        respx.get(OLD).mock(return_value=httpx.Response(403))
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=OEMBED))
        respx.get(NEW).mock(return_value=httpx.Response(
            200, content=JPEG, headers={"content-type": "image/jpeg"}))
        respx.route().mock(return_value=httpx.Response(404))
        r = asyncio.run(thumbnails.run(conn, quiet=True))
        assert r["kept"] == 1 and r["refreshed"] == 1
        assert thumbnails.get(conn, item_id)["data"] == JPEG
        assert db.get_item(conn, item_id)["thumbnail_url"] == NEW

    @respx.mock
    def test_a_video_that_is_gone_is_counted_not_crashed_on(self, conn):
        resolved_item(conn, thumb=OLD)
        respx.get(OLD).mock(return_value=httpx.Response(403))
        respx.route().mock(return_value=httpx.Response(404))
        r = asyncio.run(thumbnails.run(conn, quiet=True))
        assert r == {"attempted": 1, "kept": 0, "refreshed": 0, "found": 0, "failed": 1,
                     "why": {"unavailable (usually a deleted video)": 1}}

    @respx.mock
    def test_a_full_size_png_cover_is_kept(self, conn):
        """Found on a real library: TikTok serves some covers as 3-4 MB PNGs."""
        item_id = resolved_item(conn, thumb=NEW)
        big = b"\x89PNG" + b"x" * 4_268_753
        respx.get(NEW).mock(return_value=httpx.Response(
            200, content=big, headers={"content-type": "image/png"}))
        assert asyncio.run(thumbnails.run(conn, quiet=True))["kept"] == 1
        assert len(thumbnails.get(conn, item_id)["data"]) == len(big)

    @respx.mock
    def test_a_refused_picture_is_named_and_not_refetched(self, conn):
        resolved_item(conn, thumb=NEW)
        respx.get(NEW).mock(return_value=httpx.Response(
            200, content=b"<svg/>", headers={"content-type": "image/svg+xml"}))
        oembed = respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=OEMBED))
        r = asyncio.run(thumbnails.run(conn, quiet=True))
        assert r["why"] == {"not an image we keep (image/svg+xml)": 1}
        assert not oembed.called  # a fresh link would only fetch the same refused picture

    @respx.mock
    def test_the_command_says_why_each_failure_failed(self, tmp_path, capsys):
        path = tmp_path / "lib.db"
        c = db.connect(str(path))
        resolved_item(c, vid="1", thumb=NEW)
        resolved_item(c, vid="2", thumb=OLD)
        c.close()
        respx.get(NEW).mock(return_value=httpx.Response(
            200, content=b"x" * (thumbnails.MAX_BYTES + 1), headers={"content-type": "image/png"}))
        respx.get(OLD).mock(return_value=httpx.Response(404))
        respx.route().mock(return_value=httpx.Response(404))
        thumbnails.main(["--db", str(path), "--quiet"])
        out = capsys.readouterr().out
        assert "2 could not be saved:" in out
        assert "1  over 10 MB" in out
        assert "1  unavailable (usually a deleted video)" in out

    def test_only_resolved_items_without_a_kept_copy_are_attempted(self, conn):
        kept = resolved_item(conn, vid="1")
        thumbnails.store(conn, kept, (JPEG, "image/jpeg"), OLD)
        todo = resolved_item(conn, vid="2")
        resolved_item(conn, vid="3", thumb=None)
        db.upsert_item(conn, {"canonical_url": "https://www.tiktok.com/video/4", "shared_url": "x",
                              "platform": "tiktok", "thumbnail_url": OLD, "resolve_status": "pending"})
        assert [i["id"] for i in thumbnails.missing(conn)] == [todo]

    def test_deleting_an_item_takes_its_picture_with_it(self, conn):
        item_id = resolved_item(conn)
        thumbnails.store(conn, item_id, (JPEG, "image/jpeg"), OLD)
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        assert thumbnails.counts(conn)["kept"] == 0

    @respx.mock
    def test_the_command_reports_what_it_kept(self, tmp_path, capsys):
        path = tmp_path / "lib.db"
        c = db.connect(str(path))
        resolved_item(c, thumb=NEW)
        c.close()
        respx.get(NEW).mock(return_value=httpx.Response(
            200, content=JPEG, headers={"content-type": "image/jpeg"}))
        assert thumbnails.main(["--db", str(path), "--quiet"]) == 0
        out = capsys.readouterr().out
        assert f"library: {path}" in out
        assert "kept 1 of 1" in out
        assert "thumbnails kept      : 1 of 1" in out

    def test_stats_fetch_nothing(self, tmp_path, capsys):
        path = tmp_path / "lib.db"
        c = db.connect(str(path))
        resolved_item(c, thumb=NEW)
        c.close()
        with respx.mock(assert_all_mocked=True):  # any request would raise
            thumbnails.main(["--db", str(path), "--stats"])
        assert "thumbnails kept      : 0 of 1" in capsys.readouterr().out
