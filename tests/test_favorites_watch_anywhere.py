"""Watch from anywhere: a play button on every playable card opens the
page's videos as a full-screen feed, starting from the one you tapped, and
flicking up brings the next -- Shuffle's player, for any list."""

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import db, explore


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


def add(conn, n, platform="tiktok"):
    url = (f"https://www.tiktok.com/@city/video/{7000 + n}" if platform == "tiktok"
           else f"https://example.com/story/{n}")
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": url, "shared_url": url, "platform": platform, "external_id": str(7000 + n),
        "title": f"Video {n}", "resolve_status": "ok", "creator_handle": "@city",
        "thumbnail_url": "https://p.example/1.jpg", "saved_at": f"2026-10-{n:02d}T10:00:00+00:00"})
    return item_id


def ids_on(page):
    return [int(x.split('"')[0]) for x in page.split('class="rr-deckcard')[1:]
            for x in [x.split('data-id="')[1]]]


class TestTheButton:
    def test_every_playable_card_has_one(self, client, conn):
        tiktok, web_page = add(conn, 1), add(conn, 2, platform="web")
        page = client.get("/search").text
        assert f'data-watch="{tiktok}"' in page and f'href="/watch?ids={tiktok}&amp;at={tiktok}"' in page
        assert f'data-watch="{web_page}"' not in page          # nothing to play there
        assert 'data-watch=' in client.get("/").text           # Today's shelves too

    def test_the_script_gathers_the_rest_of_the_page(self, client):
        js = client.get("/static/museum.js").text
        fn = js[js.index("function watchFrom(e)"):js.index("/* ---- a save's extras")]
        assert ".rr-carousel, .rr-track, .rr-salon" in fn and "'/watch?'" in fn and "from:" in fn
        assert "document.addEventListener('click', watchFrom)" in js
        css = client.get("/static/style.css").text
        assert ".rr-watchbtn {" in css and ".rr-card, .rr-slide, .rr-piece { position: relative; }" in css


class TestTheFeed:
    def test_starts_at_the_one_you_tapped(self, client, conn):
        ids = [add(conn, n) for n in range(1, 13)]
        page = client.get("/watch", params={"ids": ",".join(map(str, ids)), "at": ids[3], "from": "/search?q=v"}).text
        assert ids_on(page) == ids[3:3 + explore.DECK_BATCH]
        assert 'data-earlier="1"' in page and 'data-more="1"' in page
        assert "<b>Watching</b><span>12 videos</span>" in page
        assert 'href="/search?q=v" data-back aria-label="Close"' in page

    def test_flicking_on_and_back(self, client, conn):
        ids = [add(conn, n) for n in range(1, 13)]
        q = {"ids": ",".join(map(str, ids)), "from": "/browse"}
        r = client.get("/watch/cards", params={**q, "after": ids[7]})
        assert ids_on(r.text) == ids[8:] and r.headers["X-Deck-More"] == "0"
        assert "That's all 12." in r.text and "Back to where you were" in r.text and 'href="/browse" data-back' in r.text
        r = client.get("/watch/cards", params={**q, "before": ids[3]})
        assert ids_on(r.text) == ids[:3] and r.headers["X-Deck-More"] == "0"
        assert "That's all" not in r.text

    def test_no_script_keep_going(self, client, conn):
        ids = [add(conn, n) for n in range(1, 13)]
        page = client.get("/watch", params={"ids": ",".join(map(str, ids)), "after": ids[7]}).text
        assert ids_on(page) == ids[8:]

    def test_odd_addresses_are_harmless(self, client, conn):
        a = add(conn, 1)
        page = client.get("/watch", params={"ids": f"{a},{a},99999,x,", "from": "https://evil.example/"}).text
        assert ids_on(page) == [a] and 'href="/" data-back aria-label="Close"' in page
        assert "Nothing to swipe through here." in client.get("/watch").text

    def test_shuffle_itself_is_unchanged(self, client, conn):
        add(conn, 1)
        page = client.get("/shuffle?order=newest").text
        assert "Shuffle to deal them again" in page and "Back to where you were" not in page


class TestKeepingYourPlace:
    def test_earlier_cards_never_move_you_on(self, client):
        """Chrome keeps the place by itself when cards load above; adding the
        difference as well moved Shuffle two cards on. Set it outright."""
        js = client.get("/static/museum.js").text
        deck = js[js.index("function deck(feed)"):js.index("/* ---- Save copied link")]
        assert "feed.scrollTop = here.offsetTop - feed.firstElementChild.offsetTop" in deck
        assert "feed.scrollHeight - tall" not in deck
