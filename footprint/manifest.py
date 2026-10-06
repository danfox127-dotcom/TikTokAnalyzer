"""The list of sites to check, and how to tell on each whether an account exists.

Two open projects maintain such lists, and each is good at something the other
is not:

- **Sherlock** (MIT licence) has the familiar profile addresses and a large
  list, but records only one sign per site: what a page looks like when the
  account is *missing*. A broken page or a bot wall matches no "missing" sign,
  so Sherlock reads it as "found".
- **WhatsMyName** (CC BY-SA 4.0) records both sides: what an existing account
  looks like *and* what a missing one looks like.

Both are downloaded at run time into ``~/.footprint`` (or ``$FOOTPRINT_HOME``)
and refreshed weekly -- never committed to this repository -- then merged into
one :class:`Site` per website. A site can keep a recipe from each list
(:class:`Probe`); the daily health check (:mod:`footprint.health`) decides which
recipe currently works.

Usernames are written into recipes wherever ``{account}`` appears. Sherlock's
own placeholder, ``{}``, is converted on load.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote, urlparse

import httpx

logger = logging.getLogger(__name__)

SHERLOCK_URL = (
    "https://raw.githubusercontent.com/sherlock-project/sherlock/master/"
    "sherlock_project/resources/data.json"
)
WMN_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
# Sites Sherlock's maintainers know give false results. Their own tool skips them.
EXCLUSIONS_URL = (
    "https://raw.githubusercontent.com/sherlock-project/sherlock/refs/heads/"
    "exclusions/false_positive_exclusions.txt"
)

REFRESH_AFTER = 7 * 24 * 3600

PLACEHOLDER = "{account}"

# A browser's User-Agent. Several sites answer an unknown agent with a stub page
# that matches neither sign.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


def home() -> Path:
    """The folder Footprint keeps its files in: ``$FOOTPRINT_HOME`` or ``~/.footprint``."""
    path = Path(os.path.expanduser(os.environ.get("FOOTPRINT_HOME") or "~/.footprint"))
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class Probe:
    """One recipe for asking a site whether an account exists.

    ``found_*`` describe a page for an account that exists; ``missing_*`` one
    for an account that does not. Codes and text must *both* match for that
    side to count -- the WhatsMyName rule. An empty text means the code alone
    decides that side.

    Sherlock recipes carry no ``found_text``; for them, "found" can only be
    inferred from the absence of the missing sign, which is why their verdicts
    are never better than *likely*.
    """

    source: str                       # "sherlock" or "whatsmyname"
    id: str                           # stable: "<source>:<name in that list>"
    url: str                          # address to request, with {account}
    method: str = "GET"
    body: Optional[str] = None        # request body, with {account}
    json_body: Optional[Any] = None   # or a JSON payload, with {account}
    headers: tuple[tuple[str, str], ...] = ()
    follow_redirects: bool = True
    found_codes: tuple[int, ...] = ()  # empty: any 2xx
    found_text: tuple[str, ...] = ()
    missing_codes: tuple[int, ...] = ()
    missing_text: tuple[str, ...] = ()
    # Sherlock's "status_code" and "response_url" rules: anything outside
    # 200-299 means missing.
    missing_if_not_2xx: bool = False
    known: tuple[str, ...] = ()       # accounts known to exist
    allowed: Optional[str] = None     # regex a username must match here
    strip_chars: str = ""

    @property
    def two_sided(self) -> bool:
        """Does this recipe describe what an existing account looks like?"""
        return bool(self.found_text)

    @property
    def needs_body(self) -> bool:
        return bool(self.found_text or self.missing_text)

    def username_for(self, username: str) -> str:
        if self.strip_chars:
            username = "".join(c for c in username if c not in self.strip_chars)
        return username

    def accepts(self, username: str) -> bool:
        """Could this username exist on the site at all?"""
        name = self.username_for(username)
        if not name:
            return False
        if self.allowed:
            try:
                return re.search(self.allowed, name) is not None
            except re.error:
                return True
        return True

    def request_url(self, username: str) -> str:
        return self.url.replace(PLACEHOLDER, quote(self.username_for(username), safe="@._-~"))


@dataclass
class Site:
    """One website, with every recipe we know for it."""

    key: str                         # the site's domain, e.g. "github.com"
    name: str
    profile_url: str                 # the address a person would open, with {account}
    probes: list[Probe] = field(default_factory=list)
    category: Optional[str] = None
    nsfw: bool = False
    protection: tuple[str, ...] = ()  # bot walls WhatsMyName has noted

    def profile_for(self, username: str) -> str:
        return self.profile_url.replace(PLACEHOLDER, quote(username, safe="@._-~"))

    def preferred_probes(self) -> list[Probe]:
        """Two-sided recipes first: they can tell a real page from a broken one."""
        return sorted(self.probes, key=lambda p: (not p.two_sided, p.source != "whatsmyname"))


# ---------------------------------------------------------------- site keys --

def site_key(url: str) -> str:
    """The domain a profile address lives on, ignoring ``www.`` and the
    username's own subdomain (``{account}.substack.com`` -> ``substack.com``)."""
    netloc = (urlparse(url).netloc or "").lower().rsplit("@", 1)[-1].split(":")[0]
    host = ".".join(label for label in netloc.split(".") if PLACEHOLDER not in label)
    for prefix in ("www.", "m.", "mobile."):
        if host.startswith(prefix):
            host = host[len(prefix):]
            break
    return ALIASES.get(host, host)


# Domains that are the same site under another name. Matters most for links on
# a brand's website, which may still say twitter.com.
ALIASES = {
    "twitter.com": "x.com",
    "threads.net": "threads.com",
    "youtu.be": "youtube.com",
    "instagr.am": "instagram.com",
    "fb.com": "facebook.com",
    "en.gravatar.com": "gravatar.com",
    "account.venmo.com": "venmo.com",
    "telegram.me": "t.me",
}


def _listify(value: Any) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _placeholder(value: Any) -> Any:
    """Sherlock's ``{}`` -> ``{account}``, inside strings, lists and dicts."""
    if isinstance(value, str):
        return value.replace("{}", PLACEHOLDER)
    if isinstance(value, dict):
        return {k: _placeholder(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_placeholder(v) for v in value]
    return value


# ------------------------------------------------------------- the two lists --

def from_sherlock(data: dict, exclusions: Iterable[str] = ()) -> list[tuple[Site, Probe]]:
    """Sherlock's ``data.json`` as (site, recipe) pairs."""
    skip = {e.strip() for e in exclusions if e.strip()}
    out = []
    for name, info in data.items():
        if name.startswith("$") or not isinstance(info, dict) or name in skip:
            continue
        try:
            url = _placeholder(info["url"])
        except KeyError:
            continue
        kinds = _listify(info.get("errorType"))
        if not kinds or any(k not in ("message", "status_code", "response_url") for k in kinds):
            continue
        method = (info.get("request_method") or "").upper()
        if not method:
            method = "HEAD" if kinds == ["status_code"] else "GET"
        probe = Probe(
            source="sherlock",
            id=f"sherlock:{name}",
            url=_placeholder(info.get("urlProbe") or info["url"]),
            method=method,
            json_body=_placeholder(info.get("request_payload")),
            headers=tuple((str(k), str(v)) for k, v in (info.get("headers") or {}).items()),
            follow_redirects="response_url" not in kinds,
            missing_codes=tuple(int(c) for c in _listify(info.get("errorCode"))
                                if "status_code" in kinds),
            missing_text=tuple(str(t) for t in _listify(info.get("errorMsg"))
                               if "message" in kinds and t),
            missing_if_not_2xx=bool({"status_code", "response_url"} & set(kinds)),
            known=tuple(_listify(info.get("username_claimed"))),
            allowed=info.get("regexCheck"),
        )
        site = Site(
            key=site_key(url), name=name, profile_url=url, probes=[probe],
            nsfw=bool(info.get("isNSFW")),
        )
        out.append((site, probe))
    return out


def from_whatsmyname(data: dict) -> list[tuple[Site, Probe]]:
    """WhatsMyName's ``wmn-data.json`` as (site, recipe) pairs."""
    out = []
    for info in data.get("sites", []):
        try:
            name = info["name"]
            check = info["uri_check"]
        except KeyError:
            continue
        if info.get("valid") is False:
            continue
        body = info.get("post_body")
        pretty = info.get("uri_pretty") or check
        probe = Probe(
            source="whatsmyname",
            id=f"whatsmyname:{name}",
            url=check,
            method="POST" if body else "GET",
            body=body,
            headers=tuple((str(k), str(v)) for k, v in (info.get("headers") or {}).items()),
            found_codes=(int(info["e_code"]),) if info.get("e_code") is not None else (),
            found_text=(info["e_string"],) if info.get("e_string") else (),
            missing_codes=(int(info["m_code"]),) if info.get("m_code") is not None else (),
            missing_text=(info["m_string"],) if info.get("m_string") else (),
            known=tuple(info.get("known") or ()),
            strip_chars=info.get("strip_bad_char") or "",
        )
        cat = info.get("cat")
        site = Site(
            key=site_key(pretty), name=name, profile_url=pretty, probes=[probe],
            category=cat, nsfw=bool(cat and "nsfw" in cat.lower()),
            protection=tuple(info.get("protection") or ()),
        )
        out.append((site, probe))
    return out


def merge(*lists: Iterable[tuple[Site, Probe]]) -> dict[str, Site]:
    """One :class:`Site` per domain, keeping every recipe.

    The first list to name a site gives it its name and profile address. Pass
    Sherlock's first: its addresses are the ones people recognise
    (``youtube.com/@name``), while WhatsMyName often checks an API behind the
    scenes.
    """
    sites: dict[str, Site] = {}
    for pairs in lists:
        for site, probe in pairs:
            if not site.key:
                continue
            have = sites.get(site.key)
            if have is None:
                sites[site.key] = site
                continue
            if all(p.id != probe.id for p in have.probes):
                have.probes.append(probe)
            have.category = have.category or site.category
            have.nsfw = have.nsfw or site.nsfw
            have.protection = tuple(dict.fromkeys(have.protection + site.protection))
    return sites


# ----------------------------------------------------------------- download --

def _cached(name: str) -> Path:
    return home() / name


def _stale(path: Path, now: float) -> bool:
    return not path.exists() or now - path.stat().st_mtime > REFRESH_AFTER


async def _refresh(client: httpx.AsyncClient, url: str, path: Path, now: float) -> None:
    """Download ``url`` into ``path`` if the copy is over a week old.

    A failed refresh keeps the old copy: a week-old list beats no list.
    """
    if not _stale(path, now):
        return
    try:
        resp = await client.get(url, timeout=30.0, follow_redirects=True,
                                headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        if path.suffix == ".json":
            json.loads(resp.text)  # never replace a good copy with a broken one
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_text(resp.text, encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        if path.exists():
            logger.warning("could not refresh %s (%s); using the copy from %s",
                           url, exc, time.ctime(path.stat().st_mtime))
        else:
            logger.warning("could not download %s: %s", url, exc)


async def load(client: httpx.AsyncClient, *, now: Optional[float] = None) -> dict[str, Site]:
    """Every site, downloading or refreshing the lists as needed.

    Raises ``RuntimeError`` only when neither list has ever been downloaded.
    """
    now = time.time() if now is None else now
    sherlock_path = _cached("sherlock.json")
    wmn_path = _cached("whatsmyname.json")
    excl_path = _cached("sherlock-exclusions.txt")
    for url, path in ((SHERLOCK_URL, sherlock_path), (WMN_URL, wmn_path),
                      (EXCLUSIONS_URL, excl_path)):
        await _refresh(client, url, path, now)
    return load_cached()


def load_cached() -> dict[str, Site]:
    """Every site, from the copies already on disk."""
    sherlock_path = _cached("sherlock.json")
    wmn_path = _cached("whatsmyname.json")
    excl_path = _cached("sherlock-exclusions.txt")
    pairs = []
    if wmn_path.exists():
        pairs.append(from_whatsmyname(json.loads(wmn_path.read_text(encoding="utf-8"))))
    if sherlock_path.exists():
        exclusions = excl_path.read_text(encoding="utf-8").splitlines() if excl_path.exists() else []
        pairs.append(from_sherlock(json.loads(sherlock_path.read_text(encoding="utf-8")), exclusions))
    if not pairs:
        raise RuntimeError(
            "No site list yet. Footprint downloads one from GitHub the first time it "
            "runs; check the internet connection and start it again."
        )
    # Sherlock first, so its names and addresses lead when both lists know a site.
    return merge(*reversed(pairs))
