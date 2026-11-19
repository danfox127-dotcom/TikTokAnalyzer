"""Sharper topics (Phase A): everyday words that never tag along, food
animals that are dinner, two-word subjects, hashtags read by their ending,
your note counting like a category -- and an Undefined that only counts
saves with words to read, a refiling that can't fight itself, and a page
showing what each change to the rules moved."""

import json

import pytest
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import db, explore, themes


def about(tags=(), text="", note=None, creator=None):
    return themes.decide(themes.weigh(tags, [text], note=note, creator=creator))


class TestEverydayWords:
    """Gemini's examples, and the ones in the library."""

    @pytest.mark.parametrize("tags, text, want", [
        (["pottery"], "absolutely beautiful job im very impressed", ["Art & design"]),
        (["music"], "Making music with Orba. Money-back guarantee", ["Music"]),
        ([], "Toyota RAV4 or Mazda CX-50. I know which one if it were my money", ["Cars & vehicles"]),
    ])
    def test_never_tag_along(self, tags, text, want):
        assert about(tags, text) == want

    def test_still_file_a_save_with_nothing_else(self):
        assert about([], "Don't use Apple's HYSA, do this with your money instead") == ["Money & work"]

    def test_a_subject_word_still_rides_along(self):
        assert set(about(["localgov"], "zoning meeting")) == {"News & politics", "Cities & urbanism"}


class TestFoodAnimals:
    def test_chicken_on_a_recipe_is_dinner(self):
        assert about(["butter", "foodtok"], "Chicken and mushrooms") == ["Food & cooking"]
        assert about(["recipe", "chicken"], "roast chicken") == ["Food & cooking"]
        assert about(["chickenrecipe"]) == ["Food & cooking"]
        assert about([], "You don't need to live by the sea for good fish and chips") == ["Food & cooking"]

    def test_a_pet_duck_is_still_an_animal(self):
        assert about(["pets", "ducks"], "MAGDA - MY FAMOUS DUCK") == ["Animals & wildlife"]


class TestPhrases:
    @pytest.mark.parametrize("text, want", [
        ("Trying the best slice in New York", ["New York"]),
        ("a thread on mental health at work", ["Wellness"]),
        ("how to have an effective team meeting", ["How-to & learning"]),
        ("Repost! How to find information about anyone", ["How-to & learning"]),
        ("his stand-up comedy special", ["Comedy & humour"]),
        ("real estate in this market", ["Home & DIY"]),
    ])
    def test_two_words_read_as_one(self, text, want):
        assert about([], text) == want

    @pytest.mark.parametrize("text", ["I don't know how to feel about this", "stand up for yourself"])
    def test_but_not_in_everyday_sentences(self, text):
        assert about([], text) == []

    def test_the_reason_says_it_as_written(self):
        ev = themes.weigh([], ["Trying the best slice in New York"])
        assert themes.explain(ev, ["New York"])[0]["reasons"] == ["“new york” in the caption"]


class TestHashtagEndings:
    @pytest.mark.parametrize("tag, want", [
        ("italianfood", {"Food & cooking"}), ("njfood", {"Food & cooking"}),
        ("mexicanricerecipe", {"Food & cooking"}), ("datinginnyc", {"New York"}),
        ("nycdating", {"New York"}), ("metmuseum", {"History"}), ("jewishhistory", {"History"}),
        ("iphonetips", {"Science & tech"}), ("twitchstreamer", {"Gaming"}),
    ])
    def test_a_known_ending_names_it(self, tag, want):
        assert themes._tag_hits(tag)[0] == want

    @pytest.mark.parametrize("tag", ["guidance", "husband", "heartfelt"])
    def test_everyday_endings_dont(self, tag):
        assert themes._tag_hits(tag)[0] == set()


class TestSmallFixes:
    def test_es_plurals(self):
        assert themes._norm("sandwiches") == "sandwich" and themes._norm("news") == "news"
        assert about([], "three sandwiches worth the trip") == ["Food & cooking"]

    def test_your_note_counts_like_a_category(self):
        assert about([], "just a clip", note="for the zoning piece") == ["Cities & urbanism"]
        ev = themes.weigh([], ["just a clip"], note="for the zoning piece")
        assert ev["Cities & urbanism"] == [("note", "zoning", 3)]
        assert themes.explain(ev, ["Cities & urbanism"])[0]["reasons"] == ["“zoning” in your note"]

    def test_the_link_preview_wrapper_is_not_the_caption(self):
        wrapped = '1,204 likes, 31 comments - musicdaily on March 3, 2024: "a zoning map of the city"'
        assert about([], wrapped) == ["Cities & urbanism"]
        assert about([], '3,581 likes: "a guitar lesson"') == ["Music"]

    @pytest.mark.parametrize("tags, text, creator, want", [
        (["detox", "guthealth", "nutrition"], "Detox your gut now and then.", None, ["Wellness"]),
        (["wfh", "corporate"], "repeat after me: it's not that deep", None, ["Money & work"]),
        (["masseffect", "streamer"], "NO GAME HURT ME LIKE MASS EFFECT 3", None, ["Gaming"]),
        (["marvelstudios", "disneyplus"], "That would be so crazy", None, ["Film & TV"]),
        ([], "Sometimes people are just too smol", "doggosbeinggood", ["Dogs"]),
        (["realestate", "realtor"], "Would you pay that much to live there?", None, ["Home & DIY"]),
    ])
    def test_saves_that_were_undefined(self, tags, text, creator, want):
        assert about(tags, text, creator=creator) == want


@pytest.fixture
def conn():
    c = db.connect()
    yield c
    c.close()


def add(conn, n, status="ok", **kw):
    url = f"https://www.tiktok.com/@a/video/{900 + n}"
    item_id, _ = db.upsert_item(conn, {"canonical_url": url, "shared_url": url, "platform": "tiktok",
                                       "resolve_status": status, **kw})
    return item_id


class TestUndefinedCounts:
    def test_only_saves_with_words_to_read(self, conn):
        kept = add(conn, 1, title="Just some information")
        add(conn, 2, status=db.GONE)
        add(conn, 3, status="unresolved")
        add(conn, 4, title="pasta night", tags=["recipe"])
        db.retheme(conn)
        f = explore.Filters(theme=themes.UNDEFINED)
        assert [i["id"] for i in explore.results(conn, f)[0]] == [kept]
        assert explore._with_undefined(conn, explore.Filters(), None).options[0].count == 1


class TestRefiling:
    def stale(self, conn):
        db.set_meta(conn, "themes_version", "an-older-one")
        conn.commit()

    def test_records_what_moved(self, conn):
        found = add(conn, 1, title="Trying the best slice in New York")
        same = add(conn, 2, title="pasta night", tags=["recipe"])
        conn.execute("UPDATE items SET themes = '[]' WHERE id = ?", (found,))
        conn.execute("UPDATE items SET themes = ? WHERE id = ?", (json.dumps(["Food & cooking"]), same))
        self.stale(conn)
        assert db.retheme_if_stale(conn) == 2
        rows = conn.execute("SELECT item_id, was, became FROM theme_changes").fetchall()
        assert [(r["item_id"], json.loads(r["was"]), json.loads(r["became"])) for r in rows] == [
            (found, [], ["New York"])]
        assert db.retheme_if_stale(conn) == 0       # stamped: once per change

    def test_never_from_a_preview(self, conn, monkeypatch):
        monkeypatch.setenv("VERCEL_ENV", "preview")
        self.stale(conn)
        assert db.retheme_if_stale(conn) == 0

    def test_never_undoes_a_newer_faves(self, conn):
        self.stale(conn)
        db.set_meta(conn, "themes_generation", str(themes.GENERATION + 1))
        conn.commit()
        assert db.retheme_if_stale(conn) == 0
        db.set_meta(conn, "themes_generation", str(themes.GENERATION))
        conn.commit()
        assert db.retheme_if_stale(conn) == 0        # nothing to refile, but it ran
        assert db.get_meta(conn, "themes_version") == themes.VERSION

    def test_every_change_to_the_rules_moves_the_generation_on(self):
        # Changed the words or the rules? Add one to GENERATION and put the new
        # VERSION here: an older Faves then can't undo the newer one's work.
        assert (themes.GENERATION, themes.VERSION) == (7, "f6c1a313455f")


class TestThePage:
    def test_what_changed(self, conn, monkeypatch):
        monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
        found = add(conn, 1, title="Trying the best slice in New York")
        lost = add(conn, 2, title="a quiet clip")
        conn.execute("UPDATE items SET themes = '[]' WHERE id = ?", (found,))
        conn.execute("UPDATE items SET themes = ? WHERE id = ?", (json.dumps(["Money & work"]), lost))
        db.set_meta(conn, "themes_version", "an-older-one")
        conn.commit()
        db.retheme_if_stale(conn)
        with TestClient(web.app) as client:
            page = client.get("/topics/changes").text
            assert "The new topic rules moved 2 saves" in page
            assert "Found a topic" in page and "New York</span>" in page
            assert "Lost every topic" in page and "Money &amp; work" in page
            assert f'href="/item/{lost}?rooms=1#rooms"' in page
            assert "The latest topic update moved 2 saves." in client.get("/topics/sort").text


class TestAfterTheFirstRefiling:
    """What the first run over the real library showed (#81's "What changed")."""

    def test_the_new_york_times_is_news_not_new_york(self):
        credit = ("Locals in Little Tokyo are conflicted as they clean up after the protests."
                  " Video by Mimi Dwyer/The New York Times")
        assert about([], credit) == ["News & politics"]
        assert about([], "“A delicious critique of suburbia.” -The New York Times") == ["Food & cooking"]

    @pytest.mark.parametrize("tags, text, want", [
        (["nyc", "travel", "newyork", "visitnyc", "nybucketlist"], "A Hidden Tree House in NYC",
         ["New York", "Travel"]),
        (["greek", "nyc", "foodie"], "Kiki's in Chinatown, their shrimp pasta is also great",
         ["Food & cooking", "New York"]),
        (["foodhack", "foodhacks", "lifehack"], "$3 @Chipotle", ["Food & cooking", "How-to & learning"]),
        (["movies", "funfacts", "tipsandtricks"], "Did you know this secret!?",
         ["How-to & learning", "Film & TV"]),
    ])
    def test_a_pile_of_hashtags_doesnt_drown_a_second_topic(self, tags, text, want):
        assert about(tags, text) == want

    def test_but_your_own_choice_still_does(self):
        ev = themes.weigh(["nyc", "travel"], ["a tree house"], item_id=7,
                          rules=themes.Rules(item_add={7: {"Home & DIY"}}))
        assert themes.decide(ev) == ["Home & DIY"]

    def test_an_everyday_word_loses_a_tie(self):
        text = "Final episode day! Former President Obama and I talk about the podcast"
        assert about(["podcasting"], text) == ["News & politics"]

    @pytest.mark.parametrize("tags, text", [
        (["funnytshirts", "game", "mensfashion"], "I admire your luck, Mr Bond"),
        (["thegameoflove", "nostalgia"], "the summer of 2002"),
    ])
    def test_a_game_hashtag_isnt_gaming(self, tags, text):
        assert "Gaming" not in about(tags, text)

    def test_metaphors(self):
        assert "Sport & fitness" not in about(["brainfitness", "neuroscience"], "Smart drugs")
        assert about(["siberianhuskylove", "mydogismytherapist"], "Kodi is feeling better") == ["Dogs"]

    def test_more_ways_in(self):
        assert themes._tag_hits("howtocutamango")[0] == {"How-to & learning"}
        assert about(["coverletter"], "Don't submit a cover letter until you do this") == ["Money & work"]


class TestAfterTheSecondRefiling:
    """#82's "What changed": 175 saves gained a second or third topic, half of
    them noise from hashtag piles and a few double-meaning tags."""

    HUSKY = ["husky", "siberianhusky", "huskylove", "huskiesofinstagram", "huskygram", "huskies",
             "huskypuppy", "huskylife", "huskyphotography", "dogsofinstagram", "huskybaby", "petsofig"]

    def test_one_stray_tag_in_a_pile_isnt_a_topic(self):
        assert about(self.HUSKY, "Husky sings to Rihanna") == ["Dogs"]
        ev = themes.weigh(self.HUSKY, ["Husky sings"])
        assert {k for k, _, _ in ev["Dogs"]} == {"pile"}

    def test_two_in_a_pile_still_are(self):
        tags = ["photoshop", "photoshoptutorial", "graphicdesign", "graphicdesigner", "art", "adobe",
                "lightroom", "edit", "creative", "reels", "shorts", "fyp"]
        assert "Art & design" in about(tags, "Box labeling in Photoshop")

    def test_a_dog_isnt_also_animals_and_wildlife(self):
        assert about(["pets", "dogs", "siberianhusky"], "Her weakness") == ["Dogs"]
        assert about(["pets", "ducks"], "MAGDA - MY FAMOUS DUCK") == ["Animals & wildlife"]

    def test_but_you_can_still_put_it_there(self):
        ev = themes.weigh(["dogs"], ["a good boy"], item_id=3,
                          rules=themes.Rules(item_add={3: {"Animals & wildlife"}}))
        assert "Animals & wildlife" in themes.decide(ev)

    @pytest.mark.parametrize("tags, text", [
        (["series", "potato", "roastpotatoes"], "All about the Sides, 17 of 50. Roast Potatoes"),
        (["foodtiktok", "vegetable", "pancakes"], "Korean Style Vegetable Pancakes"),
        (["foodtok", "cannellinibeans", "beans"], "Beans beans bean"),
        (["easyrecipes", "noodles", "homecooking"], "Peanut Chilli Noodles"),
    ])
    def test_a_recipe_is_just_food(self, tags, text):
        assert about(tags, text) == ["Food & cooking"]

    def test_a_drawing_sketch_isnt_comedy(self):
        assert "Comedy & humour" not in about(["art", "drawing", "sketch"], "drawing composition")

    def test_a_football_club_isnt_a_city(self):
        assert about(["chelseafc", "mancity", "premierleague", "football"], "Chelsea next season") == [
            "Sport & fitness"]

    def test_the_second_topics_worth_keeping_stay(self):
        assert about(["nyc", "travel", "newyork", "visitnyc"], "A Hidden Tree House in NYC") == [
            "New York", "Travel"]
        assert about(["newyork", "nyc", "datenight", "nycfood", "jazz"], "i love this night") == [
            "New York", "Food & cooking", "Music"]
