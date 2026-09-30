"""YouTube playlists via Google sign-in, against a faked Google."""

import asyncio
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from favorites import db, google_sync


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "shh")
    c = db.connect(str(tmp_path / "lib.db"))
    yield c
    c.close()


def run(coro):
    return asyncio.run(coro)


def connected(conn):
    db.set_meta(conn, "google_refresh_token", "refresh-1")


def fake_google(playlists, items, token_status=200):
    respx.post(google_sync.TOKEN_URL).mock(return_value=httpx.Response(
        token_status, json={"access_token": "access-1"} if token_status == 200 else {"error": "invalid_grant"}))

    def playlist_pages(request):
        page = request.url.params.get("pageToken")
        if page is None and len(playlists) > 1:
            return httpx.Response(200, json={"items": playlists[:1], "nextPageToken": "p2"})
        return httpx.Response(200, json={"items": playlists[1:] if page else playlists})

    respx.get(f"{google_sync.API}/playlists").mock(side_effect=playlist_pages)
    respx.get(f"{google_sync.API}/playlistItems").mock(side_effect=lambda r: httpx.Response(
        200, json={"items": items.get(r.url.params["playlistId"], [])}))


def pl(pid, title):
    return {"id": pid, "snippet": {"title": title}}


def vid(video_id, added="2024-03-01T10:00:00Z"):
    return {"snippet": {"publishedAt": added}, "contentDetails": {"videoId": video_id}}


class TestSignIn:
    def test_the_sign_in_address(self, conn):
        url = google_sync.start(conn, "http://localhost:8000/sync/youtube/callback")
        q = parse_qs(urlparse(url).query)
        assert url.startswith(google_sync.AUTH_URL)
        assert q["scope"] == [google_sync.SCOPE] and q["access_type"] == ["offline"]
        assert q["code_challenge_method"] == ["S256"] and q["client_id"] == ["cid.apps.googleusercontent.com"]
        assert q["redirect_uri"] == ["http://localhost:8000/sync/youtube/callback"]

    @respx.mock
    def test_finishing_keeps_the_refresh_token(self, conn):
        url = google_sync.start(conn, "http://localhost:8000/sync/youtube/callback")
        state = parse_qs(urlparse(url).query)["state"][0]
        route = respx.post(google_sync.TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "a", "refresh_token": "r"}))
        run(google_sync.finish(conn, "the-code", state))
        sent = parse_qs(route.calls.last.request.content.decode())
        assert sent["code"] == ["the-code"] and sent["code_verifier"][0]
        assert google_sync.connected(conn)

    def test_a_sign_in_that_did_not_start_here_is_refused(self, conn):
        google_sync.start(conn, "http://localhost:8000/x")
        with pytest.raises(PermissionError):
            run(google_sync.finish(conn, "code", "someone-elses-state"))
        assert not google_sync.connected(conn)

    @respx.mock
    def test_disconnect_revokes_and_forgets(self, conn):
        connected(conn)
        route = respx.post(google_sync.REVOKE_URL).mock(return_value=httpx.Response(200))
        run(google_sync.disconnect(conn))
        assert route.called and not google_sync.connected(conn)


class TestSync:
    @respx.mock
    def test_every_playlist_comes_in_filed_under_its_name(self, conn):
        connected(conn)
        fake_google([pl("PL1", "Recipes"), pl("PL2", "Woodworking")],
                    {"PL1": [vid("aaaaaaaaaaa"), vid("bbbbbbbbbbb", "2023-01-02T00:00:00Z")],
                     "PL2": [vid("aaaaaaaaaaa", "2025-01-01T00:00:00Z"), vid("bad")]})
        result = run(google_sync.sync(conn))
        assert (result["playlists"], result["videos"], result["added"]) == (2, 3, 2)
        rows = {r["external_id"]: r for r in conn.execute("SELECT * FROM items")}
        assert rows["aaaaaaaaaaa"]["source"] == "youtube-sync"
        assert rows["bbbbbbbbbbb"]["saved_at"].startswith("2023-01-02")
        assert sorted(db.collections_for(conn, rows["aaaaaaaaaaa"]["id"])) == ["Recipes", "Woodworking"]
        assert google_sync.last_sync(conn)["added"] == 2

    @respx.mock
    def test_syncing_again_adds_only_what_is_new(self, conn):
        connected(conn)
        fake_google([pl("PL1", "Recipes")], {"PL1": [vid("aaaaaaaaaaa")]})
        run(google_sync.sync(conn))
        assert run(google_sync.sync(conn))["added"] == 0

    @respx.mock
    def test_a_revoked_sign_in_is_forgotten(self, conn):
        connected(conn)
        fake_google([], {}, token_status=400)
        with pytest.raises(google_sync.NotConnected):
            run(google_sync.sync(conn))
        assert not google_sync.connected(conn)

    def test_not_connected(self, conn):
        with pytest.raises(google_sync.NotConnected):
            run(google_sync.sync(conn))
