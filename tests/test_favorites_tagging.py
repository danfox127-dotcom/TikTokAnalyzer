"""Working out what a save is about, without a model."""

from favorites import tagging


class TestHashtags:
    def test_lifted_from_a_caption(self):
        tags = tagging.hashtags("the zoning meeting #localgov #Housing #policy")
        assert tags == ["localgov", "housing", "policy"]

    def test_distribution_tags_are_dropped(self):
        # Without this every short-form save collapses into one "fyp" theme.
        assert tagging.hashtags("#fyp #viral #housing #foryoupage") == ["housing"]

    def test_decorated_spellings_of_fyp_are_noise_too(self):
        # #fypシ was the second most common unthemed hashtag in a real library.
        assert tagging.hashtags("#fypシ #fypage #foryoupageofficial #zoning") == ["zoning"]
        assert tagging.is_noise("#FYPシ") and not tagging.is_noise("zoning")
        # TikTok's label for videos made from its search suggestions.
        assert tagging.is_noise("creatorsearchinsights")

    def test_duplicates_collapse(self):
        assert tagging.hashtags("#housing", "#Housing") == ["housing"]

    def test_numeric_only_tags_are_not_tags(self):
        assert tagging.hashtags("#2026 #housing") == ["housing"]


class TestTerms:
    def test_function_words_are_removed(self):
        terms = tagging.terms("the council voted on the new zoning code")
        assert "the" not in terms and "on" not in terms
        assert "council" in terms

    def test_phrases_are_kept(self):
        # "local government" is a subject; "local" and "government" apart are
        # noise that collides with unrelated saves.
        terms = tagging.terms("local government budgets", limit=30)
        assert "local government" in terms

    def test_a_stopword_breaks_a_phrase(self):
        terms = tagging.terms("housing in cities", limit=30)
        assert "housing cities" not in terms

    def test_phrases_outrank_their_parts_at_equal_frequency(self):
        terms = tagging.terms("climate policy", limit=5)
        assert terms[0] == "climate policy"


class TestEnrich:
    def test_note_and_caption_both_feed_the_index(self):
        tags, terms = tagging.enrich(
            title="zoning meeting #localgov",
            description="council voted on the rewrite",
            note="useful for the housing newsletter",
        )
        assert tags == ["localgov"]
        assert "newsletter" in terms
        assert "council" in terms

    def test_a_term_that_only_repeats_a_hashtag_is_dropped(self):
        tags, terms = tagging.enrich(description="#housing housing housing")
        assert tags == ["housing"]
        assert "housing" not in terms

    def test_a_phrase_made_only_of_hashtags_is_dropped(self):
        # "#localgov #housing" sits adjacent in the caption and would otherwise
        # yield "localgov housing" as a phrase alongside both hashtags.
        tags, terms = tagging.enrich(description="the meeting #localgov #housing")
        assert tags == ["localgov", "housing"]
        assert "localgov housing" not in terms

    def test_nothing_in_nothing_out(self):
        assert tagging.enrich() == ([], [])


class TestCollectionThemes:
    def test_a_theme_needs_more_than_one_item(self):
        items = [
            {"tags": ["housing"], "terms": []},
            {"tags": ["housing"], "terms": []},
            {"tags": ["baking"], "terms": []},
        ]
        themes = dict(tagging.collection_themes(items, min_items=2))
        assert themes == {"housing": 2}

    def test_counted_by_item_not_by_mention(self):
        # One chatty transcript must not be able to invent a theme alone.
        items = [{"tags": ["housing", "housing", "housing"], "terms": ["housing"]}]
        assert tagging.collection_themes(items, min_items=2) == []

    def test_a_phrase_suppresses_its_component_words(self):
        items = [{"tags": [], "terms": ["local government", "local", "government"]}] * 3
        themes = [t for t, _ in tagging.collection_themes(items, min_items=2)]
        assert themes == ["local government"]
