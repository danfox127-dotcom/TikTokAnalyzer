"""Turn a shared link into a catalogue entry.

The share sheet hands us one thing: a URL, often wrapped in a sentence and
usually a redirect. Everything else -- who made it, what it is called, what it
looks like -- has to be recovered from the open web.

Two mechanisms do that, in order:

1. **oEmbed.** A published, no-auth endpoint most platforms still run. It gives
   clean structured fields where it works.
2. **OpenGraph.** The ``<meta property="og:...">`` tags a page serves so that
   chat apps can preview it. Near-universal, and the reason this works on blogs
   and newsletters as well as on video platforms.

What this deliberately does *not* do is download media. That keeps the library
on the right side of every platform's terms, and it is why transcripts are
realistically a YouTube-only feature (see :mod:`favorites.transcript`).

What varies between platforms lives in :mod:`favorites.platforms`, one
descriptor each. This module is about the mechanism, not the catalogue.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from . import platforms
from .platforms import SHORTENERS

logger = logging.getLogger(__name__)

TIMEOUT = 10.0

# A desktop UA. Several platforms serve a stub page to unknown agents, which
# costs us the OpenGraph tags we came for.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

URL_RE = re.compile(r"https?://[^\s<>\"'\]\)]+", re.IGNORECASE)

# Query parameters that identify the sharer or the session rather than the
# content. Stripping them is what makes de-duplication work: the same video
# shared twice arrives with two different `_t` values.
TRACKING_PARAMS = {
    "_t", "_r", "_d", "is_from_webapp", "sender_device", "sender_web_id",
    "web_id", "share_app_id", "share_item_id", "share_link_id", "tt_from",
    "source", "refer", "referer", "referrer", "igshid", "igsh", "img_index",
    "si", "pp", "feature", "app", "ab_channel", "kw", "fbclid", "gclid",
    "mibextid", "share_id", "ref", "ref_src", "ref_url", "s", "t", "cxt",
    "rdt", "share_source", "correlation_id", "post_fullname", "type",
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_name", "utm_id",
}


@dataclass
class Resolved:
    """What we managed to learn about a shared link."""

    canonical_url: str
    shared_url: str
    platform: str = "web"
    external_id: Optional[str] = None
    title: Optional[str] = None
    creator_name: Optional[str] = None
    creator_handle: Optional[str] = None
    creator_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None
    #: "short" for short-form vertical video, "video" when the platform says it
    #: is not, None when nobody knows. Only YouTube serves both today.
    format: Optional[str] = None
    resolve_status: str = "pending"
    resolve_error: Optional[str] = None
    raw: dict = field(default_factory=dict)


def extract_url(text: str) -> Optional[str]:
    """Pull the first URL out of shared text.

    Share sheets rarely hand over a bare link -- TikTok sends the caption and
    the URL together, and most apps prepend a title.
    """
    if not text:
        return None
    match = URL_RE.search(text)
    if match:
        # Trailing punctuation from a sentence is not part of the URL.
        return match.group(0).rstrip(".,;:!?)")
    return None


def detect_platform(url: str) -> str:
    return platforms.for_host(urlparse(url).hostname or "").name


def platform_label(platform: str) -> str:
    known = platforms.BY_NAME.get(platform)
    # Not a registered platform: title-case whatever was stored. This keeps an
    # old row readable after a platform is renamed or removed from the registry.
    return known.label if known else platform.title()


def strip_tracking(url: str) -> str:
    """Drop share-session parameters and normalise the shape of a URL."""
    parts = urlparse(url)
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False)
            if k.lower() not in TRACKING_PARAMS]
    host = (parts.hostname or "").lower().removeprefix("m.").removeprefix("www.")
    host = platforms.for_host(host).host_canonical or host
    path = parts.path.rstrip("/") or "/"
    return urlunparse((
        parts.scheme or "https", host, path, "", urlencode(kept), "",
    ))


def canonical_form(url: str, platform: str) -> tuple[str, Optional[str]]:
    """Return ``(canonical_url, external_id)``.

    The canonical URL is the library's identity for an item: two shares that
    produce the same canonical URL are the same favourite. It is *not*
    necessarily a link anyone can open -- see :func:`browsable_url`.
    """
    cleaned = strip_tracking(url)
    identity = platforms.get(platform).identity
    if identity:
        found = identity(urlparse(cleaned))
        if found:
            return found

    return cleaned, None


def browsable_url(item: dict) -> str:
    """A URL a person can actually open.

    ``canonical_url`` is an identity key, not a link. For TikTok it deliberately
    drops the @handle so that the same video files once whether it arrived from
    an export (handle stripped) or a share sheet (handle present) -- but
    ``tiktok.com/video/<id>`` is not a route TikTok serves, so linking to it
    404s. The two jobs are separate and need separate values, which is why a
    platform descriptor carries both.
    """
    canonical = item.get("canonical_url") or ""
    shared = item.get("shared_url") or ""

    build = platforms.get(item.get("platform") or "web").link
    if not build:
        # This platform's canonical form is already a real, browsable URL, and
        # it is the tidier of the two.
        return canonical or shared

    # The platform rebuilds its own link. Returning None means it could not --
    # the item never resolved -- and the original share link still redirects
    # correctly, which is the best that can be offered.
    return build(item) or shared or canonical


async def expand(url: str, client: httpx.AsyncClient) -> str:
    """Follow a shortener to its destination.

    Only known shortener hosts are followed. Chasing every link would double
    the work and, worse, turn a save into a page view on the creator's analytics.
    """
    host = (urlparse(url).hostname or "").lower()
    if host not in SHORTENERS and not host.removeprefix("www.") in SHORTENERS:
        return url
    for method in ("head", "get"):
        try:
            resp = await getattr(client, method)(
                url, follow_redirects=True, timeout=TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            final = str(resp.url)
            if final and urlparse(final).hostname and urlparse(final).hostname.lower() != host:
                return final
        except Exception as exc:  # network shape varies; a failure just means no expansion
            logger.debug("expanding %s via %s failed: %s", url, method, exc)
    return url


class _MetaReader(HTMLParser):
    """Collect OpenGraph/Twitter meta tags and the ``<title>``.

    Uses the standard library parser rather than a regex or a new dependency;
    real-world HTML has enough malformed markup that a regex is a liability.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag == "title":
            self._in_title = True
            return
        if tag != "meta":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        key = a.get("property") or a.get("name") or a.get("itemprop")
        content = a.get("content")
        if key and content and key.lower() not in self.meta:
            self.meta[key.lower()] = content

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and len(self.title) < 300:
            self.title += data


def _handle_from_url(url: str, platform: str) -> Optional[str]:
    path = urlparse(url or "").path
    m = re.search(r"/@([\w.\-]+)", path)
    if m:
        return "@" + m.group(1)
    from_path = platforms.get(platform).handle
    return from_path(path) if from_path else None


async def _try_oembed(url: str, platform: str, client: httpx.AsyncClient) -> Optional[dict]:
    endpoint = platforms.get(platform).oembed
    if not endpoint:
        return None
    try:
        resp = await client.get(
            endpoint, params={"url": url, "format": "json"},
            timeout=TIMEOUT, headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        if resp.status_code != 200:
            logger.debug("oembed %s returned %s", platform, resp.status_code)
            return None
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.debug("oembed %s failed for %s: %s", platform, url, exc)
        return None


async def _try_opengraph(
    url: str, client: httpx.AsyncClient, user_agent: str = USER_AGENT,
) -> Optional[dict]:
    try:
        resp = await client.get(
            url, timeout=TIMEOUT, follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept-Language": "en;q=0.9"},
        )
        if resp.status_code >= 400:
            return None
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype and ctype:
            return None
        reader = _MetaReader()
        # Only the head matters, and some pages are enormous.
        reader.feed(resp.text[:400_000])
        meta = reader.meta
        if not meta and not reader.title:
            return None
        meta["__title__"] = reader.title.strip()
        return meta
    except Exception as exc:
        logger.debug("opengraph read failed for %s: %s", url, exc)
        return None


def _placeholder_names(platform: str, site_name: Optional[str] = None) -> set[str]:
    """The strings that mean "this is the site, not the thing you asked for"."""
    names = {platform.lower(), platform_label(platform).lower()}
    if site_name:
        names.add(re.sub(r"\s+", " ", site_name).strip().lower())
    return names


# What sits between a page's own title and the site's name: "Foo - YouTube".
_TITLE_SEPARATORS = " -\u2013\u2014|\u00b7:"


def _is_placeholder_title(
    title: Optional[str], platform: str, site_name: Optional[str] = None
) -> bool:
    """True when the only "title" we got is the site telling us its own name.

    A deleted video, a private account or a login wall still answers 200 with a
    perfectly well-formed page whose title is just "TikTok". Treating that as a
    successful resolution produces an item that looks catalogued and describes
    nothing -- and, worse, reports a 100% success rate over a library where a
    seventh of the links are dead.
    """
    if not title:
        return True
    cleaned = re.sub(r"\s+", " ", title).strip().lower()
    # YouTube titles its pages "<video> - YouTube", so an unavailable video's
    # page is titled " - YouTube": the site name with an empty slot in front of
    # it. Stripping stray separators catches that without touching a real title
    # that merely ends in the site name.
    bare = cleaned.strip(_TITLE_SEPARATORS)
    if not bare:
        return True
    names = _placeholder_names(platform, site_name)
    return cleaned in names or bare in names


async def _probe_short_form(
    platform: str, external_id: Optional[str], client: httpx.AsyncClient
) -> Optional[str]:
    """Ask the platform whether this is short-form, where the URL could not say.

    Answers "short" on a 200, "video" on a redirect to the long-form player, and
    None on anything else -- a consent wall, a rate limit, a network error. An
    unknown format costs nothing (the link falls back to the watch URL); a wrong
    one would send you to the wrong player, so ambiguity is never guessed at.
    """
    probe = platforms.get(platform).short_form_probe
    if not probe or not external_id:
        return None
    url = probe(external_id)
    try:
        resp = await client.head(
            url, follow_redirects=False, timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        if resp.status_code == 405:
            resp = await client.get(
                url, follow_redirects=False, timeout=TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
    except Exception as exc:
        logger.debug("short-form probe failed for %s: %s", url, exc)
        return None
    if resp.status_code == 200:
        return "short"
    if resp.is_redirect and "/watch" in resp.headers.get("location", ""):
        return "video"
    return None


def _clean(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    collapsed = re.sub(r"\s+", " ", value).strip()
    return collapsed or None


async def resolve(shared: str, client: httpx.AsyncClient) -> Resolved:
    """Resolve a shared link as far as the open web allows.

    Never raises. A link that resolves to nothing is still worth keeping --
    the URL and your own note are the irreplaceable parts.
    """
    raw_url = extract_url(shared) or (shared or "").strip()
    if not raw_url:
        return Resolved(canonical_url="", shared_url=shared or "",
                        resolve_status="failed", resolve_error="no URL found in shared text")

    expanded = await expand(raw_url, client)
    platform = detect_platform(expanded)
    canonical, external_id = canonical_form(expanded, platform)

    from_url = platforms.get(platform).format_from_url
    item = Resolved(
        canonical_url=canonical,
        shared_url=raw_url,
        platform=platform,
        external_id=external_id,
        creator_handle=_handle_from_url(canonical, platform),
        # Read from the URL as shared, not the canonical form -- canonicalising
        # a /shorts/ link to watch?v= is exactly what erases the evidence.
        format=from_url(urlparse(strip_tracking(expanded))) if from_url else None,
    )

    data = await _try_oembed(canonical, platform, client)
    if data:
        item.title = _clean(data.get("title"))
        item.creator_name = _clean(data.get("author_name"))
        item.creator_url = _clean(data.get("author_url"))
        handle = data.get("author_unique_id")
        if handle:
            item.creator_handle = "@" + str(handle).lstrip("@")
        elif item.creator_url:
            item.creator_handle = _handle_from_url(item.creator_url, platform) or item.creator_handle
        item.thumbnail_url = _clean(data.get("thumbnail_url"))
        item.raw["oembed"] = data
        item.resolve_status = "ok"

    meta = None
    if item.resolve_status != "ok" or not item.thumbnail_url or not item.title:
        meta = await _try_opengraph(
            canonical, client, platforms.get(platform).preview_agent or USER_AGENT)
    if meta:
        item.title = item.title or _clean(meta.get("og:title") or meta.get("twitter:title") or meta.get("__title__"))
        item.description = _clean(meta.get("og:description") or meta.get("twitter:description") or meta.get("description"))
        item.thumbnail_url = item.thumbnail_url or _clean(meta.get("og:image") or meta.get("twitter:image"))
        item.creator_name = item.creator_name or _clean(
            meta.get("author") or meta.get("article:author") or meta.get("og:site_name")
        )
        item.raw["opengraph"] = {k: v for k, v in meta.items() if not k.startswith("__")}
        item.resolve_status = "ok"

    site_name = (meta or {}).get("og:site_name")
    if _is_placeholder_title(item.title, platform, site_name):
        item.title = None
        # og:site_name doubles as a weak creator fallback above. When the title
        # was only the site's own name, a creator taken from the same place is
        # just as hollow -- together they would pass the check below while
        # telling us nothing about the item.
        hollow = _placeholder_names(platform, site_name)
        if (item.creator_name or "").strip().lower() in hollow:
            item.creator_name = None

    # A resolution has to have produced something that actually identifies the
    # item. A bare placeholder title is not that, and neither is nothing at all.
    if not item.title and not (item.creator_name or item.creator_handle):
        item.resolve_status = "unresolved"
        item.resolve_error = item.resolve_error or "only placeholder metadata available"

    # Where the oEmbed "title" is the whole caption it is both the label and
    # the body text. Keeping it in one field loses the hashtags to truncation.
    if platforms.get(platform).caption_is_title and item.title and not item.description:
        item.description = item.title

    if item.resolve_status != "ok":
        item.resolve_status = "unresolved"
        item.resolve_error = item.resolve_error or "no oEmbed or OpenGraph metadata available"
        item.title = item.title or canonical
    elif item.format is None:
        # Only for items that resolved: asking whether a deleted video is a
        # Short spends a request to learn nothing.
        item.format = await _probe_short_form(platform, external_id, client)

    return item
