"""Where a creator lives on each platform, from their handle alone.

The idea comes from Sherlock's table of profile addresses, cut down to the
platforms Faves knows -- and without its checking: these are links, built
from a pattern, never a lookup. Whether the account exists is for the
person who taps to find out.
"""

from __future__ import annotations

from typing import Iterable, Optional

#: platform -> (name, emoji, profile address with {} for the bare handle)
PROFILES = {
    "tiktok": ("TikTok", "🎵", "https://www.tiktok.com/@{}"),
    "instagram": ("Instagram", "📸", "https://www.instagram.com/{}/"),
    "youtube": ("YouTube", "▶️", "https://www.youtube.com/@{}"),
}


def bare(handle: Optional[str]) -> Optional[str]:
    """``@Marisol.Cooks`` -> ``marisol.cooks``; None for anything that is not
    an @-handle (a Reddit ``u/…``, a Substack name, a display name)."""
    h = (handle or "").strip()
    if not h.startswith("@") or len(h) < 2 or any(c.isspace() for c in h):
        return None
    return h[1:].lower()


def links(handle: Optional[str], saved_platforms: Iterable[str] = ()) -> list[dict]:
    """One link per platform, the ones you have saved them from first."""
    name = bare(handle)
    if not name:
        return []
    saved = set(saved_platforms)
    out = [{"platform": p, "label": label, "emoji": emoji, "href": url.format(name), "saved": p in saved}
           for p, (label, emoji, url) in PROFILES.items()]
    return sorted(out, key=lambda r: not r["saved"])
