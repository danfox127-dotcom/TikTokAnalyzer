"""The engine: ask every site about a username, and stream back what each says.

Three things make it faster than Sherlock, which waits up to 60 seconds for the
slowest of its sites and prints answers in alphabetical order:

1. **Answers arrive as they happen.** :func:`search` is an async generator that
   yields each site's verdict the moment it is known.
2. **The big platforms go first** (:mod:`footprint.tiers`).
3. **Every site has its own time limit**, learned from how fast it usually
   answers (:func:`footprint.store.speeds`) -- 10 seconds until it is known,
   never more than 12. Sites that keep timing out go in a slow lane.

And it reads less: a site that only needs a status code gets a ``HEAD``
request, and a page is read only until its verdict can no longer change.

Every verdict is a :class:`Verdict` with a confidence and a reason in plain
words -- see :func:`judge`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass
from typing import AsyncIterator, Optional
from urllib.parse import urlparse

import httpx

from . import store, tiers
from .manifest import PLACEHOLDER, USER_AGENT, Probe, Site

logger = logging.getLogger(__name__)

CONCURRENCY = 50
PER_HOST = 4
# Read at most this much of a page. Big enough for the pages that put their
# account data at the very end (TikTok, Instagram), small enough not to stall.
BODY_CAP = 2_000_000

# Bot walls: pages a firewall serves instead of the site. Neither sign can be
# read through them, so they mean "unclear", never "found". Fingerprints from
# Sherlock's sherlock.py, with the dates its maintainers recorded them.
BOT_WALLS = (
    ("Cloudflare", '.loading-spinner{visibility:hidden}body.no-js .challenge-running{display:none}'),  # 2024-05-13
    ("Cloudflare", '<span id="challenge-error-text">'),  # 2024-11-11
    ("Cloudflare", "cf-browser-verification"),
    ("AWS WAF", "AwsWafIntegration.forceRefreshToken"),  # 2024-11-11
    ("PerimeterX", '{return l.onPageView}}),Object.defineProperty(r,"perimeterxIdentifiers",{enumerable:'),  # 2024-04-09
    ("DataDome", "captcha-delivery.com"),
)

# Status codes that mean "won't answer you", not "no such account" -- unless a
# site's recipe says otherwise.
REFUSED = {401, 403, 406, 429, 503, 999}

USABLE = {"working", "partly"}

STATUS_ORDER = ("found", "not_found", "unclear", "cant_exist", "skipped")


@dataclass
class Verdict:
    status: str        # found | not_found | unclear
    confidence: str    # confirmed | likely | "" (for unclear)
    reason: str


@dataclass
class Result:
    """One site's answer, ready to show."""

    site: str
    name: str
    url: str
    status: str                      # found | not_found | unclear | cant_exist | skipped
    confidence: str = ""
    reason: str = ""
    big: bool = False
    ms: Optional[int] = None
    http_status: Optional[int] = None
    probe: Optional[str] = None
    category: Optional[str] = None
    outcome: str = "ok"              # for the speed memory: ok | timeout | error

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- judging --

def _quote(text: str, limit: int = 48) -> str:
    text = " ".join(text.split())
    return f"“{text[:limit]}{'…' if len(text) > limit else ''}”"


def bot_wall(text: str) -> Optional[str]:
    for name, fingerprint in BOT_WALLS:
        if fingerprint in text:
            return name
    return None


def _all_of(probe: Probe) -> bool:
    """WhatsMyName's rule: code *and* text must match. Sherlock's: either does."""
    return probe.source == "whatsmyname"


def _found_sign(probe: Probe, code: int, text: str) -> Optional[str]:
    """Why the page looks like an existing account, or None."""
    if not probe.found_text:
        return None
    if probe.found_codes and code not in probe.found_codes:
        return None
    for t in probe.found_text:
        if t in text:
            return f"shows {_quote(t)}"
    return None


def _missing_sign(probe: Probe, code: int, text: str) -> Optional[str]:
    """Why the page looks like a missing account, or None."""
    text_hit = next((t for t in probe.missing_text if t in text), None)
    if _all_of(probe):
        if probe.missing_codes and code not in probe.missing_codes:
            return None
        if probe.missing_text and not text_hit:
            return None
        return f"says {_quote(text_hit)}" if text_hit else f"answers {code}, its 'no such account' code"
    if text_hit:
        return f"says {_quote(text_hit)}"
    if code in probe.missing_codes:
        return f"answers {code}, its 'no such account' code"
    if probe.missing_if_not_2xx and not 200 <= code < 300 and code not in REFUSED:
        return f"answers {code} instead of a profile"
    return None


def judge(probe: Probe, code: Optional[int], text: str = "", *, error: Optional[str] = None) -> Verdict:
    """Decide what a site's answer means, how sure we are, and say why.

    - **confirmed**: both signs agree -- the page looks like a profile *and*
      not like a "no such account" page, or the other way round.
    - **likely**: the site's recipe has only one sign (Sherlock's), so the
      verdict rests on it alone.
    - **unclear**: an error, a bot wall, a refusal, or a page that matches
      neither sign (or both). Never counted as found.
    """
    if error:
        return Verdict("unclear", "", error)
    if code is None:
        return Verdict("unclear", "", "No answer")
    wall = bot_wall(text)
    if wall:
        return Verdict("unclear", "", f"Blocked by a {wall} bot check")
    found = _found_sign(probe, code, text)
    missing = _missing_sign(probe, code, text)
    if probe.two_sided:
        if found and not missing:
            return Verdict("found", "confirmed", f"Profile page {found}, and no sign of a missing account")
        if missing and not found:
            return Verdict("not_found", "confirmed", f"Site {missing}, and no profile on the page")
        if found and missing:
            return Verdict("unclear", "", "The page shows signs of both an account and no account")
        if code in REFUSED:
            return Verdict("unclear", "", f"The site refused to answer ({code})")
        return Verdict("unclear", "", f"Answered {code} with a page that looks like neither a profile "
                                      f"nor a 'not found' page -- the site may have changed")
    if missing:
        return Verdict("not_found", "likely", f"Site {missing} (this site has only one sign to check)")
    if code in REFUSED:
        return Verdict("unclear", "", f"The site refused to answer ({code})")
    if 200 <= code < 300:
        return Verdict("found", "likely", f"Page answered {code} with no 'not found' message "
                                          f"(this site has only one sign, so not confirmed)")
    return Verdict("unclear", "", f"Answered {code} with nothing recognisable")


class _Scanner:
    """Watches a page arrive and says when reading more can't change the verdict."""

    def __init__(self, probe: Probe, code: int) -> None:
        self.probe = probe
        self.code = code
        self.text = ""
        self._longest = max((len(t) for t in probe.found_text + probe.missing_text), default=0)
        self.seen: set[str] = set()

    def feed(self, chunk: str) -> None:
        start = max(0, len(self.text) - self._longest)
        self.text += chunk
        window = self.text[start:]
        for t in self.probe.found_text + self.probe.missing_text:
            if t not in self.seen and t in window:
                self.seen.add(t)

    def pending(self) -> bool:
        """Could a sign we haven't seen yet still turn up and change the verdict?"""
        p, code = self.probe, self.code
        if not _all_of(p):
            return bool(p.missing_text) and not any(t in self.seen for t in p.missing_text)
        found_live = p.found_text and (not p.found_codes or code in p.found_codes)
        missing_live = p.missing_text and (not p.missing_codes or code in p.missing_codes)
        found_open = found_live and not any(t in self.seen for t in p.found_text)
        missing_open = missing_live and not any(t in self.seen for t in p.missing_text)
        return bool(found_open or missing_open)


# --------------------------------------------------------------- requests --

def _fill(value, username: str):
    if isinstance(value, str):
        return value.replace(PLACEHOLDER, username)
    if isinstance(value, dict):
        return {k: _fill(v, username) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, username) for v in value]
    return value


async def _ask(probe: Probe, username: str, client: httpx.AsyncClient, timeout: float) -> tuple[int, str]:
    """Request the probe and read only as much of the page as the verdict needs."""
    name = probe.username_for(username)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    headers.update(dict(probe.headers))
    kwargs = {}
    if probe.body is not None:
        # Bodies are usually JSON text, so the name is escaped as a JSON string would be.
        kwargs["content"] = probe.body.replace(PLACEHOLDER, json.dumps(name)[1:-1]).encode()
    elif probe.json_body is not None:
        kwargs["json"] = _fill(probe.json_body, name)
    async with client.stream(probe.method, probe.request_url(username), headers=headers,
                             follow_redirects=probe.follow_redirects,
                             timeout=httpx.Timeout(timeout), **kwargs) as resp:
        code = resp.status_code
        scanner = _Scanner(probe, code)
        wants_body = probe.method != "HEAD" and (probe.needs_body or code in REFUSED)
        if wants_body:
            cap = BODY_CAP if probe.needs_body else 65_536  # refusals: enough to name the bot wall
            async for chunk in resp.aiter_text():
                scanner.feed(chunk)
                if len(scanner.text) >= cap or (probe.needs_body and not scanner.pending()):
                    break
        return code, scanner.text


async def check_one(site: Site, probe: Probe, username: str, client: httpx.AsyncClient,
                    timeout: float = store.DEFAULT_TIMEOUT) -> Result:
    """Ask one site about one username."""
    base = dict(site=site.key, name=site.name, url=site.profile_for(username),
                big=tiers.is_big(site.key), probe=probe.id, category=site.category)
    start = time.monotonic()
    code, text, error, outcome = None, "", None, "ok"
    try:
        # httpx's limit applies to each step (connect, each read); this one
        # bounds the whole exchange, so a page that trickles in still stops.
        code, text = await asyncio.wait_for(_ask(probe, username, client, timeout), timeout * 1.5)
    except (asyncio.TimeoutError, httpx.TimeoutException):
        error, outcome = f"No answer within {timeout:g} seconds", "timeout"
    except httpx.InvalidURL:
        error, outcome = "This name doesn't make a valid address on this site", "error"
    except (httpx.HTTPError, UnicodeError, ValueError) as exc:
        error, outcome = f"Couldn't connect ({type(exc).__name__})", "error"
    ms = int((time.monotonic() - start) * 1000)
    v = judge(probe, code, text, error=error)
    return Result(**base, status=v.status, confidence=v.confidence, reason=v.reason,
                  ms=ms, http_status=code, outcome=outcome)


# ----------------------------------------------------------------- search --

@dataclass
class Planned:
    site: Site
    probe: Optional[Probe]
    timeout: float
    lane: str                 # big | more | slow
    skip: Optional[Result] = None


def choose_probe(site: Site, rows: Optional[dict]) -> tuple[Optional[Probe], Optional[str]]:
    """The recipe to use for a site, given the health check's verdicts.

    Two-sided recipes are preferred. One the health check hasn't tested yet is
    used as it stands. When every recipe has failed, the site is set aside.
    """
    ordered = site.preferred_probes()
    if not ordered:
        return None, "No recipe for this site"
    if not rows:
        return ordered[0], None
    for probe in ordered:
        row = rows.get(probe.id)
        if row is None or row["state"] in USABLE:
            return probe, None
    detail = rows[ordered[0].id]["detail"] or rows[ordered[0].id]["state"]
    return None, f"Set aside by the daily health check: {detail}"


def plan(username: str, sites: dict[str, Site], conn: Optional[sqlite3.Connection] = None, *,
         big_only: bool = False, include_nsfw: bool = False) -> list[Planned]:
    """Which sites to ask, with which recipe and time limit, in what order."""
    speed = store.speeds(conn) if conn is not None else {}
    health = store.health(conn) if conn is not None else {}
    out = []
    for site in sites.values():
        big = tiers.is_big(site.key)
        if (big_only and not big) or (site.nsfw and not include_nsfw):
            continue
        s = speed.get(site.key, store.Speed())
        lane = "big" if big else ("slow" if s.slow_lane else "more")
        base = dict(site=site.key, name=site.name, url=site.profile_for(username), big=big,
                    category=site.category)
        probe, why = choose_probe(site, health.get(site.key))
        if probe is None:
            out.append(Planned(site, None, 0, lane,
                               Result(**base, status="skipped", reason=why or "")))
            continue
        if not probe.accepts(username):
            out.append(Planned(site, probe, 0, lane, Result(
                **base, status="cant_exist", probe=probe.id,
                reason="This site doesn't allow names like this one, so it wasn't asked")))
            continue
        out.append(Planned(site, probe, s.timeout, lane))

    lane_order = {"big": 0, "more": 1, "slow": 2}

    def order(p: Planned):
        s = speed.get(p.site.key)
        typical = s.typical_ms if s and s.typical_ms is not None else 1500
        return (lane_order[p.lane], tiers.rank(p.site.key), typical, p.site.key)

    return sorted(out, key=order)


async def search(username: str, sites: dict[str, Site], client: httpx.AsyncClient, *,
                 conn: Optional[sqlite3.Connection] = None, big_only: bool = False,
                 include_nsfw: bool = False, concurrency: int = CONCURRENCY,
                 per_host: int = PER_HOST) -> AsyncIterator[Result]:
    """Every site's verdict on ``username``, yielded the moment each is known.

    Sites skipped without asking (set aside, or names they can't have) come
    first. The rest start in plan order -- big platforms first, fastest next --
    at most ``concurrency`` at once and ``per_host`` per website.
    """
    username = username.strip().lstrip("@")
    planned = plan(username, sites, conn, big_only=big_only, include_nsfw=include_nsfw)
    for p in planned:
        if p.skip:
            yield p.skip

    gate = asyncio.Semaphore(concurrency)
    hosts: dict[str, asyncio.Semaphore] = {}

    async def run(p: Planned) -> Result:
        host = urlparse(p.probe.request_url(username)).hostname or p.site.key
        host_gate = hosts.setdefault(host, asyncio.Semaphore(per_host))
        # The site's own queue first, so waiting on a busy site never holds one
        # of the shared places.
        async with host_gate, gate:
            return await check_one(p.site, p.probe, username, client, p.timeout)

    tasks = [asyncio.ensure_future(run(p)) for p in planned if not p.skip]
    timings: list[tuple[str, Optional[int], str]] = []
    try:
        for next_done in asyncio.as_completed(tasks):
            result = await next_done
            timings.append((result.site, result.ms if result.outcome == "ok" else None, result.outcome))
            yield result
    finally:
        for t in tasks:
            t.cancel()
        if conn is not None:
            store.record_timings(conn, timings)
