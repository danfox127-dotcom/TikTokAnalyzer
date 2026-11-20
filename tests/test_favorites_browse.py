"""Browse: every topic on one screen, every creator, and your saves by date."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from favorites import db, looks, museum
from favorites.app import app, initials

ICONS = (Path(__file__).parent.parent / "favorites" / "templates" / "_icons.html").read_text()


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


def listed(page):
    """The names in the A to Z list."""
    found = re.search(r'<ul class="creator-list">.*?</ul>', page, re.S)
    return re.findall(r'<span class="t"><b>([^<]+)</b>', found.group(0)) if found else []


def add(conn, n, title, name=None, handle=None, platform="tiktok", saved="2025-03-0{d}T10:00:00+00:00"):
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": f"https://www.tiktok.com/video/{n}", "shared_url": "x", "platform": platform,
        "resolve_status": "ok", "title": title, "creator_name": name, "creator_handle": handle,
        "saved_at": saved.format(d=n % 9 + 1)})
    return item_id


@pytest.fixture
def library(conn):
    add(conn, 1, "Good boy #dogs", "Barkley", "@barkley")
    add(conn, 2, "Zoomies #dogs", "Barkley", "@barkley")
    add(conn, 3, "Sit, stay #dogs", "Barkley", "@barkley")
    add(conn, 4, "Carbonara #pasta", "Chef Ana", "@chefana")
    add(conn, 5, "Cacio e pepe #pasta", "Chef Ana", "@chefana")
    add(conn, 6, "A cat in a box #cats", "🐾Whiskers Daily", "@whiskers")
    add(conn, 7, "hello there", "Abe", "@abe")
    add(conn, 8, "nobody says who", None, "@")
    return conn


class TestTopics:
    def test_every_topic_on_one_screen_biggest_first(self, client, library):
        page = client.get("/browse").text
        tiles = re.findall(r'<a class="topic-tile tone-(\w+)" href="([^"]+)">.*?<span class="name">([^<]+)</span>'
                           r'\s*<span class="n">([^<]+)</span>', page, re.S)
        assert [(name, n) for _, _, name, n in tiles] == [
            ("Dogs", "3 saves"), ("Food &amp; cooking", "2 saves"), ("Cats", "1 save")]
        assert tiles[0][:2] == ("peach", "/search?theme=Dogs")       # its own colour, and a way in
        assert "8 saves · 3 topics · 4 creators" in re.sub(r"\s+", " ", page)

    def test_a_to_z(self, client, library):
        page = client.get("/browse?sort=az").text
        assert re.findall(r'<span class="name">([^<]+)</span>', page) == ["Cats", "Dogs", "Food &amp; cooking"]
        assert '<a href="/browse?sort=az" aria-current="true">A–Z</a>' in page

    def test_the_saves_with_no_topic_come_first(self, client, library):
        notice = re.search(r'<a class="browse-notice".*?</a>', client.get("/browse").text, re.S).group(0)
        assert 'href="/shuffle?theme=Undefined&amp;order=newest"' in notice
        assert ">2</span>" in notice and "Saves with no topic yet" in notice

    def test_more_ways_in_stay_on_browse(self, client, library):
        page = client.get("/browse").text
        for href in ("/rewind", "/stats", "/rescue", "/known", "/year", "/wander", "/topics/sort"):
            assert f'href="{href}"' in page

    def test_every_topic_has_an_icon_of_its_own(self):
        names = [icon for _, icon, _ in looks.THEME_LOOK.values()]
        assert len(set(names)) == len(names)
        for name in names + [icon for _, icon, _ in looks.SEASON_LOOK.values()]:
            assert f"'{name}': '<" in ICONS, name

    @pytest.mark.parametrize("path", ["/browse", "/browse/creators", "/browse/dates"])
    def test_one_tab_at_a_time_and_browse_lit(self, client, library, path):
        page = client.get(path).text
        tabs = re.search(r'<nav class="browse-tabs".*?</nav>', page, re.S).group(0)
        assert re.findall(r'<a href="([^"]+)" aria-current="page">', tabs) == [path]
        bar = re.search(r'<nav class="rr-tabbar".*?</nav>', page, re.S).group(0)
        assert '<a href="/browse" class="is-on" aria-current="page">' in bar


class TestCreators:
    def test_regulars_as_faces_most_saves_first(self, client, library):
        page = client.get("/browse/creators").text
        cards = re.findall(r'<a class="creator-card" href="([^"]+)">.*?>(\w+)</span>\s*<span class="name">([^<]+)</span>'
                           r'.*?<span class="n[^"]*">([^<]+)</span>', page, re.S)
        assert cards == [("/creator/%40barkley", "B", "Barkley", "3 saves"),
                         ("/creator/%40chefana", "CA", "Chef Ana", "2 saves")]
        assert "2 creators you've saved from more than once" in page

    def test_a_to_z_by_handle(self, client, library):
        page = client.get("/browse/creators?sort=az").text
        assert re.findall(r'<span class="name">([^<]+)</span>', page) == ["Barkley", "Chef Ana"]

    def test_everyone_else_a_letter_at_a_time(self, client, library):
        page = client.get("/browse/creators").text
        letters = re.search(r'<nav class="browse-letters".*?</nav>', page, re.S).group(0)
        assert re.findall(r">(\w)</a>", letters) == ["A", "W"]
        assert '<a href="/browse/creators?letter=a#everyone" aria-current="true">A</a>' in letters
        assert listed(page) == ["Abe"]
        page = client.get("/browse/creators?letter=w").text
        # Emoji in a name are passed over for its initials.
        assert listed(page) == ["🐾Whiskers Daily"]
        assert '<span class="avatar tone-' in page and ">WD</span>" in page

    def test_finding_someone(self, client, library):
        page = client.get("/browse/creators?q=whisk").text
        assert "1 creator matches “whisk”" in page and "🐾Whiskers Daily" in page and "Barkley" not in page
        assert "browse-letters" not in page and "browse-notice" not in page
        assert "Nobody by that name." in client.get("/browse/creators?q=zzz").text

    def test_saves_missing_a_creator(self, client, library):
        page = client.get("/browse/creators").text
        notice = re.search(r'<a class="browse-notice".*?</a>', page, re.S).group(0)
        assert 'href="/browse/creators/missing"' in notice and "Save missing a creator" in notice
        page = client.get("/browse/creators/missing").text
        assert "Saves missing a creator" in page and "nobody says who" in page and "Good boy" not in page

    def test_the_index(self, library):
        everyone = {c["key"]: c for c in museum.creator_index(library)}
        assert set(everyone) == {"@barkley", "@chefana", "@whiskers", "@abe"}    # a bare "@" is no one
        assert everyone["@whiskers"]["letter"] == "w" and everyone["@barkley"]["count"] == 3
        assert museum.creator_count(library) == 4


class TestDates:
    def test_your_saves_by_when(self, client, library):
        page = client.get("/browse/dates").text
        assert "By month" in page and 'href="/month/2025-03"' in page and "The last month" in page
        assert "topic-grid" not in page and "creator-card" not in page


@pytest.mark.parametrize("name, letters", [
    ("Marisol Cooks", "MC"), ("@city.desk", "CD"), ("🐾🐺SIBERIAN HUSKY PUPPIES🐺🐾", "SH"), ("✧✭", "?"), ("", "?")])
def test_initials(name, letters):
    assert initials(name) == letters


def test_an_empty_library(client):
    for path in ("/browse", "/browse/dates"):
        assert "Nothing to browse yet." in client.get(path).text
