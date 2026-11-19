"""The platforms' own labels (Phase B): TikTok's topic labels and search
suggestions, YouTube's category and tags -- read from the page Faves visits
for a video's length, weighed like a hashtag, caught up on by the Mac."""

import asyncio
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import db, labels, platforms, themes


def tiktok_page(labels=("Pets", "Entertainment"), words=("funny husky videos",), poi=None, video=26):
    item = {"id": "7123", "desc": "Wait for the end", "video": {"duration": video},
            "diversificationLabels": list(labels), "suggestedWords": list(words)}
    if poi:
        item["poi"] = poi
    data = {"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": item}}}}
    return ('<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
            + json.dumps(data) + "</script></html>")


YOUTUBE_PAGE = ('<script>var ytInitialPlayerResponse = {"videoDetails":{"videoId":"abc","lengthSeconds":"149",'
                '"keywords":["kexp","live music","chvrches"]},"microformat":{"playerMicroformatRenderer":'
                '{"title":{"simpleText":"x"},"category":"Music"}}};</script>')


class TestReadingThePage:
    def test_tiktok(self):
        found = platforms.get("tiktok").labels_from_page(
            tiktok_page(poi={"name": "Brooklyn Bridge Park", "city": "New York"}))
        assert found == {"source": "TikTok", "categories": ["Pets", "Entertainment"],
                         "keywords": ["funny husky videos"],
                         "places": ["Brooklyn Bridge Park", "New York"]}

    def test_a_tiktok_page_without_the_video_is_nothing_yet(self):
        stub = "<html><title>TikTok - Make Your Day</title></html>"
        assert platforms.get("tiktok").labels_from_page(stub) is None

    def test_youtube(self):
        assert platforms.get("youtube").labels_from_page(YOUTUBE_PAGE) == {
            "source": "YouTube", "categories": ["Music"], "keywords": ["kexp", "live music", "chvrches"],
            "places": []}

    def test_instagram_has_none(self):
        assert platforms.get("instagram").labels_from_page is None


def about(text="", found=None, tags=()):
    ev = themes.weigh(tags, [text], labels=found)
    kept = themes.decide(ev)
    return kept, {e["theme"]: e["reasons"] for e in themes.explain(ev, kept)}


class TestWeighingThem:
    def test_a_caption_that_says_nothing(self):
        kept, why = about("Wait for the end 💀", {"source": "TikTok", "categories": ["Comedy", "Entertainment"]})
        assert kept == ["Comedy & humour"] and why["Comedy & humour"] == ["TikTok’s own label: “Comedy”"]

    def test_labels_that_say_nothing_are_skipped(self):
        assert about("x", {"categories": ["Entertainment", "People & Blogs", "Daily Life"]})[0] == []

    def test_a_youtube_category(self):
        kept, why = about("CHVRCHES - Full Performance", {"source": "YouTube", "categories": ["Music"],
                                                         "keywords": ["kexp", "live music"]})
        assert kept == ["Music"] and why["Music"][0] == "YouTube’s own label: “Music”"

    def test_keywords_and_places_count_a_little(self):
        kept, why = about("Just some information", {"source": "TikTok", "categories": ["Education"],
                                                    "places": ["Brooklyn Bridge Park"]})
        assert kept == ["How-to & learning", "New York"]
        assert why["New York"] == ["“brooklyn” in its keywords"]

    def test_pets_on_a_dog_video_is_just_dogs(self):
        found = {"source": "TikTok", "categories": ["Pets"], "keywords": ["husky talking", "funny husky"]}
        assert about("Wait for the end", found)[0][0] == "Dogs"

    def test_unlisted_labels_are_read_by_their_words(self):
        assert themes.label_themes("Cooking & Recipes") == {"Food & cooking"}
        assert themes.label_themes("Talents") == set()


@pytest.fixture
def conn():
    c = db.connect()
    yield c
    c.close()


def add(conn, n, platform="tiktok", **kw):
    url = (f"https://www.tiktok.com/@a/video/{7000 + n}" if platform == "tiktok"
           else f"https://www.youtube.com/watch?v=v{n}")
    item_id, _ = db.upsert_item(conn, {"canonical_url": url, "shared_url": url, "platform": platform,
                                       "external_id": str(7000 + n), "creator_handle": "@a",
                                       "resolve_status": "ok", **kw})
    return item_id


class TestCatchingUp:
    @pytest.fixture(autouse=True)
    def no_pause(self, monkeypatch):
        async def nothing(_):
            return None
        monkeypatch.setattr(labels.lengths, "_sleep", nothing)
        monkeypatch.setattr(labels, "_skipped", set())

    def test_the_ones_without_a_topic_come_first(self, conn):
        themed = add(conn, 1, title="pasta night", tags=["recipe"])
        bare = add(conn, 2, title="Wait for the end")
        add(conn, 3, platform="instagram", title="x")              # Instagram has no labels to read
        db.retheme(conn)
        assert [i["id"] for i in labels.missing(conn)] == [bare, themed]
        assert labels.counts(conn) == (0, 2)

    @respx.mock
    def test_reads_files_and_notes_the_move(self, conn):
        bare = add(conn, 2, title="Wait for the end")
        db.retheme(conn)
        respx.get(url__regex=r".*/video/7002").mock(return_value=httpx.Response(
            200, text=tiktok_page(labels=("Comedy",), words=())))
        assert asyncio.run(labels.run(conn)) == {"read": 1, "moved": 1, "skipped": 0}
        row = db.get_item(conn, bare)
        assert json.loads(row["themes"]) == ["Comedy & humour"] and row["duration"] == 26
        assert json.loads(row["labels"])["categories"] == ["Comedy"]
        change = conn.execute("SELECT was, became FROM theme_changes WHERE item_id = ?", (bare,)).fetchone()
        assert (json.loads(change["was"]), json.loads(change["became"])) == ([], ["Comedy & humour"])
        assert labels.counts(conn) == (1, 1) and labels.missing(conn) == []

    @respx.mock
    def test_a_page_without_the_video_is_tried_another_day(self, conn):
        bare = add(conn, 2, title="Wait for the end")
        respx.get(url__regex=r".*/video/7002").mock(return_value=httpx.Response(
            200, text="<title>TikTok - Make Your Day</title>"))
        assert asyncio.run(labels.run(conn)) == {"read": 0, "moved": 0, "skipped": 1}
        assert db.get_item(conn, bare)["labels"] is None
        assert labels.missing(conn) == []                       # not again this run of Faves

    @respx.mock
    def test_a_new_save_gets_them_with_its_length(self, conn, monkeypatch):
        monkeypatch.setenv("FAVES_FINISH_LATER", "1")
        monkeypatch.setattr(web, "_tried", web.Counter())
        from datetime import datetime, timezone
        item_id = add(conn, 5, title="Wait for the end", saved_at=datetime.now(timezone.utc).isoformat())
        respx.get(url__regex=r".*/video/7005").mock(return_value=httpx.Response(
            200, text=tiktok_page(labels=("Dance",), words=())))
        assert asyncio.run(web.finish(conn, item_id))["filled"] == ["length", "labels"]
        assert json.loads(db.get_item(conn, item_id)["themes"]) == ["Dance"]


class TestThePages:
    def test_progress_on_sort_things_out(self, conn, monkeypatch):
        monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
        add(conn, 1, title="a")
        add(conn, 2, title="b")
        conn.execute("UPDATE items SET labels = '{}' WHERE canonical_url LIKE '%7001'")
        conn.commit()
        with TestClient(web.app) as client:
            page = client.get("/topics/sort").text
        assert "Reading TikTok's and YouTube's own labels:" in page and "1 of 2 saves so far" in page
