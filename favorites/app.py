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

import asyncio
import dataclasses
import json
import logging
import socket
import time
from collections import Counter
from contextlib import asynccontextmanager
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from . import (backfill, blurb, db, explore, google_sync, lengths, looks, museum, tagging,
               thumbnails, transcript, watch)
from . import themes as theme_vocabulary
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
    task = asyncio.create_task(_keep_in_sync())
    try:
        yield
    finally:
        task.cancel()


#: How often the watched folder is looked at, and YouTube is synced.
SCAN_EVERY = 60
YOUTUBE_EVERY = 24 * 3600


def _scan_now() -> list:
    folders = watch.folders_from_env()
    watch.STATUS.folders = [str(f) for f in folders]
    if not folders:
        return []
    conn = db.connect()
    try:
        found = watch.scan(conn, folders)
    finally:
        conn.close()
    watch.STATUS.last_scan = db.now_iso()
    watch.STATUS.found = (found + watch.STATUS.found)[:8]
    return found


async def _fill_in(limit: int = 50) -> None:
    """Titles and pictures for what just arrived: a first batch, straight away."""
    conn = db.connect()
    try:
        await backfill.run(conn, limit, quiet=True)
    finally:
        conn.close()


async def _sync_youtube() -> Optional[dict]:
    conn = db.connect()
    try:
        if not (google_sync.configured() and google_sync.connected(conn)):
            return None
        return await google_sync.sync(conn)
    finally:
        conn.close()


async def _keep_in_sync() -> None:
    """The museum's one background job: watch the folder, sync YouTube daily.

    Both are off until switched on (FAVORITES_WATCH; Google connected), so a
    plain run -- and every test -- does nothing here but sleep.
    """
    log = logging.getLogger("uvicorn.error")
    last_youtube = 0.0
    while True:
        try:
            found = await run_in_threadpool(_scan_now)
            added = sum(f.added for f in found)
            if time.monotonic() - last_youtube > YOUTUBE_EVERY or not last_youtube:
                result = await _sync_youtube()
                last_youtube = time.monotonic()
                added += (result or {}).get("added", 0)
            if added:
                log.info("%s new saves arrived; filling in the first 50", added)
                await _fill_in()
        except asyncio.CancelledError:
            raise
        except Exception:  # never let one bad export stop the watching
            log.exception("keeping in sync failed; trying again in a minute")
        await asyncio.sleep(SCAN_EVERY)


app = FastAPI(title="Faves", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=str(HERE / "templates"))
templates.env.globals["platform_label"] = platform_label
# canonical_url identifies an item; it is not necessarily a link that opens.
templates.env.globals["browsable_url"] = browsable_url


def clock(seconds) -> str:
    """A video's length the way video sites print it: 0:26, 4:05, 1:28:55."""
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return ""
    if total <= 0:
        return ""
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


templates.env.filters["clock"] = clock
templates.env.globals["hook_badge"] = museum.hook_badge
templates.env.globals["look"] = looks.look
templates.env.globals["season_look"] = looks.SEASON_LOOK
templates.env.globals["tones"] = looks.TONES
templates.env.globals["shape"] = looks.shape


def initials(name) -> str:
    """Two letters for a picture that failed to load: "Marisol Cooks" -> "MC"."""
    words = [w for w in str(name or "").lstrip("@").replace(".", " ").replace("_", " ").split() if w]
    return "".join(w[0] for w in words[:2]).upper() or "?"


templates.env.filters["initials"] = initials
templates.env.globals["headline"] = blurb.headline
templates.env.globals["blurb"] = blurb.blurb
templates.env.globals["detail"] = blurb.detail
templates.env.globals["clean_caption"] = blurb.clean_caption
templates.env.filters["upto"] = blurb.trim
templates.env.globals["theme_names"] = list(theme_vocabulary.THEMES)


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
    if not unlocked(request):
        raise HTTPException(status_code=401, detail="bad or missing token")


#: Set on a phone's browser once you type the password on the Keep page, so
#: saving from that browser -- and Android's share sheet -- needs no header.
KEY_COOKIE = "favorites_key"


def unlocked(request: Request) -> bool:
    """True when this request may save: no password set, or it carries it --
    as a Bearer header, a ?token=, or the cookie the Keep page sets."""
    expected = os.environ.get("FAVORITES_TOKEN")
    if not expected:
        return True
    header = request.headers.get("authorization", "")
    supplied = header[7:] if header.lower().startswith("bearer ") else (
        request.query_params.get("token") or request.cookies.get(KEY_COOKIE) or ""
    )
    return secrets.compare_digest(supplied, expected)


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
        # One more page view, for the one fact no quick lookup carries.
        duration = None
        if item.resolve_status == "ok":
            duration = await lengths.fetch(dataclasses.asdict(item), client)

    if not item.canonical_url:
        raise HTTPException(status_code=400, detail=item.resolve_error or "no URL found")

    # The transcript library is synchronous and does network I/O, so it goes to
    # the threadpool rather than stalling the event loop.
    text = await run_in_threadpool(transcript.fetch, item.platform, item.external_id)

    payload = dataclasses.asdict(item)
    payload["note"] = (note or "").strip() or None
    payload["transcript"] = text
    payload["resolved_at"] = db.now_iso()
    payload["duration"] = duration
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
        "on_this_day": museum.on_this_day(conn, now=now),
        "rooms": museum.rooms(conn, limit=8, now=now),
        "creators": museum.creators_shelf(conn, now=now),
        "season": museum.season_room(conn, now=now),
        "week": museum.week_digest(conn, now=now),
        "year_now": now.strftime("%Y"),
        "digest": museum.digest(conn, days=30, now=now),
        "browse": museum.browse(conn),
        "total": db.count(conn),
        # A freshly backfilled library is mostly dated URLs. Without saying so,
        # an empty-looking front page over a four-figure item count reads as a
        # bug rather than as work still in progress.
        "pending": museum.pending_count(conn),
        "reminders": watch.reminders(conn),
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
        "pull": explore.pull(f, facets, items) if items else [],
        "own_search": True,
        "sorts": explore.SORTS,
        "q": f.q,
        "total": total,
        "has_next": f.page * explore.PAGE_SIZE < found,
    })


@app.get("/topics", response_class=HTMLResponse)
def rooms_page(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    """Every topic, biggest first."""
    found = museum.rooms(conn)
    undefined = conn.execute(
        f"SELECT count(*) FROM items WHERE {museum.RESOLVED}"
        " AND json_array_length(coalesce(nullif(themes, ''), '[]')) = 0").fetchone()[0]
    return templates.TemplateResponse(request, "rooms.html", {
        "rooms": found, "undefined": undefined, "q": "", "total": db.count(conn),
        "season": museum.season_room(conn),
    })


@app.get("/topics/sort", response_class=HTMLResponse)
def tidy_page(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    """Sort things out: teach the hashtags it doesn't know, settle its guesses."""
    report = theme_vocabulary.report(conn, top=24)
    ids = {i for t, _ in report["unrecognised_hashtags"] for i in report["examples"][t][:3]}
    hunch_ids, hunch_count = db.hunches(conn, limit=12)
    ids |= set(hunch_ids)
    by_id = {i["id"]: i for i in db.rows_to_dicts(conn.execute(
        f"SELECT * FROM items WHERE id IN ({','.join('?' * len(ids)) or 'NULL'})",
        tuple(ids)).fetchall())}
    unknown = []
    for tag, n in report["unrecognised_hashtags"]:
        # The rooms its saves are already in are the likeliest answers.
        near = Counter(t for i in report["examples"][tag] for t in (by_id.get(i) or {}).get("themes", []))
        unknown.append({"tag": tag, "count": n,
                        "saves": [by_id[i] for i in report["examples"][tag][:3] if i in by_id],
                        "likely": [t for t, _ in near.most_common(3)]})
    undefined = report["items"] - report["themed"]
    return templates.TemplateResponse(request, "tidy.html", {
        "unknown": unknown, "hunches": [by_id[i] for i in hunch_ids if i in by_id],
        "hunch_count": hunch_count, "undefined": undefined,
        "taught": db.taught_count(conn), "q": "", "total": db.count(conn),
    })


# The old names (rooms, placards) still lead somewhere, for bookmarks and
# Shortcuts made before the rename.
OLD_PAGES = {"/rooms": "/topics", "/rooms/tidy": "/topics/sort", "/placards": "/notes"}


def _moved(new: str):
    def go(request: Request):
        q = request.url.query
        return RedirectResponse(new + (f"?{q}" if q else ""), status_code=301)
    return go


for _old, _new in OLD_PAGES.items():
    app.add_api_route(_old, _moved(_new), methods=["GET"], include_in_schema=False)


@app.post("/topics/teach")
@app.post("/rooms/teach", include_in_schema=False)
def teach(tag: str = Form(""), theme: str = Form(""), conn: sqlite3.Connection = Depends(get_db)):
    """Teach a hashtag its topic -- or that it is no subject at all."""
    db.teach_tag(conn, tag, theme or None)
    return RedirectResponse("/topics/sort#hashtags", status_code=303)


def _back(to: str, fallback: str) -> str:
    """Only ever redirect within the app."""
    return to if to.startswith("/") and not to.startswith("//") else fallback


@app.post("/item/{item_id}/rooms")
def choose_rooms(
    item_id: int, room: list[str] = Form([]), whole_creator: int = Form(0),
    reset: int = Form(0), confirm: int = Form(0), next: str = Form(""),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Put a save in the topics you chose (and, if asked, all its creator's saves)."""
    if db.get_item(conn, item_id) is None:
        raise HTTPException(status_code=404, detail="no such item")
    if reset:
        db.reset_rooms(conn, item_id)
    else:
        db.set_rooms(conn, item_id, room, whole_creator=bool(whole_creator), confirm=bool(confirm))
    return RedirectResponse(_back(next, f"/item/{item_id}"), status_code=303)


@app.get("/surprise")
def surprise(conn: sqlite3.Connection = Depends(get_db)):
    """One save at random -- the museum's "show me something"."""
    row = conn.execute(
        f"SELECT id FROM items WHERE {museum.RESOLVED} ORDER BY random() LIMIT 1").fetchone()
    return RedirectResponse(f"/item/{row['id']}?surprise=1" if row else "/", status_code=303)


# ---- keeping a link from the phone -------------------------------------------

@app.get("/keep", response_class=HTMLResponse)
def keep_page(request: Request, error: str = "", conn: sqlite3.Connection = Depends(get_db)):
    """Paste a link and keep it: the way in that needs no Shortcut."""
    return templates.TemplateResponse(request, "keep.html", {
        "locked": not unlocked(request), "error": error,
        "has_password": bool(os.environ.get("FAVORITES_TOKEN")),
        "remembered": bool(request.cookies.get(KEY_COOKIE)),
        "q": "", "total": db.count(conn), "nav": "keep",
    })


@app.post("/keep")
async def keep_link(request: Request, url: str = Form(""), note: str = Form(""),
                    conn: sqlite3.Connection = Depends(get_db)):
    if not unlocked(request):
        return RedirectResponse("/keep", status_code=303)
    shared = url.strip()
    if not extract_url(shared):
        return RedirectResponse("/keep?error=no-link", status_code=303)
    try:
        result = await capture(shared, note.strip() or None, conn)
    except HTTPException:
        return RedirectResponse("/keep?error=failed", status_code=303)
    return RedirectResponse(f"/item/{result['id']}?saved=1", status_code=303)


@app.post("/unlock")
def unlock(request: Request, password: str = Form(""), next: str = Form("/keep")):
    """Remember the password on this browser for a year, so it can save."""
    expected = os.environ.get("FAVORITES_TOKEN") or ""
    if not expected or not secrets.compare_digest(password.strip(), expected):
        return RedirectResponse("/keep?error=password", status_code=303)
    resp = RedirectResponse(_back(next, "/keep"), status_code=303)
    resp.set_cookie(KEY_COOKIE, expected, max_age=365 * 24 * 3600, httponly=True,
                    samesite="lax", secure=request.url.scheme == "https")
    return resp


@app.post("/lock")
def lock():
    """Forget the password on this browser."""
    resp = RedirectResponse("/keep", status_code=303)
    resp.delete_cookie(KEY_COOKIE)
    return resp


def _trail(raw: str) -> list[int]:
    """The saves a wander has just passed through, newest last, at most eight.
    Anything that is not a plain id is dropped rather than obeyed."""
    ids = [int(x) for x in raw.split(",") if x.strip().isdigit()]
    return ids[-WANDER_TRAIL:]


WANDER_TRAIL = 8


@app.get("/wander")
def wander_start(conn: sqlite3.Connection = Depends(get_db)):
    """Start a wander from any save."""
    row = conn.execute(
        f"SELECT id FROM items WHERE {museum.RESOLVED} ORDER BY random() LIMIT 1").fetchone()
    return RedirectResponse(f"/item/{row['id']}?via=a+surprise" if row else "/", status_code=303)


@app.get("/wander/{item_id}")
def wander(item_id: int, trail: str = Query("", max_length=200),
           conn: sqlite3.Connection = Depends(get_db)):
    """Follow one of this save's threads somewhere you have not just been."""
    row = db.get_item(conn, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="no such item")
    path = _trail(trail) + [item_id]
    nxt, via = museum.wander_next(conn, db.rows_to_dicts([row])[0], path)
    if nxt is None:
        return RedirectResponse(f"/item/{item_id}", status_code=303)
    query = urlencode({"trail": ",".join(map(str, path[-WANDER_TRAIL:])), "via": via})
    return RedirectResponse(f"/item/{nxt['id']}?{query}", status_code=303)


@app.get("/year", response_class=HTMLResponse)
def year_now(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    return year_page(request, datetime.now(timezone.utc).strftime("%Y"), conn)


@app.get("/year/{year}", response_class=HTMLResponse)
def year_page(request: Request, year: str, conn: sqlite3.Connection = Depends(get_db)):
    """A year of saves in a few playful numbers."""
    if not (year.isdigit() and len(year) == 4):
        raise HTTPException(status_code=404, detail="no such year")
    review = museum.year_review(conn, year)
    if review is None:
        if year == datetime.now(timezone.utc).strftime("%Y"):
            return templates.TemplateResponse(request, "year.html", {
                "review": None, "year": year, "q": "", "total": db.count(conn)})
        raise HTTPException(status_code=404, detail="nothing saved that year")
    return templates.TemplateResponse(request, "year.html", {
        "review": review, "year": year, "q": "", "total": db.count(conn)})


@app.get("/suggest.json")
def suggest(q: str = Query("", max_length=200), conn: sqlite3.Connection = Depends(get_db)):
    """What the search box offers as you type: saves, rooms and hashtags, creators, dates.

    Every group is a way into the full search, so a word becomes a filter in
    one tap. Three of each at most -- this is a doorway, not the results.
    """
    q = q.strip()
    if len(q) < 2:
        return JSONResponse({"q": q, "groups": []})
    like = f"%{q}%"
    groups = []

    saves = explore.results(conn, explore.Filters(q=q, sort="relevance"))[0][:3]
    if saves:
        groups.append({"title": "Saves", "rows": [{
            "kind": "item", "label": i.get("title") or browsable_url(i),
            "sub": " · ".join(x for x in (i.get("creator_name") or i.get("creator_handle"),
                                           platform_label(i["platform"])) if x),
            "href": f"/item/{i['id']}",
            "thumb": f"/thumb/{i['id']}" if i.get("thumbnail_url") else None,
        } for i in saves]})

    rooms = conn.execute(
        "SELECT j.value AS v, count(*) AS n FROM items, json_each(items.themes) j"
        " WHERE j.value LIKE ? GROUP BY v ORDER BY n DESC LIMIT 2", (like,)).fetchall()
    tags = conn.execute(
        "SELECT j.value AS v, count(*) AS n FROM items, json_each(items.tags) j"
        " WHERE j.value LIKE ? GROUP BY v HAVING n >= 2 ORDER BY n DESC LIMIT 2",
        (f"%{q.lstrip('#').lower()}%",)).fetchall()
    rows = [{"kind": "room", "label": r["v"], "sub": f"Topic · {r['n']} saves",
             "href": "/search?" + urlencode({"theme": r["v"]})} for r in rooms]
    rows += [{"kind": "tag", "label": "#" + r["v"], "sub": f"Hashtag · {r['n']} saves",
              "href": "/search?" + urlencode({"tag": r["v"]})} for r in tags]
    if rows:
        groups.append({"title": "Topics & hashtags", "rows": rows[:3]})

    creators = conn.execute(
        "SELECT coalesce(creator_handle, creator_name) AS k,"
        " max(coalesce(creator_name, creator_handle)) AS label, count(*) AS n FROM items"
        " WHERE (creator_name LIKE ? OR creator_handle LIKE ?) AND k IS NOT NULL"
        " GROUP BY k ORDER BY n DESC LIMIT 2", (like, like)).fetchall()
    rows = [{"kind": "creator", "label": r["label"], "initials": initials(r["label"]),
             "sub": f"Creator · you have saved {r['n']}",
             "href": "/search?" + urlencode({"creator": r["k"]})} for r in creators]
    day = explore.today_key()
    n = explore.results(conn, explore.Filters(q=q, day=day))[1]
    if n:
        rows.append({"kind": "date", "label": f"“{q}” saved on this day",
                     "sub": f"{explore.day_label(day)} · {n} {'save' if n == 1 else 'saves'}",
                     "href": "/search?" + urlencode({"q": q, "day": day})})
    if rows:
        groups.append({"title": "Creators & dates", "rows": rows[:3]})

    total = explore.results(conn, explore.Filters(q=q))[1]
    return JSONResponse({"q": q, "total": total, "groups": groups,
                         "href": "/search?" + urlencode({"q": q})})


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
        "heading": "Missing a note",
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


@app.get("/notes", response_class=HTMLResponse)
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


@app.post("/notes/{item_id}")
@app.post("/placards/{item_id}", include_in_schema=False)
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
    return RedirectResponse(f"/notes?after={item_id}{suffix}", status_code=303)


@app.get("/item/{item_id}", response_class=HTMLResponse)
def item_page(
    request: Request, item_id: int, saved: int = Query(0),
    trail: str = Query("", max_length=200), via: str = Query("", max_length=120),
    rooms: int = Query(0), surprise: int = Query(0), conn: sqlite3.Connection = Depends(get_db),
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
    room, room_items = museum.same_room(conn, item)
    return templates.TemplateResponse(request, "item.html", {
        "item": item, "related": related, "just_saved": bool(saved),
        "reasons": db.room_reasons(conn, item_id), "rooms_open": bool(rooms),
        "surprise": bool(surprise),
        "hand_filed": conn.execute("SELECT 1 FROM theme_rules WHERE kind = 'item' AND key = ?",
                                   (str(item_id),)).fetchone() is not None,
        "threads": museum.threads(conn, item),
        "room": room, "room_items": room_items,
        # Arrived by wandering: where from, and the way on.
        "via": via.strip(),
        "wander_href": f"/wander/{item_id}" + (f"?{urlencode({'trail': trail})}" if _trail(trail) else ""),
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


# ---- keeping it in sync ------------------------------------------------------

def _on_this_mac(request: Request) -> bool:
    """True for a request from the machine the museum runs on.

    Things that should only happen at the Mac itself -- showing the password,
    signing in to Google -- check this. A phone on the wi-fi is not the Mac.
    """
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1") and "x-forwarded-for" not in request.headers


def _wifi_address() -> Optional[str]:
    """This machine's address on the local network, if it has one."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packet is sent; this just picks the route
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


@app.get("/sync", response_class=HTMLResponse)
def sync_page(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    """Keep it in sync: exports, the watched folder, YouTube, your phone."""
    now = datetime.now(timezone.utc)
    last = watch.last_imports(conn)
    exports = []
    for platform in ("tiktok", "instagram", "youtube"):
        at = last.get(platform)
        exports.append({"platform": platform, "name": watch.NAMES[platform],
                        "days": watch._days_since(at["at"], now) if at else None,
                        "due": bool(at) and watch._days_since(at["at"], now) > watch.DUE_DAYS})
    recent = conn.execute("SELECT filename, platform, imported_at, added, detail FROM imports"
                          " ORDER BY imported_at DESC LIMIT 6").fetchall()
    port = request.url.port or 8000
    token = os.environ.get("FAVORITES_TOKEN")
    wifi = _wifi_address() if token else None
    return templates.TemplateResponse(request, "sync.html", {
        "exports": exports, "recent": [dict(r) | {"detail": json.loads(r["detail"] or "{}")} for r in recent],
        "folders": [str(f) for f in watch.folders_from_env()], "status": watch.STATUS,
        "google": {"configured": google_sync.configured(), "connected": google_sync.connected(conn),
                   "last": google_sync.last_sync(conn)},
        "here": _on_this_mac(request), "token": token,
        "addresses": [f"http://{wifi}:{port}"] if wifi else [],
        "flash": request.query_params.get("done", ""),
        "q": "", "total": db.count(conn),
    })


@app.post("/sync/scan")
async def sync_scan():
    """Look in the watched folder now, instead of waiting a minute."""
    found = await run_in_threadpool(_scan_now)
    if any(f.added for f in found):
        asyncio.create_task(_fill_in())
    return RedirectResponse("/sync?done=scanned#folder", status_code=303)


@app.post("/sync/snooze")
def sync_snooze(platform: str = Form(""), next: str = Form("/"),
                conn: sqlite3.Connection = Depends(get_db)):
    watch.snooze(conn, platform)
    return RedirectResponse(_back(next, "/"), status_code=303)


def _mac_only(request: Request) -> None:
    if not _on_this_mac(request):
        raise HTTPException(status_code=403, detail="do this on the Mac Faves runs on")


@app.post("/sync/youtube/connect")
def youtube_connect(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    _mac_only(request)
    if not google_sync.configured():
        return RedirectResponse("/sync#youtube", status_code=303)
    port = request.url.port or 8000
    return RedirectResponse(
        google_sync.start(conn, f"http://localhost:{port}/sync/youtube/callback"), status_code=303)


@app.get("/sync/youtube/callback")
async def youtube_callback(request: Request, code: str = "", state: str = "", error: str = "",
                           conn: sqlite3.Connection = Depends(get_db)):
    _mac_only(request)
    if error or not code:
        return RedirectResponse("/sync?done=youtube-cancelled#youtube", status_code=303)
    try:
        await google_sync.finish(conn, code, state)
        result = await google_sync.sync(conn)
    except (PermissionError, httpx.HTTPError, google_sync.NotConnected):
        return RedirectResponse("/sync?done=youtube-failed#youtube", status_code=303)
    if result["added"]:
        asyncio.create_task(_fill_in())
    return RedirectResponse("/sync?done=youtube-connected#youtube", status_code=303)


@app.post("/sync/youtube/now")
async def youtube_now(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    _mac_only(request)
    try:
        result = await google_sync.sync(conn)
    except (httpx.HTTPError, google_sync.NotConnected):
        return RedirectResponse("/sync?done=youtube-failed#youtube", status_code=303)
    if result["added"]:
        asyncio.create_task(_fill_in())
    return RedirectResponse("/sync?done=youtube-synced#youtube", status_code=303)


@app.post("/sync/youtube/disconnect")
async def youtube_disconnect(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    _mac_only(request)
    await google_sync.disconnect(conn)
    return RedirectResponse("/sync?done=youtube-disconnected#youtube", status_code=303)


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
        "name": "Faves",
        "short_name": "Faves",
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
