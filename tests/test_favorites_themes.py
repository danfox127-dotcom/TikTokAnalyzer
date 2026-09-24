"""Themes: a fixed vocabulary of subjects, matched without a model."""

import json

import pytest
from fastapi.testclient import TestClient

from favorites import db, themes
from favorites.app import app


def about(tags=(), text="", categories=()):
    return themes.themes_for(tags, [text], categories)


class TestMatching:
    def test_a_hashtag_names_its_theme(self):
        assert about(["dogs"]) == ["Dogs"]
        assert about(["sourdough"]) == ["Food & cooking"]

    def test_compound_hashtags_are_read(self):
        assert "Dogs" in about(["dogsoftiktok"])
        assert "Dogs" in about(["goldenretrieverpuppy"])
        assert "Food & cooking" in about(["easyrecipes"])
        assert "Travel" in about(["travelgram"])

    def test_a_hashtag_that_is_a_word_is_taken_at_its_word(self):
        # "homemade" starts with "home", but it is food.
        assert about(["homemade"]) == ["Food & cooking"]

    def test_short_words_are_not_found_inside_other_words(self):
        assert about(["heart"]) == []       # not "art", though it ends in it
        assert "Cars & vehicles" not in about(["cartoon"])  # starts with "car"
        assert about(["education"]) == ["How-to & learning"]  # not "cat"

    def test_plurals_fold(self):
        # Only "corgi" and "hamster" are listed; the plurals fold onto them.
        assert about(text="two corgis and some hamsters") == ["Dogs", "Animals & wildlife"]

    def test_ambiguous_words_count_only_as_hashtags(self):
        # In a sentence "work" and "home" mean too many things.
        assert about(text="this doesn't work, back home now") == []
        assert about(["work"]) == ["Money & work"]
        # Found checking by hand: a council "budget hearing" is not personal
        # finance, and "train your dog" is not transit.
        assert about(text="Budget hearing highlights") == []
        assert about(text="train your dog to sit") == ["Dogs"]
        assert about(["budget"]) == ["Money & work"]
        assert about(["home"]) == ["Home & DIY"]

    def test_your_category_names_count(self):
        # Chosen words: a category called "Sweet sweet puppers" is about dogs.
        assert about(categories=["Sweet sweet puppers"]) == ["Dogs"]
        assert about(categories=["Food gifs"]) == ["Food & cooking"]

    def test_stronger_signals_come_first(self):
        found = about(["localgov", "zoning"], text="a bike lane")
        assert found[0] == "Cities & urbanism"  # zoning (tag) + bike (text)
        assert "News & politics" in found

    def test_a_plural_written_out_starts_a_compound(self):
        # Folding "huskies" to "husky" used to hide #huskiesofinstagram.
        assert about(["huskiesofinstagram"]) == ["Dogs"]
        assert about(["puppiesofinstagram"]) == ["Dogs"]
        # A four-letter plural is too short to look for: "eats" is in #treats.
        assert about(["treats"]) == []

    def test_instagrams_explore_page_is_not_travel(self):
        assert about(["explore", "explorepage"]) == []

    @pytest.mark.parametrize("tag, theme", [
        # The most common unthemed hashtags in a real library, September 2026.
        ("photoshop", "Photography & editing"), ("photoshoptricks", "Photography & editing"),
        ("photoshopediting", "Photography & editing"), ("photography", "Photography & editing"),
        ("photoediting", "Photography & editing"), ("adobe", "Photography & editing"),
        ("فوتوشوب", "Photography & editing"),  # Arabic: "Photoshop"
        ("illustrator", "Art & design"), ("adobeillustrator", "Art & design"),
        ("digitalart", "Art & design"),
        ("nyc", "New York"), ("brooklyn", "New York"), ("newyork", "New York"),
        ("chatgpt", "Science & tech"), ("onlinetools", "Science & tech"),
        ("websites", "Science & tech"),
        ("tipsandtricks", "How-to & learning"), ("علمني", "How-to & learning"),  # "teach me"
        ("somatichealing", "Wellness"), ("potato", "Food & cooking"),
        ("radiohost", "Marketing & media"),
    ])
    def test_a_real_librarys_missing_hashtags(self, tag, theme):
        assert theme in about([tag])

    def test_new_words_do_not_reach_too_far(self):
        assert about(["queensland"]) == []           # not Queens, New York
        assert about(["radiohead"]) == ["Music"]      # not radio
        assert about(text="caught on camera, what a photo") == []  # hashtags only
        assert "New York" not in about(text="a manhattan cocktail")

    def test_nothing_recognisable_is_no_theme(self):
        assert about(["xyzzy"], text="went sideways") == []

    def test_the_vocabulary_is_well_formed(self):
        # Every theme has words, and no word is listed twice within one theme.
        for theme, words in themes.THEMES.items():
            listed = [w.lstrip("#") for w in words.split()]
            assert listed, theme
            assert len(listed) == len(set(listed)), theme


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "lib.db")
    yield c
    c.close()


def add(conn, n, title="a video", tags=(), status="ok"):
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": f"https://example.com/{n}", "shared_url": "x", "platform": "tiktok",
        "title": title, "tags": list(tags), "resolve_status": status})
    return item_id


def stored(conn, item_id):
    return json.loads(db.get_item(conn, item_id)["themes"])


class TestStorage:
    def test_a_save_is_themed_as_it_is_stored(self, conn):
        assert stored(conn, add(conn, 1, tags=["dogsoftiktok"])) == ["Dogs"]

    def test_filing_it_under_a_category_can_add_a_theme(self, conn):
        item_id = add(conn, 1, title="look at him go")
        assert stored(conn, item_id) == []
        db.file_under(conn, item_id, "Sweet sweet puppers")
        assert stored(conn, item_id) == ["Dogs"]
        db.unfile(conn, item_id, "Sweet sweet puppers")
        assert stored(conn, item_id) == []

    def test_a_changed_vocabulary_re_themes_the_library_on_next_open(self, tmp_path, monkeypatch):
        path = tmp_path / "lib.db"
        c = db.connect(path)
        item_id = add(c, 1, tags=["zorbing"])
        assert stored(c, item_id) == []
        c.close()

        grown = dict(themes.THEMES, **{"Sport & fitness": themes.THEMES["Sport & fitness"] + " zorbing"})
        monkeypatch.setattr(themes, "THEMES", grown)
        monkeypatch.setattr(themes, "VERSION", "grown")
        anywhere, tags_only = themes._vocabulary()
        monkeypatch.setattr(themes, "ANYWHERE", anywhere)
        monkeypatch.setattr(themes, "TAG_WORDS", {**anywhere, **tags_only})
        monkeypatch.setattr(themes, "_COMPOUND", themes._compound_words())

        c = db.connect(path)
        assert stored(c, item_id) == ["Sport & fitness"]
        assert db.retheme_if_stale(c) == 0  # done once, not on every open
        c.close()

    def test_an_older_library_gains_themes_when_opened(self, tmp_path):
        import sqlite3
        path = tmp_path / "old.db"
        raw = sqlite3.connect(path)
        raw.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, canonical_url TEXT NOT NULL UNIQUE,"
                    " shared_url TEXT NOT NULL, platform TEXT NOT NULL, external_id TEXT, title TEXT,"
                    " creator_name TEXT, creator_handle TEXT, creator_url TEXT, thumbnail_url TEXT,"
                    " description TEXT, transcript TEXT, note TEXT, tags TEXT NOT NULL DEFAULT '[]',"
                    " terms TEXT NOT NULL DEFAULT '[]', saved_at TEXT NOT NULL, resolved_at TEXT,"
                    " resolve_status TEXT NOT NULL DEFAULT 'pending', resolve_error TEXT, raw TEXT)")
        raw.execute("INSERT INTO items (canonical_url, shared_url, platform, title, tags, saved_at,"
                    " resolve_status) VALUES ('u', 'u', 'tiktok', 'x', '[\"cats\"]', '2024-01-01', 'ok')")
        raw.commit()
        raw.close()
        c = db.connect(path)
        assert json.loads(c.execute("SELECT themes FROM items").fetchone()[0]) == ["Cats"]
        c.close()


class TestReport:
    def test_coverage_and_the_hashtags_it_misses(self, conn):
        add(conn, 1, tags=["dogs", "zorbing"])
        add(conn, 2, tags=["zorbing"])
        add(conn, 3, tags=["cats"])
        add(conn, 4, tags=["zorbing"], status="pending")  # not identified: not counted
        r = themes.report(conn)
        assert (r["items"], r["themed"]) == (3, 2)
        assert dict(r["per_theme"]) == {"Dogs": 1, "Cats": 1}
        assert r["unrecognised_hashtags"] == [("zorbing", 2)]

    def test_reach_and_self_naming_hashtags_are_not_listed(self, conn):
        for n in (1, 2):
            db.upsert_item(conn, {
                "canonical_url": f"https://example.com/{n}", "shared_url": "x",
                "platform": "instagram", "title": "a video", "creator_handle": "@redavisuals",
                "tags": ["fypシ", "redavisuals", "zorbing"], "resolve_status": "ok"})
        assert themes.report(conn)["unrecognised_hashtags"] == [("zorbing", 2)]

    def test_the_command_prints_it(self, tmp_path, capsys):
        path = tmp_path / "lib.db"
        c = db.connect(path)
        add(c, 1, tags=["dogs"])
        add(c, 2, tags=["zorbing"])
        add(c, 3, tags=["zorbing"])
        c.close()
        themes.main(["--db", str(path)])
        out = capsys.readouterr().out
        assert "1 of 3 identified saves have at least one theme (33%)" in out
        assert "#zorbing" in out


class TestPages:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        path = tmp_path / "favorites.db"
        monkeypatch.setenv("FAVORITES_DB", str(path))
        c = db.connect(path)
        for n in range(3):
            db.upsert_item(c, {
                "canonical_url": f"https://example.com/{n}", "shared_url": "x",
                "platform": "instagram", "title": "zoomies", "tags": ["dogs"],
                "creator_name": "Good Boy Daily", "creator_handle": "@goodboy",
                "resolve_status": "ok", "saved_at": f"2024-0{n + 1}-01T00:00:00+00:00"})
        c.close()
        with TestClient(app) as client:
            yield client

    def test_the_masthead_says_browse(self, client):
        assert '<span class="count-label">Browse</span>' in client.get("/").text

    def test_the_front_page_opens_the_catalogue(self, client):
        page = client.get("/").text
        assert "Browse the collection" in page
        assert 'href="/search?theme=Dogs"' in page
        assert 'href="/search?creator=%40goodboy"' in page
        assert 'href="/search?platform=instagram"' in page

    def test_an_items_themes_link_to_the_theme(self, client):
        c = db.connect()
        item_id = c.execute("SELECT id FROM items LIMIT 1").fetchone()[0]
        c.close()
        assert 'href="/search?theme=Dogs"' in client.get(f"/item/{item_id}").text
