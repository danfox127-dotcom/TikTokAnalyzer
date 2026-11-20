"""Creators' own pictures: kept by the Mac from TikTok's pages, shown in Browse."""

import asyncio
import io
import json
import re
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from PIL import Image

from favorites import app as web
from favorites import avatars, db, lengths, museum, platforms

PIC = "https://p16-sign.tiktokcdn-us.com/tos-useast5-avt/abc~c5_720x720.jpeg?x-expires=1"


def page(handle="ChefAna", picture=PIC, thumb=PIC.replace("720x720", "100x100")):
    author = {"uniqueId": handle, "nickname": "Chef Ana", "avatarThumb": thumb}
    if picture:
        author["avatarMedium"] = picture
    data = {"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": {
        "id": "1", "author": author, "video": {"duration": 30}}}}}}
    return f'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">{json.dumps(data)}</script>'


def jpeg(side=720):
    out = io.BytesIO()
    Image.new("RGB", (side, side), (200, 80, 60)).save(out, "JPEG", quality=95)
    return out.getvalue()


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


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    async def instantly(_):
        return None
    monkeypatch.setattr(lengths, "_sleep", instantly)


def add(conn, n, handle, platform="tiktok", saved="2025-03-01"):
    db.upsert_item(conn, {
        "canonical_url": f"https://www.tiktok.com/{handle}/video/{n}", "shared_url": "x", "platform": platform,
        "external_id": str(n), "resolve_status": "ok", "title": f"save {n}", "creator_handle": handle,
        "creator_name": handle.lstrip("@").title(), "saved_at": f"{saved}T10:00:00+00:00"})


class TestReadingThePage:
    def test_the_posters_handle_and_picture(self):
        assert platforms.tiktok_author(page()) == ("@chefana", PIC)

    def test_the_smallest_picture_will_do(self):
        assert platforms.tiktok_author(page(picture=None))[1].endswith("100x100.jpeg?x-expires=1")

    @pytest.mark.parametrize("html", ["<html>Something went wrong</html>", page(handle=""),
                                      page(picture="javascript:alert(1)", thumb="/local.jpg")])
    def test_nothing_to_go_on(self, html):
        assert platforms.tiktok_author(html) is None


class TestWhoIsNext:
    def test_the_creators_you_save_most_first_one_save_each(self, conn):
        add(conn, 1, "@once")
        for n in (2, 3, 4):
            add(conn, n, "@Regular", saved=f"2025-03-0{n}")
        add(conn, 5, "@insta", platform="instagram")
        queue = avatars.missing(conn)
        assert [(q["key"], q["external_id"]) for q in queue] == [("@regular", "4"), ("@once", "1")]

    def test_kept_ones_and_recent_misses_wait(self, conn):
        for n, h in enumerate(["@kept", "@missed", "@gaveup", "@lastweek"]):
            add(conn, n, h)
        avatars.store(conn, "@kept", (jpeg(64), "image/jpeg"))
        avatars.store(conn, "@missed", None)
        for _ in range(avatars.TRIES):
            avatars.store(conn, "@gaveup", None)
        avatars.store(conn, "@lastweek", None)
        later = datetime.now(timezone.utc) + timedelta(days=8)
        assert [q["key"] for q in avatars.missing(conn)] == []
        assert sorted(q["key"] for q in avatars.missing(conn, now=later)) == ["@lastweek", "@missed"]


class TestKeeping:
    def test_a_small_copy(self, conn):
        avatars.store(conn, "@ChefAna", (jpeg(720), "image/jpeg"), PIC)
        row = avatars.get(conn, "chefana")
        with Image.open(io.BytesIO(bytes(row["data"]))) as im:
            assert max(im.size) == avatars.SIZE
        assert avatars.known(conn) == {"@chefana"}

    @respx.mock
    def test_a_run_reads_one_page_per_creator(self, conn):
        add(conn, 1, "@chefana")
        add(conn, 2, "@gone")
        respx.get("https://www.tiktok.com/@chefana/video/1").mock(return_value=httpx.Response(200, text=page()))
        respx.get("https://www.tiktok.com/@gone/video/2").mock(return_value=httpx.Response(404))
        respx.get(PIC).mock(return_value=httpx.Response(200, content=jpeg(), headers={"content-type": "image/jpeg"}))
        assert asyncio.run(avatars.run(conn)) == {"kept": 1, "none": 1}
        assert avatars.known(conn) == {"@chefana"}
        assert conn.execute("SELECT tries FROM avatars WHERE key = '@gone'").fetchone()[0] == 1
        assert asyncio.run(avatars.run(conn)) == {"kept": 0, "none": 0}     # nobody left to ask, for now

    def test_only_on_the_mac(self, monkeypatch):
        called = []

        async def run(conn):
            called.append(1)
        monkeypatch.setattr(web.avatars, "run", run)
        monkeypatch.setenv("FAVES_FINISH_LATER", "0")
        asyncio.run(web._read_pictures())
        assert called == []
        monkeypatch.setenv("FAVES_FINISH_LATER", "1")
        asyncio.run(web._read_pictures())
        assert called == [1]


class TestShowing:
    def test_browse_shows_the_picture_over_the_initials(self, client, conn):
        for n in (1, 2):
            add(conn, n, "@ChefAna")
            add(conn, 10 + n, "@nopic")
        avatars.store(conn, "@chefana", (jpeg(64), "image/jpeg"))
        page = client.get("/browse/creators").text
        cards = dict(re.findall(r'<a class="creator-card" href="/creator/%40(\w+)">\s*<span class="avatar[^>]*>(.*?)</span>', page, re.S))
        assert cards["ChefAna"] == 'C<img src="/avatar/%40chefana" alt="" loading="lazy" data-hide-broken>'
        assert cards["nopic"] == "N"
        assert museum.creator_index(conn)[0]["picture"] in ("/avatar/%40chefana", None)

    def test_the_picture_itself(self, client, conn):
        avatars.store(conn, "@chefana", (jpeg(64), "image/jpeg"))
        r = client.get("/avatar/%40ChefAna")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"
        assert client.get("/avatar/%40nobody").status_code == 404
