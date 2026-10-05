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

    def test_a_freshly_imported_library_explains_itself(self, client, library):
        # 844 items and an empty front page reads as a bug unless the page says
        # what is actually going on.
        for i in range(5):
            db.upsert_item(library, {
                "canonical_url": f"https://www.tiktok.com/video/{7000 + i}",
                "shared_url": "x", "platform": "tiktok",
                "resolve_status": "pending", "source": "export",
            })
        body = client.get("/").text
        assert "5 saves imported, none identified yet" in body
        assert "favorites.backfill" in body

    def test_the_front_page_leads_with_the_digest(self, client, tiktok_ok):
        client.post("/save", json={"url": "https://www.tiktok.com/@citydesk/video/7123"})
        body = client.get("/").text
        assert "1 save this past month." in body
        assert "Recently saved" in body
        # The shelf must actually render its contents. Naming that key "items"
        # made Jinja resolve dict.items() instead, producing an empty shelf
        # under a correct-looking heading.
        assert "City Desk" in body
        assert 'class="rr-slide"' in body

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

    def test_the_item_page_links_somewhere_that_actually_opens(self, client, tiktok_ok):
        # The unit tests prove the helper is right; this proves the template
        # uses it. Linking the identity key sends every item in the library to
        # a 404, and nothing but rendering the page catches that.
        item_id = client.post("/save", json={
            "url": "https://www.tiktok.com/@citydesk/video/7123"}).json()["id"]
        body = client.get(f"/item/{item_id}").text
        assert 'href="https://www.tiktok.com/@citydesk/video/7123"' in body
        assert 'href="https://www.tiktok.com/video/7123"' not in body

    def test_an_unresolved_item_links_to_its_original_url(self, client, library):
        db.upsert_item(library, {
            "canonical_url": "https://www.tiktok.com/video/7123",
            "shared_url": "https://www.tiktokv.com/share/video/7123/",
            "platform": "tiktok", "external_id": "7123",
            "resolve_status": "unresolved", "source": "export",
        })
        item_id = db.rows_to_dicts(db.recent(library))[0]["id"]
        body = client.get(f"/item/{item_id}").text
        assert 'href="https://www.tiktokv.com/share/video/7123/"' in body

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


class TestPlacardRun:
    """Writing a line about the items that have no findable text at all.

    A caption of pure emoji and hashtags leaves an item searchable by nothing.
    No model recovers why it was kept -- only the person who kept it can.
    """

    def stock(self, conn):
        def add(vid, title, terms, note=None):
            db.upsert_item(conn, {
                "canonical_url": f"https://www.tiktok.com/video/{vid}",
                "shared_url": f"https://www.tiktokv.com/share/video/{vid}/",
                "platform": "tiktok", "external_id": vid,
                "title": title, "terms": terms, "note": note,
                "thumbnail_url": "https://p16.tiktokcdn.com/t.jpg",
                "resolve_status": "ok", "source": "export",
            })
        add("7001", "🥰🥰🥰 #mentalhealth", [])                      # no prose
        add("7002", "#fyp #viral", [])                               # no prose
        add("7003", "the zoning meeting went sideways", ["zoning"])  # prose, no note
        add("7004", "🎃🎃 #spooky", [], note="for the october post")  # no prose, done

    def test_only_items_with_no_prose_are_queued_by_default(self, client, library):
        self.stock(library)
        body = client.get("/notes").text
        assert "<strong>2</strong> left to label" in body
        assert "1 note written" in body

    def test_widening_includes_everything_unlabelled(self, client, library):
        self.stock(library)
        body = client.get("/notes?all=1").text
        assert "<strong>3</strong> left to label" in body

    def test_an_item_with_no_caption_says_so_rather_than_showing_blank(self, client, library):
        db.upsert_item(library, {
            "canonical_url": "https://www.tiktok.com/video/7001",
            "shared_url": "https://www.tiktokv.com/share/video/7001/",
            "platform": "tiktok", "external_id": "7001",
            "title": None, "terms": [], "resolve_status": "ok",
        })
        assert "the picture is all there is" in client.get("/notes").text

    def test_writing_a_placard_advances_to_the_next_item(self, client, library):
        self.stock(library)
        first = client.get("/notes").text
        assert "7001" in first  # its thumbnail/link carry the id

        item_id = db.rows_to_dicts(db.recent(library, limit=10))[-1]["id"]
        resp = client.post(f"/notes/{item_id}", data={"note": "made me laugh"},
                           follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == f"/notes?after={item_id}"
        assert db.get_item(library, item_id)["note"] == "made me laugh"

    def test_a_written_placard_is_immediately_searchable(self, client, library):
        # The whole point: these items had no findable text before.
        self.stock(library)
        item_id = db.rows_to_dicts(db.recent(library, limit=10))[-1]["id"]
        client.post(f"/notes/{item_id}", data={"note": "referendum explainer"},
                    follow_redirects=False)
        assert len(db.search(library, "referendum")) == 1

    def test_skipping_does_not_loop_on_the_same_item(self, client, library):
        self.stock(library)
        ids = [i["id"] for i in db.rows_to_dicts(db.recent(library, limit=10))]
        first = min(ids)
        body = client.get(f"/notes?after={first}").text
        assert f"/notes/{first}" not in body

    def test_an_empty_note_skips_rather_than_storing_blank(self, client, library):
        self.stock(library)
        item_id = db.rows_to_dicts(db.recent(library, limit=10))[-1]["id"]
        client.post(f"/notes/{item_id}", data={"note": "   "},
                    follow_redirects=False)
        assert not (db.get_item(library, item_id)["note"] or "").strip()

    def test_the_end_of_the_run_says_so(self, client, library):
        self.stock(library)
        highest = max(i["id"] for i in db.rows_to_dicts(db.recent(library, limit=10)))
        assert "That's the last one." in client.get(f"/notes?after={highest}").text

    def test_an_empty_library_is_not_an_error(self, client):
        assert "Nothing needs a note." in client.get("/notes").text

    def test_a_missing_item_is_a_404(self, client):
        assert client.post("/notes/99999", data={"note": "x"}).status_code == 404


class TestHooks:
    def test_the_old_addresses_still_lead_somewhere(self, client):
        for old, new in (("/rooms", "/topics"), ("/rooms/tidy", "/topics/sort"),
                         ("/placards?all=1", "/notes?all=1")):
            resp = client.get(old, follow_redirects=False)
            assert (resp.status_code, resp.headers["location"]) == (301, new)
        assert client.post("/placards/99999", data={"note": "x"}).status_code == 404

    def test_rooms_surprise_and_suggestions(self, client, tiktok_ok):
        client.post("/save", json={"url": "https://www.tiktok.com/@citydesk/video/7123"})
        client.post("/save", json={"url": "https://www.tiktok.com/@citydesk/video/7124"})
        assert client.get("/topics").status_code == 200
        resp = client.get("/surprise", follow_redirects=False)
        assert resp.status_code == 303 and resp.headers["location"].startswith("/item/")
        data = client.get("/suggest.json", params={"q": "zoning"}).json()
        assert data["total"] == 2
        assert data["groups"][0]["title"] == "Saves"
        assert data["groups"][0]["rows"][0]["href"].startswith("/item/")
        assert client.get("/suggest.json", params={"q": "z"}).json()["groups"] == []

    def test_an_empty_library_has_nothing_to_surprise_with(self, client):
        assert client.get("/surprise", follow_redirects=False).headers["location"] == "/"

    def test_the_front_page_remembers_this_day(self, client, library):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc)
        db.upsert_item(library, {
            "canonical_url": "https://example.com/old", "shared_url": "x", "platform": "tiktok",
            "title": "A year-old keepsake", "resolve_status": "ok",
            "saved_at": today.replace(year=today.year - 4).isoformat(),
        })
        body = client.get("/").text
        assert "On this day" in body and "4 years ago" in body


class TestLook:
    def test_the_front_page_is_a_stack_of_colour_bands(self, client, tiktok_ok):
        client.post("/save", json={"url": "https://www.tiktok.com/@citydesk/video/7123"})
        body = client.get("/").text
        assert body.count('class="rr-band tone-') >= 2
        assert 'class="rr-reveal' in body   # rises into view once scripts run
        assert "and counting" in body

    def test_pages_load_the_fonts_and_the_script(self, client):
        body = client.get("/").text
        assert "family=Fredoka" in body and "family=Nunito" in body
        assert '/static/museum.js' in body


class TestMoreHooks:
    @pytest.fixture
    def three(self, client, library):
        for n in range(3):
            db.upsert_item(library, {
                "canonical_url": f"https://example.com/w{n}", "shared_url": "x", "platform": "tiktok",
                "title": f"Dog video {n} #dog", "tags": ["dog"], "resolve_status": "ok",
                "saved_at": f"202{4 + n % 2}-0{n + 1}-10T12:00:00+00:00",
            })
        return [r[0] for r in library.execute("SELECT id FROM items ORDER BY id").fetchall()]

    def test_wandering_carries_the_trail(self, client, three):
        resp = client.get(f"/wander/{three[0]}", follow_redirects=False)
        assert resp.status_code == 303
        loc = resp.headers["location"]
        assert loc.startswith("/item/") and f"trail={three[0]}" in loc and "via=" in loc
        page = client.get(loc).text
        assert "Down the rabbit hole via" in page and "Keep going" in page

    def test_junk_in_the_trail_is_ignored(self, client, three):
        resp = client.get(f"/wander/{three[0]}?trail=abc,,7x,{three[1]}", follow_redirects=False)
        assert resp.status_code == 303 and "abc" not in resp.headers["location"]

    def test_wander_from_nowhere_starts_somewhere(self, client, three):
        assert client.get("/wander", follow_redirects=False).headers["location"].startswith("/item/")

    def test_the_year_pages(self, client, three):
        assert "saves in 2024" in client.get("/year/2024").text
        assert client.get("/year/1999").status_code == 404
        assert client.get("/year/abcd").status_code == 404
        assert client.get("/year").status_code == 200


class TestTidyingRooms:
    @pytest.fixture
    def saves(self, library):
        ids = {}
        for n, (handle, title, tags) in enumerate([
            ("@pj", "Eddie on the radio", ["pearljam", "socialmedia"]),
            ("@pj", "Backstage", ["pearljam"]),
            ("@fan", "A great night", ["pearljam", "concert"]),
            ("@kay", "a bowl of soup", []),
        ]):
            ids[title], _ = db.upsert_item(library, {
                "canonical_url": f"https://example.com/{n}", "shared_url": "x", "platform": "tiktok",
                "title": title, "tags": tags, "creator_handle": handle, "resolve_status": "ok",
                "saved_at": f"2024-0{n + 1}-01T00:00:00+00:00"})
        return ids

    def themes(self, library, item_id):
        return db.loads_list(db.get_item(library, item_id)["themes"])

    def test_the_item_page_says_why(self, client, library, saves):
        page = client.get(f"/item/{saves['Eddie on the radio']}").text
        assert "Why it's in this topic" in page
        assert "#socialmedia" in page
        assert 'action="/item/%d/rooms"' % saves["Eddie on the radio"] in page

    def test_choosing_rooms(self, client, library, saves):
        item_id = saves["Eddie on the radio"]
        resp = client.post(f"/item/{item_id}/rooms", data={"room": ["Music"]}, follow_redirects=False)
        assert resp.status_code == 303 and resp.headers["location"] == f"/item/{item_id}"
        assert self.themes(library, item_id) == ["Music"]
        page = client.get(f"/item/{item_id}").text
        assert "you put it here" in page and "Let Faves decide again" in page
        client.post(f"/item/{item_id}/rooms", data={"reset": "1"})
        assert self.themes(library, item_id) == ["Marketing & media"]

    def test_choosing_for_the_whole_creator(self, client, library, saves):
        client.post(f"/item/{saves['Backstage']}/rooms", data={"room": ["Music"], "whole_creator": "1"})
        assert self.themes(library, saves["Eddie on the radio"])[0] == "Music"

    def test_the_tidy_page_teaches_hashtags(self, client, library, saves):
        page = client.get("/topics/sort").text
        assert "#pearljam" in page and "on 3 saves" in page
        resp = client.post("/topics/teach", data={"tag": "pearljam", "theme": "Music"},
                           follow_redirects=False)
        assert resp.headers["location"] == "/topics/sort#hashtags"
        assert self.themes(library, saves["Backstage"]) == ["Music"]
        assert "#pearljam" not in client.get("/topics/sort").text

    def test_settling_a_hunch(self, client, library, saves):
        item_id = saves["a bowl of soup"]
        assert self.themes(library, item_id) == ["Food & cooking"]
        assert f'/item/{item_id}/rooms' in client.get("/topics/sort").text
        client.post(f"/item/{item_id}/rooms", data={"room": ["Food & cooking"], "confirm": "1",
                                                    "next": "/topics/sort#hunches"})
        assert f'/item/{item_id}/rooms' not in client.get("/topics/sort").text
        assert self.themes(library, item_id) == ["Food & cooking"]

    def test_a_redirect_stays_in_the_museum(self, client, saves):
        resp = client.post(f"/item/{saves['Backstage']}/rooms",
                           data={"next": "//evil.example"}, follow_redirects=False)
        assert resp.headers["location"] == f"/item/{saves['Backstage']}"

    def test_rooms_links_to_tidying(self, client, saves):
        assert 'href="/topics/sort"' in client.get("/topics").text


class TestCleanLabels:
    def test_a_search_result_shows_the_caption_cleaned(self, client, library):
        db.upsert_item(library, {
            "canonical_url": "https://example.com/d", "shared_url": "x", "platform": "tiktok",
            "title": "Folding dumplings. For the party tonight! #cooking #fyp",
            "description": "Folding dumplings. For the party tonight! #cooking #fyp",
            "tags": ["cooking"], "resolve_status": "ok"})
        page = client.get("/search?theme=Food+%26+cooking").text
        assert 'class="rr-salon"' in page and 'class="rr-piece is-tall' in page
        assert ">Folding dumplings</a></h3>" in page
        assert "For the party tonight!" in page
        assert "#fyp" not in page.split('class="rr-salon"')[1].split("</main>")[0]


class TestKeepingInSync:
    @pytest.fixture
    def mac(self, tmp_path, monkeypatch):
        """A browser on the Mac the museum runs on."""
        monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "favorites.db"))
        monkeypatch.delenv("FAVORITES_WATCH", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        with TestClient(app, client=("127.0.0.1", 50000)) as c:
            yield c

    def old_tiktok_import(self, library, days=90):
        from datetime import datetime, timedelta, timezone
        at = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        db.upsert_item(library, {"canonical_url": "https://www.tiktok.com/@a/video/1", "shared_url": "x",
                                 "platform": "tiktok", "source": "export", "imported_at": at,
                                 "saved_at": at, "resolve_status": "pending"})

    def test_the_page(self, mac, library):
        self.old_tiktok_import(library)
        page = mac.get("/sync").text
        assert "Keep it in sync" in page and "Imported 90 days ago" in page
        assert "Never imported" in page  # Instagram, YouTube
        assert "Not watching a folder yet" in page
        assert "One-time setup" in page  # no Google client yet
        assert "Europe and the UK only" in page
        assert 'href="/sync"' in mac.get("/topics").text  # the footer

    def test_the_front_page_reminds_and_can_be_told_later(self, mac, library):
        self.old_tiktok_import(library)
        db.upsert_item(library, {"canonical_url": "https://example.com/ok", "shared_url": "x",
                                 "platform": "tiktok", "title": "a save", "resolve_status": "ok"})
        assert "since your TikTok export" in mac.get("/").text
        mac.post("/sync/snooze", data={"platform": "tiktok", "next": "/"})
        assert "since your TikTok export" not in mac.get("/").text

    def test_the_password_shows_only_on_the_mac(self, mac, client, monkeypatch):
        monkeypatch.setenv("FAVORITES_TOKEN", "sesame-123")
        assert "sesame-123" in mac.get("/sync").text
        page = client.get("/sync").text  # a phone on the wi-fi
        assert "sesame-123" not in page and "shown only on the Mac" in page

    def test_the_shortcut_gets_the_tailscale_address(self, mac, monkeypatch):
        import favorites.app as appmod
        monkeypatch.setenv("FAVORITES_TOKEN", "sesame-123")
        monkeypatch.setattr(appmod, "_wifi_address", lambda: "192.168.1.20")
        monkeypatch.setattr(appmod, "_tailscale_address", lambda: "100.101.102.103")
        page = mac.get("/sync").text
        assert 'data-copy="http://100.101.102.103:8000/save"' in page
        assert 'data-copy="Bearer sesame-123"' in page
        assert "home-wi-fi-only address" in page and "http://192.168.1.20:8000" in page

    def test_without_tailscale_it_says_the_address_is_home_only(self, mac, monkeypatch):
        import favorites.app as appmod
        monkeypatch.setenv("FAVORITES_TOKEN", "sesame-123")
        monkeypatch.setattr(appmod, "_wifi_address", lambda: "192.168.1.20")
        monkeypatch.setattr(appmod, "_tailscale_address", lambda: None)
        page = mac.get("/sync").text
        assert 'data-copy="http://192.168.1.20:8000/save"' in page
        assert "Tailscale isn't on on this Mac" in page

    def test_watching_and_looking_now(self, mac, tmp_path, monkeypatch):
        import zipfile, os, time, json as j
        d = tmp_path / "Downloads"
        d.mkdir()
        z = d / "TikTok_Data.zip"
        with zipfile.ZipFile(z, "w") as f:
            f.writestr("user_data_tiktok.json", j.dumps({"Likes and Favorites": {"Favorite Videos": {
                "FavoriteVideoList": [{"Date": "2024-05-01 10:00:00",
                                       "Link": "https://www.tiktokv.com/share/video/7/"}]}}}))
        os.utime(z, (time.time() - 600,) * 2)
        monkeypatch.setenv("FAVORITES_WATCH", str(d))
        import favorites.app as appmod
        monkeypatch.setattr(appmod, "_fill_in", lambda *a, **k: asyncio_noop())
        resp = mac.post("/sync/scan", follow_redirects=False)
        assert resp.headers["location"] == "/sync?done=scanned#folder"
        page = mac.get("/sync").text
        assert "Watching 1 folder" in page and "TikTok_Data.zip" in page and "1 new" in page

    def test_google_steps_happen_only_on_the_mac(self, client, mac, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "s")
        assert client.post("/sync/youtube/connect").status_code == 403
        resp = mac.post("/sync/youtube/connect", follow_redirects=False)
        assert resp.headers["location"].startswith("https://accounts.google.com/")
        assert "redirect_uri=http%3A%2F%2Flocalhost" in resp.headers["location"]
        assert "Connect Google" in mac.get("/sync").text

    def test_a_cancelled_google_sign_in(self, mac):
        resp = mac.get("/sync/youtube/callback?error=access_denied", follow_redirects=False)
        assert resp.headers["location"] == "/sync?done=youtube-cancelled#youtube"


async def _noop():
    return None


def asyncio_noop():
    return _noop()


class TestKeepingFromThePhone:
    @pytest.fixture
    def locked(self, client, monkeypatch):
        monkeypatch.setenv("FAVORITES_TOKEN", "sesame-123")
        return client

    def test_the_tab_bar_has_surprise_and_keep(self, client):
        page = client.get("/").text
        assert 'class="scoop" href="/surprise"' in page and 'href="/keep"' in page

    def test_a_surprise_offers_another(self, client, library):
        db.upsert_item(library, {"canonical_url": "https://example.com/s", "shared_url": "x",
                                 "platform": "tiktok", "title": "a save", "resolve_status": "ok"})
        resp = client.get("/surprise", follow_redirects=False)
        assert resp.headers["location"].endswith("?surprise=1")
        assert "Another surprise" in client.get(resp.headers["location"]).text

    def test_keeping_a_link(self, client, tiktok_ok):
        assert "Paste a TikTok" in client.get("/keep").text
        resp = client.post("/keep", data={"url": "https://www.tiktok.com/@citydesk/video/7123",
                                          "note": "for later"}, follow_redirects=False)
        assert resp.status_code == 303 and resp.headers["location"].endswith("?saved=1")

    def test_not_a_link(self, client):
        resp = client.post("/keep", data={"url": "hello"}, follow_redirects=False)
        assert resp.headers["location"] == "/keep?error=no-link"

    def test_a_password_is_asked_for_once(self, locked, tiktok_ok):
        assert "Remember this phone" in locked.get("/keep").text
        resp = locked.post("/keep", data={"url": "https://www.tiktok.com/@citydesk/video/7123"},
                           follow_redirects=False)
        assert resp.headers["location"] == "/keep"  # nothing kept yet
        assert locked.post("/unlock", data={"password": "wrong"},
                           follow_redirects=False).headers["location"] == "/keep?error=password"
        resp = locked.post("/unlock", data={"password": "sesame-123"}, follow_redirects=False)
        assert "favorites_key" in resp.headers["set-cookie"] and "HttpOnly" in resp.headers["set-cookie"]
        assert "Paste a TikTok" in locked.get("/keep").text
        resp = locked.post("/keep", data={"url": "https://www.tiktok.com/@citydesk/video/7123"},
                           follow_redirects=False)
        assert resp.headers["location"].endswith("?saved=1")
        # The same cookie lets Android's share sheet save, too.
        resp = locked.get("/share-target?url=https://www.tiktok.com/@citydesk/video/7124",
                          follow_redirects=False)
        assert resp.status_code == 303 and "saved=1" in resp.headers["location"]

    def test_forgetting_the_password(self, locked):
        locked.post("/unlock", data={"password": "sesame-123"})
        locked.post("/lock")
        assert "Remember this phone" in locked.get("/keep").text

    def test_saving_without_it_is_still_refused(self, locked):
        assert locked.post("/save", json={"url": "https://www.tiktok.com/@a/video/1"}).status_code == 401


def test_the_home_screen_icon(client):
    m = client.get("/manifest.webmanifest").json()
    assert m["name"] == "Faves" and m["theme_color"] == "#eee8fc"
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes and any(i.get("purpose") == "maskable" for i in m["icons"])
    for i in m["icons"]:
        assert client.get(i["src"]).status_code == 200
    page = client.get("/topics").text
    assert '<link rel="apple-touch-icon" href="/static/icon-180.png">' in page
    assert client.get("/static/icon-180.png").headers["content-type"] == "image/png"
