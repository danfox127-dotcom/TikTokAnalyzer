"""The brand consistency report: where the brand is, whether it's really the
brand, and whether it looks like one brand everywhere.

Search engines and AI assistants piece together who an organisation is from
the profiles that agree with each other and with its website -- most directly
from the ``sameAs`` list in the website's structured data. This report checks
that picture from the outside:

1. **The website is the source of truth.** Profiles it links to (in the page,
   in ``rel="me"`` links, or in its JSON-LD ``sameAs``) are *confirmed ours*.
   So is a profile that links back to the website.
2. **Every other account with the brand's handle** is scored against the
   confirmed ones with :mod:`footprint.match`: *probably ours*, *possibly ours
   -- check*, or *taken by someone else* (a squatter or an impersonator).
3. **Where it's free**, the handle can still be claimed.
4. **Consistency** across the brand's own profiles: names, photos, links back,
   locations, handles, dormant accounts, and the gaps between what the website
   lists and what exists.
5. **A ready-to-paste JSON-LD block** with the ``sameAs`` list.
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import AsyncIterator, Optional
from urllib.parse import urljoin, urlparse

import httpx

from . import check, match, store, tiers
from .manifest import PLACEHOLDER, USER_AGENT, Site, site_key
from .profile import Profile
from .profile import fetch as fetch_profile
from .timezone import hint as time_hint

DORMANT_AFTER = timedelta(days=180)

# First path segments that are never a username.
NOT_PROFILES = {"share", "sharer", "intent", "hashtag", "watch", "explore", "search", "home",
                "login", "signup", "p", "reel", "status", "tag", "tags", "privacy", "terms",
                "about", "help", "embed", "plugins", "dialog", "groups", "events"}


# ------------------------------------------------------------------ website --

class _LinkReader(HTMLParser):
    """Outbound links, ``rel="me"`` links and JSON-LD blocks from a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.rel_me: list[str] = []
        self.jsonld: list[str] = []
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_jsonld = False
        self._in_title = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        rel = a.get("rel", "").lower().split()
        if tag in ("a", "link") and a.get("href"):
            if "me" in rel:
                self.rel_me.append(a["href"])
            if tag == "a":
                self.links.append(a["href"])
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_jsonld, self._buf = True, []
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"]
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._buf))
            self._in_jsonld = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_jsonld:
            self._buf.append(data)
        elif self._in_title and len(self.title) < 300:
            self.title += data


def _same_as(node, out: list[str]) -> None:
    if isinstance(node, dict):
        value = node.get("sameAs")
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, list):
            out.extend(v for v in value if isinstance(v, str))
        for v in node.values():
            _same_as(v, out)
    elif isinstance(node, list):
        for v in node:
            _same_as(v, out)


def _pattern(template: str) -> Optional[re.Pattern]:
    """A site's profile address as a regex capturing the username."""
    t = template.split("?")[0].split("#")[0].rstrip("/")
    t = re.sub(r"^https?://", "", t, flags=re.I)
    t = re.sub(r"^(www\.|m\.)", "", t, flags=re.I)
    if PLACEHOLDER not in t:
        return None
    escaped = re.escape(t).replace(re.escape(PLACEHOLDER), r"([^/?#]+)")
    return re.compile("^" + escaped + "$", re.I)


def _bare(url: str) -> str:
    u = re.sub(r"^https?://", "", url.strip(), flags=re.I).split("?")[0].split("#")[0].rstrip("/")
    return re.sub(r"^(www\.|m\.|mobile\.)", "", u, flags=re.I)


def profile_from_link(link: str, sites: dict[str, Site]) -> Optional[tuple[str, str]]:
    """``https://instagram.com/brand/`` -> ``("instagram.com", "brand")``, for known sites."""
    if not re.match(r"^https?://", link or "", re.I):
        return None
    key = site_key(link)
    # name.substack.com belongs to substack.com: try the parent domains too.
    while key not in sites and key.count(".") >= 2:
        key = key.split(".", 1)[1]
    site = sites.get(key)
    if site is None:
        return None
    bare = _bare(link)
    host, _, path = bare.partition("/")
    canonical = key + ("/" + path if path else "")
    pattern = _pattern(site.profile_url)
    for candidate in (bare, canonical):
        if pattern and (m := pattern.match(candidate)):
            return key, m.group(1).lstrip("@")
    # The site's own address shape didn't match (an alias, an older format):
    # fall back to the first part of the path, or the username's subdomain.
    parts = [p for p in path.split("/") if p]
    if parts and parts[0].lstrip("@").lower() not in NOT_PROFILES:
        return key, parts[0].lstrip("@")
    sub = host.split(".")[0].lower()
    if host.count(".") >= 2 and sub not in ("www", "m", "mobile", "open", "en"):
        return key, sub
    return None


@dataclass
class Website:
    url: str
    domain: str
    name: Optional[str] = None
    description: Optional[str] = None
    profiles: list[dict] = field(default_factory=list)   # {site, username, url, how}
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def links_to(self, site: str, username: str) -> Optional[dict]:
        for p in self.profiles:
            if p["site"] == site and p["username"].casefold() == username.casefold():
                return p
        return None


def domain_of(url: str) -> str:
    return match.link_host(url if re.match(r"^https?://", url, re.I) else "https://" + url)


def parse_website(page: str, url: str, sites: dict[str, Site]) -> Website:
    reader = _LinkReader()
    reader.feed(page[:2_000_000])
    site = Website(url=url, domain=domain_of(url))
    site.name = (reader.meta.get("og:site_name") or reader.meta.get("og:title")
                 or reader.title.strip() or None)
    site.description = reader.meta.get("og:description") or reader.meta.get("description")
    same_as: list[str] = []
    for block in reader.jsonld:
        try:
            _same_as(json.loads(block), same_as)
        except ValueError:
            continue
    seen = set()
    for how, links in (("sameAs", same_as), ("rel=me", reader.rel_me), ("link", reader.links)):
        for link in links:
            absolute = urljoin(url, link.strip())
            found = profile_from_link(absolute, sites)
            if not found or found in seen:
                continue
            seen.add(found)
            site.profiles.append(dict(site=found[0], username=found[1], url=absolute, how=how))
    return site


async def read_website(url: str, sites: dict[str, Site], client: httpx.AsyncClient) -> Website:
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    try:
        resp = await client.get(url, timeout=15.0, follow_redirects=True,
                                headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        if resp.status_code >= 400:
            return Website(url=url, domain=domain_of(url), error=f"The website answered {resp.status_code}")
        return parse_website(resp.text, str(resp.url), sites)
    except httpx.HTTPError as exc:
        return Website(url=url, domain=domain_of(url), error=f"Couldn't open the website ({type(exc).__name__})")


# ------------------------------------------------------------------- report --

HOW_WORDS = {"sameAs": "Listed in your website's sameAs", "rel=me": "Linked from your website (rel=me)",
             "link": "Linked from your website"}

# What a row says when there is no account to show, in plain words. The exact
# evidence stays alongside as ``detail``.
PLAIN = {
    ("free", "confirmed"): "No account with this handle (both signs agree)",
    ("free", "likely"): "No account with this handle (this site has only one sign to check)",
    ("not_allowed", ""): "This platform doesn't allow handles like this one",
}

ROW_WORDS = {
    "confirmed": "Confirmed ours", "probably": "Probably ours", "possibly": "Possibly ours — check",
    "taken": "Taken — no link to the brand", "free": "Free to claim", "dead_link":
    "Website links to a profile that doesn't exist", "unknown": "Couldn't check",
    "not_allowed": "Handle not allowed here",
}


def _website_profile(website: Website, brand_name: str) -> Profile:
    """The website itself, as a profile the others can be compared with."""
    return Profile(site=website.domain, name="your website", username=website.domain,
                   url=website.url, display_name=brand_name or website.name,
                   bio=website.description, links=[website.url])


def _links_back(p: Profile, domain: str) -> bool:
    """Does the profile link to the website -- or at least name it in its bio?"""
    if any(match.link_host(l) == domain or match.link_host(l).endswith("." + domain) for l in p.links):
        return True
    return bool(domain and p.bio and re.search(r"(?<![\w.-])" + re.escape(domain) + r"\b", p.bio, re.I))


def _days_since(iso_time: Optional[str], now: datetime) -> Optional[int]:
    if not iso_time:
        return None
    try:
        return (now - datetime.fromisoformat(iso_time)).days
    except ValueError:
        return None


def build(brand_name: str, handles: list[str], website: Website, results: list[dict],
          profiles: dict[tuple[str, str], Profile], *, now: Optional[datetime] = None) -> dict:
    """Assemble the report from what the search found. Pure: no network."""
    now = now or datetime.now(timezone.utc)
    primary = handles[0] if handles else ""
    me = _website_profile(website, brand_name)

    # 1. What is confirmed ours.
    rows: list[dict] = []
    confirmed: list[Profile] = []
    for (site, username), p in profiles.items():
        linked = website.links_to(site, username)
        if linked or _links_back(p, website.domain):
            confirmed.append(p)

    # 2. Rate everything that was found.
    by_site: dict[str, list[dict]] = {}
    for r in results:
        by_site.setdefault(r["site"], []).append(r)
    ours: list[Profile] = []
    for site, site_results in sorted(by_site.items(), key=lambda kv: (tiers.rank(kv[0]), kv[0])):
        found = [r for r in site_results if r["status"] == "found"]
        for r in found:
            p = profiles.get((site, r["username"]))
            linked = website.links_to(site, r["username"])
            evidence: list[str] = []
            if linked:
                status = "confirmed"
                evidence.append(HOW_WORDS[linked["how"]])
            elif p is not None and _links_back(p, website.domain):
                status = "confirmed"
                evidence.append(f"Links back to {website.domain}")
            else:
                best = match.Pair(site, "")
                for other in confirmed + [me]:
                    if p is None or other is p:
                        continue
                    pair = match.score(p, other)
                    if pair.score > best.score:
                        best = pair
                status = {"very_likely": "probably", "possibly": "possibly"}.get(best.band, "taken")
                evidence.extend(best.reasons)
                if p is not None and p.hidden:
                    evidence.append(p.note or "Details hidden by the platform")
            if p is not None and status in ("confirmed", "probably"):
                ours.append(p)
            rows.append(dict(site=site, name=r["name"], username=r["username"], url=r["url"],
                             status=status, label=ROW_WORDS[status], confidence=r.get("confidence", ""),
                             evidence=evidence, reason=r.get("reason", ""), big=r.get("big", False),
                             profile=p.to_dict() if p else None))
        # Profiles the website lists here that the check didn't find.
        found_names = {r["username"].casefold() for r in found}
        listed = False
        for w in website.profiles:
            if w["site"] != site or w["username"].casefold() in found_names:
                continue
            r = next((r for r in site_results if r["username"].casefold() == w["username"].casefold()), None)
            if r is None:
                continue
            listed = True
            if r["status"] == "not_found":
                status, evidence = "dead_link", [HOW_WORDS[w["how"]]]
            else:
                # The website says it's ours; the platform just wouldn't say.
                status = "confirmed"
                evidence = [HOW_WORDS[w["how"]],
                            f"Couldn't check the platform itself: {r.get('reason', '')}"]
            rows.append(dict(site=site, name=r["name"], username=r["username"], url=w["url"],
                             status=status, label=ROW_WORDS[status], confidence=r.get("confidence", ""),
                             evidence=evidence, reason=r.get("reason", ""), big=r.get("big", False),
                             profile=None))
        if found or listed:
            continue
        main = next((r for r in site_results if r["username"] == primary), site_results[0])
        status = {"not_found": "free", "cant_exist": "not_allowed"}.get(main["status"], "unknown")
        confidence = main.get("confidence", "")
        rows.append(dict(site=site, name=main["name"], username=main["username"], url=main["url"],
                         status=status, label=ROW_WORDS[status], confidence=confidence, evidence=[],
                         reason=PLAIN.get((status, confidence), main.get("reason", "")),
                         detail=main.get("reason", ""), big=main.get("big", False), profile=None))

    findings = consistency(website, rows, ours, now)
    posting = time_hint([t for p in ours for t in p.post_times], [p.name for p in ours if p.post_times])
    same_as = [r["url"] for r in rows if r["status"] in ("confirmed", "probably")]
    return dict(
        brand=dict(name=brand_name, website=website.url, domain=website.domain, handles=handles),
        website=website.to_dict(), rows=rows, findings=findings, posting=posting.to_dict(),
        same_as=same_as, jsonld=jsonld(brand_name, website.url, same_as),
        counts={s: sum(1 for r in rows if r["status"] == s) for s in ROW_WORDS},
    )


def consistency(website: Website, rows: list[dict], ours: list[Profile], now: datetime) -> list[dict]:
    """What a reader should fix, in plain words. Each finding: level, title, detail."""
    out: list[dict] = []

    def add(level: str, title: str, detail: str = "") -> None:
        out.append(dict(level=level, title=title, detail=detail))

    if website.error:
        add("warn", "Couldn't read the website", website.error)
    elif not website.profiles:
        add("warn", f"{website.domain} doesn't link to any social profiles",
            "Search engines and AI assistants use those links (and the sameAs list) to tie "
            "your accounts to you. The JSON-LD block below is a starting point.")

    names: dict[str, list[str]] = {}
    for p in ours:
        if p.display_name:
            sites_named = names.setdefault(match.fold(p.display_name), [])
            if p.name not in sites_named:
                sites_named.append(p.name)
    shown = {match.fold(p.display_name): p.display_name for p in ours if p.display_name}
    if len(names) == 1:
        add("good", f"Same name everywhere: “{next(iter(shown.values()))}”")
    elif len(names) > 1:
        add("warn", "Your profiles use different names",
            "; ".join(f"“{shown[k]}” on {', '.join(v)}" for k, v in names.items()))

    no_link = [p.name for p in ours if not _links_back(p, website.domain)]
    if ours and not no_link:
        add("good", f"Every profile links back to {website.domain}")
    elif no_link:
        add("warn", f"Not linking back to {website.domain}", ", ".join(no_link))

    with_photo = [p for p in ours if p.photo_hash]
    if len(with_photo) >= 2:
        groups: list[list[Profile]] = []
        for p in with_photo:
            for g in groups:
                if match.distance(g[0].photo_hash, p.photo_hash) <= match.PHOTO_MATCH_BITS:
                    g.append(p)
                    break
            else:
                groups.append([p])
        if len(groups) == 1:
            add("good", "The same profile photo everywhere")
        else:
            add("warn", f"{len(groups)} different profile photos",
                "; ".join(" + ".join(p.name for p in g) for g in groups))

    places = {}
    for p in ours:
        if p.location:
            places.setdefault(match.fold(p.location), []).append(f"{p.location} ({p.name})")
    if len(places) > 1:
        add("warn", "Profiles give different locations", "; ".join(v[0] for v in places.values()))
    elif len(places) == 1:
        add("good", f"One location: {next(iter(places.values()))[0].split(' (')[0]}")

    handles: dict[str, list[str]] = {}
    for r in rows:
        if r["status"] in ("confirmed", "probably"):
            on = handles.setdefault(r["username"].casefold(), [])
            if r["name"] not in on:
                on.append(r["name"])
    if len(handles) > 1:
        add("info", "Different handles on different platforms",
            "; ".join(f"@{h} on {', '.join(v)}" for h, v in handles.items()))

    for p in ours:
        days = _days_since(p.last_active, now)
        if days is not None and days >= DORMANT_AFTER.days:
            add("warn", f"{p.name} looks dormant", f"Last public post {days} days ago")

    missing = [r["name"] for r in rows if r["status"] == "probably"]
    if missing:
        add("warn", "Probably yours, but not on your website",
            f"Link these from {website.domain} and add them to sameAs: {', '.join(missing)}")
    for r in rows:
        if r["status"] == "dead_link":
            add("warn", f"Your website links to a {r['name']} profile that doesn't exist", r["url"])
    taken = [f"{r['name']} (@{r['username']})" for r in rows if r["status"] == "taken" and r["big"]]
    if taken:
        add("warn", "Your handle is taken by accounts with no link to you",
            "Possible squatters or impersonators: " + ", ".join(taken))
    free = [r["name"] for r in rows if r["status"] == "free" and r["big"]]
    if free:
        add("info", "Free to claim", ", ".join(free))
    return out


def jsonld(name: str, url: str, same_as: list[str]) -> str:
    block = {"@context": "https://schema.org", "@type": "Organization", "name": name or None,
             "url": url, "sameAs": same_as}
    block = {k: v for k, v in block.items() if v not in (None, "")}
    return '<script type="application/ld+json">\n' + json.dumps(block, indent=2) + "\n</script>"


# ---------------------------------------------------------------------- run --

def new_id() -> str:
    return secrets.token_urlsafe(8)


async def run(brand_name: str, handles: list[str], website_url: str, sites: dict[str, Site],
              client: httpx.AsyncClient, conn=None, *, big_only: bool = True) -> AsyncIterator[tuple[str, dict]]:
    """The whole report, as a stream of ``(event, data)`` for the page to show live.

    Events: ``website``, ``result``, ``details``, then ``report`` (saved, with
    its ``id``).
    """
    handles = [h.strip().lstrip("@") for h in handles if h.strip().lstrip("@")]
    website = await read_website(website_url, sites, client)
    yield "website", website.to_dict()

    results: list[dict] = []
    profiles: dict[tuple[str, str], Profile] = {}
    pending: list[asyncio.Task] = []
    queue: asyncio.Queue = asyncio.Queue()

    async def details(r: dict) -> None:
        p = await fetch_profile(r["site"], r["name"], r["username"], r["url"], client)
        await match.fingerprint(p, client)
        profiles[(r["site"], r["username"])] = p
        await queue.put(("details", p.to_dict()))

    def take(result: check.Result, username: str) -> dict:
        r = result.to_dict() | {"username": username}
        results.append(r)
        if r["status"] == "found":
            pending.append(asyncio.create_task(details(r)))
        return r

    for handle in handles:
        async for result in check.search(handle, sites, client, conn=conn, big_only=big_only):
            yield "result", take(result, handle)
            while not queue.empty():
                yield queue.get_nowait()

    # Profiles the website links to under another handle, or on smaller sites.
    asked = {(r["site"], r["username"].casefold()) for r in results}
    health = store.health(conn) if conn is not None else {}
    for linked in website.profiles:
        if (linked["site"], linked["username"].casefold()) in asked or linked["site"] not in sites:
            continue
        site = sites[linked["site"]]
        probe, why = check.choose_probe(site, health.get(site.key))
        if probe is None:
            continue
        result = await check.check_one(site, probe, linked["username"], client)
        yield "result", take(result, linked["username"])

    if pending:
        _, late = await asyncio.wait(pending, timeout=30)
        for task in late:
            task.cancel()
    while not queue.empty():
        yield queue.get_nowait()

    report = build(brand_name, handles, website, results, profiles)
    report["id"] = new_id()
    report["created_at"] = store.now_iso()
    report["scope"] = "big" if big_only else "all"
    if conn is not None:
        store.save_report(conn, report["id"], report)
    yield "report", report
