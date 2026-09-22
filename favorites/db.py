"""Storage for the favorites library.

One SQLite file holds everything. There is no server-side anything: the
database lives wherever ``FAVORITES_DB`` points, defaulting to a file next to
this package.

Search uses SQLite's built-in FTS5 full-text index. The index is a plain FTS5
table kept in step by :func:`index_item` rather than an external-content table
driven by triggers -- at personal scale the duplicated text costs nothing, and
keeping the sync in one readable function beats debugging trigger ordering.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

DEFAULT_DB = Path(__file__).resolve().parent / "favorites.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id             INTEGER PRIMARY KEY,
    canonical_url  TEXT NOT NULL UNIQUE,
    shared_url     TEXT NOT NULL,
    platform       TEXT NOT NULL,
    external_id    TEXT,
    title          TEXT,
    creator_name   TEXT,
    creator_handle TEXT,
    creator_url    TEXT,
    thumbnail_url  TEXT,
    description    TEXT,
    transcript     TEXT,
    note           TEXT,
    tags           TEXT NOT NULL DEFAULT '[]',
    terms          TEXT NOT NULL DEFAULT '[]',
    saved_at       TEXT NOT NULL,
    resolved_at    TEXT,
    resolve_status TEXT NOT NULL DEFAULT 'pending',
    resolve_error  TEXT,
    raw            TEXT
);

CREATE INDEX IF NOT EXISTS idx_items_saved_at ON items(saved_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_platform ON items(platform);
CREATE INDEX IF NOT EXISTS idx_items_creator  ON items(creator_handle);

CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    item_id UNINDEXED,
    title,
    creator,
    description,
    note,
    transcript,
    tags,
    tokenize = "unicode61 remove_diacritics 2"
);
"""

# Columns a caller is allowed to write. Anything else in a payload is ignored
# rather than silently creating a column mismatch at insert time.
WRITABLE = (
    "canonical_url", "shared_url", "platform", "external_id", "title",
    "creator_name", "creator_handle", "creator_url", "thumbnail_url",
    "description", "transcript", "note", "tags", "terms", "saved_at",
    "resolved_at", "resolve_status", "resolve_error", "raw",
)


def now_iso() -> str:
    """Current UTC time, second precision, as a sortable ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: str | os.PathLike | None = None) -> sqlite3.Connection:
    """Open the library, creating it if this is the first run."""
    target = str(path or os.environ.get("FAVORITES_DB") or DEFAULT_DB)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _json_list(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(list(value or []), ensure_ascii=False)


def loads_list(value: Any) -> list[str]:
    """Read a JSON list column back, tolerating nulls and malformed rows."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def index_item(conn: sqlite3.Connection, item_id: int) -> None:
    """Rewrite the full-text row for one item."""
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        conn.execute("DELETE FROM items_fts WHERE item_id = ?", (item_id,))
        return
    creator = " ".join(filter(None, [row["creator_name"], row["creator_handle"]]))
    tags = " ".join(loads_list(row["tags"]) + loads_list(row["terms"]))
    conn.execute("DELETE FROM items_fts WHERE item_id = ?", (item_id,))
    conn.execute(
        "INSERT INTO items_fts (item_id, title, creator, description, note, transcript, tags)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            item_id,
            row["title"] or "",
            creator,
            row["description"] or "",
            row["note"] or "",
            row["transcript"] or "",
            tags,
        ),
    )


def upsert_item(conn: sqlite3.Connection, payload: dict) -> tuple[int, bool]:
    """Insert an item, or update the existing row with the same canonical URL.

    Returns ``(item_id, created)``. Re-sharing something you already saved
    updates it rather than duplicating it -- but an existing note is never
    overwritten by a blank one, because the note is the only field the library
    cannot recover by re-resolving.
    """
    data = {k: v for k, v in payload.items() if k in WRITABLE}
    data.setdefault("saved_at", now_iso())
    data["tags"] = _json_list(data.get("tags"))
    data["terms"] = _json_list(data.get("terms"))
    if isinstance(data.get("raw"), (dict, list)):
        data["raw"] = json.dumps(data["raw"], ensure_ascii=False)

    existing = conn.execute(
        "SELECT id, note FROM items WHERE canonical_url = ?", (data["canonical_url"],)
    ).fetchone()

    if existing is None:
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        cur = conn.execute(f"INSERT INTO items ({cols}) VALUES ({marks})", tuple(data.values()))
        item_id = int(cur.lastrowid)
        created = True
    else:
        item_id = int(existing["id"])
        created = False
        if not data.get("note") and existing["note"]:
            data.pop("note", None)
        data.pop("saved_at", None)  # keep the original save date
        assignments = ", ".join(f"{k} = ?" for k in data)
        conn.execute(
            f"UPDATE items SET {assignments} WHERE id = ?", (*data.values(), item_id)
        )

    index_item(conn, item_id)
    conn.commit()
    return item_id, created


def set_note(conn: sqlite3.Connection, item_id: int, note: str) -> None:
    conn.execute("UPDATE items SET note = ? WHERE id = ?", (note, item_id))
    index_item(conn, item_id)
    conn.commit()


def get_item(conn: sqlite3.Connection, item_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()


def recent(conn: sqlite3.Connection, limit: int = 12, offset: int = 0) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM items ORDER BY saved_at DESC, id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()


def count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT count(*) AS n FROM items").fetchone()["n"])


_WORD = re.compile(r"[^\w@#]+", re.UNICODE)


def fts_query(text: str) -> str:
    """Turn whatever someone typed into a valid FTS5 MATCH expression.

    Raw user input is not a valid query -- an unbalanced quote or a bare ``OR``
    is a syntax error, not zero results. Every token is quoted and ANDed, and
    the final token gets a prefix wildcard so partial words match while typing.
    """
    tokens = [t for t in _WORD.split(text or "") if t]
    if not tokens:
        return ""
    quoted = [f'"{t}"' for t in tokens[:-1]]
    quoted.append(f'"{tokens[-1]}"*')
    return " AND ".join(quoted)


def search(conn: sqlite3.Connection, text: str, limit: int = 50) -> list[sqlite3.Row]:
    """Full-text search, newest-first within relevance.

    Falls back to a LIKE scan if FTS rejects the query for any reason, so the
    search box never returns an error page.
    """
    match = fts_query(text)
    if not match:
        return []
    try:
        return conn.execute(
            "SELECT i.* FROM items_fts f JOIN items i ON i.id = f.item_id"
            " WHERE items_fts MATCH ? ORDER BY rank LIMIT ?",
            (match, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        like = f"%{text}%"
        return conn.execute(
            "SELECT * FROM items WHERE title LIKE ? OR description LIKE ?"
            " OR note LIKE ? OR creator_name LIKE ? OR creator_handle LIKE ?"
            " ORDER BY saved_at DESC LIMIT ?",
            (like, like, like, like, like, limit),
        ).fetchall()


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict]:
    out = []
    for row in rows:
        item = dict(row)
        item["tags"] = loads_list(item.get("tags"))
        item["terms"] = loads_list(item.get("terms"))
        out.append(item)
    return out
