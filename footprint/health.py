"""The daily health check: does each site's recipe still tell the truth?

Sites redesign, add bot walls, or vanish, and a recipe that worked last month
quietly starts saying "found" for everyone. Sherlock relies on volunteers to
notice; this tests every recipe once a day, on the machine doing the searching:

- its **known account** (a name each list records as existing) should be found;
- a **made-up name** (twelve random letters) should not be.

A recipe that fails is not used. A site with no working recipe is set aside --
skipped in searches and listed as "not checked" -- until a later run passes.

The check runs by itself, in the background, on the first use each day. It
asks gently (a few sites at a time) and refuses to overwrite yesterday's
verdicts when most sites fail at once, which means the network is down rather
than the sites broken.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import sqlite3
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from . import store
from .check import USABLE, check_one
from .manifest import Probe, Site

logger = logging.getLogger(__name__)

TIMEOUT = 12.0
CONCURRENCY = 8
PER_HOST = 2
EVERY = timedelta(hours=24)
# More than this share failing at once means our connection, not the sites.
NETWORK_TROUBLE = 0.6

STATES = {
    "working": "Works: finds a known account and rejects a made-up name",
    "partly": "Rejects made-up names (no known account to test it with)",
    "false_found": "Says made-up names exist",
    "misses_real": "Can't see an account that exists",
    "changed": "Its pages no longer match the recipe",
    "blocked": "Blocks automated checks",
    "too_slow": "Too slow to answer",
    "unreachable": "Couldn't connect",
}


def made_up_name() -> str:
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(12))


def classify(real, fake) -> tuple[str, str]:
    """A recipe's state from its two test results (``real`` may be None)."""
    tried = [r for r in (real, fake) if r is not None]
    if any(r.outcome == "timeout" for r in tried):
        return "too_slow", STATES["too_slow"]
    if any(r.outcome == "error" for r in tried):
        return "unreachable", STATES["unreachable"]
    if fake is not None and fake.status == "found":
        return "false_found", f"{STATES['false_found']} ({fake.reason})"
    if real is not None and real.status == "not_found":
        return "misses_real", f"{STATES['misses_real']} ({real.reason})"
    unclear = next((r for r in tried if r.status == "unclear"), None)
    if unclear is not None:
        reason = unclear.reason.lower()
        state = "blocked" if ("bot check" in reason or "refused" in reason) else "changed"
        return state, f"{STATES[state]} ({unclear.reason})"
    if real is None:
        return "partly", STATES["partly"]
    return "working", STATES["working"]


async def try_probe(site: Site, probe: Probe, client: httpx.AsyncClient,
                     timeout: float = TIMEOUT) -> tuple[str, str]:
    known = next((k for k in probe.known if probe.accepts(k)), None)
    fake_name = made_up_name()
    fake = await check_one(site, probe, fake_name, client, timeout) if probe.accepts(fake_name) else None
    real = await check_one(site, probe, known, client, timeout) if known else None
    if real is None and fake is None:
        return "partly", "Nothing it could be tested with"
    return classify(real, fake)


@dataclass
class Progress:
    running: bool = False
    done: int = 0
    total: int = 0
    started_at: Optional[str] = None
    note: Optional[str] = None
    counts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dict(running=self.running, done=self.done, total=self.total,
                    started_at=self.started_at, note=self.note, counts=self.counts)


async def run(sites: dict[str, Site], conn: sqlite3.Connection, client: httpx.AsyncClient, *,
              progress: Optional[Progress] = None, concurrency: int = CONCURRENCY,
              timeout: float = TIMEOUT) -> Progress:
    """Test every recipe of every site, and save the verdicts."""
    progress = progress or Progress()
    jobs = [(site, probe) for site in sites.values() for probe in site.probes]
    progress.running, progress.done, progress.total = True, 0, len(jobs)
    progress.started_at = store.now_iso()
    gate = asyncio.Semaphore(concurrency)
    hosts: dict[str, asyncio.Semaphore] = {}

    async def one(site: Site, probe: Probe):
        host_gate = hosts.setdefault(site.key, asyncio.Semaphore(PER_HOST))
        async with host_gate, gate:
            try:
                state, detail = await try_probe(site, probe, client, timeout)
            except Exception as exc:  # one odd site must not stop the rest
                logger.debug("health check of %s failed: %s", probe.id, exc)
                state, detail = "unreachable", f"{STATES['unreachable']} ({type(exc).__name__})"
        progress.done += 1
        return site.key, probe.id, state, detail

    try:
        rows = await asyncio.gather(*(one(s, p) for s, p in jobs))
        failing = sum(1 for r in rows if r[2] in ("too_slow", "unreachable"))
        if len(rows) >= 20 and failing / len(rows) > NETWORK_TROUBLE:
            progress.note = (f"{failing} of {len(rows)} checks got no answer, which looks like a "
                             f"network problem rather than broken sites. Kept the previous results.")
        else:
            store.save_health(conn, rows)
            progress.note = None
        progress.counts = summary(sites, store.health(conn))
        store.set_meta(conn, "health_last_run", store.now_iso())
        store.set_meta(conn, "health_summary", json.dumps(progress.to_dict()))
    finally:
        progress.running = False
    return progress


def site_state(site: Site, rows: Optional[dict]) -> tuple[str, str]:
    """One state for a whole site: working if any recipe works."""
    if not rows:
        return "untested", "Not tested yet"
    for probe in site.preferred_probes():
        row = rows.get(probe.id)
        if row is not None and row["state"] in USABLE:
            return row["state"], row["detail"]
    first = rows.get(site.preferred_probes()[0].id) or next(iter(rows.values()))
    return first["state"], first["detail"]


def summary(sites: dict[str, Site], health: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for site in sites.values():
        state, _ = site_state(site, health.get(site.key))
        counts[state] = counts.get(state, 0) + 1
    return counts


def due(conn: sqlite3.Connection, now: Optional[datetime] = None) -> bool:
    last = store.get_meta(conn, "health_last_run")
    if not last:
        return True
    now = now or datetime.now(timezone.utc)
    try:
        return now - datetime.fromisoformat(last) >= EVERY
    except ValueError:
        return True


class Daily:
    """Starts the health check in the background when it is due, at most once at a time."""

    def __init__(self) -> None:
        self.progress = Progress()
        self.task: Optional[asyncio.Task] = None

    def start(self, sites: dict[str, Site], conn: sqlite3.Connection, client: httpx.AsyncClient,
              *, force: bool = False) -> bool:
        if self.progress.running or (self.task is not None and not self.task.done()):
            return False
        if not force and not due(conn):
            return False
        self.progress = Progress(running=True)
        self.task = asyncio.create_task(run(sites, conn, client, progress=self.progress))
        return True

    def last(self, conn: sqlite3.Connection) -> dict:
        """What the most recent finished run found, for the pages to show."""
        raw = store.get_meta(conn, "health_summary")
        data = json.loads(raw) if raw else {}
        data["last_run"] = store.get_meta(conn, "health_last_run")
        return data
