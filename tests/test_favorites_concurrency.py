"""Many requests at once, the way a page full of pictures makes them.

Found on a real library: pictures loaded on an item's own page but only
patchily on the front page. The app opens the library in one worker thread
and reads it in another; SQLite refuses that by default, so under load most
picture requests failed with a 500 -- 79 of 80 in a reproduction -- and each
card quietly removed its broken picture. One request at a time usually gets
the same thread twice, which is why a single item always looked fine.
"""

import asyncio
import threading

import httpx
import pytest

from favorites import db, thumbnails
from favorites.app import app

JPEG = b"\xff\xd8\xff\xe0" + b"picture" * 500


def test_a_connection_can_be_handed_to_another_thread(tmp_path):
    conn = db.connect(tmp_path / "lib.db")
    errors = []

    def use():
        try:
            conn.execute("SELECT count(*) FROM items").fetchone()
        except Exception as exc:  # pragma: no cover - the failure being guarded
            errors.append(exc)

    t = threading.Thread(target=use)
    t.start()
    t.join()
    conn.close()
    assert errors == []


@pytest.fixture
def library(tmp_path, monkeypatch):
    path = tmp_path / "favorites.db"
    monkeypatch.setenv("FAVORITES_DB", str(path))
    conn = db.connect(path)
    ids = []
    for n in range(60):
        item_id, _ = db.upsert_item(conn, {
            "canonical_url": f"https://example.com/{n}", "shared_url": "x",
            "platform": "tiktok", "title": f"item {n}", "resolve_status": "ok",
            "thumbnail_url": "https://example.com/t.jpg"})
        thumbnails.store(conn, item_id, (JPEG, "image/jpeg"), None)
        ids.append(item_id)
    conn.close()
    return ids


def test_a_page_full_of_pictures_all_load(library):
    async def load_all():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://fav.test") as client:
            return await asyncio.gather(*[client.get(f"/thumb/{i}") for i in library])

    for _ in range(3):
        responses = asyncio.run(load_all())
        assert [r.status_code for r in responses] == [200] * len(library)
        assert all(r.content == JPEG for r in responses)


def test_pages_load_while_pictures_do(library):
    async def mixed():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://fav.test") as client:
            paths = ["/", "/search", "/search?platform=tiktok"] + [f"/thumb/{i}" for i in library]
            return await asyncio.gather(*[client.get(p) for p in paths])

    assert {r.status_code for r in asyncio.run(mixed())} == {200}
