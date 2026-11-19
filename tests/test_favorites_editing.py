"""Putting a save in your own words, and topics that save as you tap.

A save's title and creator can be edited on its page. The platform's version
of each detail you change is kept beside it, so a later lookup never
overwrites yours, and you can go back to it. Instagram's stand-in titles
("GigiSketch on Instagram", by "Instagram") are put right by Faves itself.
"""

import asyncio
import re

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from favorites import backfill, blurb, db
from favorites.app import app
from favorites.resolve import resolve

VIDEO = "https://www.tiktok.com/@citydesk/video/7123"
REEL = "https://www.instagram.com/reel/DAbc123/"


@pytest.fixture
def conn():
    c = db.connect()
    yield c
    c.close()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
    with TestClient(app) as c:
        yield c


def add(conn, url=VIDEO, platform="tiktok", **more):
    details = {"title": "the zoning meeting went sideways #localgov", "creator_name": "City Desk",
               "creator_handle": "@citydesk", **more}
    item_id, _ = db.upsert_item(conn, {"canonical_url": url, "shared_url": url, "platform": platform,
                                       "resolve_status": "ok", **details})
    return item_id


def found(conn, words):
    """What a search for ``words`` finds (Search's own query, on either database)."""
    from favorites import explore
    return [i["id"] for i in explore.results(conn, explore.Filters(q=words))[0]]


class TestYourOwnWords:
    def test_a_title_and_creator_you_write(self, conn):
        item_id = add(conn, creator_name=None, creator_handle=None)
        changed = db.edit_details(conn, item_id, title="Zoning board, March", creator_name="City Desk",
                                  creator_handle=" @CityDesk ")
        row = db.get_item(conn, item_id)
        assert changed == ["title", "creator_name", "creator_handle"]
        assert (row["title"], row["creator_name"], row["creator_handle"]) == (
            "Zoning board, March", "City Desk", "@citydesk")
        assert db.edits_of(row["edited"]) == {"title": "the zoning meeting went sideways #localgov",
                                              "creator_name": None, "creator_handle": None}
        assert found(conn, "March") == [item_id]

    def test_a_later_lookup_never_overwrites_them(self, conn):
        item_id = add(conn)
        db.edit_details(conn, item_id, title="Zoning board, March")
        add(conn, title="the zoning meeting went sideways #localgov #update", creator_name="City Desk News")
        row = db.get_item(conn, item_id)
        assert row["title"] == "Zoning board, March"
        assert row["creator_name"] == "City Desk News"                # not yours: it follows the platform
        # The platform's newest version is the one you'd go back to.
        assert db.edits_of(row["edited"]) == {"title": "the zoning meeting went sideways #localgov #update"}
        assert db.undo_edits(conn, item_id) == ["title"]
        row = db.get_item(conn, item_id)
        assert row["title"] == "the zoning meeting went sideways #localgov #update" and row["edited"] is None

    def test_writing_back_what_the_platform_said_is_no_edit(self, conn):
        item_id = add(conn)
        db.edit_details(conn, item_id, creator_name="Desk")
        db.edit_details(conn, item_id, creator_name="City Desk")
        assert db.get_item(conn, item_id)["edited"] is None

    def test_nothing_sent_is_left_alone_and_nothing_changed_is_no_edit(self, conn):
        item_id = add(conn)
        assert db.edit_details(conn, item_id, title="the zoning meeting went sideways #localgov ") == []
        assert db.edit_details(conn, item_id) == []
        assert db.get_item(conn, item_id)["edited"] is None

    def test_the_form_sending_back_what_it_showed_is_no_edit(self, conn):
        # A caption over several lines comes back from a form with \r\n, and a
        # handle stored in capitals comes back as typed: neither is a change.
        item_id = add(conn, title="Line one\n\nLine two  #tag " + "x" * 400, creator_handle="@CityDesk")
        assert db.edit_details(conn, item_id, title="Line one\r\n\r\nLine two #tag " + "x" * 400,
                               creator_name="City Desk", creator_handle="CityDesk") == []
        assert db.edit_details(conn, item_id, creator_name="Desk") == ["creator_name"]
        assert db.edits_of(db.get_item(conn, item_id)["edited"]) == {"creator_name": "City Desk"}

    def test_an_empty_detail_clears_it(self, conn):
        item_id = add(conn)
        assert db.edit_details(conn, item_id, creator_handle="") == ["creator_handle"]
        assert db.get_item(conn, item_id)["creator_handle"] is None

    @pytest.mark.parametrize("typed, handle", [
        ("citydesk", "@citydesk"), ("@CityDesk", "@citydesk"), (" city desk ", "@citydesk"),
        ("https://www.tiktok.com/@citydesk/", "@citydesk"), ("city.desk_2", "@city.desk_2"),
        ("@", None), ("", None),
    ])
    def test_a_handle_however_it_was_typed(self, typed, handle):
        assert db.as_handle(typed) == handle

    def test_a_title_you_wrote_is_no_placeholder_to_clear(self, conn):
        item_id = add(conn)
        db.edit_details(conn, item_id, title="TikTok - Make Your Day")
        assert backfill.requeue_placeholders(conn) == {"cleared_titles": 0, "requeued": 0}
        assert db.get_item(conn, item_id)["title"] == "TikTok - Make Your Day"


class TestOnTheSavesPage:
    def test_editing_from_the_page(self, client, conn):
        item_id = add(conn)
        page = client.get(f"/item/{item_id}").text
        assert 'action="/item/%d/details"' % item_id in page and "Edit title and creator" in page
        assert 'id="edit-details" open' not in page and "version</button>" not in page
        r = client.post(f"/item/{item_id}/details", data={
            "title": "Zoning board, March", "creator_name": "City Desk", "creator_handle": "citydesk"},
            headers={"Accept": "application/json"})
        assert r.json() == {"changed": ["title"], "title": "Zoning board, March",
                            "creator_name": "City Desk", "creator_handle": "@citydesk"}
        page = client.get(f"/item/{item_id}").text
        assert "Zoning board, March" in page and "Edited by you" in page
        assert "Go back to TikTok's version</button>" in page
        r = client.post(f"/item/{item_id}/details", data={"undo": "1"}, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == f"/item/{item_id}"
        assert "Edited by you" not in client.get(f"/item/{item_id}").text

    def test_a_save_with_no_creator_asks_for_one(self, client, conn):
        item_id = add(conn, creator_name=None, creator_handle=None)
        page = client.get(f"/item/{item_id}").text
        assert 'class="edit-details is-asking" id="edit-details" open' in page
        assert "Who made this? Add the creator" in page and "TikTok didn't say who made this." in page

    def test_only_what_is_sent_changes(self, client, conn):
        item_id = add(conn)
        client.post(f"/item/{item_id}/details", data={"creator_name": "Desk"})
        row = db.get_item(conn, item_id)
        assert (row["title"], row["creator_name"], row["creator_handle"]) == (
            "the zoning meeting went sideways #localgov", "Desk", "@citydesk")

    def test_no_such_save(self, client):
        assert client.post("/item/999/details", data={"title": "x"}).status_code == 404


class TestInstagramStandIns:
    def test_the_account_is_the_creator_and_the_caption_the_title(self):
        assert blurb.instagram_standin(
            "GigiSketch on Instagram", "Instagram",
            '15K likes: "How to draw perspective with string #art #perspective #ske...') == {
            "title": "How to draw perspective with string #art #perspective #ske...",
            "creator_name": "GigiSketch"}

    def test_the_longer_preview_names_the_handle(self):
        assert blurb.instagram_standin(
            "Tom Petty & The Heartbreakers on Instagram", "Instagram",
            '1,204 likes, 31 comments - tompetty on March 3, 2024: "Full Moon Fever turns 35."') == {
            "title": "Full Moon Fever turns 35.", "creator_name": "Tom Petty & The Heartbreakers",
            "creator_handle": "@tompetty"}

    def test_a_caption_in_the_title_itself(self):
        assert blurb.instagram_standin('Kitchen Desk on Instagram: "Folding dumplings"', "", None) == {
            "title": "Folding dumplings", "creator_name": "Kitchen Desk"}

    @pytest.mark.parametrize("title, creator", [
        ("GigiSketch on Instagram", "GigiSketch"),          # a creator already: nothing to fix
        ("Folding dumplings", "Instagram"),                # no stand-in title
        ("Life on Instagram is weird, honestly", ""),      # a caption that says it
    ])
    def test_nothing_to_fix(self, title, creator):
        assert blurb.instagram_standin(title, creator, "x") is None

    @respx.mock
    def test_a_new_save_is_put_right_when_it_is_looked_up(self):
        page = ('<html><head><meta property="og:title" content="GigiSketch on Instagram">'
                '<meta property="og:site_name" content="Instagram">'
                '<meta property="og:description" content="15K likes: &quot;How to draw perspective with string #art&quot;">'
                '</head></html>')
        respx.route(host="www.instagram.com").mock(return_value=httpx.Response(
            200, text=page, headers={"content-type": "text/html"}))
        respx.route().mock(return_value=httpx.Response(404))

        async def go():
            async with httpx.AsyncClient() as c:
                return await resolve(REEL, c)
        item = asyncio.run(go())
        assert item.resolve_status == "ok"
        assert (item.title, item.creator_name) == ("How to draw perspective with string #art", "GigiSketch")

    def test_saves_kept_before_are_put_right(self, conn):
        fixed = add(conn, url=REEL, platform="instagram", title="GigiSketch on Instagram",
                    creator_name="Instagram", creator_handle=None,
                    description='15K likes: "How to draw perspective with string #art #perspective"')
        yours = add(conn, url="https://www.instagram.com/reel/DXyz789/", platform="instagram",
                    title="Drawing Tricks on Instagram", creator_name="Instagram", creator_handle=None,
                    description='21K likes: "Easy elephant drawing #drawingtricks"')
        db.edit_details(conn, yours, title="The elephant one")
        assert db.fix_instagram_standins(conn) == 2
        row = db.get_item(conn, fixed)
        assert (row["title"], row["creator_name"]) == ("How to draw perspective with string #art #perspective",
                                                       "GigiSketch")
        assert blurb.headline(row) == "How to draw perspective with string"
        assert found(conn, "GigiSketch") == [fixed]
        row = db.get_item(conn, yours)
        assert (row["title"], row["creator_name"]) == ("The elephant one", "Drawing Tricks")
        # Going back to Instagram's version gives the caption, not the stand-in.
        assert db.edits_of(row["edited"]) == {"title": "Easy elephant drawing #drawingtricks"}
        assert db.fix_instagram_standins(conn) == 0                     # once is enough


class TestTopicsSaveAsYouTap:
    def test_the_saves_page_picker(self, client, conn):
        item_id = add(conn)
        page = client.get(f"/item/{item_id}").text
        form = re.search(r'<form action="/item/\d+/rooms".*?</form>', page, re.S).group(0)
        assert "data-instant" in form and "Each tap is saved." in form
        # Kept for a page with no script; hidden once taps save themselves.
        assert 'class="rr-btn rr-btn--primary save-topics" type="submit">Save topics' in form
        assert 'name="whole_creator" value="1">Do the same for everything by City Desk</button>' in form
        css = client.get("/static/style.css").text
        assert ".change-rooms form.is-instant .save-topics { display: none; }" in css.replace(
            ".change-rooms form:not(.is-instant) .instant-hint, ", "")

    def test_adding_a_topic_keeps_the_ones_left_ticked(self, client, conn):
        item_id = add(conn, title="The best carbonara in the world #pasta #carbonara")
        auto = db.rows_to_dicts([db.get_item(conn, item_id)])[0]["themes"]
        assert auto == ["Food & cooking"]
        r = client.post(f"/item/{item_id}/rooms", data={"room": ["Food & cooking", "Music"]},
                        headers={"Accept": "application/json"})
        assert set(r.json()["themes"]) == {"Food & cooking", "Music"}
        r = client.post(f"/item/{item_id}/rooms", data={"room": ["Music"]}, headers={"Accept": "application/json"})
        assert r.json()["themes"] == ["Music"]

    def test_the_whole_creator_button_still_files_them_all(self, client, conn):
        one = add(conn, title="The best carbonara in the world #pasta #carbonara")
        two = add(conn, url="https://www.tiktok.com/@citydesk/video/7124", title="Rooftop gig tonight")
        client.post(f"/item/{one}/rooms", data={"room": ["Food & cooking", "Music"], "whole_creator": "1"})
        # Music for all of them -- not this one's Food, which it was only ever given by its caption.
        assert db.rows_to_dicts([db.get_item(conn, two)])[0]["themes"] == ["Music"]
        assert set(db.rows_to_dicts([db.get_item(conn, one)])[0]["themes"]) == {"Food & cooking", "Music"}

    def test_the_script_saves_each_tap_in_order_with_an_undo(self, client):
        js = client.get("/static/museum.js").text
        tap = js[js.index("function topicTap("):js.index("/* ---- sheets")]
        assert "form.rrQueue = (form.rrQueue || Promise.resolve()).then(" in tap   # one after another
        assert "'Added to '" in tap and "'Taken out of '" in tap and "save('Put back as it was ✓')" in tap
        inplace = js[js.index("function inplace(form)"):js.index("/* ---- search results")]
        assert "form.hasAttribute('data-instant')" in inplace and "redraw('#change-rooms')" in inplace
        redraw = js[js.index("function redraw(keep)"):js.index("function inplace(form)")]
        assert "slot.replaceWith(live)" in redraw                         # the picker you're tapping stays

    def test_give_them_a_topic_saves_each_tap_then_next(self, client, conn):
        add(conn, title="something", creator_name=None, creator_handle="@nobody")
        page = client.get("/shuffle?theme=Undefined&order=newest").text
        tagger = re.search(r'<form class="tagger".*?</form>', page, re.S).group(0)
        assert "Each tap is saved" in tagger and ">Next<" in tagger and ">Done<" not in tagger
        js = client.get("/static/museum.js").text
        deck = js[js.index("// Untagged: tap a topic"):js.index("// Every other card")]
        assert "topicTap(form, e.target" in deck and "step(1);" in deck and "post(form)" not in deck

    def test_shuffles_topic_sheet_has_no_save_button(self, client, conn):
        add(conn)
        page = client.get("/shuffle?seed=3").text
        sheet = re.search(r'<dialog class="rr-sheet-dialog" id="topic-sheet".*?</dialog>', page, re.S).group(0)
        assert "Save topics" not in sheet and '<p class="said" role="status"' in sheet and ">Done</button>" in sheet
