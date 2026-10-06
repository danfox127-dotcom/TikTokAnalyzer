"""The web app: a search page whose results fill in live, a brand report, and
the daily health check's findings.

Run it with ``footprint/start.command`` (double-click on a Mac) or::

    uvicorn footprint.app:app --port 8010

It listens on this computer only. Results stream to the page as Server-Sent
Events: one ``result`` per site as it answers, ``details`` as public profiles
are read, then ``match`` and ``timezone`` once everything is in.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import brand, check, health, manifest, match, store, tiers
from . import profile as profile_mod
from .timezone import hint as time_hint

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

DETAILS_WAIT = 25.0


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def create_app(*, sites: Optional[dict] = None, client: Optional[httpx.AsyncClient] = None,
               conn: Optional[sqlite3.Connection] = None, auto_health: bool = True) -> FastAPI:
    """The app. Tests pass their own site list, client and database."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        own_client = client is None
        st = app.state
        st.client = client or httpx.AsyncClient(
            limits=httpx.Limits(max_connections=check.CONCURRENCY + 20, max_keepalive_connections=20))
        st.conn = conn or store.connect()
        st.daily = health.Daily()
        st.auto_health = auto_health
        st.load_error = None
        if sites is not None:
            st.sites = sites
        else:
            try:
                st.sites = await manifest.load(st.client)
            except RuntimeError as exc:
                st.sites, st.load_error = {}, str(exc)
        if st.sites and auto_health:
            st.daily.start(st.sites, st.conn, st.client)
        try:
            yield
        finally:
            if st.daily.task is not None and not st.daily.task.done():
                st.daily.task.cancel()
            if own_client:
                await st.client.aclose()
            if conn is None:
                st.conn.close()

    app = FastAPI(title="Footprint", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    def status(request: Request) -> dict:
        st = request.app.state
        last = st.daily.last(st.conn)
        counts = last.get("counts") or {}
        working = sum(v for k, v in counts.items() if k in check.USABLE)
        set_aside = sum(v for k, v in counts.items() if k not in check.USABLE and k != "untested")
        return dict(sites=len(st.sites), big=sum(1 for k in st.sites if tiers.is_big(k)),
                    working=working, set_aside=set_aside, tested=working + set_aside,
                    last_run=last.get("last_run"), running=st.daily.progress.running,
                    progress=st.daily.progress.to_dict(), load_error=st.load_error)

    def maybe_health(request: Request) -> None:
        st = request.app.state
        if st.sites and st.auto_health:
            st.daily.start(st.sites, st.conn, st.client)

    # ------------------------------------------------------------- pages --

    @app.get("/healthz")
    async def healthz():
        """For start.command: is the server up yet?"""
        return {"ok": True}

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request, u: str = ""):
        return templates.TemplateResponse(request, "search.html",
                                          dict(status=status(request), page="search", u=u))

    @app.get("/brand", response_class=HTMLResponse)
    async def brand_page(request: Request):
        return templates.TemplateResponse(request, "brand.html", dict(status=status(request), page="brand"))

    @app.get("/health", response_class=HTMLResponse)
    async def health_page(request: Request, state: str = ""):
        st = request.app.state
        rows = []
        speeds = store.speeds(st.conn)
        h = store.health(st.conn)
        for site in sorted(st.sites.values(), key=lambda s: (tiers.rank(s.key), s.name.casefold())):
            if site.nsfw:
                continue  # not health-checked, and not listed on a page that may be on a work screen
            site_state, detail = health.site_state(site, h.get(site.key))
            probe, _ = check.choose_probe(site, h.get(site.key))
            checked = max((r["checked_at"] for r in (h.get(site.key) or {}).values()), default=None)
            sp = speeds.get(site.key)
            rows.append(dict(key=site.key, name=site.name, state=site_state, detail=detail,
                             recipe=probe.source if probe else "—", big=tiers.is_big(site.key),
                             two_sided=bool(probe and probe.two_sided), checked=checked,
                             typical_ms=sp.typical_ms if sp else None,
                             timeout=sp.timeout if sp else store.DEFAULT_TIMEOUT,
                             slow=bool(sp and sp.slow_lane), nsfw=site.nsfw))
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["state"]] = counts.get(r["state"], 0) + 1
        if state:
            rows = [r for r in rows if r["state"] == state]
        return templates.TemplateResponse(request, "health.html", dict(
            status=status(request), page="health", rows=rows, counts=counts, state=state,
            states=health.STATES))

    @app.post("/health/run")
    async def health_run(request: Request):
        st = request.app.state
        if st.sites:
            st.daily.start(st.sites, st.conn, st.client, force=True)
        return RedirectResponse("/health", status_code=303)

    @app.get("/health/progress")
    async def health_progress(request: Request):
        return JSONResponse(status(request))

    # ------------------------------------------------------------ search --

    @app.get("/search/stream")
    async def search_stream(request: Request, u: str = Query(..., min_length=1, max_length=100),
                            scope: str = "big", nsfw: int = 0):
        st = request.app.state
        username = u.strip().lstrip("@")
        if not username or re.search(r"[\s/?#]", username):
            raise HTTPException(400, "A username can't contain spaces, slashes, ? or #")
        maybe_health(request)
        big_only = scope != "all"
        planned = check.plan(username, st.sites, st.conn, big_only=big_only, include_nsfw=bool(nsfw))

        async def events() -> AsyncIterator[str]:
            queue: asyncio.Queue = asyncio.Queue()
            profiles: dict[str, profile_mod.Profile] = {}
            started = time.monotonic()

            async def details(r: check.Result) -> None:
                p = await profile_mod.fetch(r.site, r.name, username, r.url, st.client)
                await match.fingerprint(p, st.client)
                profiles[r.site] = p
                await queue.put(("details", p.to_dict()))

            async def produce() -> None:
                tasks: list[asyncio.Task] = []
                counts: dict[str, int] = {}
                try:
                    async for r in check.search(username, st.sites, st.client, conn=st.conn,
                                                big_only=big_only, include_nsfw=bool(nsfw)):
                        counts[r.status] = counts.get(r.status, 0) + 1
                        await queue.put(("result", r.to_dict()))
                        if r.status == "found":
                            tasks.append(asyncio.create_task(details(r)))
                    searched = round(time.monotonic() - started, 1)
                    await queue.put(("searched", dict(seconds=searched, counts=counts)))
                    if tasks:
                        _, late = await asyncio.wait(tasks, timeout=DETAILS_WAIT)
                        for t in late:
                            t.cancel()
                    found = list(profiles.values())
                    assessment = match.assess(found)
                    await queue.put(("match", assessment))
                    group = [p for p in found if p.site in set(assessment["main"])] or found
                    tz = time_hint([t for p in group for t in p.post_times],
                                   [p.name for p in group if p.post_times])
                    await queue.put(("timezone", tz.to_dict()))
                    await queue.put(("done", dict(seconds=round(time.monotonic() - started, 1),
                                                  searched=searched, counts=counts)))
                except Exception as exc:  # tell the page rather than hang it
                    logger.exception("search failed")
                    await queue.put(("failed", dict(message=str(exc))))
                finally:
                    await queue.put(None)

            yield _sse("start", dict(username=username, total=len(planned), scope=scope,
                                     big=[dict(site=p.site.key, name=p.site.name)
                                          for p in planned if p.lane == "big"]))
            worker = asyncio.create_task(produce())
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield _sse(*item)
            finally:
                worker.cancel()

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ------------------------------------------------------------- brand --

    @app.get("/brand/stream")
    async def brand_stream(request: Request, name: str = "", site: str = Query(..., min_length=3),
                           handles: str = Query(..., min_length=1), scope: str = "big"):
        st = request.app.state
        maybe_health(request)
        handle_list = [h for h in re.split(r"[,\s]+", handles) if h.strip().lstrip("@")][:5]

        async def events() -> AsyncIterator[str]:
            try:
                async for kind, data in brand.run(name.strip(), handle_list, site.strip(), st.sites,
                                                  st.client, st.conn, big_only=scope != "all"):
                    yield _sse(kind, data)
            except Exception as exc:
                logger.exception("brand report failed")
                yield _sse("failed", dict(message=str(exc)))

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/brand/report/{report_id}.json")
    async def report_json(request: Request, report_id: str):
        data = store.load_report(request.app.state.conn, report_id)
        if data is None:
            raise HTTPException(404, "No such report")
        return JSONResponse(data)

    @app.get("/brand/report/{report_id}", response_class=HTMLResponse)
    async def report_html(request: Request, report_id: str, download: int = 0,
                          same_as: Optional[list[str]] = Query(None)):
        data = store.load_report(request.app.state.conn, report_id)
        if data is None:
            raise HTTPException(404, "No such report")
        if same_as is not None:
            # Only addresses the report itself found can be chosen.
            allowed = {r["url"] for r in data["rows"]}
            data["same_as"] = [u for u in same_as if u in allowed]
            data["jsonld"] = brand.jsonld(data["brand"]["name"], data["brand"]["website"], data["same_as"])
        resp = templates.TemplateResponse(request, "report.html", dict(r=data))
        if download:
            slug = re.sub(r"[^a-z0-9]+", "-", (data["brand"]["name"] or data["brand"]["domain"]).lower()).strip("-")
            resp.headers["Content-Disposition"] = f'attachment; filename="{slug or "brand"}-report.html"'
        return resp

    return app


app = create_app()
