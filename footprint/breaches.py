"""Has a website itself had a known data breach? From Have I Been Pwned.

Have I Been Pwned (HIBP) keeps a public catalogue of data breaches: which
service was breached, when, how many accounts, and what leaked. Asking it about
one website's domain is free and needs no key -- only the domain is sent. (HIBP
can also say which breaches an *email address* appears in, but that needs a paid
API key, and Footprint doesn't use it.)

HIBP licenses its data under CC BY 4.0: anywhere a result is shown to other
people -- a shared brand report -- it must credit HIBP with a link (``CREDIT``).
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

API = "https://haveibeenpwned.com/api/v3/breaches"
TIMEOUT = 10.0
# HIBP refuses requests without a User-Agent that names the app.
USER_AGENT = "Footprint (github.com/danfox127-dotcom/TikTokAnalyzer)"

CREDIT = "Breach data from Have I Been Pwned"
CREDIT_URL = "https://haveibeenpwned.com/"


def _plain(b: dict) -> dict:
    return {
        "name": b.get("Name"), "title": b.get("Title") or b.get("Name"), "domain": b.get("Domain"),
        "date": b.get("BreachDate"), "added": (b.get("AddedDate") or "")[:10] or None,
        "count": b.get("PwnCount") or 0, "data": list(b.get("DataClasses") or []),
        "verified": bool(b.get("IsVerified")), "fabricated": bool(b.get("IsFabricated")),
        "sensitive": bool(b.get("IsSensitive")), "spam_list": bool(b.get("IsSpamList")),
    }


async def _ask(domain: str, client: httpx.AsyncClient) -> Optional[list[dict]]:
    """The breaches HIBP lists for exactly this domain, or None if it couldn't be asked."""
    try:
        resp = await client.get(API, params={"domain": domain}, timeout=TIMEOUT,
                                headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        if resp.status_code != 200:
            logger.debug("HIBP answered %s for %s", resp.status_code, domain)
            return None
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.debug("HIBP lookup for %s failed: %s", domain, exc)
        return None
    return [_plain(b) for b in data if isinstance(b, dict)] if isinstance(data, list) else None


async def for_domain(domain: str, client: httpx.AsyncClient) -> dict:
    """Known breaches of a website, newest first.

    ``checked`` is False when HIBP couldn't be asked -- never read that as
    "no breaches". A subdomain with none of its own (``shop.brand.com``) is
    also checked under its parent (``brand.com``), where breaches are listed.
    """
    domain = domain.strip().lower().rstrip(".")
    out = {"domain": domain, "checked": False, "breaches": [], "error": None,
           "credit": CREDIT, "credit_url": CREDIT_URL}
    found = await _ask(domain, client)
    if found == [] and domain.count(".") >= 2:
        parent = ".".join(domain.split(".")[-2:])
        from_parent = await _ask(parent, client)
        if from_parent:
            found, out["domain"] = from_parent, parent
    if found is None:
        out["error"] = "Couldn't reach Have I Been Pwned just now."
        return out
    out["checked"] = True
    out["breaches"] = sorted(found, key=lambda b: b["date"] or "", reverse=True)
    for b in out["breaches"]:
        b["summary"] = describe(b)
    return out


def describe(b: dict) -> str:
    """One breach in a line: "Adobe, Oct 2013: 152,445,165 accounts — email addresses, …"."""
    when = ""
    if b.get("date"):
        year, month = b["date"][:4], b["date"][5:7]
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        when = f", {months[int(month) - 1]} {year}" if month.isdigit() and 1 <= int(month) <= 12 else f", {year}"
    leaked = ", ".join(d.lower() for d in b.get("data", []))
    line = f"{b['title']}{when}: {b['count']:,} accounts" + (f" — {leaked}" if leaked else "")
    flags = [w for w, on in (("not verified by HIBP", not b.get("verified")),
                             ("believed fabricated", b.get("fabricated")),
                             ("a spam list", b.get("spam_list"))) if on]
    return line + (f" ({'; '.join(flags)})" if flags else "")
