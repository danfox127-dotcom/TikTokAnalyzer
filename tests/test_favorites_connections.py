"""Connections: everything that feeds the library, one row each, with a
status in words and a button only where something needs you."""

import html
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import cloud, db

HTML = {"accept": "text/html"}


def rows(page):
    """Each row's name -> (state, status in words, its button or None)."""
    out = {}
    for state, main, rest in re.findall(
            r'<li class="conn-row is-(\w+)">\s*<a class="conn-main" href="[^"]+">(.*?)</a>(.*?)</li>', page, re.S):
        name = re.search(r"<b>(.*?)</b>", main).group(1)
        status = html.unescape(" ".join(re.sub(r"<[^>]+>", " ", main.split("</b>", 1)[1]).split()))
        button = re.search(r'<a class="rr-btn[^"]*" href="([^"]+)">([^<]+)</a>', rest)
        out[name] = (state, status, (button.group(2), button.group(1)) if button else None)
    return out


def ago(**kw):
    return (datetime.now(timezone.utc) - timedelta(**kw)).replace(microsecond=0).isoformat()


def add(conn, n, **fields):
    db.upsert_item(conn, {"canonical_url": f"https://example.com/{n}", "shared_url": "x",
                          "platform": "tiktok", "resolve_status": "ok", **fields})


@pytest.fixture
def mac(monkeypatch):
    """A browser on the Mac Faves runs on."""
    monkeypatch.setattr(web, "_cloud_address", lambda request: None)
    monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
    monkeypatch.delenv("FAVES_CLOUD", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    with TestClient(web.app, client=("127.0.0.1", 50000)) as c:
        yield c


@pytest.fixture
def library():
    conn = db.connect()
    yield conn
    conn.close()


@pytest.fixture
def cloud_app(monkeypatch):
    """The cloud copy, signed in."""
    monkeypatch.setenv("FAVES_CLOUD", "1")
    monkeypatch.setenv("FAVORITES_TOKEN", "sesame")
    if not db.on_postgres():
        real = cloud.missing
        monkeypatch.setattr(cloud, "missing", lambda: [n for n in real() if n != "DATABASE_URL"])
    with TestClient(web.app, base_url="https://faves.example.vercel.app") as client:
        client.post("/unlock", data={"password": "sesame", "next": "/"}, follow_redirects=False)
        yield client


class TestOnTheMac:
    def test_a_new_library(self, mac, library):
        page = mac.get("/connections").text
        r = rows(page)
        assert r["This phone"] == ("need", "Needs you: Nothing saved from a phone yet", ("Set it up", "/setup"))
        assert r["TikTok"] == ("idle", "No export added yet", ("How", "/sync#exports"))
        assert r["Titles and pictures"] == ("idle", "Nothing saved yet", None)
        if db.on_postgres():
            assert r["This Mac"] == ("ok", "Keeping the cloud copy filled in", None)
            assert r["Your library"][1] == "In your own cloud database"
        else:
            assert r["Your Mac"] == ("ok", "Your library lives here", None)
            assert r["Your library"][1] == "On this Mac, in one file"
        assert "<b>1 thing needs you.</b>" in page
        assert '<a href="/sync">Every detail and how-to is in Keep it in sync →</a>' in page

    def test_a_save_from_the_phone_and_an_export_due(self, mac, library):
        add(library, 1, source="share", saved_at=ago(minutes=30))
        add(library, 2, source="export", imported_at=ago(days=90), saved_at=ago(days=90))
        r = rows(mac.get("/connections").text)
        assert r["This phone"] == ("ok", "Last save from a phone 30 minutes ago", None)
        assert r["TikTok"] == ("need", "Needs you: Last export 90 days ago: time for a new one",
                               ("Get one", "/sync#exports"))
        assert r["Instagram"][0] == "idle"

    def test_a_recent_export_is_fine(self, mac, library):
        add(library, 1, source="export", imported_at=ago(days=1), saved_at=ago(days=1))
        assert rows(mac.get("/connections").text)["TikTok"] == ("ok", "Export added yesterday", None)

    def test_titles_and_pictures_still_missing(self, mac, library):
        add(library, 1)
        add(library, 2, resolve_status="pending")
        assert rows(mac.get("/connections").text)["Titles and pictures"] == (
            "idle", "1 found · 1 missing (deleted or private videos stay that way)", ("Look", "/sync#details"))

    def test_everything_working(self, mac, library):
        add(library, 1, source="share", saved_at=ago(hours=3))
        page = mac.get("/connections").text
        assert "All working." in page and "needs you" not in page
        assert rows(page)["Titles and pictures"] == ("ok", "All 1 found", None)


class TestInTheCloud:
    @pytest.mark.parametrize("seen, expected", [
        (None, ("need", "Needs you: Hasn't checked in yet: open Faves there (start.command)", None)),
        (dict(minutes=3), ("ok", "Checked in 3 minutes ago", None)),
        (dict(days=3), ("need", "Needs you: Last checked in 3 days ago: open Faves there to catch up", None)),
    ])
    def test_it_says_when_the_mac_last_checked_in(self, cloud_app, library, seen, expected):
        if seen:
            db.set_meta(library, web.MAC_SEEN, ago(**seen))
        assert rows(cloud_app.get("/connections", headers=HTML).text)["Your Mac"] == expected
    # Signed out, it asks for the password like every page: test_favorites_cloud.TestSignedOut.


class TestTheMacChecksIn:
    def test_only_a_cloud_library_gets_the_note(self, library):
        if db.on_postgres():
            pytest.skip("the library here is the cloud database")
        web._mark_the_mac_seen()
        assert db.get_meta(library, web.MAC_SEEN) is None

    def test_the_cloud_library_gets_the_time(self, tmp_path, monkeypatch):
        if not db.on_postgres():
            path = tmp_path / "cloud.db"

            def connect(*args, **kwargs):
                c = sqlite3.connect(path)
                c.row_factory = sqlite3.Row
                c.executescript(db.SCHEMA)
                return c
            monkeypatch.setattr(db, "connect", connect)
            monkeypatch.setattr(db, "on_postgres", lambda: True)
        web._mark_the_mac_seen()
        conn = db.connect()
        try:
            seen = datetime.fromisoformat(db.get_meta(conn, web.MAC_SEEN))
        finally:
            conn.close()
        assert datetime.now(timezone.utc) - seen < timedelta(minutes=1)


class TestAgo:
    @pytest.mark.parametrize("delta, words", [
        (timedelta(seconds=20), "just now"), (timedelta(minutes=12), "12 minutes ago"),
        (timedelta(minutes=80), "an hour ago"), (timedelta(hours=5), "5 hours ago"),
        (timedelta(days=1, hours=2), "yesterday"), (timedelta(days=12), "12 days ago")])
    def test_words(self, delta, words):
        now = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
        assert web._ago((now - delta).isoformat(), now) == words

    def test_nonsense_is_a_while_ago(self):
        assert web._ago("not a date", datetime.now(timezone.utc)) == "a while ago"
