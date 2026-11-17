"""Can someone send email that appears to come from this domain?

A squatted handle is one way to impersonate a brand; a forged "From" line is
another, and it needs no account at all. Whether inboxes fall for it depends on
three public records the domain's owner publishes in the DNS:

- **MX** -- which servers receive the domain's mail. None means the domain
  doesn't receive email, so an address there probably doesn't work.
- **SPF** -- the list of servers allowed to send mail as the domain.
- **DMARC** -- what receiving inboxes should do with mail that fails the
  check: ``reject`` it, ``quarantine`` it (spam folder), or ``none`` (deliver
  it anyway, and just send the owner a report).

Without a DMARC record, or with ``p=none``, most inboxes deliver a forgery.

The records are read through Google's public DNS-over-HTTPS service, because
Python's standard library can't ask for them. Only the domain name is sent --
never the full address.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Optional

import httpx

DOH = "https://dns.google/resolve"
TIMEOUT = 6.0
_TYPES = {"MX": 15, "TXT": 16}

# Who runs the mail, from the names of the receiving servers.
PROVIDERS = (
    ("google.com", "Google Workspace"), ("googlemail.com", "Google Workspace"),
    ("outlook.com", "Microsoft 365"), ("pphosted.com", "Proofpoint"),
    ("mimecast.com", "Mimecast"), ("protonmail.ch", "Proton Mail"),
    ("zoho.com", "Zoho Mail"), ("zoho.eu", "Zoho Mail"),
    ("messagingengine.com", "Fastmail"), ("icloud.com", "iCloud Mail"),
    ("secureserver.net", "GoDaddy"), ("registrar-servers.com", "Namecheap"),
    ("improvmx.com", "ImprovMX forwarding"), ("forwardemail.net", "Forward Email"),
    ("cloudflare.net", "Cloudflare Email Routing"), ("mailgun.org", "Mailgun"),
    ("amazonaws.com", "Amazon"), ("yandex.net", "Yandex"), ("mxroute.com", "MXroute"),
    ("squarespace-mail.com", "Squarespace"), ("titan.email", "Titan"),
)


@dataclass
class MailCheck:
    domain: str
    verdict: str = "unknown"          # protected | partly | watching | open | no_domain | unknown
    summary: str = ""
    advice: str = ""
    receives_mail: Optional[bool] = None
    provider: Optional[str] = None
    mx: list[str] = field(default_factory=list)
    spf: Optional[str] = None
    dmarc: Optional[str] = None
    dmarc_from: Optional[str] = None   # the domain whose record applies
    policy: Optional[str] = None       # reject | quarantine | none
    pct: int = 100
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _unquote(data: str) -> str:
    """A TXT record as one string. Long ones arrive as several quoted pieces."""
    data = data.strip()
    if data.startswith('"'):
        data = re.sub(r'"\s+"', "", data).strip('"')
    return data


async def _lookup(client: httpx.AsyncClient, name: str, rtype: str) -> tuple[Optional[int], list[str]]:
    """``(status, records)``: status 0 answered, 3 no such name, None the lookup failed."""
    try:
        resp = await client.get(DOH, params={"name": name, "type": rtype}, timeout=TIMEOUT,
                                headers={"Accept": "application/dns-json"})
        if resp.status_code != 200:
            return None, []
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None, []
    status = data.get("Status")
    if status not in (0, 3):
        return None, []
    return status, [_unquote(a.get("data", "")) for a in data.get("Answer") or []
                    if a.get("type") == _TYPES[rtype]]


async def records(client: httpx.AsyncClient, name: str, rtype: str) -> Optional[list[str]]:
    """The records of one type for a name: ``[]`` when there are none, ``None``
    when the lookup itself failed (so "no record" is never guessed)."""
    status, found = await _lookup(client, name, rtype)
    return None if status is None else found


def provider_of(mx: list[str]) -> Optional[str]:
    for host in mx:
        host = host.rstrip(".").lower()
        for suffix, name in PROVIDERS:
            if host == suffix or host.endswith("." + suffix):
                return name
    return None


def parse_dmarc(record: str) -> dict[str, str]:
    """``v=DMARC1; p=reject; pct=50`` -> ``{"v": "DMARC1", "p": "reject", "pct": "50"}``."""
    out = {}
    for part in record.split(";"):
        key, sep, value = part.partition("=")
        if sep:
            out[key.strip().lower()] = value.strip()
    return out


def _parents(domain: str) -> list[str]:
    """``mail.shop.example.com`` -> itself, then each parent down to two labels.
    A subdomain without its own DMARC record inherits its parent's."""
    labels = domain.split(".")
    return [".".join(labels[i:]) for i in range(0, max(1, len(labels) - 1))]


def judge(check: MailCheck) -> MailCheck:
    """Fill in the verdict, the plain-words summary and the advice."""
    d = check.domain
    if check.dmarc is None:
        check.verdict = "open"
        check.summary = (f"Nothing tells inboxes to refuse fake email from @{d}. Anyone can send "
                         f"a message that appears to come from it, and most inboxes will deliver it.")
        check.advice = ("Ask whoever runs this domain's email to publish a DMARC record: start with "
                        "p=none to collect reports, then move to quarantine or reject.")
    elif check.policy == "none":
        check.verdict = "watching"
        check.summary = (f"@{d} collects reports about fake email but tells inboxes to deliver it "
                         f"anyway (its DMARC policy is “none”).")
        check.advice = ("Once the reports show only your real senders, move the DMARC policy from "
                        "none to quarantine or reject.")
    elif check.policy in ("reject", "quarantine"):
        action = "refused" if check.policy == "reject" else "sent to spam"
        if check.pct < 100:
            check.verdict = "partly"
            check.summary = (f"Fake email claiming to be from @{d} is {action} only {check.pct}% of "
                             f"the time; the rest is delivered.")
            check.advice = "Raise the DMARC percentage (pct) to 100 once you're confident in it."
        else:
            check.verdict = "protected"
            check.summary = f"Protected: email that fakes an @{d} sender is {action}."
    else:
        check.verdict = "open"
        check.summary = f"@{d} has a DMARC record, but without a usable policy, so fakes are delivered."
        check.advice = "Ask whoever runs this domain's email to fix the DMARC record's p= value."

    if check.spf is None:
        check.notes.append("It doesn't publish which servers may send its mail (no SPF record).")
    elif re.search(r"(^|\s)\+?all\b", check.spf):
        check.notes.append("Its SPF record allows any server at all to send as it (+all), "
                           "which defeats the point.")
    if check.receives_mail is False:
        check.notes.append("No mail servers are listed for this domain, so an address here "
                           "probably can't receive email.")
    return check


async def check(domain: str, client: httpx.AsyncClient) -> MailCheck:
    """Read a domain's mail records and say whether its email can be faked."""
    domain = domain.strip().lower().rstrip(".")
    out = MailCheck(domain=domain)
    mx_status, mx = await _lookup(client, domain, "MX")
    if mx_status == 3:
        out.verdict = "no_domain"
        out.receives_mail = False
        out.summary = f"{domain} doesn't exist, so no email address there works."
        return out
    txt = await records(client, domain, "TXT")
    if mx_status is None or txt is None:
        out.summary = "Couldn't look up this domain's mail records just now."
        return out
    # "0 ." is the standard way to say "this domain takes no mail".
    out.mx = [m.split()[-1].rstrip(".") for m in mx if m.split() and m.split()[-1] != "."]
    out.receives_mail = bool(out.mx)
    out.provider = provider_of(out.mx)
    out.spf = next((t for t in txt if t.lower().startswith("v=spf1")), None)

    for i, name in enumerate(_parents(domain)):
        found = await records(client, "_dmarc." + name, "TXT")
        if found is None:
            out.summary = "Couldn't look up this domain's mail records just now."
            return out
        record = next((t for t in found if t.lower().startswith("v=dmarc1")), None)
        if record:
            tags = parse_dmarc(record)
            out.dmarc, out.dmarc_from = record, name
            # A parent's record applies to subdomains through sp=, when it has one.
            policy = (tags.get("sp") if i > 0 and tags.get("sp") else tags.get("p") or "").lower()
            out.policy = policy if policy in ("reject", "quarantine", "none") else None
            try:
                out.pct = max(0, min(100, int(tags.get("pct", "100"))))
            except ValueError:
                out.pct = 100
            break
    return judge(out)
