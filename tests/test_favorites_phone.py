"""Faves on a phone: getting around with no browser Back button, the More
sheet, and Shuffle -- a feed of saves flicked through one screen at a time."""

import re
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from favorites import db, explore, tagging
from favorites.app import app
from favorites.explore import Filters


def add(conn, n, caption="Tomato salad #cooking", saved="2024-07-15", creator="@kitchendesk",
        status="ok"):
    tags, terms = tagging.enrich(title=caption, description=caption)
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": f"https://example.com/{n}", "shared_url": "x", "platform": "tiktok",
        "title": caption, "description": caption, "creator_handle": creator, "tags": tags,
        "terms": terms, "resolve_status": status, "saved_at": f"{saved}T12:00:00+00:00",
    })
    return item_id


@pytest.fixture
def conn(tmp_path, monkeypatch):
    path = tmp_path / "favorites.db"
    monkeypatch.setenv("FAVORITES_DB", str(path))
    monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
    c = db.connect(str(path))
    yield c
    c.close()


@pytest.fixture
def library(conn):
    """Twenty-five saves: fifteen about food, ten with no topic at all."""
    food = [add(conn, n, saved=f"2024-{(n % 12) + 1:02d}-{(n % 27) + 1:02d}") for n in range(15)]
    plain = [add(conn, 100 + n, caption=f"you have to see this {n}", creator=f"@someone{n}",
                 saved=f"2025-0{(n % 9) + 1}-10") for n in range(10)]
    return {"food": food, "plain": plain}


@pytest.fixture
def client(conn):
    with TestClient(app) as c:
        yield c


def deck_ids(conn, f=Filters(), **kw):
    return [i["id"] for i in explore.deck(conn, f, **kw)[0]]


def card_ids(html):
    return [int(x) for x in re.findall(r'class="rr-deckcard[^"]*" data-id="(\d+)"', html)]


class TestTheFeedsOrder:
    def test_a_seed_deals_every_save_once(self, conn, library):
        seen, after = [], None
        while True:
            items, total, more = explore.deck(conn, Filters(), seed=4242, after=after, n=8)
            seen += [i["id"] for i in items]
            if not more:
                break
            after = items[-1]["id"]
        assert total == 25
        assert sorted(seen) == sorted(library["food"] + library["plain"])

    def test_the_same_seed_deals_the_same_order_and_another_seed_another(self, conn, library):
        assert deck_ids(conn, seed=99, n=25) == deck_ids(conn, seed=99, n=25)
        assert deck_ids(conn, seed=99, n=25) != deck_ids(conn, seed=12345, n=25)

    @pytest.mark.parametrize("seed", [1, 2, 99, 500_000])
    def test_even_a_small_seed_over_a_small_library_is_shuffled(self, conn, library, seed):
        dealt = deck_ids(conn, seed=seed, n=25)
        assert dealt != sorted(dealt) and dealt != sorted(dealt, reverse=True)
        # Not just counting up from somewhere, either.
        rises = sum(b > a for a, b in zip(dealt, dealt[1:]))
        assert 4 <= rises <= 20

    def test_starting_at_a_save_and_going_back_before_it(self, conn, library):
        everything = deck_ids(conn, seed=7, n=25)
        assert deck_ids(conn, seed=7, at=everything[10], n=3) == everything[10:13]
        assert deck_ids(conn, seed=7, before=everything[10], n=3) == everything[7:10]

    def test_newest_and_oldest_follow_the_saved_date(self, conn, library):
        newest = [i["saved_at"] for i in explore.deck(conn, Filters(), order="newest", n=25)[0]]
        assert newest == sorted(newest, reverse=True)
        oldest = deck_ids(conn, order="oldest", n=25)
        assert oldest == list(reversed(deck_ids(conn, order="newest", n=25)))

    def test_filters_narrow_it_like_search(self, conn, library):
        items, total, _ = explore.deck(conn, Filters(theme="Undefined"), seed=3, n=25)
        assert total == 10 and {i["id"] for i in items} == set(library["plain"])
        assert explore.results(conn, Filters(theme="Undefined"))[1] == total

    def test_giving_a_save_a_topic_mid_feed_skips_nothing(self, conn, library):
        # The untagged feed empties as you go. Carrying on from the last card
        # seen, not from a position, means nothing slides past unseen.
        f = Filters(theme="Undefined")
        first = deck_ids(conn, f, order="newest", n=4)
        for item_id in first:
            db.set_rooms(conn, item_id, ["Comedy & humour"])
        rest = deck_ids(conn, f, order="newest", after=first[-1], n=25)
        assert sorted(first + rest) == sorted(library["plain"])

    def test_saves_still_being_identified_are_left_out(self, conn, library):
        add(conn, 999, caption="https://example.com/999", status="pending")
        assert explore.deck(conn, Filters(), seed=5, n=40)[1] == 25

    @pytest.mark.parametrize("raw, seed", [("123", 123), ("", None), ("abc", None), ("0", None),
                                           ("12345678901", None), (" 42 ", 42)])
    def test_a_seed_from_the_address(self, raw, seed):
        assert explore.deck_seed(raw) == seed


class TestShufflePage:
    def test_it_deals_a_fresh_shuffle_and_keeps_your_filters(self, client, library):
        resp = client.get("/shuffle", params={"theme": "Undefined"}, follow_redirects=False)
        assert resp.status_code == 303
        q = parse_qs(urlparse(resp.headers["location"]).query)
        assert q["theme"] == ["Undefined"] and q["seed"][0].isdigit()

    def test_a_malformed_seed_is_dealt_again(self, client, library):
        resp = client.get("/shuffle?seed=<script>", follow_redirects=False)
        assert resp.status_code == 303 and "script" not in resp.headers["location"]

    def test_a_list_in_its_own_order_needs_no_seed(self, client, conn, library):
        page = client.get("/shuffle", params={"order": "newest"}, follow_redirects=False)
        assert page.status_code == 200
        assert card_ids(page.text) == deck_ids(conn, order="newest")

    def test_the_first_cards_and_the_way_to_more(self, client, conn, library):
        page = client.get("/shuffle?seed=77").text
        assert card_ids(page) == deck_ids(conn, seed=77)
        assert 'data-more="1"' in page
        assert 'data-cards="/shuffle/cards?seed=77"' in page
        # With no script, the last screen is a link to the next few.
        assert f'href="/shuffle?seed=77&amp;after={card_ids(page)[-1]}"' in page

    def test_coming_back_lands_on_the_same_card(self, client, conn, library):
        everything = deck_ids(conn, seed=77, n=25)
        page = client.get(f"/shuffle?seed=77&at={everything[12]}").text
        assert card_ids(page)[0] == everything[12]
        assert 'data-earlier="1"' in page

    def test_the_next_batch_carries_on_without_repeats(self, client, library):
        first = card_ids(client.get("/shuffle?seed=77").text)
        resp = client.get(f"/shuffle/cards?seed=77&after={first[-1]}")
        nxt = card_ids(resp.text)
        assert nxt and not set(nxt) & set(first)
        assert resp.headers["X-Deck-More"] == "1" and resp.headers["X-Deck-Total"] == "25"

    def test_the_last_batch_ends_the_feed(self, client, conn, library):
        everything = deck_ids(conn, seed=77, n=25)
        resp = client.get(f"/shuffle/cards?seed=77&after={everything[-3]}")
        assert card_ids(resp.text) == everything[-2:]
        assert resp.headers["X-Deck-More"] == "0" and "That's all 25." in resp.text

    def test_untagged_saves_come_with_topics_to_tap(self, client, library):
        page = client.get("/shuffle?theme=Undefined&order=newest").text
        assert "Give them a topic" in page and "10 left" in page
        assert page.count('class="tagger"') == 8
        # The topics already holding the most saves come first.
        lanes = re.search(r'class="room-choices is-lanes">(.*?)</fieldset>', page, re.S).group(1)
        assert lanes.index('value="Food &amp; cooking"') < lanes.index('value="Dogs"')

    def test_tagging_without_script_returns_to_the_feed(self, client, library):
        page = client.get("/shuffle?theme=Undefined&order=newest").text
        target = card_ids(page)[0]
        nxt = re.search(rf'action="/item/{target}/rooms".*?name="next" value="([^"]+)"', page, re.S).group(1)
        resp = client.post(f"/item/{target}/rooms", data={"room": "Comedy & humour", "next": nxt.replace("&amp;", "&")},
                           follow_redirects=False)
        assert resp.status_code == 303 and resp.headers["location"].startswith("/shuffle?theme=Undefined")
        after = client.get(resp.headers["location"]).text
        assert target not in card_ids(after) and "9 left" in after

    def test_when_every_save_has_a_topic(self, client, library):
        for item_id in library["plain"]:
            client.post(f"/item/{item_id}/rooms", data={"room": "Comedy & humour"})
        page = client.get("/shuffle?theme=Undefined&order=newest").text
        assert "Every save has a topic." in page and not card_ids(page)

    def test_an_empty_library(self, client):
        assert "Nothing to swipe through here." in client.get("/shuffle?seed=5").text


class TestSavingInPlace:
    def test_topics_answer_with_the_new_topics(self, client, library):
        target = library["plain"][0]
        resp = client.post(f"/item/{target}/rooms", data={"room": ["Music", "Dance"]},
                           headers={"Accept": "application/json"})
        assert resp.status_code == 200
        assert set(resp.json()["themes"]) == {"Music", "Dance"}
        assert any(label.endswith(" Music") for label in resp.json()["labels"])

    def test_a_note_answers_with_the_note(self, client, library):
        resp = client.post(f"/item/{library['food'][0]}/note", data={"note": "  for Sunday "},
                           headers={"Accept": "application/json"})
        assert resp.json() == {"note": "for Sunday"}

    def test_a_plain_form_still_goes_back_to_the_save(self, client, library):
        resp = client.post(f"/item/{library['food'][0]}/note", data={"note": "x"}, follow_redirects=False)
        assert resp.status_code == 303 and resp.headers["location"] == f"/item/{library['food'][0]}"

    def test_the_save_page_marks_its_forms_to_save_in_place(self, client, library):
        page = client.get(f"/item/{library['plain'][0]}").text
        assert 'data-inplace="Topics saved"' in page and 'data-inplace="Note saved"' in page


class TestGettingAround:
    def test_the_tab_bar(self, client, library):
        tabs = re.search(r'<nav class="rr-tabbar".*?</nav>', client.get("/").text, re.S).group(0)
        assert [h for h in re.findall(r'href="([^"]+)"', tabs)] == ["/", "/search", "/shuffle", "/topics", "/more"]
        assert 'data-sheet-open="more"' in tabs

    @pytest.mark.parametrize("path", ["/", "/more"])
    def test_more_holds_everything_that_isnt_a_tab(self, client, library, path):
        page = client.get(path).text
        for href in ["/keep", "/shuffle?theme=Undefined&amp;order=newest", "/notes", "/topics/sort",
                     "/year", "/wander", "/sync"]:
            assert f'<a href="{href}">' in page
        assert 'data-mode="dark"' in page

    @pytest.mark.parametrize("path", ["/keep", "/year", "/sync", "/more", "/notes"])
    def test_more_lights_up_for_its_pages(self, client, library, path):
        tabs = re.search(r'<nav class="rr-tabbar".*?</nav>', client.get(path).text, re.S).group(0)
        assert '<a href="/more" data-sheet-open="more" class="is-on" aria-current="page">' in tabs

    @pytest.mark.parametrize("path", ["/", "/topics", "/search", "/more"])
    def test_the_tabs_own_pages_start_the_trail(self, client, library, path):
        page = client.get(path).text
        assert "<body class=\"rr\" data-root" in page and "data-back" not in page.split("</header>")[0]

    @pytest.mark.parametrize("path, parent", [
        ("/search?theme=Undefined", "/search"), ("/topics/sort", "/topics"), ("/notes", "/more"),
        ("/keep", "/more"), ("/year", "/more"), ("/sync", "/more")])
    def test_pages_below_the_tabs_have_a_way_back(self, client, library, path, parent):
        page = client.get(path).text
        assert f'<a class="rr-back" href="{parent}" data-back>' in page
        assert "data-root" not in page[:page.index("<header")]

    def test_a_save_names_itself_for_the_page_after(self, client, library):
        page = client.get(f"/item/{library['food'][0]}").text
        assert '<a class="rr-back" href="/search" data-back>' in page
        assert 'data-here="Tomato salad"' in page

    def test_the_feed_closes_back_to_where_you_were(self, client, library):
        page = client.get("/shuffle?seed=3").text
        assert '<a class="rr-deck-btn" href="/" data-back aria-label="Close">' in page
        assert 'class="rr-masthead' not in page

    def test_lists_offer_their_saves_as_a_feed(self, client, library):
        page = client.get("/search", params={"theme": "Undefined"}).text
        assert 'href="/shuffle?theme=Undefined&amp;order=newest"' in page
        assert "Give these a topic, one flick at a time." in page
        page = client.get("/search", params={"theme": "Food & cooking", "sort": "oldest"}).text
        assert 'href="/shuffle?theme=Food+%26+cooking&amp;order=oldest"' in page

    def test_search_pages_load_more_in_place(self, client, conn):
        for n in range(explore.PAGE_SIZE + 2):
            add(conn, 500 + n)
        page = client.get("/search").text
        assert 'href="/search?page=2" data-next>' in page

    def test_the_front_door_surprise_is_the_feed(self, client, library):
        assert '<a class="rr-surprise" href="/shuffle">' in client.get("/").text
