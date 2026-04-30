import pytest

from psychographic import extract_themes


def test_extract_themes_basic():
    titles = [
        "Fun dance challenge #dance",
        "Fun dance duet",
        "Sad song vibes",
        "No Caption (Just Hashtags)",
    ]

    themes = extract_themes(titles)
    assert "top_keywords" in themes
    assert "top_phrases" in themes
    # 'fun' and 'dance' should appear as keywords
    keywords = [k["term"] for k in themes["top_keywords"]]
    assert any("fun" == kw for kw in keywords)
    assert any("dance" == kw for kw in keywords)


def test_hashtags_and_emojis():
    titles = [
        "Party time #party 🎉",
        "Another clip #party",
        "Chill vibes 🎶",
    ]

    themes = extract_themes(titles)
    keywords = [k["term"] for k in themes["top_keywords"]]
    emojis = [e["emoji"] for e in themes["top_emojis"]]
    # hashtag content should appear (without '#')
    assert "party" in keywords
    # emoji tokens should be preserved in their own list
    assert "🎉" in emojis
    assert "🎶" in emojis
