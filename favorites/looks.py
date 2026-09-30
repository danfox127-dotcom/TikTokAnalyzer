"""How each theme and season looks: its band colour, its icon, its emoji.

The museum's sections are bands in six candy tones, and every room (theme)
belongs to one of them, so a theme wears the same colour on its door, its
pills and its slides. Kept in step with the "Favorites Museum" design system.
"""

from __future__ import annotations

import zlib

# The order the bands rotate in, down a page.
TONES = ("sky", "mint", "butter", "peach", "pink", "lilac")

# theme -> (tone, icon, emoji). Icons are names in templates/_icons.html.
THEME_LOOK: dict[str, tuple[str, str, str]] = {
    "Dogs": ("peach", "paw", "🐶"),
    "Cats": ("peach", "paw", "🐱"),
    "Animals & wildlife": ("peach", "paw", "🦊"),
    "Home & DIY": ("peach", "home", "🏡"),
    "Parenting & family": ("peach", "home", "🧸"),
    "Food & cooking": ("butter", "bowl", "🍝"),
    "Drinks": ("butter", "bowl", "☕"),
    "Comedy & humour": ("butter", "laugh", "😂"),
    "Satisfying & ASMR": ("butter", "laugh", "🫧"),
    "Music": ("pink", "note2", "🎵"),
    "Dance": ("pink", "note2", "💃"),
    "Art & design": ("pink", "brush", "🎨"),
    "Fashion & beauty": ("pink", "brush", "💄"),
    "Photography & editing": ("pink", "brush", "📷"),
    "Books & writing": ("lilac", "book", "📚"),
    "History": ("lilac", "column", "🏛️"),
    "Film & TV": ("lilac", "spark", "🎬"),
    "Language": ("lilac", "book", "🗣️"),
    "Nostalgia & retro": ("lilac", "spark", "📼"),
    "Gaming": ("lilac", "spark", "🎮"),
    "Cities & urbanism": ("sky", "city", "🏙️"),
    "New York": ("sky", "city", "🗽"),
    "Science & tech": ("sky", "spark", "🔭"),
    "Travel": ("sky", "city", "✈️"),
    "News & politics": ("sky", "column", "📰"),
    "Money & work": ("sky", "spark", "💼"),
    "Marketing & media": ("sky", "spark", "📣"),
    "Cars & vehicles": ("sky", "city", "🚗"),
    "How-to & learning": ("sky", "book", "💡"),
    "Nature & outdoors": ("mint", "plant", "🌲"),
    "Gardening & plants": ("mint", "plant", "🪴"),
    "Wellness": ("mint", "plant", "🌿"),
    "Sport & fitness": ("mint", "spark", "🏃"),
}

SEASON_LOOK: dict[str, tuple[str, str, str]] = {
    "winter": ("sky", "snow", "❄️"),
    "spring": ("mint", "bud", "🌷"),
    "summer": ("butter", "sun", "☀️"),
    "autumn": ("peach", "leaf", "🍂"),
}


def look(theme: str | None) -> tuple[str, str, str]:
    """(tone, icon, emoji) for a theme. A theme not listed gets a tone picked
    from its name -- the same one every time -- and the plain spark icon."""
    if theme and theme in THEME_LOOK:
        return THEME_LOOK[theme]
    tone = TONES[zlib.crc32((theme or "").encode()) % len(TONES)]
    return (tone, "spark", "✨")


def shape(item) -> str:
    """The shape a save's picture keeps on a salon wall: its media's own.

    Vertical video stands tall (3:4), a long-form video or a web page lies
    wide (16:10), an Instagram post is square. Carousels ignore this and crop
    everything to 3:4 so a row stays even to swipe.
    """
    get = item.get if hasattr(item, "get") else (lambda k: item[k])
    platform, fmt = get("platform"), get("format")
    if platform == "tiktok" or fmt == "short":
        return "tall"
    if platform == "instagram":
        return "square"
    return "wide"
