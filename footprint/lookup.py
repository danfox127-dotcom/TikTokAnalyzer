"""Look up an email address or a phone number: what is it linked to?

**An email address** is checked only where its owner chose to publish the link:

- **Gravatar** -- the public profile some people attach to their address,
  including the accounts they have *verified* there (X, LinkedIn, GitHub,
  Instagram...). Gravatar is asked by a scrambled code made from the address
  (a SHA-256 hash), which is how Gravatar lookups always work.
- **GitHub** -- public commits made with the address. When GitHub has
  verified the address belongs to an account, the commits name that account.
- **WebFinger** -- the address's own domain may say which fediverse
  (Mastodon-style) profile it belongs to. Skipped for big webmail domains,
  which never answer and shouldn't be told about the address.
- **The domain's mail records** -- whether email from it can be faked
  (:mod:`footprint.mailcheck`). Only the domain is sent.

Every account found is then read like any search result (public profile
details, photo fingerprint) and scored for "same person?" with
:mod:`footprint.match`.

**A phone number** is never looked up anywhere: :mod:`footprint.phone` works
out what the number itself says.

What this deliberately does not do: try sign-up or password-reset pages to see
whether an address or number has an account somewhere (it misuses those
systems and can alert the owner), name a number's owner (data brokers), or
search breach databases. Nothing about a lookup is kept.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from urllib.parse import urlparse

import httpx

from . import mailcheck, match, phone
from .brand import profile_from_link
from .manifest import USER_AGENT, Site
from .profile import Profile
from .profile import fetch as fetch_profile

logger = logging.getLogger(__name__)

TIMEOUT = 8.0
GRAVATAR_API = "https://api.gravatar.com/v3/profiles/"
GITHUB_COMMITS = "https://api.github.com/search/commits"
DETAILS_WAIT = 20.0

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'\-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[\d\s().\-]+$")

# Big personal-mail providers: their mail settings are the provider's, not the
# owner's, and their domains don't answer WebFinger for a person.
WEBMAIL = {
    "gmail.com": "Gmail", "googlemail.com": "Gmail", "outlook.com": "Outlook",
    "hotmail.com": "Outlook", "live.com": "Outlook", "msn.com": "Outlook",
    "yahoo.com": "Yahoo Mail", "ymail.com": "Yahoo Mail", "aol.com": "AOL Mail",
    "icloud.com": "iCloud Mail", "me.com": "iCloud Mail", "mac.com": "iCloud Mail",
    "proton.me": "Proton Mail", "protonmail.com": "Proton Mail", "pm.me": "Proton Mail",
    "gmx.com": "GMX", "gmx.de": "GMX", "web.de": "WEB.DE", "mail.com": "Mail.com",
    "zoho.com": "Zoho Mail", "yandex.com": "Yandex Mail", "yandex.ru": "Yandex Mail",
    "fastmail.com": "Fastmail", "hey.com": "HEY", "qq.com": "QQ Mail", "163.com": "NetEase Mail",
    "naver.com": "Naver Mail", "comcast.net": "Xfinity", "verizon.net": "Verizon",
    "att.net": "AT&T", "sbcglobal.net": "AT&T",
}
WEBMAIL_FAMILIES = {"yahoo": "Yahoo Mail", "hotmail": "Outlook", "outlook": "Outlook",
                    "live": "Outlook", "gmx": "GMX", "yandex": "Yandex Mail"}


def kind(text: str) -> Optional[str]:
    """``"email"``, ``"phone"``, ``"username"`` -- or None for nothing usable."""
    t = (text or "").strip()
    if not t:
        return None
    if EMAIL_RE.match(t):
        return "email"
    digits = re.sub(r"\D", "", t)
    if PHONE_RE.match(t) and 7 <= len(digits) <= 15:
        return "phone"
    name = t.lstrip("@")
    if name and not re.search(r"[\s/?#]", name):
        return "username"
    return None


def webmail(domain: str) -> Optional[str]:
    domain = domain.lower()
    return WEBMAIL.get(domain) or WEBMAIL_FAMILIES.get(domain.split(".")[0])


# Shared inboxes: the part before the @ says nothing about anyone's username.
ROLE_ADDRESSES = {"hello", "hi", "info", "contact", "support", "help", "admin", "team", "press",
                  "media", "sales", "office", "mail", "email", "noreply", "no-reply", "hr", "jobs",
                  "careers", "billing", "accounts", "marketing", "partners", "enquiries", "inquiries"}


def local_handle(email: str) -> Optional[str]:
    """The part before the @, without a +tag: a guess at a username."""
    local = email.split("@", 1)[0].split("+", 1)[0]
    if local.lower() in ROLE_ADDRESSES:
        return None
    return local if len(local) >= 3 and re.search(r"[a-z]", local, re.I) else None


# ----------------------------------------------------------------- Gravatar --

async def gravatar(email: str, client: httpx.AsyncClient) -> dict:
    """The public Gravatar profile for an address, if its owner made one."""
    code = hashlib.sha256(email.strip().lower().encode()).hexdigest()
    try:
        resp = await client.get(GRAVATAR_API + code, timeout=TIMEOUT,
                                headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    except httpx.HTTPError as exc:
        return {"found": None, "error": f"Couldn't reach Gravatar ({type(exc).__name__})"}
    if resp.status_code == 404:
        return {"found": False}
    if resp.status_code != 200:
        return {"found": None, "error": f"Gravatar answered {resp.status_code}"}
    try:
        data = resp.json()
    except ValueError:
        return {"found": None, "error": "Gravatar sent something unreadable"}
    accounts = [{"label": a.get("service_label") or a.get("service_type"), "url": a.get("url")}
                for a in data.get("verified_accounts") or []
                if a.get("url") and not a.get("is_hidden")]
    links = [l.get("url") for l in data.get("links") or [] if isinstance(l, dict) and l.get("url")]
    return {
        "found": True, "profile_url": data.get("profile_url"),
        "display_name": data.get("display_name") or None, "location": data.get("location") or None,
        "description": data.get("description") or None, "job_title": data.get("job_title") or None,
        "company": data.get("company") or None, "pronouns": data.get("pronouns") or None,
        "avatar_url": data.get("avatar_url"), "accounts": accounts, "links": links,
    }


def gravatar_profile(g: dict) -> Optional[Profile]:
    """The Gravatar result as a profile, so it can be compared with the others."""
    url = g.get("profile_url")
    if not g.get("found") or not url:
        return None
    p = Profile(site="gravatar.com", name="Gravatar", url=url,
                username=urlparse(url).path.strip("/") or "gravatar")
    src = "Gravatar's public profile"
    p.set("display_name", g.get("display_name"), src)
    p.set("bio", " · ".join(x for x in (g.get("job_title"), g.get("company"), g.get("description")) if x)
          or None, src)
    p.set("avatar_url", g.get("avatar_url"), src)
    p.set("location", g.get("location"), src)
    p.add_links([a["url"] for a in g.get("accounts", [])] + g.get("links", []), src)
    return p


# ------------------------------------------------------------------- GitHub --

def _when(value: Optional[str]) -> Optional[str]:
    """A commit date as ISO UTC, ignoring the impossible future dates some
    repositories carry."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
    return None if dt > datetime.now(timezone.utc) else dt.replace(microsecond=0).isoformat()


async def github(email: str, client: httpx.AsyncClient) -> dict:
    """Public GitHub commits made with this address, and the accounts they belong to."""
    try:
        resp = await client.get(GITHUB_COMMITS, timeout=TIMEOUT, params={
            "q": f"author-email:{email}", "per_page": 50, "sort": "author-date", "order": "desc"},
            headers={"Accept": "application/vnd.github+json", "User-Agent": "Footprint"})
    except httpx.HTTPError as exc:
        return {"error": f"Couldn't reach GitHub ({type(exc).__name__})"}
    if resp.status_code in (403, 429):
        return {"error": "GitHub's search limit for this hour is used up; try again in a minute."}
    if resp.status_code != 200:
        return {"error": f"GitHub answered {resp.status_code}"}
    try:
        data = resp.json()
    except ValueError:
        return {"error": "GitHub sent something unreadable"}
    accounts: dict[str, dict] = {}
    names: list[str] = []
    repos: list[str] = []
    dates: list[str] = []
    owners: dict[str, int] = {}
    unlinked = 0
    items = data.get("items") or []
    for item in items:
        commit = item.get("commit") or {}
        author = commit.get("author") or {}
        repo = (item.get("repository") or {}).get("full_name")
        when = _when(author.get("date"))
        if when:
            dates.append(when)
        if author.get("name") and author["name"] not in names:
            names.append(author["name"])
        if repo and repo not in repos:
            repos.append(repo)
        login = (item.get("author") or {}).get("login")
        if not login:
            unlinked += 1
            if repo:
                owner = repo.split("/", 1)[0]
                owners[owner] = owners.get(owner, 0) + 1
            continue
        acct = accounts.setdefault(login, {
            "login": login, "url": f"https://github.com/{login}",
            "avatar_url": (item.get("author") or {}).get("avatar_url"), "commits": 0, "repos": []})
        acct["commits"] += 1
        if repo and repo not in acct["repos"]:
            acct["repos"].append(repo)
    # GitHub hasn't tied these commits to an account, but when most of them sit
    # in one person's repositories, that person is likely the author. Likely,
    # not verified: people commit to friends' projects too.
    owner = max(owners, key=owners.get) if owners else None
    likely_owner = None
    if owner and owners[owner] >= 3 and owners[owner] * 2 >= len(items):
        likely_owner = {"login": owner, "url": f"https://github.com/{owner}", "commits": owners[owner]}
    return {
        "total": data.get("total_count", 0), "accounts": list(accounts.values()), "names": names[:5],
        "repos": repos[:8], "unlinked": unlinked, "likely_owner": likely_owner,
        "first_seen": min(dates) if dates else None, "last_seen": max(dates) if dates else None,
    }


# --------------------------------------------------------------- WebFinger --

async def webfinger(email: str, client: httpx.AsyncClient) -> Optional[dict]:
    """Ask the address's own domain whether it belongs to a fediverse profile."""
    domain = email.rsplit("@", 1)[1].lower()
    if webmail(domain):
        return None
    try:
        resp = await client.get(f"https://{domain}/.well-known/webfinger", timeout=6.0,
                                params={"resource": f"acct:{email}"},
                                headers={"Accept": "application/jrd+json, application/json",
                                         "User-Agent": USER_AGENT})
        if resp.status_code != 200:
            return {"found": False}
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return {"found": False}
    page = next((l.get("href") for l in data.get("links") or []
                 if isinstance(l, dict) and l.get("rel") == "http://webfinger.net/rel/profile-page"
                 and l.get("href")), None)
    page = page or next((a for a in data.get("aliases") or [] if isinstance(a, str)), None)
    if not page or not re.match(r"^https?://", page):
        return {"found": False}
    return {"found": True, "profile_url": page, "subject": data.get("subject")}


# ----------------------------------------------------------------- the run --

def _linked(url: str, source: str, sites: dict[str, Site]) -> dict:
    """A linked address as an account card: which site, which username, how we know."""
    known = profile_from_link(url, sites)
    if known:
        key, username = known
        name = sites[key].name
    else:
        key = match.link_host(url)
        name = key
        username = urlparse(url).path.strip("/").split("/")[-1].lstrip("@") or key
    return {"site": key, "name": name, "username": username, "url": url, "sources": [source]}


async def run(query: str, sites: dict[str, Site], client: httpx.AsyncClient,
              ) -> AsyncIterator[tuple[str, dict]]:
    """A whole lookup as a stream of ``(event, data)`` for the page to show live.

    Events: ``kind``; for a phone, ``phone``; for an email, ``mail``,
    ``gravatar``, ``github`` and ``fediverse`` (each as it answers), then
    ``linked``, ``details`` per account, ``match`` and ``handles``; always
    ``done`` last.
    """
    q = (query or "").strip()
    k = kind(q)
    yield "kind", {"kind": k, "query": q}
    if k == "phone":
        yield "phone", phone.facts(q)
        yield "done", {}
        return
    if k != "email":
        yield "done", {}
        return

    email = q.lower()
    domain = email.rsplit("@", 1)[1]
    provider = webmail(domain)

    async def mail():
        if provider:
            return {"domain": domain, "verdict": "webmail", "provider": provider,
                    "summary": f"A personal address at {provider}. How well it's protected against "
                               f"fakes is up to {provider}, not the person who owns it."}
        return (await mailcheck.check(domain, client)).to_dict()

    async def named(name: str, coro):
        return name, await coro

    jobs = [asyncio.create_task(named(n, c)) for n, c in (
        ("mail", mail()), ("gravatar", gravatar(email, client)),
        ("github", github(email, client)), ("fediverse", webfinger(email, client)))]
    results: dict[str, Optional[dict]] = {}
    try:
        for done in asyncio.as_completed(jobs):
            name, result = await done
            results[name] = result
            if result is not None:
                yield name, result
    finally:
        for task in jobs:
            task.cancel()

    # Every account the address is linked to, and how we know.
    linked: dict[str, dict] = {}

    def add(url: Optional[str], source: str, strength: str) -> None:
        """``strength``: "verified" when the owner or the platform proved the
        link; "likely" when it's inferred."""
        if not url or not re.match(r"^https?://", url):
            return
        key = match.link_key(url)
        if key not in linked:
            linked[key] = _linked(url, source, sites) | {"strength": strength}
            return
        if source not in linked[key]["sources"]:
            linked[key]["sources"].append(source)
        if strength == "verified":
            linked[key]["strength"] = "verified"

    def commits(n: int) -> str:
        return f"{n} public commit{'s' if n != 1 else ''}"

    g = results.get("gravatar") or {}
    for a in g.get("accounts", []):
        add(a["url"], "Verified on their Gravatar", "verified")
    gh = results.get("github") or {}
    for a in gh.get("accounts", []):
        add(a["url"], f"GitHub ties {commits(a['commits'])} with this address to this account",
            "verified")
    owner = gh.get("likely_owner")
    if owner and not gh.get("accounts"):
        add(owner["url"], f"{commits(owner['commits'])} with this address are in "
                          f"{owner['login']}'s projects", "likely")
    f = results.get("fediverse") or {}
    if f.get("found"):
        add(f["profile_url"], f"{domain} says this profile is theirs", "verified")
    yield "linked", {"accounts": list(linked.values())}

    # Read each linked account's public profile, as a search would.
    profiles: list[Profile] = []
    gp = gravatar_profile(g)
    if gp is not None:
        await match.fingerprint(gp, client)
        profiles.append(gp)
    queue: asyncio.Queue = asyncio.Queue()

    async def details(acct: dict) -> None:
        p = await fetch_profile(acct["site"], acct["name"], acct["username"], acct["url"], client)
        await match.fingerprint(p, client)
        await queue.put(p)

    tasks = [asyncio.create_task(details(a)) for a in linked.values()]
    try:
        if tasks:
            _, late = await asyncio.wait(tasks, timeout=DETAILS_WAIT)
            for t in late:
                t.cancel()
        while not queue.empty():
            p = queue.get_nowait()
            profiles.append(p)
            yield "details", p.to_dict()
    finally:
        for t in tasks:
            t.cancel()

    if len(profiles) >= 2:
        yield "match", match.assess(profiles)

    # Usernames worth a full search: what the accounts are called, and a guess.
    handles: list[dict] = []
    seen: set[str] = set()
    for acct in linked.values():
        h = acct["username"]
        if h and h.casefold() not in seen and not h.startswith("http"):
            seen.add(h.casefold())
            handles.append({"handle": h, "why": f"their {acct['name']} username"})
    guess = local_handle(email)
    if guess and guess.casefold() not in seen:
        handles.append({"handle": guess, "why": "a guess from the part before the @"})
    yield "handles", {"handles": handles[:6]}
    yield "done", {"accounts": len(linked)}


# Have I Been Pwned, for checking your own address in known data breaches. The
# page is linked bare -- the address goes there only if you type it in.
BREACH_CHECK = "https://haveibeenpwned.com/"
