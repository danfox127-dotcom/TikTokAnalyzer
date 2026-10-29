"""Faves in the cloud: the same app on Vercel, reading the library in Supabase.

On your Mac, Faves is yours because only you can reach it. In the cloud anyone
could, so the cloud copy asks for the Faves password (``FAVORITES_TOKEN``) once
on each browser, before it shows anything at all. Without that password -- or
without the library's address (``DATABASE_URL``) -- it shows only a page saying
which setting is missing. It never falls back to being open.

The cloud copy does no background work: a function that answers a request and
stops can't watch a folder or wake up every minute. Faves on your Mac keeps
doing that, into the same library -- the "helper" -- importing exports,
reading the phone's inbox, syncing YouTube and filling in any save the cloud
couldn't look up.
"""

from __future__ import annotations

import os

#: Paths anyone may open: the sign-in itself, and what a page needs to draw it
#: or to be added to a home screen. Nothing here reads the library.
OPEN = ("/signin", "/unlock", "/healthz", "/manifest.webmanifest", "/sw.js", "/favicon.ico")
OPEN_PREFIXES = ("/static/",)

#: The settings the cloud copy needs, and what each is.
NEEDS = {
    "DATABASE_URL": "the address of your library in Supabase",
    "FAVORITES_TOKEN": "your Faves password",
}


def active(request=None) -> bool:
    """Whether this is the cloud copy: on Vercel, or told so (``FAVES_CLOUD``).

    Vercel says so twice -- in a setting (``VERCEL``) and on every request it
    passes on (an ``x-vercel-id`` header) -- and either is enough. A header
    can only ever switch the password on, never off.
    """
    if os.environ.get("VERCEL") or os.environ.get("FAVES_CLOUD"):
        return True
    return request is not None and "x-vercel-id" in request.headers


def missing() -> list[str]:
    """Settings the cloud copy can't run without, by name."""
    return [name for name in NEEDS if not os.environ.get(name)]


def is_open(path: str) -> bool:
    return path in OPEN or path.startswith(OPEN_PREFIXES)
