"""What the library knows about each platform, in one place per platform.

Platform knowledge used to live in nine separate branch points scattered across
two modules: a host table, an oEmbed table, a label table, and if-chains inside
canonicalisation, link building, handle extraction, URL normalisation and
resolution. Adding a platform meant finding all nine.

It also caused a bug. TikTok's identity rule changed in one branch and the link
builder had its own TikTok branch that no longer agreed, so every link in a real
library 404'd. Two functions, same platform, same file, required to stay in
sync, with nothing holding them together.

A :class:`Platform` holds all of it, so the pieces that have to agree sit in one
object. Adding a platform is writing a descriptor.

Some of what varies is genuinely behavioural rather than parametric -- YouTube
takes an id from a query parameter *or* one of several path shapes, Instagram
normalises ``reels`` to ``reel`` -- so those fields are small named functions
defined beside the descriptor, not regex strings. Forcing them into data would
be a worse abstraction, not a better one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import ParseResult, parse_qsl

# Identity: the parsed, tracking-stripped URL -> (canonical_url, external_id).
# Returning None means "no platform-specific identity"; the cleaned URL is used.
Identity = Callable[[ParseResult], Optional[tuple[str, str]]]

# Link: a stored item -> a URL a person can open, or None to use the default.
Link = Callable[[dict], Optional[str]]

# Handle: a URL path -> a display handle, beyond the generic "/@name" rule.
Handle = Callable[[str], Optional[str]]

# Format: the parsed URL -> "short" when the URL itself proves the item is
# short-form vertical video, else None. None means "unknown", never "long".
Format = Callable[[ParseResult], Optional[str]]

# Probe: an external id -> a URL that answers 200 only if the item is
# short-form, and redirects otherwise. Used when the URL alone cannot tell.
Probe = Callable[[str], str]


@dataclass(frozen=True)
class Platform:
    name: str
    label: str

    #: Hosts that belong to this platform. Matched exactly or as a suffix.
    hosts: tuple[str, ...] = ()

    #: Redirect-only hosts this platform owns. Followed on the way in.
    shorteners: tuple[str, ...] = ()

    #: No-auth oEmbed endpoint, where one exists.
    oembed: Optional[str] = None

    #: Host every URL of this platform normalises to, if it has several.
    host_canonical: Optional[str] = None

    identity: Optional[Identity] = None
    link: Optional[Link] = None
    handle: Optional[Handle] = None

    #: How to tell short-form vertical video from the URL, and how to ask the
    #: platform when the URL is silent. Only matters where one platform serves
    #: both -- YouTube does, TikTok does not.
    format_from_url: Optional[Format] = None
    short_form_probe: Optional[Probe] = None

    #: Whether captions are obtainable for this platform (see transcript.py).
    transcripts: bool = False

    #: The oEmbed "title" is the item's whole caption, not a headline. Keeping
    #: it only in the title field loses the tail of it to truncation.
    caption_is_title: bool = False


# --- identity rules ---------------------------------------------------------

def _tiktok_identity(parts: ParseResult) -> Optional[tuple[str, str]]:
    # Identity is the video id alone -- deliberately NOT the @handle. A data
    # export strips the handle while a share sheet includes it, so keying on it
    # would file the same video twice depending on how it arrived. The handle is
    # an attribute of the item, not its name.
    vid = re.search(r"/video/(\d+)", parts.path) or re.search(r"/photo/(\d+)", parts.path)
    if not vid:
        return None
    return f"https://www.tiktok.com/video/{vid.group(1)}", vid.group(1)


def _youtube_identity(parts: ParseResult) -> Optional[tuple[str, str]]:
    vid = dict(parse_qsl(parts.query)).get("v")
    if not vid:
        m = re.search(r"/(?:shorts|embed|live|v)/([\w\-]{6,})", parts.path)
        vid = m.group(1) if m else None
        if not vid and parts.hostname == "youtu.be":
            vid = parts.path.lstrip("/") or None
    if not vid:
        return None
    return f"https://www.youtube.com/watch?v={vid}", vid


def _youtube_format(parts: ParseResult) -> Optional[str]:
    # A /shorts/ URL proves it. A watch?v= URL proves nothing: every Short also
    # plays at watch?v=, so a Short shared from a desktop arrives looking long.
    return "short" if parts.path.startswith("/shorts/") else None


def _youtube_short_probe(video_id: str) -> str:
    # /shorts/<id> serves a Short and redirects anything else to /watch.
    return f"https://www.youtube.com/shorts/{video_id}"


def _instagram_identity(parts: ParseResult) -> Optional[tuple[str, str]]:
    m = re.search(r"/(p|reel|reels|tv)/([\w\-]+)", parts.path)
    if not m:
        return None
    kind = "reel" if m.group(1) in {"reel", "reels"} else m.group(1)
    return f"https://www.instagram.com/{kind}/{m.group(2)}", m.group(2)


def _instagram_format(parts: ParseResult) -> Optional[str]:
    # A reel is short-form vertical video; a /p/ post may be a photo, a
    # carousel or a video, so it says nothing either way.
    return "short" if parts.path.startswith(("/reel/", "/reels/")) else None


def _x_identity(parts: ParseResult) -> Optional[tuple[str, str]]:
    m = re.search(r"/([\w]+)/status/(\d+)", parts.path)
    if not m:
        return None
    return f"https://x.com/{m.group(1)}/status/{m.group(2)}", m.group(2)


# --- link rules -------------------------------------------------------------

def _tiktok_link(item: dict) -> Optional[str]:
    """Rebuild the real URL, because TikTok's identity is not browsable.

    ``tiktok.com/video/<id>`` is not a route TikTok serves. Returning None here
    falls through to the default, which is the URL the item arrived as -- an
    export's share link still redirects correctly.
    """
    handle = (item.get("creator_handle") or "").lstrip("@").strip()
    external_id = (item.get("external_id") or "").strip()
    if handle and external_id:
        return f"https://www.tiktok.com/@{handle}/video/{external_id}"
    return None


def _youtube_link(item: dict) -> Optional[str]:
    """Open a Short in the Shorts player; everything else at its watch URL.

    The identity is ``watch?v=<id>`` for both, so a Short shared from the
    Shorts player and from a desktop files once. But a Short opened at
    ``watch?v=`` plays in the landscape player, letterboxed, with none of the
    vertical feed around it -- a worse way to see the thing you kept.
    """
    external_id = (item.get("external_id") or "").strip()
    if item.get("format") == "short" and external_id:
        return f"https://www.youtube.com/shorts/{external_id}"
    return item.get("canonical_url") or None


# --- handle rules -----------------------------------------------------------

def _x_handle(path: str) -> Optional[str]:
    m = re.search(r"^/([\w]+)/status/", path)
    return "@" + m.group(1) if m else None


def _reddit_handle(path: str) -> Optional[str]:
    m = re.search(r"/r/([\w]+)", path)
    return "r/" + m.group(1) if m else None


# --- the registry -----------------------------------------------------------

#: Instagram and X have no entry here on purpose: both now require an app token
#: for oEmbed, so their links fall through to the OpenGraph reader rather than
#: failing on a 401.
PLATFORMS: tuple[Platform, ...] = (
    Platform(
        name="tiktok", label="TikTok",
        # Data-export links are served from tiktokv.com, not tiktok.com.
        # Without it an imported favourite is filed as a generic web page and
        # its video id is never extracted.
        hosts=("tiktok.com", "tiktokv.com"),
        shorteners=("vm.tiktok.com", "vt.tiktok.com", "m.tiktok.com"),
        oembed="https://www.tiktok.com/oembed",
        host_canonical="www.tiktok.com",
        identity=_tiktok_identity, link=_tiktok_link,
        caption_is_title=True,
    ),
    Platform(
        name="youtube", label="YouTube",
        hosts=("youtube.com", "youtu.be"), shorteners=("youtu.be",),
        oembed="https://www.youtube.com/oembed",
        identity=_youtube_identity, link=_youtube_link, transcripts=True,
        format_from_url=_youtube_format, short_form_probe=_youtube_short_probe,
    ),
    Platform(
        name="instagram", label="Instagram",
        hosts=("instagram.com",), identity=_instagram_identity,
        format_from_url=_instagram_format,
    ),
    Platform(
        name="reddit", label="Reddit",
        hosts=("reddit.com", "redd.it"), shorteners=("redd.it",),
        oembed="https://www.reddit.com/oembed", handle=_reddit_handle,
    ),
    Platform(
        name="x", label="X",
        hosts=("twitter.com", "x.com"), identity=_x_identity, handle=_x_handle,
    ),
    Platform(name="bluesky", label="Bluesky", hosts=("bsky.app",),
             oembed="https://embed.bsky.app/oembed"),
    Platform(name="threads", label="Threads", hosts=("threads.net", "threads.com")),
    Platform(name="vimeo", label="Vimeo", hosts=("vimeo.com",),
             oembed="https://vimeo.com/api/oembed.json"),
    Platform(name="soundcloud", label="SoundCloud", hosts=("soundcloud.com",),
             shorteners=("on.soundcloud.com",),
             oembed="https://soundcloud.com/oembed"),
    Platform(name="spotify", label="Spotify", hosts=("open.spotify.com",),
             shorteners=("spotify.link",),
             oembed="https://open.spotify.com/oembed"),
    Platform(name="pinterest", label="Pinterest", hosts=("pinterest.com",),
             oembed="https://www.pinterest.com/oembed.json"),
    Platform(name="linkedin", label="LinkedIn", hosts=("linkedin.com",)),
    Platform(name="substack", label="Substack", hosts=("substack.com",)),
    Platform(name="mastodon", label="Mastodon", hosts=("mastodon.social",)),
    Platform(name="tumblr", label="Tumblr", hosts=("tumblr.com",)),
)

#: Anything else: a blog, a newsletter, a news site. OpenGraph carries these.
WEB = Platform(name="web", label="Web")

BY_NAME: dict[str, Platform] = {p.name: p for p in PLATFORMS}
BY_NAME[WEB.name] = WEB

#: (host, platform) in declaration order, so host matching stays predictable.
HOST_TABLE: tuple[tuple[str, Platform], ...] = tuple(
    (host, p) for p in PLATFORMS for host in p.hosts
)

#: Link shorteners owned by no particular platform.
GENERIC_SHORTENERS = frozenset({
    "t.co", "bit.ly", "tinyurl.com", "buff.ly", "dlvr.it", "trib.al",
    "lnkd.in", "flip.it", "a.co",
})

SHORTENERS = GENERIC_SHORTENERS | {
    host for p in PLATFORMS for host in p.shorteners
}


def for_host(host: str) -> Platform:
    """The platform owning a hostname, or :data:`WEB`."""
    host = (host or "").lower().removeprefix("www.")
    for needle, platform in HOST_TABLE:
        if host == needle or host.endswith("." + needle):
            return platform
    return WEB


def get(name: str) -> Platform:
    """The platform with this name, or :data:`WEB` for anything unrecognised."""
    return BY_NAME.get(name, WEB)
