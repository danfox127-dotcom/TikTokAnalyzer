"""How long each video is, read from its own page.

Tested on a real library: YouTube pages gave 149s, 2301s and 5335s; TikTok
pages 26s, 32s and 41s; Instagram pages gave nothing, so Instagram has no
length reader and its saves sit outside the Length filter.
"""

import asyncio
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from favorites import db, explore, lengths, platforms
from favorites.app import app, clock
from favorites.explore import Filters


def tiktok_page(video=26, music=60):
    data = {"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": {
        "music": {"duration": music}, "video": {"height": 1024, "duration": video}}}}}}
    return ('<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
            + json.dumps(data) + "</script></html>")


YOUTUBE_PAGE = ('<html><meta itemprop="duration" content="PT2M29S">'
                '<script>var ytInitialPlayerResponse = {"videoDetails":{"lengthSeconds":"149"}};'
                '</script></html>')


class TestReadingThePage:
    def test_youtube_states_it_in_the_player_data(self):
        assert platforms.get("youtube").length_from_page(YOUTUBE_PAGE) == 149

    def test_youtube_player_data_alone_is_enough(self):
        assert platforms.get("youtube").length_from_page('{"lengthSeconds":"2301"}') == 2301

    def test_youtube_falls_back_to_the_page_metadata(self):
        read = platforms.get("youtube").length_from_page
        assert read('<meta itemprop="duration" content="PT1H28M55S">') == 5335
        assert read('<meta itemprop="duration" content="PT4M">') == 240

    def test_tiktok_reads_the_videos_length_not_the_soundtracks(self):
        # The soundtrack's "duration" comes first on the page.
        assert platforms.get("tiktok").length_from_page(tiktok_page(video=26, music=60)) == 26

    def test_tiktok_falls_back_to_an_older_page_layout(self):
        read = platforms.get("tiktok").length_from_page
        assert read('{"video":{"id":"1","duration":32,"ratio":"720p"}}') == 32

    @pytest.mark.parametrize("page", [
        "<html>nothing here</html>",
        '{"lengthSeconds":"0"}',
        '{"lengthSeconds":"999999"}',          # longer than a day: a misread
        '<meta itemprop="duration" content="P">',
    ])
    def test_nothing_believable_is_no_length(self, page):
        assert platforms.get("youtube").length_from_page(page) is None

    def test_instagram_does_not_say(self):
        assert platforms.get("instagram").length_from_page is None
        assert lengths.readable_platforms() == ("tiktok", "youtube")


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "lib.db")
    yield c
    c.close()


def add(conn, n, platform="tiktok", duration=None, status="ok"):
    urls = {"tiktok": f"https://www.tiktok.com/video/{n}",
            "youtube": f"https://www.youtube.com/watch?v=vid{n:08d}",
            "instagram": f"https://www.instagram.com/p/code{n}"}
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": urls[platform], "shared_url": "x", "platform": platform,
        "external_id": str(n), "title": "a video", "resolve_status": status,
        # Identified TikToks carry a handle; their page address is built from it.
        "creator_handle": "@citydesk" if platform == "tiktok" else None,
        "duration": duration, "saved_at": f"2024-01-{n:02d}T00:00:00+00:00"})
    return item_id


@pytest.fixture
def no_waiting(monkeypatch):
    pauses = []

    async def fake(seconds):
        pauses.append(seconds)
    monkeypatch.setattr(lengths, "_sleep", fake)
    return pauses


class TestCatchingUp:
    def test_only_identified_videos_that_could_have_a_length_are_asked(self, conn):
        todo = add(conn, 1)
        add(conn, 2, duration=30)             # already known
        add(conn, 3, platform="instagram")    # never says
        add(conn, 4, status="pending")        # not identified yet
        assert [i["id"] for i in lengths.missing(conn)] == [todo]

    @respx.mock
    def test_lengths_are_stored_one_page_at_a_time(self, conn, no_waiting):
        tt = add(conn, 1)
        yt = add(conn, 2, platform="youtube")
        gone = add(conn, 3)
        respx.get("https://www.tiktok.com/@citydesk/video/1").mock(
            return_value=httpx.Response(200, text=tiktok_page(video=41)))
        respx.get("https://www.youtube.com/watch?v=vid00000002").mock(
            return_value=httpx.Response(200, text=YOUTUBE_PAGE))
        respx.get("https://www.tiktok.com/@citydesk/video/3").mock(return_value=httpx.Response(404))

        r = asyncio.run(lengths.run(conn, quiet=True))
        assert r == {"attempted": 3, "found": 2, "failed": 1,
                     "why": {"unavailable (usually a deleted video)": 1}}
        assert db.get_item(conn, tt)["duration"] == 41
        assert db.get_item(conn, yt)["duration"] == 149
        assert db.get_item(conn, gone)["duration"] is None
        assert no_waiting == [lengths.PAUSE] * 2  # between pages, not after the last

    @respx.mock
    def test_a_page_without_the_data_is_named(self, conn, no_waiting):
        add(conn, 1)
        respx.get("https://www.tiktok.com/@citydesk/video/1").mock(
            return_value=httpx.Response(200, text="<html>please log in</html>"))
        r = asyncio.run(lengths.run(conn, quiet=True))
        assert r["why"] == {"not on the page": 1}

    @respx.mock
    def test_the_command_reports_by_platform(self, tmp_path, capsys, no_waiting):
        path = tmp_path / "lib.db"
        c = db.connect(path)
        add(c, 1)
        add(c, 2, platform="youtube", duration=149)
        c.close()
        respx.get("https://www.tiktok.com/@citydesk/video/1").mock(
            return_value=httpx.Response(200, text=tiktok_page(video=26)))
        lengths.main(["--db", str(path), "--quiet"])
        out = capsys.readouterr().out
        assert "found the length of 1 of 1" in out
        assert "TikTok    : 1 of 1 have a length" in out
        assert "YouTube   : 1 of 1 have a length" in out

    def test_re_saving_without_a_length_keeps_the_known_one(self, conn):
        item_id = add(conn, 1, duration=26)
        db.upsert_item(conn, {"canonical_url": "https://www.tiktok.com/video/1",
                              "shared_url": "x", "platform": "tiktok", "duration": None})
        assert db.get_item(conn, item_id)["duration"] == 26


class TestSavingFromThePhone:
    @respx.mock
    def test_a_share_records_its_length(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "favorites.db"))
        respx.get(host="www.tiktok.com", path="/oembed").mock(return_value=httpx.Response(
            200, json={"title": "zoning #localgov", "author_name": "City Desk",
                       "author_unique_id": "citydesk"}))
        respx.get("https://www.tiktok.com/@citydesk/video/7123").mock(
            return_value=httpx.Response(200, text=tiktok_page(video=32)))
        respx.route().mock(return_value=httpx.Response(404))
        with TestClient(app) as client:
            item_id = client.post("/save", json={
                "url": "https://www.tiktok.com/@citydesk/video/7123"}).json()["id"]
            page = client.get(f"/item/{item_id}").text
        c = db.connect()
        assert db.get_item(c, item_id)["duration"] == 32
        c.close()
        assert "0:32 long" in page


class TestTheFilter:
    @pytest.fixture
    def library(self, conn):
        return {
            "clip": add(conn, 1, duration=26),
            "short": add(conn, 2, duration=150),
            "talk": add(conn, 3, platform="youtube", duration=2301),
            "film": add(conn, 4, platform="youtube", duration=5335),
            "unknown": add(conn, 5, platform="instagram"),
        }

    def names(self, conn, library, **f):
        by_id = {v: k for k, v in library.items()}
        return {by_id[i["id"]] for i in explore.results(conn, Filters(**f))[0]}

    def test_each_band(self, conn, library):
        assert self.names(conn, library, length="under1") == {"clip"}
        assert self.names(conn, library, length="1to3") == {"short"}
        assert self.names(conn, library, length="over30") == {"talk", "film"}

    def test_a_video_on_a_boundary_belongs_to_the_longer_band(self, conn, library):
        library["one_minute"] = add(conn, 6, duration=60)
        library["three_minutes"] = add(conn, 7, duration=180)
        assert self.names(conn, library, length="under1") == {"clip"}
        assert self.names(conn, library, length="1to3") == {"short", "one_minute"}
        assert self.names(conn, library, length="3to10") == {"three_minutes"}

    def test_the_bands_are_offered_in_order_with_counts(self, conn, library):
        facet = {f.name: f for f in explore.facets(conn, Filters())}["length"]
        assert [(o.value, o.count) for o in facet.options] == [
            ("under1", 1), ("1to3", 1), ("over30", 2)]  # the unknown one is not counted

    def test_junk_in_the_address_is_dropped(self):
        assert Filters.from_params({"length": "forever"}) == Filters()

    def test_the_heading_says_it(self):
        assert explore.describe(Filters(length="under1", platform="tiktok"), []) == \
            "TikTok saves under a minute"
        assert explore.describe(Filters(length="over30"), []) == "Saves over 30 minutes long"


class TestShowingIt:
    @pytest.mark.parametrize("seconds, shown", [
        (26, "0:26"), (245, "4:05"), (5335, "1:28:55"), (None, ""), (0, ""), ("x", "")])
    def test_a_length_reads_like_a_video_sites(self, seconds, shown):
        assert clock(seconds) == shown

    def test_cards_carry_the_length(self, tmp_path, monkeypatch):
        path = tmp_path / "favorites.db"
        monkeypatch.setenv("FAVORITES_DB", str(path))
        c = db.connect(path)
        add(c, 1, duration=26)
        c.close()
        with TestClient(app) as client:
            assert '<span class="length" aria-label="Length">0:26</span>' in client.get("/search").text
