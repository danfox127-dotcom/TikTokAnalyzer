"""Search and filters: one page that narrows the whole library."""

import pytest
from fastapi.testclient import TestClient

from favorites import db, explore, tagging
from favorites.app import app
from favorites.explore import Filters


def add(conn, n, platform="tiktok", saved="2024-07-15", caption="Tomato salad #cooking",
        creator=("Kitchen Desk", "@kitchendesk"), note=None, fmt="short", filed=()):
    tags, terms = tagging.enrich(title=caption, description=caption)
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": f"https://example.com/{n}", "shared_url": "x", "platform": platform,
        "title": caption, "description": caption, "creator_name": creator[0],
        "creator_handle": creator[1], "tags": tags, "terms": terms, "note": note,
        "format": fmt, "resolve_status": "ok", "saved_at": f"{saved}T12:00:00+00:00",
    })
    for name in filed:
        db.file_under(conn, item_id, name)
    return item_id


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "lib.db"))
    yield c
    c.close()


@pytest.fixture
def library(conn):
    ids = {
        "salad_summer_tt": add(conn, 1, saved="2024-07-15", filed=("Food gifs",)),
        "salad_summer_ig": add(conn, 2, platform="instagram", saved="2023-08-02",
                               filed=("food GIFS",)),
        "dumplings_winter": add(conn, 3, saved="2024-01-10", caption="Folding dumplings #cooking #dumplings",
                                note="make these for the party"),
        "zoning_autumn": add(conn, 4, platform="youtube", saved="2024-10-03", fmt="video",
                             caption="Zoning meeting went sideways #localgov",
                             creator=("City Desk", "@citydesk")),
        "budget_dec": add(conn, 5, platform="youtube", saved="2023-12-20",
                          caption="Budget hearing highlights #localgov",
                          creator=("City Desk", "@citydesk")),
    }
    return ids


def ids(conn, library, **filters):
    items, total = explore.results(conn, Filters(**filters))
    assert total == len(items)
    names = {v: k for k, v in library.items()}
    return {names[i["id"]] for i in items}


class TestNarrowing:
    def test_nothing_chosen_is_everything_newest_first(self, conn, library):
        items, total = explore.results(conn, Filters())
        assert total == 5
        assert [i["saved_at"][:10] for i in items] == sorted(
            (i["saved_at"][:10] for i in items), reverse=True)

    def test_platform(self, conn, library):
        assert ids(conn, library, platform="youtube") == {"zoning_autumn", "budget_dec"}

    def test_year_is_the_year_you_saved_it(self, conn, library):
        assert ids(conn, library, year="2023") == {"salad_summer_ig", "budget_dec"}

    def test_season_spans_years_and_winter_spans_new_year(self, conn, library):
        assert ids(conn, library, season="summer") == {"salad_summer_tt", "salad_summer_ig"}
        # December 2023 and January 2024 are the same winter.
        assert ids(conn, library, season="winter") == {"dumplings_winter", "budget_dec"}

    def test_category_ignores_capitalisation(self, conn, library):
        assert ids(conn, library, collection="FOOD gifs") == {"salad_summer_tt", "salad_summer_ig"}

    def test_creator(self, conn, library):
        assert ids(conn, library, creator="@citydesk") == {"zoning_autumn", "budget_dec"}

    def test_hashtag_with_or_without_the_hash(self, conn, library):
        assert ids(conn, library, tag="dumplings") == {"dumplings_winter"}
        assert ids(conn, library, tag="#Dumplings") == {"dumplings_winter"}

    def test_theme(self, conn, library):
        # Salads and dumplings are both cooking; zoning and budgets are both politics.
        assert ids(conn, library, theme="Food & cooking") == {
            "salad_summer_tt", "salad_summer_ig", "dumplings_winter"}
        assert ids(conn, library, theme="news & POLITICS") == {"zoning_autumn", "budget_dec"}
        assert ids(conn, library, theme="Cities & urbanism") == {"zoning_autumn"}

    def test_notes(self, conn, library):
        assert ids(conn, library, noted="1") == {"dumplings_winter"}

    def test_kind(self, conn, library):
        assert ids(conn, library, format="video") == {"zoning_autumn"}

    def test_filters_combine(self, conn, library):
        assert ids(conn, library, tag="cooking", season="summer", platform="tiktok") == {"salad_summer_tt"}
        assert ids(conn, library, tag="localgov", year="2024") == {"zoning_autumn"}

    def test_words_combine_with_filters(self, conn, library):
        assert ids(conn, library, q="salad", platform="instagram") == {"salad_summer_ig"}
        # A note is searchable, like everything else you wrote.
        assert ids(conn, library, q="party") == {"dumplings_winter"}

    def test_a_query_that_would_break_the_search_engine_does_not(self, conn, library):
        explore.results(conn, Filters(q='broken "quote'))
        explore.results(conn, Filters(q="!!!", platform="tiktok"))


class TestTheAddress:
    def test_junk_in_the_address_is_dropped_not_obeyed(self):
        f = Filters.from_params({"season": "monsoon", "year": "20x4", "sort": "random",
                                 "format": "gif", "noted": "yes", "page": "-3",
                                 "platform": "tiktok"})
        assert f == Filters(platform="tiktok")

    def test_changing_a_filter_goes_back_to_page_one(self):
        f = Filters(platform="tiktok", page=3)
        assert f.href(year="2024") == "/search?platform=tiktok&year=2024"
        assert f.href(page=4) == "/search?platform=tiktok&page=4"

    def test_removing_the_last_filter_is_plain_search(self):
        assert Filters(tag="cooking").href(tag=None) == "/search"

    def test_best_match_only_means_something_with_words(self):
        assert Filters(sort="relevance").order == "newest"
        assert Filters(q="salad").order == "relevance"
        assert Filters(q="salad", sort="oldest").order == "oldest"


class TestTheOptions:
    def by_name(self, conn, f):
        return {facet.name: facet for facet in explore.facets(conn, f)}

    def test_each_option_says_how_many_it_would_leave(self, conn, library):
        platform = self.by_name(conn, Filters())["platform"]
        assert {o.value: o.count for o in platform.options} == {
            "tiktok": 2, "youtube": 2, "instagram": 1}

    def test_counts_respect_the_other_filters_but_not_their_own(self, conn, library):
        facets = self.by_name(conn, Filters(platform="youtube", year="2024"))
        # Platform counts are within 2024, and still offer the other platforms.
        assert {o.value: o.count for o in facets["platform"].options} == {
            "youtube": 1, "tiktok": 2}
        # Year counts are within YouTube, and still offer the other year.
        assert {o.value: o.count for o in facets["year"].options} == {"2024": 1, "2023": 1}

    def test_the_chosen_option_is_marked_and_clicking_it_again_removes_it(self, conn, library):
        platform = self.by_name(conn, Filters(platform="youtube"))["platform"]
        chosen = platform.active
        assert chosen.value == "youtube"
        assert chosen.href == "/search"

    def test_seasons_run_in_calendar_order(self, conn, library):
        season = self.by_name(conn, Filters())["season"]
        assert [o.value for o in season.options] == ["winter", "summer", "autumn"]

    def test_categories_group_regardless_of_capitalisation(self, conn, library):
        collection = self.by_name(conn, Filters())["collection"]
        assert [(o.label.lower(), o.count) for o in collection.options] == [("food gifs", 2)]

    def test_themes_are_offered_with_counts(self, conn, library):
        themes = {o.value: o.count for o in self.by_name(conn, Filters())["theme"].options}
        assert themes["Food & cooking"] == 3

    def test_creators_and_themes_come_before_when(self, conn, library):
        order = [facet.name for facet in explore.facets(conn, Filters())]
        assert order.index("creator") < order.index("theme") < order.index("tag")
        assert order.index("tag") < order.index("year") < order.index("season")
        assert order[-2:] == ["season", "noted"]
        assert "term" not in order  # keywords were noise; themes replace them

    def test_a_hashtag_on_a_single_save_is_not_offered(self, conn, library):
        tags = {o.value for o in self.by_name(conn, Filters())["tag"].options}
        assert tags == {"cooking", "localgov"}  # dumplings appears once

    def test_reach_hashtags_are_not_offered(self, conn, library):
        # Saves from before a spelling was known to be noise still carry it.
        for n in (6, 7):
            item_id = add(conn, n)
            conn.execute("UPDATE items SET tags = '[\"fypシ\", \"cooking\"]' WHERE id = ?", (item_id,))
        tags = {o.value for o in self.by_name(conn, Filters())["tag"].options}
        assert tags == {"cooking", "localgov"}

    def test_unless_it_is_the_one_chosen(self, conn, library):
        tags = {o.value for o in self.by_name(conn, Filters(tag="dumplings"))["tag"].options}
        assert "dumplings" in tags


class TestTheHeading:
    @pytest.mark.parametrize("filters, words", [
        ({}, "Everything"),
        ({"q": "salad"}, "“salad”"),
        ({"tag": "cooking", "season": "summer"}, "Saves tagged #cooking from summers"),
        ({"platform": "tiktok", "season": "summer", "year": "2024"},
         "TikTok saves from summer 2024"),
        ({"theme": "Dogs", "platform": "instagram"}, "Instagram saves about Dogs"),
        ({"format": "short", "creator": "@citydesk", "noted": "1"},
         "Short-form videos by @citydesk, with your notes"),
    ])
    def test_the_view_is_described_in_words(self, filters, words):
        assert explore.describe(Filters(**filters), []) == words


class TestThePage:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        path = tmp_path / "favorites.db"
        monkeypatch.setenv("FAVORITES_DB", str(path))
        monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
        c = db.connect(str(path))
        add(c, 1, saved="2024-07-15")
        add(c, 2, platform="youtube", saved="2023-12-20", caption="Budget hearing #localgov",
            creator=("City Desk", "@citydesk"))
        c.close()
        with TestClient(app) as client:
            yield client

    def test_filters_show_as_removable_chips(self, client):
        page = client.get("/search", params={"platform": "youtube", "season": "winter"}).text
        assert "YouTube saves from winters" in page
        assert "1 result of 2" in page
        assert 'href="/search?season=winter"' in page      # remove YouTube
        assert 'href="/search?platform=youtube"' in page   # remove Winter
        assert "Budget hearing" in page and "Tomato salad" not in page

    def test_searching_within_keeps_the_filters(self, client):
        page = client.get("/search", params={"platform": "youtube"}).text
        assert '<input type="hidden" name="platform" value="youtube">' in page

    def test_there_is_one_search_box_and_it_keeps_the_filters(self, client):
        # The masthead box would start over, dropping every filter.
        page = client.get("/search", params={"platform": "youtube"}).text
        assert page.count('name="q"') == 1
        assert client.get("/").text.count('name="q"') == 1  # other pages keep theirs

    def test_everything_is_the_search_page_with_nothing_chosen(self, client):
        resp = client.get("/all", follow_redirects=False)
        assert resp.status_code == 307 and resp.headers["location"] == "/search"
        page = client.get("/all").text
        assert "Everything" in page and "2 saves" in page

    def test_nothing_matching_says_so(self, client):
        page = client.get("/search", params={"platform": "youtube", "year": "2024"}).text
        assert "Nothing matches all of these together" in page

    def test_an_items_hashtags_open_that_exact_hashtag(self, client):
        c = db.connect()
        item_id = db.search(c, "salad")[0]["id"]
        c.close()
        assert 'href="/search?tag=cooking"' in client.get(f"/item/{item_id}").text


class TestUndefined:
    """The saves no theme recognises yet, offered as "Undefined"."""

    @pytest.fixture
    def with_unthemed(self, conn, library):
        # By someone new: a Kitchen Desk save would lean to Food, as theirs all are.
        library["mystery_tt"] = add(conn, 6, caption="you have to see this one",
                                    creator=("Someone New", "@someonenew"))
        library["mystery_yt"] = add(conn, 7, platform="youtube", fmt="video",
                                    caption="tonight, again", creator=("City Desk", "@citydesk"))
        return library

    def test_it_holds_the_saves_with_no_theme(self, conn, with_unthemed):
        assert ids(conn, with_unthemed, theme="Undefined") == {"mystery_tt", "mystery_yt"}
        assert ids(conn, with_unthemed, theme="undefined", platform="youtube") == {"mystery_yt"}

    def test_it_heads_the_themes_with_a_count_that_follows_the_other_filters(self, conn, with_unthemed):
        themes = {f.name: f for f in explore.facets(conn, Filters())}["theme"].options
        assert (themes[0].value, themes[0].count, themes[0].kind) == ("Undefined", 2, "undefined")
        assert [o.value for o in themes[1:]] == ["Food & cooking", "News & politics", "Cities & urbanism"]
        mine = {f.name: f for f in explore.facets(conn, Filters(platform="tiktok"))}["theme"]
        assert mine.options[0].count == 1

    def test_choosing_it_and_choosing_it_again(self, conn, with_unthemed):
        chosen = {f.name: f for f in explore.facets(conn, Filters(theme="Undefined"))}["theme"]
        assert chosen.active.value == "Undefined"
        assert chosen.active.href == "/search"
        # The other themes stay on offer, so you can switch straight to one.
        assert "Food & cooking" in {o.value for o in chosen.options}

    def test_it_is_not_offered_when_everything_has_a_theme(self, conn, library):
        themes = {f.name: f for f in explore.facets(conn, Filters())}["theme"].options
        assert "Undefined" not in {o.value for o in themes}

    @pytest.mark.parametrize("filters, words", [
        ({"theme": "Undefined"}, "Undefined saves"),
        ({"theme": "Undefined", "platform": "tiktok"}, "Undefined TikTok saves"),
        ({"theme": "Undefined", "creator": "@citydesk", "year": "2024"},
         "Undefined saves by @citydesk from 2024"),
    ])
    def test_the_heading(self, filters, words):
        assert explore.describe(Filters(**filters), []) == words


class TestUndefinedOnThePages:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        path = tmp_path / "favorites.db"
        monkeypatch.setenv("FAVORITES_DB", str(path))
        monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
        c = db.connect(str(path))
        add(c, 1)                                         # themed: Food & cooking
        add(c, 2, caption="you have to see this one")     # no theme
        c.close()
        with TestClient(app) as client:
            yield client

    def test_the_filter_page_offers_it(self, client):
        page = client.get("/search").text
        assert '<li class="undefined"><a href="/search?theme=Undefined">' in page
        page = client.get("/search", params={"theme": "Undefined"}).text
        assert "Undefined saves" in page and "you have to see this one" in page
        assert "Tomato salad" not in page

    def test_the_front_page_ends_the_themes_with_it(self, client):
        page = client.get("/").text
        assert ('class="rr-pill is-undefined" href="/search?theme=Undefined">Undefined'
                ' <span class="n">1</span>') in page


class TestOnThisDay:
    """A month and day matched across every year, and the week around it."""

    @pytest.fixture
    def dated(self, conn):
        return {
            "sep27_2023": add(conn, 11, saved="2023-09-27"),
            "sep27_2025": add(conn, 12, saved="2025-09-27"),
            "sep29_2024": add(conn, 13, saved="2024-09-29"),
            "oct20_2024": add(conn, 14, saved="2024-10-20"),
            "dec30_2022": add(conn, 15, saved="2022-12-30"),
            "jan02_2024": add(conn, 16, saved="2024-01-02"),
        }

    def test_the_day_in_every_year(self, conn, dated):
        assert ids(conn, dated, day="09-27") == {"sep27_2023", "sep27_2025"}

    def test_the_week_reaches_three_days_either_side(self, conn, dated):
        assert ids(conn, dated, day="09-27", week="1") == {"sep27_2023", "sep27_2025", "sep29_2024"}

    def test_the_week_wraps_at_new_year(self, conn, dated):
        assert ids(conn, dated, day="12-31", week="1") == {"dec30_2022", "jan02_2024"}

    def test_a_date_that_does_not_exist_is_dropped(self):
        assert Filters.from_params({"day": "02-30"}).day == ""
        assert Filters.from_params({"day": "9-27"}).day == ""
        assert Filters.from_params({"day": "02-29"}).day == "02-29"

    def test_the_week_means_nothing_without_a_day(self):
        assert Filters.from_params({"week": "1"}).week == ""

    def test_offered_for_today_before_the_years(self, conn, dated):
        found = explore.facets(conn, Filters(), today="09-27")
        names = [f.name for f in found]
        assert names.index("day") < names.index("year")
        day = next(f for f in found if f.name == "day")
        assert [(o.label, o.count) for o in day.options] == [
            ("On this day", 2), ("This week, other years", 3)]

    def test_described_and_removed_as_one_filter(self, conn, dated):
        f = Filters(day="09-27", week="1")
        found = explore.facets(conn, f, today="09-27")
        assert explore.describe(f, found) == "Saves saved the week of 27 September"
        assert explore.chips(f, found) == [("This week, other years", "/search")]


class TestAQuietToday:
    """Found on a real library, 4 October 2026: nothing saved on today's date in
    any year, but something two days off -- every search page returned 500,
    because the "On this day" suggestion read the week's value "10-04~" as a date."""

    @pytest.fixture
    def near_today(self, conn):
        from datetime import datetime, timedelta, timezone
        near = (datetime.now(timezone.utc) - timedelta(days=2)).replace(year=2022)
        add(conn, 1, saved=near.strftime("%Y-%m-%d"), caption="Folding dumplings #cooking")
        add(conn, 2, saved="2022-01-15" if near.month != 1 else "2022-06-15",
            caption="Tomato salad #cooking")
        return conn

    def test_the_search_page_still_opens(self, near_today, tmp_path, monkeypatch):
        monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "lib.db"))
        with TestClient(app) as client:
            resp = client.get("/search")
        assert resp.status_code == 200
        assert "saved the week of" in resp.text

    def test_the_week_row(self, near_today):
        items, _ = explore.results(near_today, Filters())
        rows = explore.pull(Filters(), explore.facets(near_today, Filters()), items)
        [week] = [r for r in rows if "week of" in r["sub"]]
        assert week["sub"].startswith("1 of these were saved the week of")
        assert len(week["covers"]) == 1

    def test_a_week_value_reads_as_its_day(self):
        assert explore.day_label("10-04~") == "4 October"
        assert explore.week_days("01-02~") >= {"12-30", "01-05"}
