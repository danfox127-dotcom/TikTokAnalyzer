"""Watching a save in place: each platform's own embed player, asked for only
when you press play, with the way out to the app always beside it."""

import re

import pytest
from fastapi.testclient import TestClient

from favorites import db, platforms
from favorites.app import app


@pytest.mark.parametrize("item, src, shape", [
    ({"platform": "youtube", "external_id": "dQw4w9WgXcQ", "format": "video"},
     "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?playsinline=1&rel=0&autoplay=1", "wide"),
    ({"platform": "youtube", "external_id": "abc-DEF_123", "format": "short"},
     "https://www.youtube-nocookie.com/embed/abc-DEF_123?playsinline=1&rel=0&autoplay=1", "tall"),
    ({"platform": "tiktok", "external_id": "7123456789",
      "shared_url": "https://www.tiktok.com/@citydesk/video/7123456789"},
     "https://www.tiktok.com/player/v1/7123456789?autoplay=1&loop=1&rel=0&music_info=1&description=1", "tall"),
    ({"platform": "instagram", "canonical_url": "https://www.instagram.com/reel/C9xY_z-1"},
     "https://www.instagram.com/reel/C9xY_z-1/embed/", "ig-reel"),
    ({"platform": "instagram", "canonical_url": "https://www.instagram.com/p/C9xYz1"},
     "https://www.instagram.com/p/C9xYz1/embed/", "ig-post"),
])
def test_each_platform_has_its_own_player(item, src, shape):
    found = platforms.embed(item)
    assert (found["src"], found["shape"]) == (src, shape)
    assert found["label"] == platforms.get(item["platform"]).label


@pytest.mark.parametrize("item", [
    # A TikTok photo slideshow files under a video's identity; its player can't show one.
    {"platform": "tiktok", "external_id": "7123", "shared_url": "https://www.tiktok.com/@a/photo/7123"},
    {"platform": "tiktok", "external_id": None},
    {"platform": "youtube", "external_id": ""},
    # An id is only ever used as one: nothing else gets into the player's address.
    {"platform": "youtube", "external_id": "abc/../x?y=1"},
    {"platform": "tiktok", "external_id": "7123?autoplay=0"},
    {"platform": "instagram", "canonical_url": "https://www.instagram.com/someone"},
    {"platform": "reddit", "external_id": "abc", "canonical_url": "https://www.reddit.com/r/x/comments/abc"},
    {"platform": "x", "external_id": "123"},
    {"platform": "web", "canonical_url": "https://example.com/a"},
    {},
])
def test_no_player_means_linking_out_as_before(item):
    assert platforms.embed(item) is None


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "favorites.db"
    monkeypatch.setenv("FAVORITES_DB", str(path))
    monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
    conn = db.connect(str(path))
    ids = {
        "tiktok": db.upsert_item(conn, {
            "canonical_url": "https://www.tiktok.com/video/7123456789", "external_id": "7123456789",
            "shared_url": "https://www.tiktok.com/@citydesk/video/7123456789", "platform": "tiktok",
            "creator_handle": "@citydesk", "title": "The zoning meeting", "resolve_status": "ok",
            "format": "short", "saved_at": "2025-05-01T12:00:00+00:00"})[0],
        "youtube": db.upsert_item(conn, {
            "canonical_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "external_id": "dQw4w9WgXcQ",
            "shared_url": "x", "platform": "youtube", "title": "A long talk", "resolve_status": "ok",
            "format": "video", "saved_at": "2025-05-02T12:00:00+00:00"})[0],
        "web": db.upsert_item(conn, {
            "canonical_url": "https://example.com/essay", "shared_url": "https://example.com/essay",
            "platform": "web", "title": "An essay", "resolve_status": "ok",
            "saved_at": "2025-05-03T12:00:00+00:00"})[0],
    }
    conn.close()
    with TestClient(app) as c:
        c.ids = ids
        yield c


class TestOnThePages:
    def test_a_saves_page_offers_to_play_it_here(self, client):
        page = client.get(f"/item/{client.ids['tiktok']}").text
        assert 'data-embed="https://www.tiktok.com/player/v1/7123456789?autoplay=1&amp;loop=1' in page
        assert 'data-shape="tall" data-label="TikTok" aria-label="Play it here"' in page

    def test_nothing_loads_from_the_platform_before_you_press_play(self, client):
        for path in [f"/item/{client.ids['tiktok']}", f"/item/{client.ids['youtube']}",
                     "/shuffle?order=newest"]:
            assert "<iframe" not in client.get(path).text

    def test_without_script_play_is_the_old_link_out(self, client):
        page = client.get(f"/item/{client.ids['youtube']}").text
        assert re.search(r'<a class="rr-player" href="https://www\.youtube\.com/watch\?v=dQw4w9WgXcQ"'
                         r' target="_blank" rel="noopener noreferrer" data-embed=', page)

    @pytest.mark.parametrize("which, words", [("tiktok", "Watch the Short"), ("youtube", "Open on YouTube"),
                                              ("web", "Open on Web")])
    def test_the_way_out_to_the_app_stays_on_a_saves_page(self, client, which, words):
        assert words in client.get(f"/item/{client.ids[which]}").text

    def test_every_shuffle_card_plays_in_place_and_still_links_out(self, client):
        page = client.get("/shuffle?order=newest").text
        cards = re.findall(r'<article class="rr-deckcard.*?</article>', page, re.S)
        assert len(cards) == 3
        for card in cards:
            assert 'class="rr-btn rr-btn--primary open"' in card        # Watch it / Open on …
        tiktok = next(c for c in cards if f'data-id="{client.ids["tiktok"]}"' in c)
        assert 'data-embed="https://www.tiktok.com/player/v1/7123456789' in tiktok

    def test_a_save_with_no_player_keeps_its_plain_picture(self, client):
        page = client.get("/shuffle?order=newest").text
        web = next(c for c in re.findall(r'<article class="rr-deckcard.*?</article>', page, re.S)
                   if f'data-id="{client.ids["web"]}"' in c)
        assert "data-embed" not in web
        assert f'<div class="pic"><a href="/item/{client.ids["web"]}" tabindex="-1" aria-hidden="true">' in web
        assert "data-embed" not in client.get(f"/item/{client.ids['web']}").text
