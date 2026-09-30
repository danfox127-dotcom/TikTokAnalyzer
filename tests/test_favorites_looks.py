"""Each theme's look: its band colour, icon and emoji."""

from favorites import looks
from favorites.themes import THEMES


def test_every_theme_has_a_look_of_its_own():
    assert set(looks.THEME_LOOK) == set(THEMES)
    for tone, icon, emoji in looks.THEME_LOOK.values():
        assert tone in looks.TONES and icon and emoji


def test_a_theme_not_listed_still_gets_a_steady_colour():
    first = looks.look("Knitting")
    assert first == looks.look("Knitting")          # the same every time
    assert first[0] in looks.TONES and first[1] == "spark"
    assert looks.look(None)[0] in looks.TONES


def test_seasons_each_have_a_look():
    assert set(looks.SEASON_LOOK) == {"winter", "spring", "summer", "autumn"}
