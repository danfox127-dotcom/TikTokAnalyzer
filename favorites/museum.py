"""The front door: shelves and a digest, assembled from the library itself.

A search box is a fine way to find something you already remember. It is a
useless way to be reminded of something you forgot, which is most of what a
library of favourites is for. So the front page is arranged like a small
museum -- recent acquisitions, a themed room, a month, a creator you keep
coming back to -- and the arrangement rotates on its own so that opening the
app on a Tuesday shows you something different from Monday.

Nothing here needs a language model. Every sentence in the digest is computed
from counts the library already holds, which means it works on day one with an
empty API key and never invents a fact. :func:`digest` returns its components
alongside the prose so an optional model can rewrite it later without having to
re-derive anything.
"""

from __future__ import annotations

import random
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from . import db
from .resolve import platform_label
from .tagging import collection_themes

# The museum only arranges items it can actually describe. A backfilled import
# is a dated URL until it resolves, and a shelf of untitled links is worse than
# no shelf -- so unresolved items contribute their dates to the counts but stay
# out of the display until they have a title.
RESOLVED = "resolve_status = 'ok'"

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _cutoff(days: int, now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    return (now - timedelta(days=days)).replace(microsecond=0).isoformat()


def _month_title(key: str) -> str:
    """``2026-09`` -> ``September 2026``."""
    try:
        year, month = key.split("-")
        return f"{MONTH_NAMES[int(month) - 1]} {year}"
    except (ValueError, IndexError):
        return key


def _plural(n: int, one: str, many: Optional[str] = None) -> str:
    return one if n == 1 else (many or one + "s")


def _join(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def _creator_label(item: dict) -> str:
    return item.get("creator_name") or item.get("creator_handle") or "Unknown"


def _creator_key(item: dict) -> Optional[str]:
    return item.get("creator_handle") or item.get("creator_name")


def digest(conn: sqlite3.Connection, days: int = 30, now: Optional[datetime] = None) -> dict:
    """A summary of the recent past, with the numbers that produced it.

    The comparison against the previous window is the point. A count on its own
    says nothing; "twelve, up from four" is the sentence that tells you
    something has shifted in what you are paying attention to.
    """
    now = now or datetime.now(timezone.utc)
    start = _cutoff(days, now)
    prev_start = _cutoff(days * 2, now)

    current = db.rows_to_dicts(conn.execute(
        "SELECT * FROM items WHERE saved_at >= ? ORDER BY saved_at DESC", (start,)
    ).fetchall())
    previous = db.rows_to_dicts(conn.execute(
        "SELECT * FROM items WHERE saved_at >= ? AND saved_at < ?", (prev_start, start)
    ).fetchall())

    platforms = Counter(platform_label(i["platform"]) for i in current)
    creators = Counter(
        _creator_label(i) for i in current if _creator_key(i)
    )
    themes = collection_themes(current, min_items=2, limit=6)

    earlier_keys = {
        row["k"] for row in conn.execute(
            "SELECT DISTINCT coalesce(creator_handle, creator_name) AS k"
            " FROM items WHERE saved_at < ? AND coalesce(creator_handle, creator_name) IS NOT NULL",
            (start,),
        ).fetchall()
    }
    new_creators = []
    for item in current:
        key = _creator_key(item)
        label = _creator_label(item)
        if key and key not in earlier_keys and label not in new_creators:
            new_creators.append(label)

    result = {
        "days": days,
        "count": len(current),
        "previous_count": len(previous),
        "platforms": platforms.most_common(),
        "creators": creators.most_common(5),
        "themes": themes,
        "new_creators": new_creators[:4],
        "with_notes": sum(1 for i in current if (i.get("note") or "").strip()),
        "with_transcripts": sum(1 for i in current if (i.get("transcript") or "").strip()),
        "entries": current,
    }
    result["prose"] = _digest_prose(result)
    return result


def _digest_prose(d: dict) -> str:
    n, prev, days = d["count"], d["previous_count"], d["days"]
    window = "month" if 28 <= days <= 31 else f"{days} days"
    preposition = "this past " + window if window == "month" else f"in the last {window}"

    if n == 0:
        return (
            f"Nothing saved {preposition}."
            if prev == 0 else
            f"Nothing saved {preposition}, after {prev} the {window} before."
        )

    sentences = []
    opener = f"{n} {_plural(n, 'save')} {preposition}"
    if prev == 0:
        sentences.append(opener + ".")
    elif n > prev:
        sentences.append(f"{opener}, up from {prev}.")
    elif n < prev:
        sentences.append(f"{opener}, down from {prev}.")
    else:
        sentences.append(f"{opener}, the same as the {window} before.")

    platforms = d["platforms"]
    if len(platforms) == 1:
        sentences.append(f"All of it from {platforms[0][0]}.")
    elif platforms and platforms[0][1] * 2 >= n:
        # "Mostly" is only true when one platform actually holds a majority.
        rest = [name for name, _ in platforms[1:3]]
        lead = f"Mostly {platforms[0][0]} ({platforms[0][1]})"
        sentences.append(f"{lead}, with {_join(rest)}." if rest else lead + ".")
    elif platforms:
        spread = [f"{name} ({c})" for name, c in platforms[:3]]
        sentences.append(f"Spread across {_join(spread)}.")

    themes = d["themes"]
    if themes:
        named = [t for t, _ in themes[:3]]
        lead = "The thread running through them is" if len(named) == 1 else "Recurring threads:"
        sentences.append(f"{lead} {_join(named)}.")

    creators = d["creators"]
    if creators and creators[0][1] >= 2:
        name, c = creators[0]
        sentences.append(f"{name} accounts for {c} of them.")

    new = d["new_creators"]
    if new:
        sentences.append(
            f"{_plural(len(new), 'One creator is', f'{len(new)} creators are')} "
            f"new to the library: {_join(new)}."
        )

    missing = n - d["with_notes"]
    if missing and n >= 4 and missing >= n // 2:
        sentences.append(
            f"{missing} of them {_plural(missing, 'has', 'have')} no note yet."
        )

    return " ".join(sentences)


def shared_terms(conn: sqlite3.Connection, item: dict, limit: int = 10) -> list[str]:
    """Terms this item has in common with the rest of the library.

    Extracted terms are noisy on a single item -- a caption yields phrases like
    "went sideways" that describe nothing. They become meaningful only where
    they recur, so the item page shows hashtags (author-written, precise) plus
    the terms that lead somewhere other than back here. A pill that matches
    one item is a dead end, not a label.
    """
    others = db.rows_to_dicts(conn.execute(
        "SELECT tags, terms FROM items WHERE id != ?", (item.get("id"),)
    ).fetchall())
    pool: Counter[str] = Counter()
    for other in others:
        pool.update(set((other.get("tags") or []) + (other.get("terms") or [])[:8]))
    mine = list(dict.fromkeys((item.get("terms") or [])[:12]))
    ranked = sorted(((t, pool[t]) for t in mine if pool.get(t)), key=lambda kv: -kv[1])
    return [t for t, _ in ranked[:limit]]


def _shelf(kind: str, title: str, subtitle: str, entries: list[dict], href: str = "") -> dict:
    # Deliberately not called "items": Jinja resolves ``shelf.items`` to the
    # dict's own ``items()`` method before it looks for a key of that name,
    # so a shelf keyed that way silently renders nothing.
    return {"kind": kind, "title": title, "subtitle": subtitle,
            "entries": entries, "href": href}


def _items_where(conn: sqlite3.Connection, clause: str, params: tuple, limit: int = 8) -> list[dict]:
    return db.rows_to_dicts(conn.execute(
        f"SELECT * FROM items WHERE {RESOLVED} AND ({clause}) ORDER BY saved_at DESC LIMIT ?",
        (*params, limit),
    ).fetchall())


def resolved_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute(
        f"SELECT count(*) AS n FROM items WHERE {RESOLVED}").fetchone()["n"])


def pending_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute(
        f"SELECT count(*) AS n FROM items WHERE NOT ({RESOLVED})").fetchone()["n"])


def shelves(
    conn: sqlite3.Connection,
    now: Optional[datetime] = None,
    max_shelves: int = 4,
) -> list[dict]:
    """Build the front page.

    "Recently saved" is always first, because that is the question you have
    most often. The rest are drawn from a pool and seeded by the date, so the
    arrangement is stable through the day and different tomorrow.
    """
    now = now or datetime.now(timezone.utc)
    total = resolved_count(conn)
    out: list[dict] = []

    recent = db.rows_to_dicts(conn.execute(
        f"SELECT * FROM items WHERE {RESOLVED} ORDER BY saved_at DESC, id DESC LIMIT 8"
    ).fetchall())
    if recent:
        out.append(_shelf(
            "recent", "Recently saved",
            f"The last {len(recent)} things you kept", recent, href="/all",
        ))
    if total <= 3:
        return out

    everything = db.rows_to_dicts(conn.execute(
        f"SELECT * FROM items WHERE {RESOLVED}").fetchall())
    rng = random.Random(f"{now.date().isoformat()}:{total}")
    candidates: list[dict] = []

    # A themed room.
    for term, n in collection_themes(everything, min_items=2, limit=8):
        hits = [
            i for i in everything
            if term in (i.get("tags") or []) or term in (i.get("terms") or [])[:8]
        ][:8]
        if len(hits) >= 2:
            candidates.append(_shelf(
                "theme", term.title(),
                f"{n} {_plural(n, 'save')} share this thread", hits,
                href=f"/search?q={term.replace(' ', '+')}",
            ))

    # A month you were busy.
    months = conn.execute(
        f"SELECT substr(saved_at, 1, 7) AS m, count(*) AS n FROM items"
        f" WHERE {RESOLVED} GROUP BY m HAVING n >= 3 ORDER BY n DESC LIMIT 6"
    ).fetchall()
    for row in months:
        if row["m"] == now.strftime("%Y-%m"):
            continue  # the current month is already the "recent" shelf
        items = _items_where(conn, "substr(saved_at, 1, 7) = ?", (row["m"],))
        candidates.append(_shelf(
            "month", _month_title(row["m"]),
            f"{row['n']} {_plural(row['n'], 'save')} that month", items,
            href=f"/month/{row['m']}",
        ))

    # A category you made yourself. Of all the shelves this is the one that is
    # yours rather than inferred: you did the curating when you saved it.
    for name, n in db.collection_counts(conn, resolved_only=True)[:6]:
        if n < 2:
            continue
        entries = db.rows_to_dicts(conn.execute(
            f"SELECT i.* FROM items i JOIN collections c ON c.item_id = i.id"
            f" WHERE i.{RESOLVED} AND c.name = ?"
            f" ORDER BY i.saved_at DESC, i.id DESC LIMIT 8", (name,)
        ).fetchall())
        candidates.append(_shelf(
            "collection", name, f"Your category · {n} {_plural(n, 'save')}", entries,
            href=f"/collection/{quote(name)}",
        ))

    # Someone you keep coming back to.
    creators = conn.execute(
        f"SELECT coalesce(creator_handle, creator_name) AS k, count(*) AS n FROM items"
        f" WHERE {RESOLVED} AND k IS NOT NULL GROUP BY k HAVING n >= 2"
        f" ORDER BY n DESC LIMIT 6"
    ).fetchall()
    for row in creators:
        items = _items_where(
            conn, "coalesce(creator_handle, creator_name) = ?", (row["k"],)
        )
        if items:
            candidates.append(_shelf(
                "creator", _creator_label(items[0]),
                f"You have saved {row['n']} from them", items,
                href=f"/creator/{row['k']}",
            ))

    # Things you have not looked at in a long time. This is the shelf that
    # justifies the whole exercise -- it is the only one that surfaces
    # something you were not already thinking about.
    old_cutoff = _cutoff(120, now)
    old = db.rows_to_dicts(conn.execute(
        f"SELECT * FROM items WHERE {RESOLVED} AND saved_at < ?"
        f" ORDER BY random() LIMIT 8", (old_cutoff,)
    ).fetchall())
    if len(old) >= 3:
        candidates.append(_shelf(
            "rediscover", "From the vault",
            "Saved a while ago, and easy to forget", old,
        ))

    # Items with no note. A museum piece without a placard.
    unlabelled = _items_where(conn, "note IS NULL OR trim(note) = ''", ())
    if len(unlabelled) >= 4:
        candidates.append(_shelf(
            "unlabelled", "Missing a placard",
            "No note yet -- a line now saves you guessing later", unlabelled,
            href="/unlabelled",
        ))

    rng.shuffle(candidates)
    # One shelf per kind, so the page never shows three themed rooms in a row.
    seen_kinds: set[str] = set()
    for shelf in candidates:
        if len(out) >= max_shelves:
            break
        if shelf["kind"] in seen_kinds:
            continue
        seen_kinds.add(shelf["kind"])
        out.append(shelf)

    return out
