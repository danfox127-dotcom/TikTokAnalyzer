"""YouTube playlists, synced by signing in with Google.

Once you connect, every playlist you made comes in by itself, daily: each
video filed into a category named after its playlist, dated from when you
added it -- the same as a Takeout import, with no export to request.

**What Google does not share.** Watch Later and Liked videos have been closed
to apps since 2016. A scheduled Google Takeout (every two months, to Drive,
with the watched folder pointed at it) covers Watch Later.

**The one-time setup** is yours, because this museum is yours rather than a
service: a Google Cloud project with the YouTube Data API switched on, and an
OAuth client of type *Desktop app*. Its ID and secret go in ~/.favorites.env as
``GOOGLE_CLIENT_ID`` and ``GOOGLE_CLIENT_SECRET``. The steps are on the Keep it
in sync page.

Read-only access (``youtube.readonly``). The sign-in is kept as a refresh token
in the library file's ``meta`` table; Disconnect revokes it with Google and
forgets it. Plain ``httpx``, no Google libraries.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
from typing import Optional
from urllib.parse import urlencode

import httpx

from . import db
from .importers import youtube_takeout

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com/youtube/v3"
SCOPE = "https://www.googleapis.com/auth/youtube.readonly"

SOURCE = "youtube-sync"
_TOKEN = "google_refresh_token"
_PENDING = "google_oauth_pending"
_LAST = "google_last_sync"


class NotConnected(Exception):
    pass


def configured() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def connected(conn: sqlite3.Connection) -> bool:
    return bool(db.get_meta(conn, _TOKEN))


def last_sync(conn: sqlite3.Connection) -> Optional[dict]:
    raw = db.get_meta(conn, _LAST)
    return json.loads(raw) if raw else None


def _client() -> tuple[str, str]:
    return os.environ["GOOGLE_CLIENT_ID"], os.environ["GOOGLE_CLIENT_SECRET"]


def start(conn: sqlite3.Connection, redirect_uri: str) -> str:
    """The Google sign-in address to send the browser to (PKCE, offline)."""
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    db.set_meta(conn, _PENDING, json.dumps({"state": state, "verifier": verifier, "redirect": redirect_uri}))
    client_id, _ = _client()
    return AUTH_URL + "?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })


async def finish(conn: sqlite3.Connection, code: str, state: str,
                 client: Optional[httpx.AsyncClient] = None) -> None:
    """Swap the code Google sent back for a refresh token, and keep it."""
    pending = json.loads(db.get_meta(conn, _PENDING) or "{}")
    if not pending or not secrets.compare_digest(pending.get("state", ""), state or ""):
        raise PermissionError("that sign-in didn't start here -- try Connect again")
    client_id, client_secret = _client()
    async with _maybe(client) as c:
        resp = await c.post(TOKEN_URL, data={
            "code": code, "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": pending["redirect"], "grant_type": "authorization_code",
            "code_verifier": pending["verifier"],
        })
    resp.raise_for_status()
    token = resp.json().get("refresh_token")
    if not token:
        raise PermissionError("Google didn't give a lasting sign-in -- try Connect again")
    db.set_meta(conn, _TOKEN, token)
    db.set_meta(conn, _PENDING, None)


async def disconnect(conn: sqlite3.Connection, client: Optional[httpx.AsyncClient] = None) -> None:
    token = db.get_meta(conn, _TOKEN)
    if token:
        try:
            async with _maybe(client) as c:
                await c.post(REVOKE_URL, params={"token": token})
        except httpx.HTTPError:
            pass  # forgotten here either way; it can also be removed at myaccount.google.com
    db.set_meta(conn, _TOKEN, None)
    db.set_meta(conn, _LAST, None)


class _maybe:
    """Use the client passed in (tests), or a fresh one."""
    def __init__(self, client):
        self.client, self.own = client, client is None

    async def __aenter__(self):
        if self.own:
            self.client = httpx.AsyncClient(timeout=20)
        return self.client

    async def __aexit__(self, *exc):
        if self.own:
            await self.client.aclose()


async def _access_token(conn: sqlite3.Connection, c: httpx.AsyncClient) -> str:
    token = db.get_meta(conn, _TOKEN)
    if not token:
        raise NotConnected()
    client_id, client_secret = _client()
    resp = await c.post(TOKEN_URL, data={
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": token, "grant_type": "refresh_token"})
    if resp.status_code in (400, 401):
        # Revoked, or expired (a Google project left in "Testing" drops it
        # after 7 days): forget it, so the page offers Connect again.
        db.set_meta(conn, _TOKEN, None)
        raise NotConnected()
    resp.raise_for_status()
    return resp.json()["access_token"]


async def _pages(c: httpx.AsyncClient, path: str, params: dict, access: str):
    page = None
    while True:
        q = dict(params, maxResults=50, **({"pageToken": page} if page else {}))
        resp = await c.get(f"{API}/{path}", params=q, headers={"Authorization": f"Bearer {access}"})
        resp.raise_for_status()
        body = resp.json()
        for it in body.get("items", []):
            yield it
        page = body.get("nextPageToken")
        if not page:
            return


async def playlists(conn: sqlite3.Connection, client: Optional[httpx.AsyncClient] = None
                    ) -> list[youtube_takeout.Playlist]:
    """Every playlist you made, with each video and when you added it."""
    out = []
    async with _maybe(client) as c:
        access = await _access_token(conn, c)
        async for pl in _pages(c, "playlists", {"part": "snippet", "mine": "true"}, access):
            entries = []
            async for it in _pages(c, "playlistItems",
                                   {"part": "snippet,contentDetails", "playlistId": pl["id"]}, access):
                vid = (it.get("contentDetails") or {}).get("videoId")
                added = (it.get("snippet") or {}).get("publishedAt")
                if vid and youtube_takeout.VIDEO_ID.fullmatch(vid):
                    entries.append((vid, youtube_takeout.parse_timestamp(added)))
            out.append(youtube_takeout.Playlist(
                name=(pl.get("snippet") or {}).get("title") or "Untitled playlist",
                playlist_id=pl["id"], entries=entries))
    return out


async def sync(conn: sqlite3.Connection, client: Optional[httpx.AsyncClient] = None) -> dict:
    """Bring every playlist in. Returns counts, and remembers when it ran."""
    found = await playlists(conn, client)
    stats = youtube_takeout.import_playlists(conn, found, source=SOURCE)
    conn.commit()
    result = {"at": db.now_iso(), "playlists": len(found),
              "videos": sum(len(p.entries) for p in found),
              "added": stats["imported"], "filings": stats["filings"]}
    db.set_meta(conn, _LAST, json.dumps(result))
    return result
