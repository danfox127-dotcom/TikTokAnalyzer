"""The web app: one capture endpoint and a handful of pages to browse.

Capture is a single ``POST /save`` that takes a URL and an optional note. That
is the whole contract an iOS Shortcut or an Android share target needs, which
is what keeps the friction near zero -- there is no app to open, no field to
fill in, and no folder to choose.

Everything is server-rendered. There is no build step, no bundler and no
JavaScript framework, because the entire point is that this keeps working in
three years when you have forgotten it exists.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from . import db, museum, tagging, transcript
from .resolve import browsable_url, extract_url, platform_label, resolve

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
PAGE_SIZE = 48

app = FastAPI(title="Favorites", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=str(HERE / "templates"))
templates.env.globals["platform_label"] = platform_label
# canonical_url identifies an item; it is not necessarily a link that opens.
templates.env.globals["browsable_url"] = browsable_url


def get_db():
    """One connection per request.

    SQLite connections are not safe to share across threads, and FastAPI runs
    sync endpoints in a threadpool. Opening per request sidesteps the problem
    entirely; against a local file it costs microseconds.
    """
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def require_token(request: Request) -> None:
    """Optional shared-secret gate.

    Unset by default, which is right for something running on your own laptop.
    Set ``FAVORITES_TOKEN`` before putting this on a public address, or the
    save endpoint is an open write to your library.
    """
    expected = os.environ.get("FAVORITES_TOKEN")
    if not expected:
        return
    header = request.headers.get("authorization", "")
    supplied = header[7:] if header.lower().startswith("bearer ") else (
        request.query_params.get("token") or ""
    )
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="bad or missing token")


async def capture(shared: str, note: Optional[str], conn: sqlite3.Connection) -> dict:
    """Resolve a shared link and shelve it. Never raises on a bad link."""
    async with httpx.AsyncClient() as client:
        item = await resolve(shared, client)

    if not item.canonical_url:
        raise HTTPException(status_code=400, detail=item.resolve_error or "no URL found")

    # The transcript library is synchronous and does network I/O, so it goes to
    # the threadpool rather than stalling the event loop.
    text = await run_in_threadpool(transcript.fetch, item.platform, item.external_id)

    payload = dataclasses.asdict(item)
    payload["note"] = (note or "").strip() or None
    payload["transcript"] = text
    payload["resolved_at"] = db.now_iso()
    payload["tags"], payload["terms"] = tagging.enrich(
        title=item.title, description=item.description,
        note=payload["note"], transcript=text,
    )

    item_id, created = await run_in_threadpool(db.upsert_item, conn, payload)
    return {
        "id": item_id,
        "created": created,
        "title": item.title,
        "platform": item.platform,
        "canonical_url": item.canonical_url,
        "resolve_status": item.resolve_status,
        "has_transcript": bool(text),
    }


@app.post("/save")
async def save(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_token),
):
    """Capture a link.

    Accepts JSON or a form post, and takes the URL under any of ``url``,
    ``text`` or ``title`` -- share sheets are inconsistent about which field
    carries the link, and several send it inside a sentence.
    """
    data: dict = {}
    ctype = request.headers.get("content-type", "")
    if "application/json" in ctype:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if not data:
        form = await request.form()
        data = {k: v for k, v in form.items()}
    if not data:
        data = dict(request.query_params)

    shared = ""
    for key in ("url", "text", "link", "title", "shared"):
        value = (data.get(key) or "").strip() if isinstance(data.get(key), str) else ""
        if value and extract_url(value):
            shared = value
            break
    if not shared:
        raise HTTPException(status_code=400, detail="no URL in request")

    result = await capture(shared, data.get("note"), conn)
    return JSONResponse(result, status_code=201 if result["created"] else 200)


@app.get("/share-target")
async def share_target(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_token),
    url: str = Query(""),
    text: str = Query(""),
    title: str = Query(""),
):
    """Android's Web Share Target lands here, then bounces to the saved item.

    It has to be a GET that redirects: the browser opens this as a navigation,
    so returning JSON would leave the person staring at raw text.
    """
    shared = next((v for v in (url, text, title) if v and extract_url(v)), "")
    if not shared:
        return RedirectResponse("/?error=no-url", status_code=303)
    try:
        result = await capture(shared, None, conn)
    except HTTPException:
        return RedirectResponse("/?error=save-failed", status_code=303)
    return RedirectResponse(f"/item/{result['id']}?saved=1", status_code=303)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse(request, "museum.html", {
        "shelves": museum.shelves(conn, now=now),
        "digest": museum.digest(conn, days=30, now=now),
        "total": db.count(conn),
        # A freshly backfilled library is mostly dated URLs. Without saying so,
        # an empty-looking front page over a four-figure item count reads as a
        # bug rather than as work still in progress.
        "pending": museum.pending_count(conn),
    })


@app.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request, q: str = Query(""), conn: sqlite3.Connection = Depends(get_db)
):
    results = db.rows_to_dicts(db.search(conn, q, limit=200)) if q.strip() else []
    return templates.TemplateResponse(request, "list.html", {
        "heading": f"“{q}”" if q else "Search",
        "subheading": f"{len(results)} {'result' if len(results) == 1 else 'results'}" if q else "",
        "items": results,
        "q": q,
        "total": db.count(conn),
    })


@app.get("/all", response_class=HTMLResponse)
def all_items(
    request: Request, page: int = Query(1, ge=1), conn: sqlite3.Connection = Depends(get_db)
):
    total = db.count(conn)
    items = db.rows_to_dicts(db.recent(conn, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE))
    return templates.TemplateResponse(request, "list.html", {
        "heading": "Everything",
        "subheading": f"{total} {'save' if total == 1 else 'saves'}",
        "items": items,
        "q": "",
        "total": total,
        "page": page,
        "has_next": page * PAGE_SIZE < total,
    })


@app.get("/month/{key}", response_class=HTMLResponse)
def month(request: Request, key: str, conn: sqlite3.Connection = Depends(get_db)):
    items = db.rows_to_dicts(conn.execute(
        "SELECT * FROM items WHERE substr(saved_at, 1, 7) = ? ORDER BY saved_at DESC", (key,)
    ).fetchall())
    return templates.TemplateResponse(request, "list.html", {
        "heading": museum._month_title(key),
        "subheading": f"{len(items)} {'save' if len(items) == 1 else 'saves'}",
        "items": items, "q": "", "total": db.count(conn),
    })


@app.get("/creator/{key:path}", response_class=HTMLResponse)
def creator(request: Request, key: str, conn: sqlite3.Connection = Depends(get_db)):
    items = db.rows_to_dicts(conn.execute(
        "SELECT * FROM items WHERE coalesce(creator_handle, creator_name) = ?"
        " ORDER BY saved_at DESC", (key,)
    ).fetchall())
    return templates.TemplateResponse(request, "list.html", {
        "heading": items[0]["creator_name"] or key if items else key,
        "subheading": f"{len(items)} {'save' if len(items) == 1 else 'saves'}",
        "items": items, "q": "", "total": db.count(conn),
    })


@app.get("/unlabelled", response_class=HTMLResponse)
def unlabelled(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    items = db.rows_to_dicts(conn.execute(
        "SELECT * FROM items WHERE note IS NULL OR trim(note) = ''"
        " ORDER BY saved_at DESC LIMIT 200"
    ).fetchall())
    return templates.TemplateResponse(request, "list.html", {
        "heading": "Missing a placard",
        "subheading": "A line about why you kept it is worth more later than it costs now",
        "items": items, "q": "", "total": db.count(conn),
    })


# An item with no extracted terms has a caption of pure emoji and hashtags --
# nothing a person could search for. Those are the ones worth a placard first:
# they are the only items in the library with no findable text at all.
NO_PROSE = "(terms = '[]' OR terms IS NULL)"


def _placard_clause(everything: bool) -> str:
    unlabelled = "(note IS NULL OR trim(note) = '')"
    base = f"resolve_status = 'ok' AND {unlabelled}"
    return base if everything else f"{base} AND {NO_PROSE}"


@app.get("/placards", response_class=HTMLResponse)
def placards(
    request: Request,
    after: int = Query(0),
    all: int = Query(0),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Write a line about one item, then the next.

    One at a time rather than a grid: the point is to get through them, and a
    wall of thumbnails invites deciding which to do rather than doing them.
    """
    clause = _placard_clause(bool(all))
    row = conn.execute(
        f"SELECT * FROM items WHERE {clause} AND id > ? ORDER BY id LIMIT 1", (after,)
    ).fetchone()

    remaining = conn.execute(
        f"SELECT count(*) AS n FROM items WHERE {clause}").fetchone()["n"]
    written = conn.execute(
        "SELECT count(*) AS n FROM items WHERE note IS NOT NULL AND trim(note) != ''"
    ).fetchone()["n"]

    return templates.TemplateResponse(request, "placard.html", {
        "item": db.rows_to_dicts([row])[0] if row else None,
        "remaining": remaining,
        "written": written,
        "after": after,
        "everything": bool(all),
        "q": "", "total": db.count(conn),
    })


@app.post("/placards/{item_id}")
def write_placard(
    item_id: int,
    note: str = Form(""),
    all: int = Form(0),
    conn: sqlite3.Connection = Depends(get_db),
):
    if db.get_item(conn, item_id) is None:
        raise HTTPException(status_code=404, detail="no such item")
    if note.strip():
        db.set_note(conn, item_id, note.strip())
    # Advance past this item either way, so a skip does not loop on it.
    suffix = "&all=1" if all else ""
    return RedirectResponse(f"/placards?after={item_id}{suffix}", status_code=303)


@app.get("/item/{item_id}", response_class=HTMLResponse)
def item_page(
    request: Request, item_id: int, saved: int = Query(0),
    conn: sqlite3.Connection = Depends(get_db),
):
    row = db.get_item(conn, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="no such item")
    item = db.rows_to_dicts([row])[0]
    related = db.rows_to_dicts(conn.execute(
        "SELECT * FROM items WHERE coalesce(creator_handle, creator_name) = ?"
        " AND id != ? ORDER BY saved_at DESC LIMIT 6",
        (item.get("creator_handle") or item.get("creator_name"), item_id),
    ).fetchall())
    return templates.TemplateResponse(request, "item.html", {
        "item": item, "related": related, "just_saved": bool(saved),
        "shared": museum.shared_terms(conn, item),
        "q": "", "total": db.count(conn),
    })


@app.post("/item/{item_id}/note")
def update_note(
    item_id: int, note: str = Form(""), conn: sqlite3.Connection = Depends(get_db)
):
    if db.get_item(conn, item_id) is None:
        raise HTTPException(status_code=404, detail="no such item")
    db.set_note(conn, item_id, note.strip())
    return RedirectResponse(f"/item/{item_id}", status_code=303)


@app.get("/healthz")
def healthz(conn: sqlite3.Connection = Depends(get_db)):
    return {
        "ok": True,
        "items": db.count(conn),
        "transcripts_enabled": transcript.available(),
    }


@app.get("/manifest.webmanifest")
def manifest():
    """Declares the app as an Android share target.

    Once the page is installed to the home screen, this is what puts it in the
    system share sheet -- the Android half of the capture story, with no store
    listing and no native build.
    """
    return JSONResponse({
        "name": "Favorites",
        "short_name": "Favorites",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f1115",
        "theme_color": "#0f1115",
        "icons": [{"src": "/static/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
        "share_target": {
            "action": "/share-target",
            "method": "GET",
            "params": {"title": "title", "text": "text", "url": "url"},
        },
    }, media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    """A service worker exists only because installability requires one."""
    return Response("self.addEventListener('fetch', () => {});\n",
                    media_type="application/javascript")
