"""Do two accounts belong to the same person or brand? Points, with reasons.

"An account called @marisol.cooks exists on Pinterest" is not the same as
"Marisol's Pinterest". A squatter, a fan page or a stranger with the same name
all look identical to a username check. What tells them apart is what the
profiles say about themselves:

==================================================  ======
Evidence                                             Points
==================================================  ======
One profile links straight to the other              40
Both link to the same outside page                   25
Profile photos match (picture fingerprint)           25
Same display name (near-identical: 5)                15
Bios share distinctive wording                       10
Same self-reported location                           5
==================================================  ======

60 or more: **very likely the same**; 30-59: **possibly**; under 30: **no
evidence**. Every point comes with the sentence that earned it, so the verdict
can always be checked by eye. A different location is noted, never penalised
-- people move, and brands have offices.

The picture fingerprint is a 64-bit "difference hash": the photo shrunk to a
9x8 grey grid, recording whether each square is brighter than its neighbour.
The same photo re-compressed or resized by two platforms keeps nearly the same
fingerprint; different photos don't. It needs Pillow; without it photos are
simply not compared.
"""

from __future__ import annotations

import base64
import difflib
import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Optional
from urllib.parse import urlparse

import httpx

from . import tiers
from .manifest import ALIASES, USER_AGENT
from .profile import Profile

logger = logging.getLogger(__name__)

VERY_LIKELY = 60
POSSIBLY = 30
PHOTO_MATCH_BITS = 10       # of 64 may differ
MAX_PHOTO_BYTES = 3_000_000

# Link pages and platforms: a bare link to one of these says nothing about who
# you are. A link to a page *on* one of them (linktr.ee/marisol) does.
HUBS = {"linktr.ee", "beacons.ai", "lnk.bio", "bio.link", "campsite.bio", "carrd.co",
        "linkin.bio", "stan.store", "allmylinks.com", "solo.to"} | set(tiers.BIG)

STOPWORDS = set("""
about after again also always among and any are around because been before being
best both but can could daily does doing down each even every first for from
get gets have here into just like love make more most much never only other
our ours over posts same she should some such than that the their them then
there these they this those through too under until very want what when where
which while who will with would you your yours official account page welcome
follow follows following followers instagram tiktok youtube twitter
""".split())


@dataclass
class Pair:
    a: str
    b: str
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def band(self) -> str:
        return band(self.score)

    def add(self, points: int, reason: str) -> None:
        self.score = min(100, self.score + points)
        self.reasons.append(f"{reason} (+{points})")

    def to_dict(self) -> dict:
        return dict(a=self.a, b=self.b, score=self.score, band=self.band,
                    reasons=self.reasons, notes=self.notes)


def band(score: int) -> str:
    if score >= VERY_LIKELY:
        return "very_likely"
    if score >= POSSIBLY:
        return "possibly"
    return "no_evidence"


BAND_WORDS = {"very_likely": "Very likely the same", "possibly": "Possibly the same",
              "no_evidence": "No evidence they're the same"}


# --------------------------------------------------------------- normalise --

def fold(text: Optional[str]) -> str:
    """Lower-case, accents and emoji removed, punctuation to spaces."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text.casefold())
    return " ".join(text.replace("_", " ").split())


def link_host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    for prefix in ("www.", "m.", "mobile."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return ALIASES.get(host, host)


def link_key(url: str) -> str:
    """A link reduced to what identifies it: host and path, nothing else."""
    path = urlparse(url).path.rstrip("/").lower()
    return link_host(url) + path


def points_to(link: str, profile: Profile) -> bool:
    """Does this link lead to this profile?"""
    host = link_host(link)
    if host != profile.site and not host.endswith("." + profile.site):
        return False
    name = profile.username.casefold().lstrip("@")
    parsed = urlparse(link)
    parts = [p.casefold().lstrip("@") for p in parsed.path.split("/") if p]
    sub = (parsed.hostname or "").casefold().split(".")[0]
    return name in parts or sub == name or link_key(link) == link_key(profile.url)


def distinctive_links(profile: Profile) -> set[str]:
    out = set()
    for link in profile.links:
        key = link_key(link)
        host = link_host(link)
        if key == host and host in HUBS:
            continue  # a bare platform or link-page address says nothing
        out.add(key)
    return out


def bio_words(text: Optional[str]) -> set[str]:
    text = re.sub(r"https?://\S+", " ", text or "")
    return {w for w in fold(text).split() if len(w) >= 4 and w not in STOPWORDS and not w.isdigit()}


# ----------------------------------------------------------------- photos --

def dhash(image_bytes: bytes) -> Optional[str]:
    """The 64-bit difference hash of a picture, as 16 hex digits."""
    from PIL import Image  # optional: photos aren't compared without Pillow

    with Image.open(io.BytesIO(image_bytes)) as img:
        grey = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        px = grey.tobytes()  # one byte per pixel, row by row
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    ones = bin(bits).count("1")
    if ones < 4 or ones > 60:
        return None  # a plain or blank picture: everything would "match" it
    return f"{bits:016x}"


def thumbnail(image_bytes: bytes, size: int = 96) -> Optional[str]:
    """A small JPEG of the picture as a data: address, so reports need no outside requests."""
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        img.thumbnail((size, size))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def distance(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


async def fingerprint(profile: Profile, client: httpx.AsyncClient) -> None:
    """Download the profile photo once; keep its fingerprint and a thumbnail."""
    if not profile.avatar_url or profile.photo_hash:
        return
    try:
        resp = await client.get(profile.avatar_url, timeout=6.0, follow_redirects=True,
                                headers={"User-Agent": USER_AGENT})
        if resp.status_code != 200 or len(resp.content) > MAX_PHOTO_BYTES:
            return
        profile.photo_hash = dhash(resp.content)
        profile.photo_thumb = thumbnail(resp.content)
    except ImportError:
        profile.sources.setdefault("photo", "not compared: Pillow is not installed")
    except Exception as exc:  # unreadable image or network trouble: just no fingerprint
        logger.debug("photo fingerprint failed for %s: %s", profile.url, exc)


# ---------------------------------------------------------------- scoring --

def _short(text: str, limit: int = 40) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


def score(a: Profile, b: Profile) -> Pair:
    """How much evidence there is that two profiles are the same person or brand."""
    pair = Pair(a.site, b.site)
    if any(points_to(link, b) for link in a.links):
        pair.add(40, f"{a.name} links to their {b.name}")
    elif any(points_to(link, a) for link in b.links):
        pair.add(40, f"{b.name} links to their {a.name}")

    shared = distinctive_links(a) & distinctive_links(b)
    shared = {k for k in shared if not any(points_to("https://" + k, p) for p in (a, b))}
    if shared:
        pair.add(25, f"Both link to {_short(sorted(shared)[0])}")

    if a.photo_hash and b.photo_hash:
        d = distance(a.photo_hash, b.photo_hash)
        if d <= PHOTO_MATCH_BITS:
            pair.add(25, f"Profile photos match ({round(100 * (64 - d) / 64)}% alike)")

    na, nb = fold(a.display_name), fold(b.display_name)
    handle = fold(a.username)
    if na and nb and na != handle:
        if na == nb:
            pair.add(15, f"Same display name: “{_short(a.display_name)}”")
        elif difflib.SequenceMatcher(None, na, nb).ratio() >= 0.8 or \
                (min(len(na), len(nb)) >= 4 and (na in nb or nb in na)):
            pair.add(5, f"Similar display names: “{_short(a.display_name)}” and "
                        f"“{_short(b.display_name)}”")

    wa, wb = bio_words(a.bio), bio_words(b.bio)
    common = wa & wb
    if len(common) >= 3 and len(common) / max(1, len(wa | wb)) >= 0.25:
        pair.add(10, "Bios share the words " + ", ".join(f"“{w}”" for w in sorted(common)[:4]))

    la, lb = fold(a.location), fold(b.location)
    if la and lb:
        if la == lb or la in lb or lb in la:
            pair.add(5, f"Both say they're in {a.location}")
        else:
            pair.notes.append(f"Locations differ: {a.location} ({a.name}) and {b.location} ({b.name})")
    return pair


def _groups(keys: list[str], pairs: Iterable[Pair]) -> list[list[str]]:
    parent = {k: k for k in keys}

    def root(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for p in pairs:
        if p.score >= VERY_LIKELY:
            parent[root(p.a)] = root(p.b)
    groups: dict[str, list[str]] = {}
    for k in keys:
        groups.setdefault(root(k), []).append(k)
    return sorted(groups.values(), key=lambda g: (-len(g), min(tiers.rank(k) for k in g)))


def assess(profiles: list[Profile]) -> dict:
    """Score every pair, group the very-likely ones, and rate each profile
    against the main group.

    Returns ``{"pairs": [...], "groups": [[site, ...]], "profiles": {site:
    {"score", "band", "reasons", "notes", "with"}}}``.
    """
    usable = [p for p in profiles if not p.hidden]
    pairs = [score(a, b) for i, a in enumerate(usable) for b in usable[i + 1:]]
    keys = [p.site for p in usable]
    groups = _groups(keys, pairs) if keys else []
    main = set(groups[0]) if groups and len(groups[0]) > 1 else set()
    by_site = {}
    for p in usable:
        best: Optional[Pair] = None
        for pair in pairs:
            if p.site not in (pair.a, pair.b):
                continue
            other = pair.b if pair.a == p.site else pair.a
            if main and other not in main:
                continue
            if best is None or pair.score > best.score:
                best = pair
        if best is None:
            by_site[p.site] = {"score": 0, "band": "no_evidence", "reasons": [], "notes": [], "with": None}
            continue
        other = best.b if best.a == p.site else best.a
        by_site[p.site] = {"score": best.score, "band": best.band, "reasons": best.reasons,
                           "notes": best.notes, "with": other}
    return dict(pairs=[p.to_dict() for p in pairs if p.score or p.notes], groups=groups,
                main=sorted(main, key=tiers.rank), profiles=by_site)
