"""Footprint's memory: one SQLite file in ``~/.footprint`` (or ``$FOOTPRINT_HOME``).

It remembers three things between runs:

- **How fast each site answers.** The last 20 response times per site set
  that site's time limit next time, and put habitual laggards in a slow lane.
- **Which sites work.** The daily health check's verdict on every recipe.
- **Brand reports**, so a finished report can be downloaded again.

Nothing about the people searched for is kept beyond the reports you make.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from . import manifest

SCHEMA = """
CREATE TABLE IF NOT EXISTS timings (
    site     TEXT NOT NULL,
    ms       INTEGER,
    outcome  TEXT NOT NULL,          -- ok | timeout | error
    at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS timings_site ON timings (site, at);
CREATE TABLE IF NOT EXISTS health (
    site        TEXT NOT NULL,
    probe       TEXT NOT NULL,
    state       TEXT NOT NULL,
    detail      TEXT,
    checked_at  TEXT NOT NULL,
    PRIMARY KEY (site, probe)
);
CREATE TABLE IF NOT EXISTS reports (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    data        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key    TEXT PRIMARY KEY,
    value  TEXT
);
"""

KEEP_TIMINGS = 20

DEFAULT_TIMEOUT = 10.0
MIN_TIMEOUT = 3.0
MAX_TIMEOUT = 12.0
SLOW_LANE_TIMEOUT = 4.0


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: Optional[str] = None) -> sqlite3.Connection:
    target = path or str(manifest.home() / "footprint.db")
    # The web app opens the connection in one thread and uses it from the event
    # loop and the threadpool; each use is short and never overlaps a write.
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if target != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def get_meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: Optional[str]) -> None:
    conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
    conn.commit()


# ------------------------------------------------------------------ speed --

def record_timings(conn: sqlite3.Connection, rows: Iterable[tuple[str, Optional[int], str]]) -> None:
    """Remember how each site answered: ``(site, milliseconds, outcome)``."""
    rows = list(rows)
    if not rows:
        return
    at = now_iso()
    conn.executemany("INSERT INTO timings (site, ms, outcome, at) VALUES (?, ?, ?, ?)",
                     [(site, ms, outcome, at) for site, ms, outcome in rows])
    for site in {r[0] for r in rows}:
        conn.execute(
            "DELETE FROM timings WHERE site = ? AND rowid NOT IN "
            "(SELECT rowid FROM timings WHERE site = ? ORDER BY rowid DESC LIMIT ?)",
            (site, site, KEEP_TIMINGS))
    conn.commit()


@dataclass
class Speed:
    """What we have learned about one site's speed."""

    timeout: float = DEFAULT_TIMEOUT
    typical_ms: Optional[int] = None  # median of successful answers
    slow_lane: bool = False
    samples: int = 0


def _percentile(values: list[int], q: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))]


def speeds(conn: sqlite3.Connection) -> dict[str, Speed]:
    """Each site's time limit for the next search.

    Twice the site's usual slow answer (its 90th-percentile time), kept between
    3 and 12 seconds; 10 seconds until there are three answers to go on. A site
    that timed out in three of its last five checks goes in the slow lane:
    checked last, with a 4-second limit, until it starts answering again.
    """
    by_site: dict[str, list[sqlite3.Row]] = {}
    for row in conn.execute("SELECT site, ms, outcome FROM timings ORDER BY rowid"):
        by_site.setdefault(row["site"], []).append(row)
    out = {}
    for site, rows in by_site.items():
        ok = [r["ms"] for r in rows if r["outcome"] == "ok" and r["ms"] is not None]
        recent = rows[-5:]
        speed = Speed(samples=len(rows))
        if len(ok) >= 3:
            speed.timeout = min(MAX_TIMEOUT, max(MIN_TIMEOUT, 2 * _percentile(ok, 0.9) / 1000))
        if ok:
            speed.typical_ms = _percentile(ok, 0.5)
        if sum(1 for r in recent if r["outcome"] == "timeout") >= 3:
            speed.slow_lane = True
            speed.timeout = SLOW_LANE_TIMEOUT
        out[site] = speed
    return out


# ----------------------------------------------------------------- health --

def save_health(conn: sqlite3.Connection, rows: Iterable[tuple[str, str, str, str]]) -> None:
    """Store health verdicts: ``(site, probe id, state, detail)``."""
    at = now_iso()
    conn.executemany(
        "INSERT INTO health (site, probe, state, detail, checked_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(site, probe) DO UPDATE SET state = excluded.state, "
        "detail = excluded.detail, checked_at = excluded.checked_at",
        [(site, probe, state, detail, at) for site, probe, state, detail in rows])
    conn.commit()


def health(conn: sqlite3.Connection) -> dict[str, dict[str, sqlite3.Row]]:
    """``{site: {probe id: row}}`` for every recipe the health check has tested."""
    out: dict[str, dict[str, sqlite3.Row]] = {}
    for row in conn.execute("SELECT * FROM health"):
        out.setdefault(row["site"], {})[row["probe"]] = row
    return out


# ---------------------------------------------------------------- reports --

def save_report(conn: sqlite3.Connection, report_id: str, data: dict) -> None:
    conn.execute("INSERT OR REPLACE INTO reports (id, created_at, data) VALUES (?, ?, ?)",
                 (report_id, now_iso(), json.dumps(data)))
    conn.commit()


def load_report(conn: sqlite3.Connection, report_id: str) -> Optional[dict]:
    row = conn.execute("SELECT data FROM reports WHERE id = ?", (report_id,)).fetchone()
    return json.loads(row["data"]) if row else None
