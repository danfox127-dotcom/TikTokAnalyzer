"""What TikTok knows: the summary of your latest export, in plain words.

The summary itself is made when an export is imported
(:func:`favorites.importers.tiktok_export.read_dossier`), and holds only
counts, spans, and the names of devices and companies -- never messages,
comments, IP addresses or contact details. This module reads it back and
puts names to the jargon.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from typing import Optional

from . import rewind
from .museum import MONTH_NAMES

#: What the tracking events apps and websites send TikTok mean, in words.
EVENT_WORDS = {
    "viewcontent": "looked at something", "pageview": "visited a page",
    "addtocart": "added something to a basket", "addtowishlist": "saved something to a wish list",
    "initiatecheckout": "started to check out", "addpaymentinfo": "added payment details",
    "purchase": "bought something", "completepayment": "bought something", "placeanorder": "placed an order",
    "search": "searched", "subscribe": "subscribed", "completeregistration": "signed up",
    "registration": "signed up", "lead": "filled in a form", "submitform": "filled in a form",
    "contact": "got in touch", "download": "downloaded something",
    "installapp": "installed their app", "launchapp": "opened their app", "activateapp": "opened their app",
    "clickbutton": "tapped a button", "login": "logged in",
}


def event_words(name: str) -> str:
    """A tracking event in plain words: "AddToCart" -> "added something to a basket"."""
    key = re.sub(r"[^a-z]", "", (name or "").lower())
    if key in EVENT_WORDS:
        return EVENT_WORDS[key]
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])|_", " ", name or "").strip()
    return spaced.lower() or "something unnamed"


def latest(conn: sqlite3.Connection) -> Optional[dict]:
    """The newest export's summary, with when it was read, or None."""
    row = conn.execute(
        "SELECT made_at, read_at, data FROM dossiers WHERE platform = 'tiktok'"
        " ORDER BY made_at DESC LIMIT 1").fetchone()
    if not row:
        return None
    d = json.loads(row["data"])
    d["made_at"], d["read_at"] = row["made_at"], row["read_at"]
    return d


def when(iso: Optional[str]) -> str:
    """``2024-05-12T…`` -> "May 2024"."""
    if not iso or len(iso) < 7:
        return ""
    return f"{MONTH_NAMES[int(iso[5:7]) - 1]} {iso[:4]}"


def day(iso: Optional[str]) -> str:
    """``2026-11-02T…`` -> "2 November 2026"."""
    if not iso or len(iso) < 10:
        return ""
    return f"{int(iso[8:10])} {MONTH_NAMES[int(iso[5:7]) - 1]} {iso[:4]}"


def your_topics(conn: sqlite3.Connection, limit: int = 8) -> list[str]:
    """Your own top topics, from everything you liked and saved -- to set
    beside the labels TikTok gave advertisers."""
    videos, _ = rewind._videos(conn, "0000", "9999")
    _, _, topics, _ = rewind._mix(videos)
    return [t for t, _ in topics.most_common() if t][:limit]


def page(conn: sqlite3.Connection) -> Optional[dict]:
    """Everything the page says, or None before any export."""
    d = latest(conn)
    if not d:
        return None
    off = d["off_tiktok"]
    words: Counter[str] = Counter()           # Purchase and CompletePayment both say "bought something"
    for event, n in off.get("events", []):
        words[event_words(event)] += n
    off["events"] = [[w, n] for w, n in words.most_common()]
    return {
        **d,
        "entries": sum(r["count"] for r in d["records"]),
        "kinds": len(d["records"]),
        "topics": your_topics(conn),
    }
