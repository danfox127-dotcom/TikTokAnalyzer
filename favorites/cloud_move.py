"""Move the library on this Mac into the cloud: Supabase, through ``DATABASE_URL``.

    python -m favorites.cloud_move [--from PATH]

Or double-click ``move-to-cloud.command``, which does the same.

Everything comes across: the saves, your notes, the categories you filed
things in, the rooms you chose for a save or a creator, and the pictures --
as phone-sized copies, so a few thousand fit easily in the free database.

The library file on this Mac is opened read-only, so nothing on the Mac can be
changed by this: it stays as it was, a complete backup. And the move can be run
again at any time. Saves are matched by their link, never by number, so a
second run duplicates nothing; it only fills in what the cloud is missing. What
the cloud already has wins -- a note written on the phone after the move is
never replaced by the Mac's older copy -- and the Mac fills any gaps.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sqlite3
import sys
import urllib.parse
from pathlib import Path
from typing import Callable, Iterable, Optional

import psycopg

from . import db, pg, thumbnails
from . import themes as theme_vocabulary

BATCH = 200
PICTURE_BATCH = 50

# Item columns that hold numbers; everything else copied is text.
_NUMBERS = {"duration", "resolve_attempts"}
# How a save was looked up: taken together, from whichever side succeeded.
_LOOKUP = ("resolve_status", "resolve_error", "resolved_at", "resolve_attempts")
# Facts of the moment that mean nothing in another library.
_SKIP_META = {"themes_version", "google_oauth_pending"}


def _merge(col: str) -> str:
    """How a save already in the cloud takes a column from the Mac's copy."""
    if col in _LOOKUP:
        # A save the cloud couldn't look up takes the Mac's successful lookup.
        return (f"CASE WHEN items.resolve_status <> 'ok' AND excluded.resolve_status = 'ok'"
                f" THEN excluded.{col} ELSE items.{col} END")
    if col == "saved_at":  # when you first saved it is the date that means something
        return "CASE WHEN excluded.saved_at < items.saved_at THEN excluded.saved_at ELSE items.saved_at END"
    if col in ("tags", "terms"):
        return f"CASE WHEN items.{col} IN ('', '[]') THEN excluded.{col} ELSE items.{col} END"
    if col in _NUMBERS:
        return f"coalesce(items.{col}, excluded.{col})"
    return f"coalesce(nullif(items.{col}, ''), excluded.{col})"


def _clean(col: str, value):
    """A value from SQLite, which stores whatever it is given, as Postgres will take it."""
    if isinstance(value, bytes) and col != "data":
        value = value.decode("utf-8", "replace")
    if isinstance(value, str):
        value = value.replace("\x00", "")  # the one character Postgres text can't hold
    if col in _NUMBERS and value is not None:
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = None if col == "duration" else 0
    return value


def _chunks(seq: list, n: int) -> Iterable[list]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _marks(n: int) -> str:
    return ", ".join("?" * n)


def open_readonly(path: str) -> sqlite3.Connection:
    """The library file, opened so that nothing can write to it."""
    conn = sqlite3.connect(f"file:{urllib.parse.quote(path)}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _tables(src: sqlite3.Connection) -> set[str]:
    return {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _columns(src: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in src.execute(f"PRAGMA table_info({table})")]


def _count(conn, table: str, where: str = "") -> int:
    return int(conn.execute(f"SELECT count(*) FROM {table}{where}").fetchone()[0])


_NOTES = " WHERE note IS NOT NULL AND note <> ''"

#: What the summary compares, in the words it uses.
REPORT = (
    ("items", "", "saves"),
    ("items", _NOTES, "notes"),
    ("collections", "", "filed in categories"),
    ("theme_rules", "", "room choices you made"),
    ("thumbnails", "", "pictures"),
    ("imports", "", "imports remembered"),
    ("inbox_seen", "", "shared links already seen"),
)
#: The ones the cloud must have at least as many of. Room choices can merge
#: with ones already made in the cloud, so they aren't counted on.
MUST_ARRIVE = ("saves", "notes", "filed in categories", "pictures")


def tally(conn, tables: Optional[set[str]] = None) -> dict[str, int]:
    return {label: (_count(conn, table, where) if tables is None or table in tables else 0)
            for table, where, label in REPORT}


def move_items(src, conn, say=print) -> dict[int, int]:
    """Every save, matched to the cloud by its link. Returns Mac id -> cloud id."""
    have = set(_columns(src, "items"))
    cols = [c for c in (*db.WRITABLE, "themes") if c in have]
    merged = ", ".join(f"{c} = {_merge(c)}" for c in cols if c not in ("canonical_url", "themes"))
    rows = src.execute(f"SELECT id, {', '.join(cols)} FROM items ORDER BY id").fetchall()
    ids: dict[int, int] = {}
    for done, batch in enumerate(_chunks(rows, BATCH), 1):
        values = [_clean(c, r[c]) for r in batch for c in cols]
        found = conn.execute(
            f"INSERT INTO items ({', '.join(cols)}) VALUES "
            + ", ".join([f"({_marks(len(cols))})"] * len(batch))
            + f" ON CONFLICT (canonical_url) DO UPDATE SET {merged} RETURNING id, canonical_url",
            values).fetchall()
        cloud = {r["canonical_url"]: r["id"] for r in found}
        ids.update((r["id"], cloud[_clean("canonical_url", r["canonical_url"])]) for r in batch)
        conn.commit()
        say(f"  saves: {min(done * BATCH, len(rows)):,} of {len(rows):,}")
    return ids


def move_collections(src, conn, ids: dict[int, int]) -> None:
    # Names match whatever the capitals, as filing does: the Mac's "recipes"
    # joins the cloud's "Recipes" rather than sitting beside it.
    spelled = {r["name"].casefold(): r["name"]
               for r in conn.execute("SELECT DISTINCT name FROM collections")}
    rows = []
    for r in src.execute("SELECT item_id, name, added_at FROM collections"):
        if r["item_id"] in ids and r["name"]:
            name = spelled.setdefault(r["name"].casefold(), r["name"])
            rows.append((ids[r["item_id"]], _clean("name", name), r["added_at"]))
    conn.executemany(
        "INSERT INTO collections (item_id, name, added_at) VALUES (?, ?, ?)"
        " ON CONFLICT (item_id, name) DO UPDATE SET added_at = CASE"
        "   WHEN collections.added_at IS NULL THEN excluded.added_at"
        "   WHEN excluded.added_at IS NULL THEN collections.added_at"
        "   WHEN excluded.added_at < collections.added_at THEN excluded.added_at"
        "   ELSE collections.added_at END", rows)
    conn.commit()


def move_rules(src, conn, ids: dict[int, int]) -> None:
    """What you taught the museum. A save's rule names the save by number,
    so it follows the save to its number in the cloud."""
    # A save's rooms, and a hashtag's meaning, are set as a whole: where the
    # cloud has already been told, the Mac's older answer is left out.
    told = {(r["kind"], r["key"]) for r in conn.execute(
        "SELECT DISTINCT kind, key FROM theme_rules WHERE kind IN ('item', 'tag')")}
    rows = []
    for r in src.execute("SELECT kind, key, theme, action, created_at FROM theme_rules"):
        kind, key = r["kind"], str(r["key"])
        if kind == "item":
            if not key.isdigit() or int(key) not in ids:
                continue  # a rule for a save that is gone
            key = str(ids[int(key)])
        if (kind, key) in told:
            continue
        rows.append((kind, _clean("key", key), r["theme"], r["action"], r["created_at"]))
    conn.executemany(
        "INSERT INTO theme_rules (kind, key, theme, action, created_at) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT (kind, key, theme) DO NOTHING", rows)
    conn.commit()


def move_pictures(src, conn, ids: dict[int, int], say=print) -> tuple[int, int, int]:
    """Phone-sized copies of the pictures the cloud doesn't have yet.

    Returns (pictures copied, their bytes on the Mac, their bytes in the cloud).
    """
    kept = {r["item_id"] for r in conn.execute("SELECT item_id FROM thumbnails")}
    todo = _count(src, "thumbnails")
    copied = before = after = seen = 0
    batch: list[tuple] = []

    def flush():
        conn.executemany(
            "INSERT INTO thumbnails (item_id, content_type, data, source_url, fetched_at)"
            " VALUES (?, ?, ?, ?, ?) ON CONFLICT (item_id) DO NOTHING", batch)
        conn.commit()
        batch.clear()

    # One at a time, never all at once: the pictures can be most of the file.
    for r in src.execute("SELECT item_id, content_type, data, source_url, fetched_at FROM thumbnails"):
        seen += 1
        target = ids.get(r["item_id"])
        if target is not None and target not in kept and r["data"]:
            original = bytes(r["data"])
            data, ctype = thumbnails.shrink(original, r["content_type"] or "image/jpeg")
            batch.append((target, ctype, data, _clean("source_url", r["source_url"]),
                          r["fetched_at"] or db.now_iso()))
            copied, before, after = copied + 1, before + len(original), after + len(data)
            if len(batch) == PICTURE_BATCH:
                flush()
        if seen % BATCH == 0 or seen == todo:
            say(f"  pictures: {seen:,} of {todo:,}")
    if batch:
        flush()
    return copied, before, after


def move_plain(src, conn, table: str, skip: Iterable[str] = ()) -> None:
    """A table whose rows mean the same anywhere; the cloud's own rows stay."""
    cols = _columns(src, table)
    first = cols[0]
    rows = [tuple(_clean(c, r[c]) for c in cols)
            for r in src.execute(f"SELECT {', '.join(cols)} FROM {table}") if r[first] not in skip]
    conn.executemany(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({_marks(len(cols))}) ON CONFLICT DO NOTHING",
        rows)
    conn.commit()


def reindex(conn, ids: Iterable[int]) -> None:
    """Search rows for the moved saves, written as the museum writes them."""
    for chunk in _chunks(sorted(set(ids)), BATCH):
        marks = _marks(len(chunk))
        filed: dict[int, list[str]] = {}
        for c in conn.execute(f"SELECT item_id, name FROM collections WHERE item_id IN ({marks})", chunk):
            filed.setdefault(c["item_id"], []).append(c["name"])
        rows = conn.execute(
            "SELECT id, title, creator_name, creator_handle, description, note, transcript, tags, terms"
            f" FROM items WHERE id IN ({marks})", chunk).fetchall()
        conn.execute(f"DELETE FROM items_fts WHERE item_id IN ({marks})", chunk)
        conn.executemany(db.FTS_INSERT, [db.fts_row(r, filed.get(r["id"], ())) for r in rows])
        conn.commit()


def move(src: sqlite3.Connection, conn, say=print) -> dict:
    """Copy everything in ``src`` into the cloud library ``conn``."""
    tables = _tables(src)
    say("Copying...")
    ids = move_items(src, conn, say) if "items" in tables else {}
    if "collections" in tables:
        move_collections(src, conn, ids)
    if "theme_rules" in tables:
        move_rules(src, conn, ids)
    pictures = move_pictures(src, conn, ids, say) if "thumbnails" in tables else (0, 0, 0)
    for table in ("imports", "inbox_seen"):
        if table in tables:
            move_plain(src, conn, table)
    if "meta" in tables:
        move_plain(src, conn, "meta", skip=_SKIP_META)
    say("Updating search and rooms...")
    reindex(conn, ids.values())
    db.retheme(conn)
    db.set_meta(conn, "themes_version", theme_vocabulary.VERSION)
    return {"ids": ids, "pictures": pictures}


def _mb(n: float) -> str:
    return f"{n / 1_000_000:,.1f} MB"


def where_to(url: str) -> tuple[Optional[str], str]:
    """``(problem, host)`` for a ``DATABASE_URL``: what's wrong with it, if
    anything, and the server it names -- never the password."""
    if "[YOUR-PASSWORD]" in url:
        return ("DATABASE_URL still says [YOUR-PASSWORD]. Put your database password in its"
                " place (no brackets) in ~/.favorites.env."), ""
    try:
        parts = urllib.parse.urlsplit(url)
        host, port = parts.hostname or "", parts.port
    except ValueError:
        return ("DATABASE_URL isn't an address this can read. Copy it again from Supabase:"
                " Connect, then Session pooler. If your password has symbols in it,"
                " reset it to one with only letters and numbers."), ""
    if port == 6543:
        return ("DATABASE_URL is Supabase's Transaction pooler address (port 6543). Use the"
                " Session pooler one instead: Connect, then Session pooler (port 5432)."), host
    return None, host


ENV_FILE = Path.home() / ".favorites.env"

FIRST_TIME = """\
First, Faves needs the address of your cloud library. This is a one-time step.

  1. On supabase.com, open your project and click Connect, at the top.
  2. Choose "Session pooler" and copy the address. It starts with postgresql://
  3. Paste it below. Where it says [YOUR-PASSWORD], you'll be asked for your
     database password next. (Forgotten it? In Supabase: Project Settings,
     Database, Reset database password.)
"""


def fill_password(address: str, password: str) -> str:
    """The address with the password in place of Supabase's ``[YOUR-PASSWORD]``,
    written so any symbols in it survive."""
    return address.replace("[YOUR-PASSWORD]", urllib.parse.quote(password, safe=""))


def remember(address: str, env_file: Path = ENV_FILE) -> None:
    """Add the address to the settings file start.command reads, for this Mac only."""
    env_file.touch(mode=0o600, exist_ok=True)
    with env_file.open("a") as f:
        f.write("\n# The cloud library (Supabase), added by move-to-cloud.command.\n"
                f"DATABASE_URL='{address.replace(chr(39), '%27')}'\n")
    env_file.chmod(0o600)  # it holds a password


def setup(env_file: Path = ENV_FILE, ask: Callable[[str], str] = input,
          ask_secret: Callable[[str], str] = getpass.getpass, tries: int = 3) -> Optional[str]:
    """Ask for the cloud library's address, check it connects, then keep it.

    Nothing is saved until the address has worked, so a mistyped password
    just means trying again. Returns the address, or None.
    """
    print(FIRST_TIME)
    for _ in range(tries):
        address = ask("Paste the address and press Return: ").strip().strip("\"'")
        if not address.startswith(("postgresql://", "postgres://")):
            print("That isn't it: the address starts with postgresql://\n")
            continue
        if "[YOUR-PASSWORD]" in address:
            address = fill_password(address, ask_secret(
                "Your database password (it won't show as you type): "))
        problem, host = where_to(address)
        if problem:
            print(problem + "\n")
            continue
        try:
            psycopg.connect(address, connect_timeout=20).close()
        except psycopg.Error as exc:
            print(f"Couldn't connect to {host or 'that address'}:\n  {str(exc).strip().splitlines()[0]}\n"
                  "Check the password (or reset it) and try again.\n")
            continue
        remember(address, env_file)
        print(f"Connected. Saved in {env_file}, so Faves on this Mac can use it too.\n")
        return address
    return None


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="source", help="the library file to move (default: $FAVORITES_DB)")
    args = ap.parse_args(argv)

    if not db.on_postgres():
        address = setup() if sys.stdin.isatty() else None
        if not address:
            print("There's no cloud library to move into yet: DATABASE_URL isn't set.\n"
                  "See \"Moving to the cloud\" in favorites/README.md.")
            return 2
        os.environ["DATABASE_URL"] = address
    problem, host = where_to(os.environ["DATABASE_URL"])
    if problem:
        print(problem)
        return 2
    path = db.resolve_path(args.source)
    if not os.path.isfile(path):
        print(f"There's no library at {path}. Pass --from with the path of the one to move.")
        return 2

    src = open_readonly(path)
    try:
        src.execute("BEGIN")  # one consistent picture, even if Faves is saving meanwhile
        tables = _tables(src)
        mac = tally(src, tables)
        print("Moving your library into the cloud.")
        print(f"  from  {path}  ({mac['saves']:,} saves, {mac['pictures']:,} pictures)"
              " -- read only, never changed")
        try:
            conn = db.connect()
        except psycopg.Error as exc:
            print(f"\nCouldn't reach the cloud library at {host}:\n  {str(exc).strip().splitlines()[0]}\n"
                  "Check the password in DATABASE_URL, and that the Supabase project isn't paused.")
            return 1
        try:
            print(f"  to    Postgres at {host}, schema {pg.schema()}"
                  f"  ({db.count(conn):,} saves there now)\n")
            result = move(src, conn, say=lambda line: print(line, flush=True))
            cloud = tally(conn)
            size = conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
        finally:
            conn.close()
    except (sqlite3.Error, psycopg.Error) as exc:
        print(f"\nThe move stopped: {str(exc).strip().splitlines()[0]}\n"
              "Nothing is lost. Run it again and it picks up where it left off.")
        return 1
    finally:
        src.close()

    print(f"\n{'':<28}{'this Mac':>10}{'cloud':>10}")
    for label in mac:
        print(f"  {label:<26}{mac[label]:>10,}{cloud[label]:>10,}")
    copied, before, after = result["pictures"]
    if copied:
        print(f"\n{copied:,} pictures copied: {_mb(before)} on this Mac became {_mb(after)}"
              " as phone-sized copies.")
    print(f"The cloud database now uses {_mb(size)} of the free plan's 500 MB.")
    short = [label for label in MUST_ARRIVE if cloud[label] < mac[label]]
    if short:
        print(f"\nThe cloud has fewer {', '.join(short)} than this Mac. Run the move again;"
              " if that doesn't settle it, keep this window open and ask for help.")
    else:
        print("\nEverything on this Mac is in the cloud.")
    print("Nothing on this Mac was changed: its library file is still a complete backup.")
    return 1 if short else 0


if __name__ == "__main__":
    sys.exit(main())
