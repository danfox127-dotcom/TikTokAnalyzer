"""Storage for the favorites library.

One SQLite file holds everything. There is no server-side anything: the
database lives wherever ``FAVORITES_DB`` points, defaulting to
``~/favorites.db`` in your home folder.

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

from . import themes as theme_vocabulary

# The home folder, not the project folder: a default that depends on where the
# code happens to be checked out is how one person ended up with two libraries
# -- an import quietly filled one while the museum kept showing the other.
DEFAULT_DB = Path.home() / "favorites.db"

# Where the default used to be. Still honoured when it is the only library
# there is, so an existing one is never swapped for an empty museum.
LEGACY_DB = Path(__file__).resolve().parent / "favorites.db"

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
    resolve_attempts INTEGER NOT NULL DEFAULT 0,
    source         TEXT NOT NULL DEFAULT 'share',
    imported_at    TEXT,
    format         TEXT,
    themes         TEXT NOT NULL DEFAULT '[]',
    duration       INTEGER,
    raw            TEXT
);

CREATE INDEX IF NOT EXISTS idx_items_saved_at ON items(saved_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_platform ON items(platform);
CREATE INDEX IF NOT EXISTS idx_items_creator  ON items(creator_handle);
CREATE INDEX IF NOT EXISTS idx_items_status   ON items(resolve_status);

-- Categories you filed things into: an imported YouTube playlist, a name picked
-- in the share sheet, one typed on an item's page. Separate from items because
-- one thing can sit in several. "Just saved" -- Watch later, a plain favourite
-- -- is no row at all.
CREATE TABLE IF NOT EXISTS collections (
    item_id  INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    name     TEXT NOT NULL,
    added_at TEXT,
    PRIMARY KEY (item_id, name)
);
CREATE INDEX IF NOT EXISTS idx_collections_name ON collections(name);

-- The picture itself, kept because the platforms' own links expire (TikTok's
-- within a day or two). In its own table so that "SELECT * FROM items" never
-- drags image bytes along with it.
CREATE TABLE IF NOT EXISTS thumbnails (
    item_id      INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
    content_type TEXT NOT NULL,
    data         BLOB NOT NULL,
    source_url   TEXT,
    fetched_at   TEXT NOT NULL
);

-- What you taught the museum about its rooms: "this save is not Marketing",
-- "everything by @pearljam is Music", "#eddievedder means Music", "#siriusxm
-- is no subject at all". Kept apart from items so re-theming never loses them.
CREATE TABLE IF NOT EXISTS theme_rules (
    kind       TEXT NOT NULL,   -- 'item', 'creator' or 'tag'
    key        TEXT NOT NULL,   -- the item id, creator handle or hashtag
    theme      TEXT NOT NULL,   -- '' for an ignored hashtag
    action     TEXT NOT NULL,   -- 'add', 'remove' or 'ignore'
    created_at TEXT,
    PRIMARY KEY (kind, key, theme)
);

-- Small facts about the library file itself, such as which version of the
-- theme vocabulary its themes were worked out with.
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

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
    "resolved_at", "resolve_status", "resolve_error", "resolve_attempts",
    "source", "imported_at", "format", "duration", "raw",
)

# Columns added after the first release. A library created by an earlier version
# is migrated in place on open rather than rebuilt -- it holds the only copy of
# your notes.
MIGRATIONS = {
    "resolve_attempts": "INTEGER NOT NULL DEFAULT 0",
    "source": "TEXT NOT NULL DEFAULT 'share'",
    "imported_at": "TEXT",
    "format": "TEXT",
    "themes": "TEXT NOT NULL DEFAULT '[]'",
    "duration": "INTEGER",
}


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Add any columns this version expects but the file does not have."""
    have = {row["name"] for row in conn.execute("PRAGMA table_info(items)")}
    added = []
    for column, ddl in MIGRATIONS.items():
        if column not in have:
            conn.execute(f"ALTER TABLE items ADD COLUMN {column} {ddl}")
            added.append(column)
    if added:
        conn.commit()
    return added


def now_iso() -> str:
    """Current UTC time, second precision, as a sortable ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_path(path: str | os.PathLike | None = None) -> str:
    """Which library file a command will use, as an absolute path.

    An explicit path wins, then ``$FAVORITES_DB``, then ``~/favorites.db`` --
    or the old in-project default, if that is the only library that exists.
    Absolute because a relative one silently means a different file depending
    on which folder the command was run from.
    """
    target = str(path or os.environ.get("FAVORITES_DB") or _default())
    if target == ":memory:":
        return target
    return os.path.abspath(os.path.expanduser(target))


def _default() -> Path:
    if not DEFAULT_DB.exists() and LEGACY_DB.exists():
        return LEGACY_DB
    return DEFAULT_DB


def connect(path: str | os.PathLike | None = None) -> sqlite3.Connection:
    """Open the library, creating it if this is the first run."""
    target = resolve_path(path)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    # The web app opens a connection in one worker thread and uses it in
    # another: FastAPI runs the dependency that opens it and the endpoint that
    # reads it on separate threadpool threads. SQLite refuses that by default,
    # which failed most of a page's picture requests at once while any single
    # one looked fine. Each connection still serves one request at a time,
    # which is the condition the default check exists to protect.
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    migrate(conn)
    retheme_if_stale(conn)
    return conn


def connect_announced(path: str | os.PathLike | None = None) -> tuple[sqlite3.Connection, str]:
    """:func:`connect`, plus a line saying which file -- and whether it is new.

    Two library files can exist side by side without anything looking wrong:
    an import into the wrong one reports success and the museum simply never
    shows what was imported. Every command that writes says which file it
    used, and says loudly when it has just created one.
    """
    target = resolve_path(path)
    existed = target == ":memory:" or os.path.exists(target)
    conn = connect(target)
    if existed:
        n = count(conn)
        line = f"library: {target}  ({n} {'item' if n == 1 else 'items'})"
        if target == str(LEGACY_DB) and not path and not os.environ.get("FAVORITES_DB"):
            line += (f"\n  This is the old default location. Move it to make it the"
                     f" default everywhere:  mv \"{target}\" ~/favorites.db")
        return conn, line
    return conn, (f"library: {target}  (NEW -- created just now. If you expected your "
                  f"existing library, pass --db with its path or set FAVORITES_DB.)")


def load_rules(conn: sqlite3.Connection) -> theme_vocabulary.Rules:
    return theme_vocabulary.Rules.from_rows(
        (r["kind"], r["key"], r["theme"], r["action"])
        for r in conn.execute("SELECT kind, key, theme, action FROM theme_rules"))


_THEME_COLUMNS = ("id, title, description, note, tags, transcript,"
                  " creator_handle, creator_name")


def _filed(conn: sqlite3.Connection) -> dict[int, list[str]]:
    filed: dict[int, list[str]] = {}
    for c in conn.execute("SELECT item_id, name FROM collections"):
        filed.setdefault(c["item_id"], []).append(c["name"])
    return filed


def _key(row) -> str:
    return theme_vocabulary.creator_key(row["creator_handle"], row["creator_name"])


def _leans(rows, filed, rules) -> dict[str, list[str]]:
    """creator -> the rooms their saves mostly sit in, each save themed alone."""
    alone: dict[str, list[list[str]]] = {}
    for r in rows:
        if _key(r):
            alone.setdefault(_key(r), []).append(
                theme_vocabulary.for_row(r, filed.get(r["id"], ()), rules=rules))
    return {k: theme_vocabulary.lean(v) for k, v in alone.items()}


def hunches(conn: sqlite3.Connection, limit: int = 12) -> tuple[list[int], int]:
    """Saves filed on a hunch -- one word in passing -- newest first, and how many.

    The ones worth a second look: the museum is guessing, and one tap from
    you settles it for good.
    """
    rules = load_rules(conn)
    filed = _filed(conn)
    rows = conn.execute(
        f"SELECT {_THEME_COLUMNS} FROM items WHERE resolve_status = 'ok'"
        " AND json_array_length(coalesce(nullif(themes, ''), '[]')) > 0"
        " ORDER BY saved_at DESC").fetchall()
    leans = _leans(rows, filed, rules)
    found = []
    for r in rows:
        if r["id"] in rules.item_add or r["id"] in rules.item_remove:
            continue
        ev = theme_vocabulary.evidence_for_row(
            r, filed.get(r["id"], ()), rules=rules, regular=leans.get(_key(r), ()))
        kept = theme_vocabulary.explain(ev, theme_vocabulary.decide(ev))
        if kept and all(k["hunch"] for k in kept):
            found.append(r["id"])
    return found[:limit], len(found)


def retheme(conn: sqlite3.Connection) -> int:
    """Work every item's themes out again. Returns how many items there are.

    Two passes: the first themes each save on its own, which shows which rooms
    each creator's saves mostly sit in; the second adds that lean, so a save
    by a creator you keep for their music leans towards Music.
    """
    rules = load_rules(conn)
    filed = _filed(conn)
    rows = conn.execute(f"SELECT {_THEME_COLUMNS} FROM items").fetchall()
    leans = _leans(rows, filed, rules)
    conn.executemany(
        "UPDATE items SET themes = ? WHERE id = ?",
        [(json.dumps(theme_vocabulary.for_row(
            r, filed.get(r["id"], ()), rules=rules, regular=leans.get(_key(r), ()))), r["id"])
         for r in rows],
    )
    conn.commit()
    return len(rows)


def retheme_if_stale(conn: sqlite3.Connection) -> int:
    """Work every item's themes out again if the vocabulary has changed.

    Themes are stored so filters can count them in SQL, which means an edit to
    the vocabulary would otherwise leave every existing item on the old one.
    A version stamp in the file makes the edit apply everywhere on the next
    start, with nothing to run. Returns how many items were re-themed.
    """
    row = conn.execute("SELECT value FROM meta WHERE key = 'themes_version'").fetchone()
    if row is not None and row["value"] == theme_vocabulary.VERSION:
        return 0
    n = retheme(conn)
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('themes_version', ?)",
                 (theme_vocabulary.VERSION,))
    conn.commit()
    return n


def _creator_lean(conn: sqlite3.Connection, key: str, item_id: int,
                  rules: theme_vocabulary.Rules) -> list[str]:
    """The rooms a creator's *other* saves mostly sit in, each themed alone."""
    if not key:
        return []
    rows = conn.execute(
        f"SELECT {_THEME_COLUMNS} FROM items WHERE id != ? AND ("
        " lower(ltrim(coalesce(creator_handle, ''), '@')) = ?"
        " OR (coalesce(creator_handle, '') = '' AND lower(creator_name) = ?))",
        (item_id, key, key)).fetchall()
    if len(rows) < theme_vocabulary.LEAN_MIN:
        return []
    filed = _filed(conn)
    return theme_vocabulary.lean(
        theme_vocabulary.for_row(r, filed.get(r["id"], ()), rules=rules) for r in rows)


def _theme_inputs(conn: sqlite3.Connection, item_id: int, rules=None):
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        return None
    rules = load_rules(conn) if rules is None else rules
    filed = [r["name"] for r in conn.execute(
        "SELECT name FROM collections WHERE item_id = ?", (item_id,))]
    regular = _creator_lean(conn, _key(row), item_id, rules)
    return row, filed, rules, regular


def themes_of(conn: sqlite3.Connection, item_id: int) -> list[str]:
    got = _theme_inputs(conn, item_id)
    if got is None:
        return []
    row, filed, rules, regular = got
    return theme_vocabulary.for_row(row, filed, rules=rules, regular=regular)


def room_reasons(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    """Why a save is in each of its rooms, in words, for its page."""
    got = _theme_inputs(conn, item_id)
    if got is None:
        return []
    row, filed, rules, regular = got
    ev = theme_vocabulary.evidence_for_row(row, filed, rules=rules, regular=regular)
    return theme_vocabulary.explain(ev, theme_vocabulary.decide(ev))


def set_rooms(conn: sqlite3.Connection, item_id: int, chosen: Iterable[str],
              whole_creator: bool = False, confirm: bool = False) -> None:
    """Put a save in exactly the rooms you chose.

    Only the difference from what the museum would have worked out is kept,
    so a later improvement to the vocabulary still reaches the rest. With
    ``whole_creator`` the difference is kept for everything by its creator.
    ``confirm`` keeps the rooms you agreed with too, so a guess you checked
    stays settled.
    """
    got = _theme_inputs(conn, item_id)
    if got is None:
        return
    row, filed, rules, regular = got
    rules.item_add.pop(item_id, None)
    rules.item_remove.pop(item_id, None)
    auto = set(theme_vocabulary.for_row(row, filed, rules=rules, regular=regular))
    chosen = {t for t in chosen if t in theme_vocabulary.THEMES}
    adds, removes = (chosen if confirm else chosen - auto), auto - chosen
    key = _key(row)
    conn.execute("DELETE FROM theme_rules WHERE kind = 'item' AND key = ?", (str(item_id),))
    kind, rule_key = ("creator", key) if whole_creator and key else ("item", str(item_id))
    if kind == "creator":
        conn.execute("DELETE FROM theme_rules WHERE kind = 'creator' AND key = ? AND theme IN"
                     f" ({','.join('?' * len(adds | removes)) or 'NULL'})",
                     (key, *(adds | removes)))
    conn.executemany(
        "INSERT OR REPLACE INTO theme_rules (kind, key, theme, action, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        [(kind, rule_key, t, "add", now_iso()) for t in adds]
        + [(kind, rule_key, t, "remove", now_iso()) for t in removes])
    retheme(conn)


def reset_rooms(conn: sqlite3.Connection, item_id: int) -> None:
    """Forget your choice for one save; the museum works its rooms out again."""
    conn.execute("DELETE FROM theme_rules WHERE kind = 'item' AND key = ?", (str(item_id),))
    retheme(conn)


def teach_tag(conn: sqlite3.Connection, tag: str, theme: Optional[str]) -> None:
    """Teach a hashtag: it means ``theme``, or (``None``) it is no subject at all."""
    tag = theme_vocabulary.tag_key(tag)
    if not tag or (theme is not None and theme not in theme_vocabulary.THEMES):
        return
    conn.execute("DELETE FROM theme_rules WHERE kind = 'tag' AND key = ?", (tag,))
    conn.execute(
        "INSERT INTO theme_rules (kind, key, theme, action, created_at) VALUES ('tag', ?, ?, ?, ?)",
        (tag, theme or "", "add" if theme else "ignore", now_iso()))
    retheme(conn)


def taught_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT count(*) FROM theme_rules").fetchone()[0]


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
    # A category name is your own label, as telling as a note: filing something
    # under "Recipes" should make it findable by searching "recipes".
    filed = [r["name"] for r in conn.execute(
        "SELECT name FROM collections WHERE item_id = ?", (item_id,))]
    tags = " ".join(loads_list(row["tags"]) + loads_list(row["terms"]) + filed)
    conn.execute("UPDATE items SET themes = ? WHERE id = ?",
                 (json.dumps(themes_of(conn, item_id)), item_id))
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
        for learned in ("format", "duration"):
            if data.get(learned) is None:
                # A re-resolve that could not tell (a probe hit a consent wall,
                # a page came back without its data) must not erase what an
                # earlier one established.
                data.pop(learned, None)
        data.pop("saved_at", None)  # keep the original save date
        assignments = ", ".join(f"{k} = ?" for k in data)
        conn.execute(
            f"UPDATE items SET {assignments} WHERE id = ?", (*data.values(), item_id)
        )

    index_item(conn, item_id)
    conn.commit()
    return item_id, created


def file_under(
    conn: sqlite3.Connection, item_id: int, name: str, added_at: Optional[str] = None
) -> Optional[str]:
    """Put an item in a collection. Returns the collection's name as stored.

    Names match case-insensitively, so "recipes" typed at save time lands in
    the "Recipes" playlist you imported rather than beside it. The earliest
    date wins: when you first filed it there is the date that means something.
    """
    name = re.sub(r"\s+", " ", name or "").strip()
    if not name:
        return None
    existing = conn.execute(
        "SELECT name FROM collections WHERE name = ? COLLATE NOCASE LIMIT 1", (name,)
    ).fetchone()
    name = existing["name"] if existing else name
    conn.execute(
        "INSERT INTO collections (item_id, name, added_at) VALUES (?, ?, ?)"
        " ON CONFLICT (item_id, name) DO UPDATE SET added_at = CASE"
        "   WHEN collections.added_at IS NULL THEN excluded.added_at"
        "   WHEN excluded.added_at IS NULL THEN collections.added_at"
        "   ELSE min(collections.added_at, excluded.added_at) END",
        (item_id, name, added_at),
    )
    index_item(conn, item_id)
    conn.commit()
    return name


def unfile(conn: sqlite3.Connection, item_id: int, name: str) -> None:
    conn.execute(
        "DELETE FROM collections WHERE item_id = ? AND name = ? COLLATE NOCASE",
        (item_id, (name or "").strip()))
    index_item(conn, item_id)
    conn.commit()


def collections_for(conn: sqlite3.Connection, item_id: int) -> list[str]:
    return [r["name"] for r in conn.execute(
        "SELECT name FROM collections WHERE item_id = ? ORDER BY name COLLATE NOCASE",
        (item_id,))]


def collection_counts(conn: sqlite3.Connection, resolved_only: bool = False) -> list[tuple[str, int]]:
    """Every collection with how many items it holds, largest first."""
    join = " JOIN items i ON i.id = c.item_id AND i.resolve_status = 'ok'" if resolved_only else ""
    return [(r["name"], r["n"]) for r in conn.execute(
        f"SELECT c.name AS name, count(*) AS n FROM collections c{join}"
        " GROUP BY c.name ORDER BY n DESC, c.name COLLATE NOCASE")]


def in_collection(conn: sqlite3.Connection, name: str, limit: int = 200) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT i.* FROM items i JOIN collections c ON c.item_id = i.id"
        " WHERE c.name = ? COLLATE NOCASE ORDER BY i.saved_at DESC, i.id DESC LIMIT ?",
        (name, limit),
    ).fetchall()


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
        item["themes"] = loads_list(item.get("themes"))
        out.append(item)
    return out
