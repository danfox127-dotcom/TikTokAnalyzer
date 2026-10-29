"""Faves in the cloud: nothing shows without the password, nothing opens up when
a setting is missing, and the Vercel bundle has what the app needs."""

import ast
import json
import sys
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import backfill, cloud, db

ROOT = Path(__file__).resolve().parent.parent
HTML = {"accept": "text/html"}


@pytest.fixture
def cloud_app(tmp_path, monkeypatch):
    """The app as it runs on Vercel, with one save in its library."""
    monkeypatch.setenv("FAVES_CLOUD", "1")
    monkeypatch.setenv("FAVORITES_TOKEN", "sesame")
    if not db.on_postgres():
        # The library is a test file here, not Supabase: only the password
        # counts as a setting the cloud copy could be missing.
        real = cloud.missing
        monkeypatch.setattr(cloud, "missing", lambda: [n for n in real() if n != "DATABASE_URL"])
    conn = db.connect()
    item = db.upsert_item(conn, {
        "canonical_url": "https://www.tiktok.com/video/7123", "shared_url": "https://www.tiktok.com/@a/video/7123",
        "platform": "tiktok", "title": "A secret zoning meeting", "resolve_status": "ok",
        "thumbnail_url": "https://example.com/p.jpg"})[0]
    conn.close()
    with TestClient(web.app, base_url="https://faves.example.vercel.app") as client:
        client.item = item
        yield client


def sign_in(client, password="sesame", next="/"):
    return client.post("/unlock", data={"password": password, "next": next}, follow_redirects=False)


class TestSignedOut:
    @pytest.mark.parametrize("path", ["/", "/search?q=zoning", "/shuffle", "/topics", "/notes", "/sync",
                                      "/keep", "/more", "/year", "/creator/@a"])
    def test_every_page_asks_for_the_password_first(self, cloud_app, path):
        r = cloud_app.get(path, headers=HTML, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=")

    def test_it_comes_back_to_the_page_you_wanted(self, cloud_app):
        r = cloud_app.get(f"/item/{cloud_app.item}?saved=1", headers=HTML, follow_redirects=False)
        assert r.headers["location"] == f"/signin?next=%2Fitem%2F{cloud_app.item}%3Fsaved%3D1"
        r = sign_in(cloud_app, next=f"/item/{cloud_app.item}?saved=1")
        assert r.headers["location"] == f"/item/{cloud_app.item}?saved=1"

    def test_pictures_and_data_are_refused_not_redirected(self, cloud_app):
        assert cloud_app.get(f"/thumb/{cloud_app.item}").status_code == 401
        assert cloud_app.get("/suggest.json?q=zon").status_code == 401
        assert cloud_app.post("/save", json={"url": "https://www.tiktok.com/video/1"}).status_code == 401

    def test_the_sign_in_page_shows_nothing_of_the_library(self, cloud_app):
        page = cloud_app.get("/signin", headers=HTML).text
        assert 'name="password"' in page and "zoning" not in page
        assert "rr-tabbar" not in page and "rr-footer" not in page

    def test_what_a_page_needs_to_draw_stays_open(self, cloud_app):
        assert cloud_app.get("/static/style.css").status_code == 200
        assert cloud_app.get("/manifest.webmanifest").status_code == 200
        health = cloud_app.get("/healthz").json()
        assert health == {"ok": True, "cloud": True, "missing": [], "version": None}


class TestSigningIn:
    def test_a_wrong_password_says_so_and_remembers_nothing(self, cloud_app):
        r = sign_in(cloud_app, password="open sesame", next="/notes")
        assert r.headers["location"] == "/signin?next=%2Fnotes&error=password"
        assert "set-cookie" not in r.headers
        assert "didn't match" in cloud_app.get(r.headers["location"], headers=HTML).text

    def test_the_right_one_is_remembered_for_a_year_and_only_sent_securely(self, cloud_app):
        cookie = sign_in(cloud_app).headers["set-cookie"]
        assert "Max-Age=31536000" in cookie and "HttpOnly" in cookie and "Secure" in cookie
        assert "samesite=lax" in cookie.lower()
        page = cloud_app.get("/", headers=HTML)
        assert page.status_code == 200 and "in your own cloud database" in page.text
        assert cloud_app.get(f"/thumb/{cloud_app.item}", follow_redirects=False).status_code == 302

    @pytest.mark.parametrize("next", ["//evil.example", "/\\evil.example", "/\t/evil.example",
                                      "https://evil.example"])
    def test_signing_in_never_sends_you_off_site(self, cloud_app, next):
        assert sign_in(cloud_app, next=next).headers["location"] == "/"
        assert 'name="next" value="/"' in cloud_app.get("/signin", params={"next": next}, headers=HTML).text

    def test_signing_out_forgets_it(self, cloud_app):
        sign_in(cloud_app)
        r = cloud_app.post("/lock", follow_redirects=False)
        assert r.headers["location"] == "/signin"
        cloud_app.cookies.clear()
        assert cloud_app.get("/", headers=HTML, follow_redirects=False).status_code == 303

    def test_the_phone_shortcut_saves_with_the_password_as_before(self, cloud_app, monkeypatch):
        async def fake_capture(shared, note, conn, collection=None, saved_at=None):
            return {"id": 1, "created": True}
        monkeypatch.setattr(web, "capture", fake_capture)
        r = cloud_app.post("/save", json={"url": "https://www.tiktok.com/video/9"},
                           headers={"authorization": "Bearer sesame"})
        assert r.status_code == 201
        assert cloud_app.get("/collections.json", headers={"authorization": "Bearer sesame"}).status_code == 200


class TestASettingMissing:
    def test_every_page_says_which_and_shows_nothing_else(self, monkeypatch):
        monkeypatch.setenv("FAVES_CLOUD", "1")
        monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
        with TestClient(web.app) as client:
            for path in ("/", "/item/1", "/thumb/1", "/signin"):
                r = client.get(path, headers=HTML)
                assert r.status_code == 503, path
                assert "FAVORITES_TOKEN" in r.text and "Redeploy" in r.text
            # Not even the password gets you in: there is none to check against.
            assert client.post("/unlock", data={"password": ""}, follow_redirects=False).headers[
                "location"].startswith("/signin")
            assert "FAVORITES_TOKEN" in client.get("/healthz").json()["missing"]

    def test_both_missing_names_both(self, monkeypatch):
        monkeypatch.setenv("FAVES_CLOUD", "1")
        monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with TestClient(web.app) as client:
            page = client.get("/", headers=HTML).text
        assert "needs two settings" in page and "DATABASE_URL" in page


class TestTheCloudPages:
    def test_keep_it_in_sync_gives_the_cloud_address(self, cloud_app):
        sign_in(cloud_app)
        page = cloud_app.get("/sync", headers=HTML).text
        assert "<code>https://faves.example.vercel.app/save</code>" in page
        assert "Your Mac does the watching" in page and "Faves in the cloud." in page
        assert "Tailscale address" not in page and "White screen" not in page
        assert "change its address to <code>https://faves.example.vercel.app/save</code>" in page
        assert "This Mac can't prepare" not in page
        assert "sesame" not in page  # the password is never shown off the Mac

    def test_mac_only_actions_stay_on_the_mac(self, cloud_app):
        sign_in(cloud_app)
        assert cloud_app.post("/sync/youtube/connect").status_code == 403

    def test_no_background_work_starts_in_the_cloud(self, monkeypatch):
        monkeypatch.setenv("FAVES_CLOUD", "1")
        started = []
        monkeypatch.setattr(web, "_keep_in_sync", lambda: started.append(1))
        with TestClient(web.app):
            pass
        assert started == []


def test_the_mac_fills_in_only_shared_saves_still_waiting():
    conn = db.connect()
    assert not _waiting()
    db.upsert_item(conn, {"canonical_url": "https://x.com/a/status/1", "shared_url": "x", "platform": "x",
                          "resolve_status": "failed", "source": "tiktok-export"})
    assert not _waiting()  # an import's leftovers are backfill's business
    item = db.upsert_item(conn, {"canonical_url": "https://www.tiktok.com/video/5", "shared_url": "x",
                                 "platform": "tiktok", "resolve_status": "failed"})[0]
    assert _waiting()
    conn.execute("UPDATE items SET resolve_attempts = ? WHERE id = ?", (backfill.MAX_ATTEMPTS, item))
    conn.commit()
    conn.close()
    assert not _waiting()  # tried enough


def _waiting() -> bool:
    return web._shared_waiting()


class TestTheBundle:
    """What Vercel installs and uploads: Faves, its libraries, nothing else."""

    def test_it_installs_everything_faves_imports(self):
        wanted = {"PIL": "pillow", "fastapi": "fastapi", "starlette": "fastapi", "httpx": "httpx",
                  "psycopg": "psycopg", "youtube_transcript_api": "youtube-transcript-api",
                  "jinja2": "jinja2", "multipart": "python-multipart"}
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())
        installs = {d.split("[")[0].split(">")[0].split("=")[0].strip().lower()
                    for d in project["project"]["dependencies"]}
        imported = set()
        for f in (ROOT / "favorites").rglob("*.py"):
            if ".venv" in f.parts:
                continue
            for node in ast.walk(ast.parse(f.read_text())):
                if isinstance(node, ast.Import):
                    imported |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported.add(node.module.split(".")[0])
        third_party = {m for m in imported if m not in sys.stdlib_module_names and m != "favorites"}
        assert third_party <= set(wanted), f"add these to pyproject.toml: {third_party - set(wanted)}"
        assert {wanted[m] for m in third_party} | {"jinja2", "python-multipart"} <= installs

    def test_it_runs_the_faves_app(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())
        assert project["tool"]["vercel"]["entrypoint"] == "favorites.app:app"
        config = json.loads((ROOT / "vercel.json").read_text())
        assert list(config["functions"]) == ["favorites/app.py"]
        assert config["regions"] == ["pdx1"]  # next to the database, in us-west-2

    def test_only_faves_is_uploaded(self):
        rules = [l for l in (ROOT / ".vercelignore").read_text().splitlines() if l and not l.startswith("#")]
        assert rules[0] == "/*"
        assert {"!/favorites", "!/pyproject.toml", "!/vercel.json"} <= set(rules)
        assert "!/api" not in rules  # the old analyzer's functions stay out
