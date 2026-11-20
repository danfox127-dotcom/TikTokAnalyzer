"""Search's one row of filter buttons: Topic, Creator, When, From, Yours."""

import re

import pytest
from fastapi.testclient import TestClient

from favorites import db, explore
from favorites.app import app
from favorites.explore import Filters


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


@pytest.fixture
def library(conn):
    for n, (title, who, platform, saved) in enumerate([
            ("Carbonara #pasta", "@chefana", "tiktok", "2024-07-15"),
            ("Cacio e pepe #pasta", "@chefana", "tiktok", "2023-01-10"),
            ("Good boy #dogs", "@barkley", "instagram", "2024-07-20")]):
        db.upsert_item(conn, {"canonical_url": f"https://example.com/{n}", "shared_url": "x", "platform": platform,
                              "resolve_status": "ok", "title": title, "creator_handle": who,
                              "saved_at": f"{saved}T10:00:00+00:00"})
    return conn


def buttons(page):
    return re.findall(r'<details class="filter-pill" id="f-(\w+)">\s*<summary class="rr-pill( is-on)?"><span class="t">([^<]+)</span>',
                      page)


class TestTheButtons:
    def test_in_the_order_people_reach_for_them(self, client, library):
        assert [(key, shown) for key, _, shown in buttons(client.get("/search").text)] == [
            ("topic", "Topic"), ("creator", "Creator"), ("when", "When"), ("from", "From")]

    def test_a_button_says_what_is_chosen_in_it(self, client, library):
        page = client.get("/search?theme=Food+%26+cooking").text
        assert ("topic", " is-on", "Food &amp; cooking") in buttons(page)
        page = client.get("/search?year=2024&season=summer").text
        assert ("when", " is-on", "When · 2") in buttons(page)

    def test_each_opens_its_own_filters_and_comes_back_after_a_pick(self, client, library):
        page = client.get("/search").text
        topic = re.search(r'<details class="filter-pill" id="f-topic">.*?</details>', page, re.S).group(0)
        assert "<h3 class=\"rr-label\">Topics</h3>" in topic and "Creators" not in topic
        assert 'href="/search?theme=Food+%26+cooking#f-topic"' in topic
        assert 'href="/browse">Every topic at a glance' in topic and "Show 3 saves" in topic
        creator = re.search(r'<details class="filter-pill" id="f-creator">.*?</details>', page, re.S).group(0)
        assert 'href="/browse/creators">Every creator, A to Z' in creator

    def test_clearing_a_button_clears_all_it_holds(self, client, library):
        page = client.get("/search?year=2024&season=summer&platform=tiktok").text
        when = re.search(r'<details class="filter-pill" id="f-when">.*?</details>', page, re.S).group(0)
        assert '<a class="rr-btn rr-btn--quiet" href="/search?platform=tiktok">Clear</a>' in when

    def test_the_clear_link_forgets_the_week_with_the_day(self):
        f = Filters(day="07-15", week="1", platform="tiktok")
        found = [explore.Facet("day", "On this day", [explore.Option("07-15", "On this day", 1, "#", active=True)])]
        [when] = explore.groups(f, found)
        assert (when.key, when.shown, when.clear) == ("when", "On this day", "/search?platform=tiktok")

    def test_no_side_column_or_tabbed_sheet_any_more(self, client, library):
        page = client.get("/search").text
        assert "filters-side" not in page and "rr-filters-mobile" not in page and 'class="tabs"' not in page

    def test_a_way_to_browse_after_the_results(self, client, library):
        page = client.get("/search?q=pasta").text
        assert '<a class="browse-door" href="/browse">' in page

    def test_the_script_keeps_one_open_and_reopens_after_a_pick(self, client):
        js = client.get("/static/museum.js").text
        fn = js[js.index("function sheet(details)"):js.index("/* ---- suggestions under the search field")]
        assert "location.hash === '#' + details.id" in fn and "d !== details) d.open = false" in fn
        assert "document.querySelectorAll('.filter-pill').forEach(sheet)" in js
