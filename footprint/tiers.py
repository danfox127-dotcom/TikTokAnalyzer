"""The big platforms: checked first, shown first.

Most of what anyone wants from a username search is on a few dozen platforms.
Checking those first means the answer people came for arrives in seconds, and
the long tail of 900 smaller sites fills in behind it.

Hand-picked rather than computed from a traffic ranking: the list is short,
changes rarely, and "where would a creator or a brand plausibly be" is a
judgement, not a statistic. Keys are site domains as :func:`manifest.site_key`
writes them. Order is the order they are checked and shown.
"""

from __future__ import annotations

BIG = (
    # Where creators and brands live
    "tiktok.com", "instagram.com", "youtube.com", "x.com", "facebook.com",
    "threads.com", "bsky.app", "linkedin.com", "reddit.com", "pinterest.com",
    "snapchat.com", "twitch.tv", "kick.com", "tumblr.com", "mastodon.social",
    "t.me", "discord.com", "vimeo.com", "dailymotion.com", "rumble.com",
    # Writing and newsletters
    "substack.com", "medium.com", "wordpress.com", "blogspot.com", "quora.com",
    # Link-in-bio and support pages
    "linktr.ee", "about.me", "patreon.com", "ko-fi.com", "buymeacoffee.com",
    "cash.app", "venmo.com", "paypal.com",
    # Music, art, photography
    "open.spotify.com", "soundcloud.com", "bandcamp.com", "mixcloud.com",
    "behance.net", "dribbble.com", "deviantart.com", "artstation.com",
    "flickr.com", "unsplash.com",
    # Making things
    "github.com", "gitlab.com", "dev.to", "news.ycombinator.com", "etsy.com",
    "gravatar.com", "keybase.io",
    # Hobbies with big public profiles
    "letterboxd.com", "goodreads.com", "strava.com", "chess.com",
    "steamcommunity.com", "roblox.com",
)

_RANK = {key: i for i, key in enumerate(BIG)}


def is_big(key: str) -> bool:
    return key in _RANK


def rank(key: str) -> int:
    """Position among the big platforms; everything else sorts after them."""
    return _RANK.get(key, len(BIG))
