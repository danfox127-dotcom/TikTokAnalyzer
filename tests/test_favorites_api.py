"""The capture endpoint and the pages, end to end."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from favorites import db
from favorites.app import app

OEMBED = {
    "title": "the zoning meeting went sideways #localgov",
    "author_name": "City Desk",
    "author_unique_id": "citydesk",
    "author_url": "https://www.tiktok.com/@citydesk",
    "thumbnail_url": "https://p16.tiktokcdn.com/thumb.jpg",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "favorites.db"))
    monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def library(tmp_path):
    conn = db.connect(str(tmp_path / "favorites.db"))
    yield conn
    conn.close()


@pytest.fixture
def tiktok_ok():
    with respx.mock:
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=OEMBED))
        respx.route().mock(return_value=httpx.Response(404))
        yield


class TestSave:
    def test_json_post_creates_an_item(self, client, library, tiktok_ok):
        resp = client.post("/save", json={
            "url": "https://www.tiktok.com/@citydesk/video/7123?_t=abc",
            "note": "for the housing newsletter",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["created"] is True
        assert body["platform"] == "tiktok"

        row = db.get_item(library, body["id"])
        assert row["creator_handle"] == "@citydesk"
        assert row["note"] == "for the housing newsletter"
        assert "localgov" in db.loads_list(row["tags"])

    def test_form_post_works_too(self, client, tiktok_ok):
        resp = client.post("/save", data={
            "url": "https://www.tiktok.com/@citydesk/video/7123"})
        assert resp.status_code == 201

    def test_a_url_buried_in_shared_text_is_found(self, client, tiktok_ok):
        # This is the normal case: share sheets send a sentence, not a link.
        resp = client.post("/save", json={
            "text": "Check this out https://www.tiktok.com/@citydesk/video/7123 on TikTok"})
        assert resp.status_code == 201

    def test_resaving_updates_instead_of_duplicating(self, client, library, tiktok_ok):
        first = client.post("/save", json={
            "url": "https://www.tiktok.com/@citydesk/video/7123?_t=one"})
        second = client.post("/save", json={
            "url": "https://m.tiktok.com/@citydesk/video/7123/?_t=two"})
        assert first.status_code == 201
        assert second.status_code == 200
        assert second.json()["created"] is False
        assert db.count(library) == 1

    def test_no_url_is_a_bad_request(self, client, tiktok_ok):
        assert client.post("/save", json={"note": "hello"}).status_code == 400
        assert client.post("/save", json={"url": "not a link"}).status_code == 400

    def test_an_unreachable_link_is_still_saved(self, client, library):
        # Losing the save because a CDN was down would defeat the purpose.
        with respx.mock:
            respx.route().mock(side_effect=httpx.ConnectError("down"))
            resp = client.post("/save", json={"url": "https://gone.example/thing"})
        assert resp.status_code == 201
        assert resp.json()["resolve_status"] == "unresolved"
        assert db.count(library) == 1


class TestToken:
    def test_no_token_configured_means_no_gate(self, client, tiktok_ok):
        assert client.post("/save", json={
            "url": "https://www.tiktok.com/@citydesk/video/7123"}).status_code == 201

    def test_a_configured_token_is_required(self, client, monkeypatch, tiktok_ok):
        monkeypatch.setenv("FAVORITES_TOKEN", "s3cret")
        url = "https://www.tiktok.com/@citydesk/video/7123"
        assert client.post("/save", json={"url": url}).status_code == 401
        assert client.post("/save", json={"url": url},
                           headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.post("/save", json={"url": url},
                           headers={"Authorization": "Bearer s3cret"}).status_code == 201

    def test_a_query_token_works_for_share_targets(self, client, monkeypatch, tiktok_ok):
        # An iOS Shortcut can attach a header, but a PWA share target cannot.
        monkeypatch.setenv("FAVORITES_TOKEN", "s3cret")
        resp = client.post("/save?token=s3cret", json={
            "url": "https://www.tiktok.com/@citydesk/video/7123"})
        assert resp.status_code == 201


class TestShareTarget:
    def test_android_share_lands_on_the_saved_item(self, client, tiktok_ok):
        resp = client.get(
            "/share-target",
            params={"text": "look https://www.tiktok.com/@citydesk/video/7123"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"].startswith("/item/")

    def test_a_share_with_no_link_goes_home_rather_than_erroring(self, client):
        resp = client.get("/share-target", params={"text": "just words"},
                          follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/?error=no-url"

    def test_the_manifest_declares_the_share_target(self, client):
        share = client.get("/manifest.webmanifest").json()["share_target"]
        assert share["action"] == "/share-target"
        assert share["params"]["url"] == "url"


class TestPages:
    def test_an_empty_library_invites_a_first_save(self, client):
        body = client.get("/").text
        assert "Nothing here yet" in body

    def test_the_front_page_leads_with_the_digest(self, client, tiktok_ok):
        client.post("/save", json={"url": "https://www.tiktok.com/@citydesk/video/7123"})
        body = client.get("/").text
        assert "1 save this past month." in body
        assert "Recently saved" in body
        # The shelf must actually render its contents. Naming that key "items"
        # made Jinja resolve dict.items() instead, producing an empty shelf
        # under a correct-looking heading.
        assert "City Desk" in body
        assert 'class="card' in body

    def test_search_finds_a_saved_item(self, client, tiktok_ok):
        client.post("/save", json={"url": "https://www.tiktok.com/@citydesk/video/7123"})
        body = client.get("/search", params={"q": "zoning"}).text
        assert "1 result" in body

    def test_search_survives_input_that_would_break_fts(self, client, tiktok_ok):
        client.post("/save", json={"url": "https://www.tiktok.com/@citydesk/video/7123"})
        assert client.get("/search", params={"q": 'broken "quote'}).status_code == 200

    def test_an_item_page_renders_and_a_missing_one_404s(self, client, tiktok_ok):
        item_id = client.post("/save", json={
            "url": "https://www.tiktok.com/@citydesk/video/7123"}).json()["id"]
        page = client.get(f"/item/{item_id}")
        assert page.status_code == 200
        assert "City Desk" in page.text
        # Hashtags are author-written and always shown; extracted phrases are
        # only shown when another save shares them, so a lone item has none.
        assert "#localgov" in page.text
        assert "/search?q=meeting+went" not in page.text
        assert client.get("/item/99999").status_code == 404

    def test_a_note_can_be_written_from_the_item_page(self, client, library, tiktok_ok):
        item_id = client.post("/save", json={
            "url": "https://www.tiktok.com/@citydesk/video/7123"}).json()["id"]
        resp = client.post(f"/item/{item_id}/note", data={"note": "cite in the brief"},
                           follow_redirects=False)
        assert resp.status_code == 303
        assert db.get_item(library, item_id)["note"] == "cite in the brief"
        # and it becomes searchable immediately
        assert len(db.search(library, "brief")) == 1

    def test_browse_pages_render(self, client, tiktok_ok):
        client.post("/save", json={"url": "https://www.tiktok.com/@citydesk/video/7123"})
        for path in ("/all", "/unlabelled", "/month/2026-09", "/creator/@citydesk"):
            assert client.get(path).status_code == 200, path

    def test_healthz_reports_the_library_size(self, client, tiktok_ok):
        client.post("/save", json={"url": "https://www.tiktok.com/@citydesk/video/7123"})
        body = client.get("/healthz").json()
        assert body == {"ok": True, "items": 1, "transcripts_enabled": body["transcripts_enabled"]}
