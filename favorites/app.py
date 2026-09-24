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
from contextlib import asynccontextmanager
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

from . import db, explore, museum, tagging, thumbnails, transcript
from .resolve import browsable_url, extract_url, platform_label, resolve

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(_: FastAPI):
    # Say which library file this server is reading. Without it, a second
    # library file -- one an import quietly created somewhere else -- is
    # invisible: the page loads fine, it just never shows what was imported.
    # uvicorn's own logger, because it is the one uvicorn prints.
    conn, where = db.connect_announced()
    conn.close()
    logging.getLogger("uvicorn.error").info(where)
    yield


app = FastAPI(title="Favorites", docs_url=None, redoc_url=None, lifespan=lifespan)
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


async def capture(
    shared: str, note: Optional[str], conn: sqlite3.Connection,
    collection: Optional[str] = None,
) -> dict:
    """Resolve a shared link and shelve it. Never raises on a bad link.

    ``collection`` files it under a category in the same motion -- YouTube's
    "save to playlist" and TikTok's "add to collection", without a second step.
    Leaving it out is "just save".
    """
    async with httpx.AsyncClient() as client:
        item = await resolve(shared, client)
        # Fetched now, while the link is fresh -- a TikTok thumbnail link is
        # dead within a day or two, and the picture with it.
        image = await thumbnails.fetch(item.thumbnail_url, client)

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
    if image:
        await run_in_threadpool(thumbnails.store, conn, item_id, image, item.thumbnail_url)
    filed = None
    if isinstance(collection, str) and collection.strip():
        filed = await run_in_threadpool(db.file_under, conn, item_id, collection, payload["resolved_at"])
    return {
        "id": item_id,
        "created": created,
        "title": item.title,
        "platform": item.platform,
        "canonical_url": item.canonical_url,
        "resolve_status": item.resolve_status,
        "has_transcript": bool(text),
        "collection": filed,
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

    result = await capture(shared, data.get("note"), conn, data.get("collection"))
    return JSONResponse(result, status_code=201 if result["created"] else 200)


@app.get("/collections.json")
def collections_json(
    conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_token),
):
    """Your categories, largest first, as plain names.

    Plain names because this feeds an iOS Shortcut's "Choose from List", which
    shows a list of strings as-is and a list of objects as nothing useful.
    """
    return [name for name, _ in db.collection_counts(conn)]


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
        "browse": museum.browse(conn),
        "total": db.count(conn),
        # A freshly backfilled library is mostly dated URLs. Without saying so,
        # an empty-looking front page over a four-figure item count reads as a
        # bug rather than as work still in progress.
        "pending": museum.pending_count(conn),
    })


@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    """Search and filter the whole library. With nothing chosen, it is everything."""
    f = explore.Filters.from_params(request.query_params)
    items, found = explore.results(conn, f)
    facets = explore.facets(conn, f)
    total = db.count(conn)
    noun = ("result", "results") if (f.q or f.narrowing()) else ("save", "saves")
    return templates.TemplateResponse(request, "explore.html", {
        "heading": explore.describe(f, facets),
        "subheading": f"{found} {noun[0] if found == 1 else noun[1]}"
                      + (f" of {total}" if f.narrowing() or f.q else ""),
        "items": items,
        "found": found,
        "filters": f,
        "facets": facets,
        "chips": explore.chips(f, facets),
        "own_search": True,
        "sorts": explore.SORTS,
        "q": f.q,
        "total": total,
        "has_next": f.page * explore.PAGE_SIZE < found,
    })


@app.get("/all")
def all_items(page: int = Query(1, ge=1)):
    """Everything, newest first -- the search page with nothing chosen."""
    return RedirectResponse("/search" + (f"?page={page}" if page > 1 else ""), status_code=307)


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


@app.get("/collection/{name:path}", response_class=HTMLResponse)
def collection(request: Request, name: str, conn: sqlite3.Connection = Depends(get_db)):
    items = db.rows_to_dicts(db.in_collection(conn, name))
    if not items:
        raise HTTPException(status_code=404, detail="no such collection")
    shown = next((c for c in db.collections_for(conn, items[0]["id"])
                  if c.lower() == name.lower()), name)
    return templates.TemplateResponse(request, "list.html", {
        "heading": shown,
        "subheading": f"{len(items)} {'save' if len(items) == 1 else 'saves'} you filed here",
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
        "collections": db.collections_for(conn, item_id),
        "all_collections": [n for n, _ in db.collection_counts(conn)],
        "q": "", "total": db.count(conn),
    })


@app.post("/item/{item_id}/file")
def file_item(
    item_id: int, name: str = Form(""), conn: sqlite3.Connection = Depends(get_db)
):
    """File something you "just saved" under a category after the fact."""
    if db.get_item(conn, item_id) is None:
        raise HTTPException(status_code=404, detail="no such item")
    db.file_under(conn, item_id, name, db.now_iso())
    return RedirectResponse(f"/item/{item_id}", status_code=303)


@app.post("/item/{item_id}/unfile")
def unfile_item(
    item_id: int, name: str = Form(""), conn: sqlite3.Connection = Depends(get_db)
):
    if db.get_item(conn, item_id) is None:
        raise HTTPException(status_code=404, detail="no such item")
    db.unfile(conn, item_id, name)
    return RedirectResponse(f"/item/{item_id}", status_code=303)


@app.post("/item/{item_id}/note")
def update_note(
    item_id: int, note: str = Form(""), conn: sqlite3.Connection = Depends(get_db)
):
    if db.get_item(conn, item_id) is None:
        raise HTTPException(status_code=404, detail="no such item")
    db.set_note(conn, item_id, note.strip())
    return RedirectResponse(f"/item/{item_id}", status_code=303)


@app.get("/thumb/{item_id}")
def thumb(item_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """The kept picture, or the platform's link if none has been kept yet."""
    row = thumbnails.get(conn, item_id)
    if row is not None:
        return Response(row["data"], media_type=row["content_type"], headers={
            "Cache-Control": "private, max-age=86400",
            # Belt and braces: only raster types are ever stored, but nothing
            # served from here should be able to run as a page.
            "Content-Security-Policy": "default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        })
    item = db.get_item(conn, item_id)
    if item is not None and item["thumbnail_url"]:
        return RedirectResponse(item["thumbnail_url"], status_code=302)
    raise HTTPException(status_code=404, detail="no thumbnail")


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
