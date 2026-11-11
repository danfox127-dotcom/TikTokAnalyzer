"""Rewind: a month on TikTok from your own export -- what it keeps, the
numbers it tells, the likes the Mac looks up, and the story page."""

import asyncio
import json
import re
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import backfill, db, rewind, watch
from favorites.importers import tiktok_export
from favorites.resolve import Resolved

NY = rewind.zone("America/New_York")
DECEMBER = datetime(2026, 12, 1, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def conn():
    c = db.connect()
    yield c
    c.close()


def link(vid):
    return f"https://www.tiktokv.com/share/video/{vid}/"


def activity(conn, kind, at, ref):
    conn.execute("INSERT INTO activity (platform, kind, at, ref) VALUES ('tiktok', ?, ?, ?)", (kind, at, ref))
    conn.commit()


def save(conn, ext, handle, themes, at, duration=None):
    db.upsert_item(conn, {"canonical_url": f"https://www.tiktok.com/video/{ext}", "shared_url": "x",
                          "platform": "tiktok", "external_id": ext, "creator_handle": handle,
                          "title": f"a save {ext}", "resolve_status": "ok", "saved_at": at, "duration": duration})
    conn.execute("UPDATE items SET themes = ? WHERE external_id = ?", (json.dumps(themes), ext))
    conn.commit()


def looked_up(conn, ext, handle=None, themes=(), status="ok", attempts=1, at="2026-11-01T00:00:00+00:00"):
    conn.execute("INSERT INTO videos (platform, external_id, creator_handle, themes, status, attempts, looked_at)"
                 " VALUES ('tiktok', ?, ?, ?, ?, ?, ?)", (ext, handle, json.dumps(list(themes)), status, attempts, at))
    conn.commit()


@pytest.fixture
def october(conn):
    """A sample October and September, with known answers."""
    for day in range(3, 22):                      # 11am in New York, Oct 3-21
        activity(conn, "watch", f"2026-10-{day:02d}T15:00:00+00:00", f"9{day}")
    for n in range(4):                            # Saturday Oct 10, 11pm in New York
        activity(conn, "watch", "2026-10-11T03:00:00+00:00", f"80{n}")
    activity(conn, "watch", "2026-10-01T02:30:00+00:00", "700")  # Sept 30 in New York, Oct 1 in UTC
    for n in range(10):
        activity(conn, "watch", f"2026-09-10T15:{n:02d}:00+00:00", f"60{n}")
    # Saves: Casee Brim four times, mostly Home & DIY.
    save(conn, "101", "@caseebrim", ["Home & DIY"], "2026-10-05T12:00:00+00:00", 40)
    save(conn, "102", "@caseebrim", ["Home & DIY"], "2026-10-06T12:00:00+00:00", 60)
    save(conn, "103", "@caseebrim", ["Comedy"], "2026-10-07T12:00:00+00:00", 20)
    save(conn, "104", "@caseebrim", ["Home & DIY"], "2026-10-08T12:00:00+00:00")
    # Likes: one is also a save, three by Jason Pargin, two not looked up yet.
    for n, ref in enumerate(["101", "201", "202", "203", "204", "205"]):
        activity(conn, "like", f"2026-10-1{n}T18:00:00+00:00", ref)
    for ref in ("201", "202", "203"):
        looked_up(conn, ref, "@jasonpargin", ["News & politics"])
    looked_up(conn, "204", status="unresolved")
    for n, term in enumerate(("orzo", "Ballot questions", "orzo", "lagarde")):
        activity(conn, "search", f"2026-10-12T1{n}:00:00+00:00", term)
    # September: mostly comedy, Jason Pargin third.
    for ext, who, topic in [("109", "@someone", "Comedy"), ("110", "@someone", "Comedy"),
                            ("111", "@someone", "Comedy"), ("112", "@other", "Comedy"),
                            ("113", "@other", "Comedy"), ("115", "@other", "Home & DIY"),
                            ("114", "@jasonpargin", "Comedy")]:
        save(conn, ext, who, [topic], f"2026-09-1{ext[-1]}T12:00:00+00:00")
    return conn


def export_file(tmp_path, data, name="user_data_tiktok.json"):
    p = tmp_path / name
    p.write_text(json.dumps(data))
    return p


class TestReadingTheExport:
    def test_watch_likes_and_searches(self, tmp_path):
        p = export_file(tmp_path, {
            "Your Activity": {
                "Video Browsing History": {"VideoList": [
                    {"Date": "2026-10-05 14:22:01", "Link": link(7001)},
                    {"Date": "", "Link": link(7002)},                 # no date: left out
                    {"Date": "2026-10-05 14:23:00", "Link": "https://example.com/x"}]},  # no id
                "Searches": {"SearchList": [{"Date": "2026-10-06 09:00:00", "SearchTerm": " orzo "},
                                            {"Date": "2026-10-06 09:01:00", "SearchTerm": ""}]}},
            "Likes and Favorites": {"Like List": {"ItemFavoriteList": [
                {"date": "2026-10-07 20:00:00", "link": link(7003)}]}},
        })
        assert tiktok_export.read_activity(p) == {
            "watch": [("2026-10-05T14:22:01+00:00", "7001")],
            "like": [("2026-10-07T20:00:00+00:00", "7003")],
            "search": [("2026-10-06T09:00:00+00:00", "orzo")]}

    @pytest.mark.parametrize("shape", [("Activity", "Video Browsing History"), ("Your Activity", "Watch History")])
    def test_older_and_newer_shapes(self, tmp_path, shape):
        p = export_file(tmp_path, {shape[0]: {shape[1]: {"VideoList": [{"Date": "2026-10-05 14:22:01",
                                                                        "Link": link(7001)}]}}})
        assert tiktok_export.read_activity(p)["watch"] == [("2026-10-05T14:22:01+00:00", "7001")]

    def test_a_second_overlapping_export_adds_only_whats_new(self, conn):
        first = {"watch": [("2026-10-05T14:22:01+00:00", "7001")], "like": [], "search": [("2026-10-06T09:00:00+00:00", "orzo")]}
        assert tiktok_export.import_activity(conn, first) == {"watch": 1, "like": 0, "search": 1}
        second = {"watch": first["watch"] + [("2026-10-09T10:00:00+00:00", "7009")], "like": [], "search": first["search"]}
        assert tiktok_export.import_activity(conn, second) == {"watch": 1, "like": 0, "search": 0}

    def test_importing_an_export_keeps_its_activity_and_not_its_likes_as_saves(self, conn, tmp_path):
        p = export_file(tmp_path, {
            "Activity": {"Video Browsing History": {"VideoList": [{"Date": "2026-10-05 14:22:01", "Link": link(7001)}]},
                         "Favorite Videos": {"FavoriteVideoList": [{"Date": "2026-10-04 10:00:00", "Link": link(7100)}]},
                         "Like List": {"ItemFavoriteList": [{"Date": "2026-10-07 20:00:00", "Link": link(7003)}]}}})
        r = tiktok_export.import_export(conn, p)
        assert r["favorites"]["imported"] == 1 and r["activity"] == {"watch": 1, "like": 1, "search": 0}
        assert [row[0] for row in conn.execute("SELECT external_id FROM items")] == ["7100"]


class TestTheWatchedFolder:
    def test_an_export_read_before_is_read_once_more_and_keeps_its_date(self, conn, tmp_path):
        folder = tmp_path / "Downloads"
        folder.mkdir()
        p = export_file(folder, {"Activity": {"Video Browsing History": {"VideoList": [
            {"Date": "2026-10-05 14:22:01", "Link": link(7001)}]}}})
        conn.execute("INSERT INTO imports (key, filename, platform, imported_at, added) VALUES (?, ?, 'tiktok', ?, 0)",
                     (watch.fingerprint(p), p.name, "2026-10-20T08:00:00+00:00"))
        conn.commit()
        later = time.time() + 3600
        found = watch.scan(conn, [folder], now=later)
        assert len(found) == 1
        assert conn.execute("SELECT count(*) FROM activity WHERE kind = 'watch'").fetchone()[0] == 1
        assert watch.last_imports(conn)["tiktok"]["at"] == "2026-10-20T08:00:00+00:00"  # not "today"
        assert watch.scan(conn, [folder], now=later) == []


class TestAMonth:
    def test_how_much(self, october):
        m = rewind.month(october, "2026-10", NY, now=DECEMBER)
        assert (m["opened"], m["prev_opened"], m["change"]) == (23, 11, 109)
        assert m["coverage"] == "Oct 3–21"
        assert (m["seconds"], m["seconds_guessed"], m["hours"]) == (40, False, 0)
        assert m["tz"] == "America/New_York"

    def test_the_month_is_your_month_not_utcs(self, october):
        assert rewind.month(october, "2026-10", None, now=DECEMBER)["opened"] == 24
        assert rewind.month(october, "2026-10", None, now=DECEMBER)["coverage"] == "Oct 1–21"

    def test_the_clock(self, october):
        m = rewind.month(october, "2026-10", NY, now=DECEMBER)
        assert m["busiest"] == {"day": "Saturday", "hour": 23}
        assert m["clock"][5][23] == 4 and m["peak"] == 4
        assert sum(map(sum, m["clock"])) == 23

    def test_who(self, october):
        m = rewind.month(october, "2026-10", NY, now=DECEMBER)
        assert [(c["name"], c["count"], c["was"]) for c in m["creators"]] == [
            ("@caseebrim", 4, "new"), ("@jasonpargin", 3, "up from 3rd")]
        assert (m["liked"], m["kept"], m["waiting"], m["saved"], m["looked_at"]) == (6, 1, 2, 4, 7)

    def test_what(self, october):
        m = rewind.month(october, "2026-10", NY, now=DECEMBER)
        assert [(t["name"], t["share"]) for t in m["themes"]] == [
            ("Home & DIY", 43), ("News & politics", 43), ("Comedy", 14)]
        assert m["jump"]["name"] == "News & politics" and (m["jump"]["share"], m["jump"]["before"]) == (43, 0)
        assert m["searches"] == ["orzo", "ballot questions", "lagarde"] and m["searched"] == 4

    def test_a_small_rise_is_not_a_jump(self, conn):
        for n in range(10):
            save(conn, f"3{n}", "@a", ["Comedy" if n < 9 else "Style"], f"2026-09-1{n}T12:00:00+00:00")
            save(conn, f"4{n}", "@a", ["Comedy" if n < 8 else "Style"], f"2026-10-1{n}T12:00:00+00:00")
        activity(conn, "watch", "2026-10-02T12:00:00+00:00", "1")
        assert rewind.month(conn, "2026-10", NY, now=DECEMBER)["jump"] is None  # Style 10% -> 20%, only two saves

    def test_a_guess_when_nothing_saved_has_a_length(self, conn):
        activity(conn, "watch", "2026-10-02T12:00:00+00:00", "1")
        m = rewind.month(conn, "2026-10", NY, now=DECEMBER)
        assert (m["seconds"], m["seconds_guessed"]) == (rewind.GUESS_SECONDS, True)

    def test_the_month_so_far(self, october):
        assert rewind.month(october, "2026-10", NY, now=datetime(2026, 10, 25, tzinfo=timezone.utc))["coverage"] == "Oct 3–21"
        activity(october, "watch", "2026-10-01T15:00:00+00:00", "1")
        assert rewind.month(october, "2026-10", NY, now=datetime(2026, 10, 25, tzinfo=timezone.utc))["coverage"] == "Oct 1–21, so far"

    def test_nothing_to_say(self, october):
        assert rewind.month(october, "2026-07", NY, now=DECEMBER) is None
        assert rewind.months(october) == ["2026-10", "2026-09"] and rewind.latest(october) == "2026-10"


    def test_the_months_are_your_months(self, conn):
        # 10pm on Halloween in New York is already November in UTC.
        activity(conn, "watch", "2026-11-01T02:00:00+00:00", "1")
        assert rewind.months(conn, NY) == ["2026-10"] and rewind.months(conn) == ["2026-11"]
        tokyo = rewind.zone("Asia/Tokyo")
        activity(conn, "watch", "2026-09-30T20:00:00+00:00", "2")   # Oct 1, 5am in Tokyo
        assert rewind.months(conn, tokyo) == ["2026-11", "2026-10"]


class TestLookingUpLikes:
    def test_which_likes_are_looked_up(self, october):
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        # 101 is a save, 201-203 are known, 204 failed within the day; 205 is new.
        assert rewind.likes_to_look_up(october, now=now) == ["205"]
        later = datetime(2026, 11, 3, tzinfo=timezone.utc)
        assert rewind.likes_to_look_up(october, now=later) == ["205", "204"]  # newest like first
        october.execute("UPDATE videos SET attempts = ? WHERE external_id = '204'", (backfill.MAX_ATTEMPTS,))
        assert rewind.likes_to_look_up(october, now=later) == ["205"]

    def test_a_like_gets_its_creator_and_topic(self, conn, monkeypatch):
        activity(conn, "like", "2026-10-10T18:00:00+00:00", "301")
        activity(conn, "like", "2026-10-11T18:00:00+00:00", "302")

        async def fake(url, client):
            vid = url.rsplit("/", 1)[1]
            if vid == "302":
                return Resolved(canonical_url=url, shared_url=url, platform="tiktok", resolve_status="unresolved")
            return Resolved(canonical_url=url, shared_url=url, platform="tiktok", external_id=vid,
                            title="Tomato salad for a crowd #cooking #recipe", creator_handle="@kitchendesk",
                            creator_name="Kitchen Desk", resolve_status="ok")
        monkeypatch.setattr(rewind, "resolve", fake)
        assert asyncio.run(rewind.look_up_likes(conn)) == 1
        rows = {r["external_id"]: dict(r) for r in conn.execute("SELECT * FROM videos")}
        assert rows["301"]["creator_handle"] == "@kitchendesk" and rows["301"]["status"] == "ok"
        assert "Food & cooking" in json.loads(rows["301"]["themes"])
        assert (rows["302"]["status"], rows["302"]["attempts"]) == ("unresolved", 1)
        # Tried again a day later, it counts a second attempt.
        conn.execute("UPDATE videos SET looked_at = '2026-01-01T00:00:00+00:00' WHERE external_id = '302'")
        conn.commit()
        asyncio.run(rewind.look_up_likes(conn))
        assert conn.execute("SELECT attempts FROM videos WHERE external_id = '302'").fetchone()[0] == 2

    def test_nothing_to_look_up_opens_no_connection_to_tiktok(self, conn, monkeypatch):
        monkeypatch.setattr(rewind, "resolve", lambda *a: pytest.fail("looked something up"))
        assert asyncio.run(rewind.look_up_likes(conn)) == 0


@pytest.fixture
def client():
    with TestClient(web.app) as c:
        yield c


class TestThePage:
    def test_with_no_export_it_says_how_to_get_one(self, client):
        page = client.get("/rewind").text
        assert "Rewind needs a TikTok export" in page and 'href="/sync#exports"' in page
        assert "data-rewind" not in page

    def test_it_opens_the_latest_month_and_keeps_your_time_zone(self, client, october):
        r = client.get("/rewind?tz=America/New_York", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/rewind/2026-10?tz=America%2FNew_York"
        page = client.get(r.headers["location"]).text
        assert db.get_meta(october, rewind.TZ_KEY) == "America/New_York"
        assert 'data-tz="America/New_York"' in page and "data-tz-unknown" not in page
        assert page.count('class="rw-card') == 5
        assert '<p class="rw-hero">23</p>' in page and "↑ 109% on September (11)" in page
        assert "Busiest: Saturdays, 11pm–12am" in page
        assert "@caseebrim" in page and "up from 3rd" in page
        assert "Biggest jump: News &amp; politics" in page and ">orzo</a>" in page
        assert "1 in 6 likes made it to Faves" in page
        assert 'href="/rewind/2026-09"' in page
        # Next time, with no tz, it remembers.
        assert 'data-tz="America/New_York"' in client.get("/rewind/2026-10").text

    def test_the_latest_month_is_yours(self, client, conn):
        activity(conn, "watch", "2026-11-01T02:00:00+00:00", "1")
        r = client.get("/rewind?tz=America/New_York", follow_redirects=False)
        assert r.headers["location"].startswith("/rewind/2026-10?")
        assert client.get(r.headers["location"]).status_code == 200

    def test_learning_the_time_zone_on_a_month_that_was_only_utcs(self, client, conn):
        # /rewind sent you to November before the page said where you are.
        activity(conn, "watch", "2026-11-01T02:00:00+00:00", "1")
        assert client.get("/rewind", follow_redirects=False).headers["location"] == "/rewind/2026-11"
        r = client.get("/rewind/2026-11?tz=America/New_York", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/rewind/2026-10"

    def test_a_made_up_time_zone_is_ignored(self, client, october):
        page = client.get("/rewind/2026-10?tz=Mars/Olympus_Mons").text
        assert 'data-tz="UTC"' in page and "data-tz-unknown" in page
        assert db.get_meta(october, rewind.TZ_KEY) is None

    @pytest.mark.parametrize("path", ["/rewind/2026-13", "/rewind/latest", "/rewind/2026-07"])
    def test_no_such_month(self, client, october, path):
        assert client.get(path).status_code == 404

    def test_the_ways_in(self, client, october):
        assert 'href="/rewind/2026-10">' in client.get("/").text and "October Rewind" in client.get("/").text
        assert 'href="/rewind"' in client.get("/browse").text

    def test_today_offers_it_only_with_something_to_show(self, client, conn):
        db.upsert_item(conn, {"canonical_url": "https://example.com/1", "shared_url": "x", "platform": "tiktok",
                              "title": "a save", "resolve_status": "ok"})
        assert "/rewind" not in client.get("/").text

    def test_the_script_sends_the_time_zone(self, client):
        js = client.get("/static/museum.js").text
        assert "[data-rewind]" in js and "resolvedOptions().timeZone" in js


def test_the_cloud_installs_the_time_zone_list():
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    assert any(d.startswith("tzdata") for d in deps)
