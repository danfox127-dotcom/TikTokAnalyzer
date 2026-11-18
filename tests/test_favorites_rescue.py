"""Rescue: the saves you forgot to make, read from what the export says you
did -- shared, came back to in another session, stayed on for minutes."""

import json

import pytest
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import db, rescue, watch
from favorites.importers import tiktok_export


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


def did(conn, kind, at, ref):
    conn.execute("INSERT INTO activity (platform, kind, at, ref) VALUES ('tiktok', ?, ?, ?)", (kind, at, ref))
    conn.commit()


@pytest.fixture
def history(conn):
    """Three evenings, each video opened 15 seconds after the last unless said.

    - 101: watched on two evenings -- came back to it.
    - 109: opened on two evenings, but flicked past the second time: not
      coming back to it.
    - 102: shared, and liked.
    - 103: liked, and stayed on for 100 seconds.
    - 110: stayed on for 100 seconds, not liked: on its own, not enough.
    - 111: liked, and 5 minutes before the next -- a phone set down, not watching.
    - 104: opened once, briefly: nothing to say.
    - 105: came back to it, but it's already saved.
    - 106: came back to it, but you passed on it.
    """
    evenings = {1: [("101", 15), ("104", 15), ("105", 15), ("106", 15), ("109", 15)],
                2: [("101", 15), ("105", 15), ("106", 15), ("109", 1), ("103", 100), ("110", 100),
                    ("111", 300), ("107", 15)],
                3: [("108", 15)]}
    for day, videos in evenings.items():
        secs = 0
        for ref, stay in videos:
            did(conn, "watch", f"2026-10-0{day}T20:{secs // 60:02d}:{secs % 60:02d}+00:00", ref)
            secs += stay
    did(conn, "share", "2026-10-02T21:00:00+00:00", "102")
    for ref in ("102", "103", "111"):
        did(conn, "like", "2026-10-02T21:01:00+00:00", ref)
    db.upsert_item(conn, {"canonical_url": "https://www.tiktok.com/video/105", "shared_url": "x", "platform": "tiktok",
                          "external_id": "105", "title": "kept", "resolve_status": "ok",
                          "saved_at": "2026-10-03T00:00:00+00:00"})
    rescue.skip(conn, "106")
    return conn


class TestWhichOnes:
    def test_the_ones_that_mattered(self, history):
        found = {c["ref"]: c["why"] for c in rescue.candidates(history)}
        assert found == {
            "102": ["You shared it", "You liked it"],
            "101": ["Watched in 2 different sessions"],
            "103": ["You stayed 1m 40s", "You liked it"],
        }

    def test_best_first(self, history):
        assert [c["ref"] for c in rescue.candidates(history)] == ["102", "101", "103"]

    def test_what_a_like_looked_up_says(self, history):
        history.execute("INSERT INTO videos (platform, external_id, creator_handle, title, status, looked_at)"
                        " VALUES ('tiktok', '102', '@cassie', 'Brown butter orzo', 'ok', '2026-10-05')")
        history.commit()
        top = rescue.candidates(history)[0]
        assert (top["title"], top["creator_handle"]) == ("Brown butter orzo", "@cassie")
        assert top["shared_url"] == "https://www.tiktokv.com/share/video/102/"

    def test_nothing_without_an_export(self, conn):
        assert rescue.candidates(conn) == []


class TestShares:
    def test_the_export_s_share_history_is_kept(self, tmp_path):
        p = tmp_path / "user_data_tiktok.json"
        p.write_text(json.dumps({"Your Activity": {"Share History": {"ShareHistoryList": [
            {"Date": "2026-10-02 21:00:00", "Link": "https://www.tiktokv.com/share/video/7400000000000000001/",
             "Method": "sms", "SharedContent": "video"},
            {"Date": "2026-10-03 21:00:00", "Link": "https://www.tiktok.com/@someone", "Method": "copy"}]}}}))
        assert tiktok_export.read_activity(p)["share"] == [("2026-10-02T21:00:00+00:00", "7400000000000000001")]

    def test_exports_already_read_are_read_again_for_them(self):
        assert watch.READS["tiktok"] == 4


class TestTheScreen:
    def test_one_at_a_time(self, client, history):
        page = client.get("/rescue").text
        assert "3 saves you forgot to make" in page and "3 left" in page and "it's surest about" not in page
        assert page.index('data-id="102"') < page.index('data-id="101"') < page.index('data-id="103"')
        assert 'data-embed="https://www.tiktok.com/player/v1/102' in page
        assert "You shared it" in page and 'action="/rescue/102/keep"' in page and 'action="/rescue/102/skip"' in page

    def test_keep(self, client, history, monkeypatch):
        asked = []

        async def fake_capture(shared, note, conn, collection=None, saved_at=None):
            asked.append(shared)
            item_id, created = db.upsert_item(conn, {
                "canonical_url": "https://www.tiktok.com/video/102", "shared_url": shared, "platform": "tiktok",
                "external_id": "102", "title": "Brown butter orzo", "resolve_status": "ok"})
            return {"id": item_id, "created": created}
        monkeypatch.setattr(web, "capture", fake_capture)
        r = client.post("/rescue/102/keep", headers={"Accept": "application/json"})
        assert asked == ["https://www.tiktokv.com/share/video/102/"]
        assert r.json()["said"] == "Saved ✓ Brown butter orzo"
        assert "102" not in [c["ref"] for c in rescue.candidates(history)]

    def test_pass(self, client, history):
        assert client.post("/rescue/101/skip", headers={"Accept": "application/json"}).json() == {"skipped": True}
        assert [c["ref"] for c in rescue.candidates(history)] == ["102", "103"]

    def test_only_a_video_number(self, client):
        assert client.post("/rescue/not-a-video/skip").status_code == 404

    def test_the_ways_in(self, client, history):
        assert 'href="/rescue"' in client.get("/browse").text
        js = client.get("/static/museum.js").text
        assert "form[data-onwards]" in js
