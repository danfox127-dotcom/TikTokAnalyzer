"""Captions made readable: headlines and descriptions that end cleanly."""

import pytest

from favorites import blurb

CAPTION = ("Folding dumplings for the party. My grandmother taught me this in 1998 and I still "
           "get it wrong every single time, but that is the fun of it! Next week: soup "
           "#cooking #dumplings #fyp")


def tiktok(caption):
    # TikTok's oEmbed title is the whole caption; resolve.py copies it to the description.
    return {"title": caption, "description": caption, "platform": "tiktok"}


class TestCleaning:
    def test_the_hashtag_pile_goes(self):
        assert blurb.clean_caption("so good #cooking #dumplings #fyp") == "so good."

    def test_a_hashtag_in_a_sentence_keeps_its_word(self):
        assert blurb.clean_caption("the #nyc subway at 3am") == "the nyc subway at 3am."

    def test_instagrams_preview_wrapper_goes(self):
        raw = ('1,204 likes, 31 comments - citydesk on March 3, 2024: "Zoning meeting went '
               'sideways. Here is what happened. #localgov". ')
        assert blurb.clean_caption(raw) == "Zoning meeting went sideways. Here is what happened."
        assert blurb.clean_caption('City Desk on Instagram: "Zoning, again"') == "Zoning, again."

    def test_tiktoks_reply_label_goes(self):
        assert blurb.clean_caption("Replying to @someone yes it really does") == "yes it really does."

    def test_youtube_housekeeping_goes(self):
        raw = "I turn a walnut bowl.\n00:00 intro\n01:20 roughing\nhttps://amzn.to/x\nSubscribe for more!"
        assert blurb.clean_caption(raw) == "I turn a walnut bowl."

    def test_only_hashtags_is_nothing(self):
        assert blurb.clean_caption("#fyp #dogs #goldenretriever") == ""
        assert blurb.clean_caption(None) == ""


class TestTrimming:
    def test_whole_sentences_only(self):
        text = "One short one. Then a second, somewhat longer sentence. And a third."
        assert blurb.trim(text, 40) == "One short one."
        assert blurb.trim(text, 60) == "One short one. Then a second, somewhat longer sentence."

    def test_one_overlong_sentence_stops_at_a_clause_or_a_word(self):
        text = "My grandmother taught me this in 1998, and I still get it wrong every single time"
        assert blurb.trim(text, 60) == "My grandmother taught me this in 1998…"
        cut = blurb.trim("word " * 40, 50)
        assert cut.endswith("word…") and len(cut) <= 51

    def test_an_abbreviation_is_not_the_end(self):
        assert blurb.sentences("Cat vs. cardboard box. Round two.") == ["Cat vs. cardboard box.", "Round two."]
        assert blurb.sentences("Dr. Who at St. Pancras, e.g. today. Yes.") == [
            "Dr. Who at St. Pancras, e.g. today.", "Yes."]

    def test_nothing_is_nothing(self):
        assert blurb.trim("", 50) == ""


class TestLabels:
    def test_the_headline_is_the_first_sentence(self):
        assert blurb.headline(tiktok(CAPTION)) == "Folding dumplings for the party"

    def test_the_blurb_carries_on_from_the_headline(self):
        assert blurb.blurb(tiktok(CAPTION), 160) == (
            "My grandmother taught me this in 1998 and I still get it wrong every single time, "
            "but that is the fun of it! Next week: soup.")
        # The next sentence alone is too long: it stops at its comma.
        assert blurb.blurb(tiktok(CAPTION), 100) == (
            "My grandmother taught me this in 1998 and I still get it wrong every single time…")
        assert blurb.blurb(tiktok("Tiny. A b c."), 100) == "A b c."

    def test_a_real_title_keeps_its_description(self):
        item = {"title": "How I made a wooden bowl", "description": "I turn a walnut bowl. It took a week."}
        assert blurb.headline(item) == "How I made a wooden bowl"
        assert blurb.blurb(item) == "I turn a walnut bowl. It took a week."

    def test_a_caption_of_only_hashtags_is_named_for_its_creator(self):
        item = tiktok("#fyp #dogs") | {"creator_name": "Good Boy Daily"}
        assert blurb.headline(item) == "A save from Good Boy Daily"

    @pytest.mark.parametrize("ending", ["!", "?"])
    def test_a_headline_keeps_a_question_or_a_shout(self, ending):
        assert blurb.headline(tiktok(f"Would you eat this{ending} Honestly")) == f"Would you eat this{ending}"

    def test_a_long_headline_stops_at_a_clause(self):
        head = blurb.headline(tiktok(
            "this is one extraordinarily long single caption about pasta, sauce and the way "
            "my nonna used to make it on sundays in the old house"))
        assert head.endswith("…") and len(head) <= blurb.HEADLINE_CHARS + 1

    def test_its_own_page_gives_the_whole_first_sentence(self):
        item = tiktok("this is one extraordinarily long single caption about pasta, sauce and the way "
                      "my nonna used to make it on sundays in the old house. Recipe below")
        assert blurb.headline(item).endswith("…")
        assert blurb.detail(item).startswith("this is one extraordinarily long single caption")
        assert blurb.detail(item).endswith("Recipe below.")
        assert blurb.detail(tiktok(CAPTION)).startswith("My grandmother")
