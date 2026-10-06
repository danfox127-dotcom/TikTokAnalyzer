"""What a found account's public profile says about itself.

Public details only. Footprint never signs in and never works around a login
wall: when a platform shows a profile only to signed-in visitors, the profile
is marked *hidden by the platform* and left at that.

Two ways in, in order:

1. **Open public endpoints** a few platforms run for anyone -- GitHub, GitLab,
   Bluesky, Mastodon, Reddit -- and the data TikTok embeds in its own page.
   These give the richest fields, including a self-reported location and the
   times of recent public posts (which :mod:`footprint.timezone` turns into a
   time-zone hint).
2. **OpenGraph tags**, the preview data almost every page serves to chat
   apps: a name, a description and a picture. Read with the same parser Faves
   uses (:func:`favorites.resolve.parse_meta`).

Every field records where it came from, so a verdict built on it can say so.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional
from urllib.parse import quote, urlparse

import httpx

from favorites.resolve import parse_meta

from .manifest import USER_AGENT

logger = logging.getLogger(__name__)

TIMEOUT = 8.0

# Mastodon servers share one API. These are the large ones the site lists know.
MASTODON = {"mastodon.social", "mastodon.online", "mstdn.social", "mas.to", "fosstodon.org",
            "hachyderm.io", "infosec.exchange", "techhub.social", "mastodon.world",
            "mastodon.cloud", "mstdn.io", "mastodon.xyz"}

LOGIN_WALL = re.compile(r"/(accounts/)?(login|signin|sign_in|auth)\b", re.I)

# Links in a bio: full addresses; bare ones with a path (brand.coffee/shop);
# and bare domains on common endings (marisol.kitchen would be missed, but
# "e.g." and "i.e." aren't taken for links).
URL_RE = re.compile(
    r"(?:https?://[^\s<>\"'()]+)"
    r"|(?:(?<![@\w.-])(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,24}/[^\s<>\"'()]*)"
    r"|(?:(?<![@\w.-])(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\."
    r"(?:com|net|org|io|co|ee|me|app|dev|ly|link|bio|page|xyz|uk|us|ca|de|fr|au|tv|gg|fm|so|ai|"
    r"studio|shop|store|blog|social)\b(?![.@\w]))",
    re.I,
)


@dataclass
class Profile:
    site: str
    name: str
    username: str
    url: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    links: list[str] = field(default_factory=list)
    location: Optional[str] = None
    created_at: Optional[str] = None
    last_active: Optional[str] = None
    post_times: list[str] = field(default_factory=list)  # ISO 8601, UTC
    sources: dict[str, str] = field(default_factory=dict)
    hidden: bool = False
    note: Optional[str] = None
    # Filled in by footprint.match.fingerprint
    photo_hash: Optional[str] = None
    photo_thumb: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def set(self, key: str, value, source: str) -> None:
        """Fill a field if it is still empty, remembering where the value came from."""
        if value in (None, "", []) or getattr(self, key) not in (None, "", []):
            return
        setattr(self, key, value)
        self.sources[key] = source

    def add_links(self, links, source: str) -> None:
        for link in links:
            link = _clean_link(link)
            if link and link not in self.links:
                self.links.append(link)
                self.sources.setdefault("links", source)


# ---------------------------------------------------------------- helpers --

def _clean_link(link: Optional[str]) -> Optional[str]:
    if not link:
        return None
    link = link.strip().rstrip(".,;:!)")
    if not link:
        return None
    if not re.match(r"^https?://", link, re.I):
        link = "https://" + link
    return link


def links_in(text: Optional[str]) -> list[str]:
    return [m.group(0) for m in URL_RE.finditer(text or "")]


def strip_html(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    text = re.sub(r"<br\s*/?>|</p>\s*<p>", "\n", text, flags=re.I)
    return html_lib.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def hrefs(text: Optional[str]) -> list[str]:
    return [html_lib.unescape(h) for h in re.findall(r'href="([^"]+)"', text or "")]


def iso(value) -> Optional[str]:
    """Any timestamp (ISO text or Unix seconds) as ISO 8601 in UTC."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def clean_title(title: Optional[str], site_name: str, username: str) -> Optional[str]:
    """``Marisol Cooks (@marisol.cooks) • Instagram photos and videos`` -> ``Marisol Cooks``."""
    if not title:
        return None
    t = html_lib.unescape(title).strip()
    t = re.split(r"\s+(?:\||•|·|–|—|-)\s+", t)[0]
    t = re.sub(r"\s*\((?:@)?" + re.escape(username) + r"\)\s*", " ", t, flags=re.I)
    t = re.sub(r"\s*\(@[^)]*\)\s*", " ", t).strip(" @")
    if not t or t.lower() in {site_name.lower(), "profile", "user", "login", "log in"}:
        return None
    return t


async def _get_json(client: httpx.AsyncClient, url: str, **params):
    resp = await client.get(url, params=params or None, timeout=TIMEOUT, follow_redirects=True,
                            headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    if resp.status_code != 200:
        return None
    return resp.json()


# ------------------------------------------------------- open endpoints --

async def _github(p: Profile, client: httpx.AsyncClient) -> None:
    src = "GitHub's public API"
    data = await _get_json(client, f"https://api.github.com/users/{quote(p.username)}")
    if not isinstance(data, dict):
        return
    p.set("display_name", data.get("name"), src)
    p.set("bio", data.get("bio"), src)
    p.set("avatar_url", data.get("avatar_url"), src)
    p.set("location", data.get("location"), src)
    p.set("created_at", iso(data.get("created_at")), src)
    p.add_links([data.get("blog")] + links_in(data.get("bio")), src)
    if data.get("twitter_username"):
        p.add_links([f"https://x.com/{data['twitter_username']}"], src)
    socials = await _get_json(client, f"https://api.github.com/users/{quote(p.username)}/social_accounts")
    if isinstance(socials, list):
        p.add_links([s.get("url") for s in socials if isinstance(s, dict)], src)
    events = await _get_json(client, f"https://api.github.com/users/{quote(p.username)}/events/public",
                             per_page=100)
    if isinstance(events, list):
        p.post_times = [t for t in (iso(e.get("created_at")) for e in events) if t]


async def _gitlab(p: Profile, client: httpx.AsyncClient) -> None:
    src = "GitLab's public API"
    found = await _get_json(client, "https://gitlab.com/api/v4/users", username=p.username)
    if not (isinstance(found, list) and found):
        return
    data = await _get_json(client, f"https://gitlab.com/api/v4/users/{found[0]['id']}") or found[0]
    p.set("display_name", data.get("name"), src)
    p.set("bio", data.get("bio"), src)
    p.set("avatar_url", data.get("avatar_url"), src)
    p.set("location", data.get("location"), src)
    p.set("created_at", iso(data.get("created_at")), src)
    p.add_links([data.get("website_url")] + links_in(data.get("bio")), src)


async def _bluesky(p: Profile, client: httpx.AsyncClient) -> None:
    src = "Bluesky's public API"
    actor = urlparse(p.url).path.rstrip("/").split("/")[-1] or p.username
    base = "https://public.api.bsky.app/xrpc"
    data = await _get_json(client, f"{base}/app.bsky.actor.getProfile", actor=actor)
    if not isinstance(data, dict):
        return
    p.set("display_name", data.get("displayName"), src)
    p.set("bio", data.get("description"), src)
    p.set("avatar_url", data.get("avatar"), src)
    p.set("created_at", iso(data.get("createdAt")), src)
    p.add_links(links_in(data.get("description")), src)
    feed = await _get_json(client, f"{base}/app.bsky.feed.getAuthorFeed", actor=actor, limit=100,
                           filter="posts_no_replies")
    if isinstance(feed, dict):
        times = [iso(((item.get("post") or {}).get("record") or {}).get("createdAt"))
                 for item in feed.get("feed", []) if not item.get("reason")]
        p.post_times = [t for t in times if t]


async def _mastodon(p: Profile, client: httpx.AsyncClient) -> None:
    host = urlparse(p.url).hostname
    src = f"{host}'s public API"
    data = await _get_json(client, f"https://{host}/api/v1/accounts/lookup", acct=p.username)
    if not isinstance(data, dict):
        return
    p.set("display_name", data.get("display_name"), src)
    p.set("bio", strip_html(data.get("note")), src)
    p.set("avatar_url", data.get("avatar"), src)
    p.set("created_at", iso(data.get("created_at")), src)
    p.add_links(hrefs(data.get("note")), src)
    for f in data.get("fields") or []:
        value = f.get("value") or ""
        p.add_links(hrefs(value), src)
        if re.search(r"location|based|where|city|lives", f.get("name") or "", re.I):
            p.set("location", strip_html(value), src)
    statuses = await _get_json(client, f"https://{host}/api/v1/accounts/{data.get('id')}/statuses",
                               limit=40)
    if isinstance(statuses, list):
        p.post_times = [t for t in (iso(s.get("created_at")) for s in statuses) if t]


async def _reddit(p: Profile, client: httpx.AsyncClient) -> None:
    src = "Reddit's public JSON"
    about = await _get_json(client, f"https://www.reddit.com/user/{quote(p.username)}/about.json")
    data = (about or {}).get("data") if isinstance(about, dict) else None
    if not isinstance(data, dict):
        return
    sub = data.get("subreddit") or {}
    p.set("display_name", sub.get("title"), src)
    p.set("bio", sub.get("public_description"), src)
    p.set("avatar_url", html_lib.unescape(data.get("snoovatar_img") or data.get("icon_img") or "")
          .split("?")[0] or None, src)
    p.set("created_at", iso(data.get("created_utc")), src)
    p.add_links(links_in(sub.get("public_description")), src)
    times = []
    for kind in ("submitted", "comments"):
        listing = await _get_json(client, f"https://www.reddit.com/user/{quote(p.username)}/{kind}.json",
                                  limit=100)
        for child in ((listing or {}).get("data") or {}).get("children", []) if isinstance(listing, dict) else []:
            times.append(iso((child.get("data") or {}).get("created_utc")))
    p.post_times = [t for t in times if t]


TIKTOK_DATA = re.compile(
    r'<script[^>]+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', re.S)


def tiktok_user(page: str) -> Optional[dict]:
    """The user record TikTok embeds in its own profile page, if it is there."""
    m = TIKTOK_DATA.search(page)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        info = data["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]
        return info.get("user") or None
    except (ValueError, KeyError, TypeError):
        return None


EXTRACTORS: dict[str, Callable[[Profile, httpx.AsyncClient], Awaitable[None]]] = {
    "github.com": _github,
    "gitlab.com": _gitlab,
    "bsky.app": _bluesky,
    "reddit.com": _reddit,
    **{host: _mastodon for host in MASTODON},
}


# ------------------------------------------------------------ the page --

async def _page(p: Profile, client: httpx.AsyncClient) -> None:
    """OpenGraph tags from the profile page itself (and TikTok's embedded data)."""
    resp = await client.get(p.url, timeout=TIMEOUT, follow_redirects=True,
                            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    final = str(resp.url)
    if resp.status_code in (401, 403) or LOGIN_WALL.search(urlparse(final).path):
        if not (p.display_name or p.bio or p.avatar_url):
            p.hidden = True
            p.note = "The platform only shows this profile to signed-in visitors"
        return
    if resp.status_code >= 400 or "html" not in resp.headers.get("content-type", "html"):
        return
    page = resp.text
    if p.site == "tiktok.com":
        user = tiktok_user(page)
        if user:
            src = "TikTok's page data"
            p.set("display_name", user.get("nickname"), src)
            p.set("bio", user.get("signature"), src)
            p.set("avatar_url", user.get("avatarLarger") or user.get("avatarMedium"), src)
            p.set("created_at", iso(user.get("createTime")), src)
            p.add_links([(user.get("bioLink") or {}).get("link")] + links_in(user.get("signature")), src)
    meta, title = parse_meta(page)
    src = "the profile page's preview tags"
    p.set("display_name", clean_title(meta.get("og:title") or meta.get("twitter:title") or title,
                                      p.name, p.username), src)
    bio = meta.get("og:description") or meta.get("twitter:description") or meta.get("description")
    p.set("bio", html_lib.unescape(bio) if bio else None, src)
    p.set("avatar_url", meta.get("og:image") or meta.get("twitter:image"), src)
    p.add_links(links_in(bio), src)


async def fetch(site: str, name: str, username: str, url: str, client: httpx.AsyncClient) -> Profile:
    """Everything public we can learn about one found account."""
    p = Profile(site=site, name=name, username=username, url=url)
    extractor = EXTRACTORS.get(site)
    for step in ([extractor] if extractor else []) + [_page]:
        try:
            await step(p, client)
        except Exception as exc:  # a profile is a bonus; a failure just means fewer details
            logger.debug("profile step %s failed for %s: %s", step.__name__, url, exc)
        if p.hidden:
            break
    if p.post_times:
        p.last_active = max(p.post_times)
        p.sources["post_times"] = f"{len(p.post_times)} public posts"
        p.sources["last_active"] = "its most recent public post"
    return p
