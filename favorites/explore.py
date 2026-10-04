"""Search and filters: one page that narrows the whole library.

Every filter lives in the page address (``/search?platform=tiktok&season=summer``)
so a narrowed view can be bookmarked, shared with yourself, or reached with the
back button, and the page needs no JavaScript to work.

Filters combine: each one you add narrows what the others see. Next to every
option is how many saves it would leave -- counted with every *other* filter
applied, so picking a year shows what each platform holds in that year rather
than just greying everything out.

Seasons are read from the day you saved something, in the northern hemisphere
(winter is December to February). They answer "what do I keep in the summer",
which a year cannot.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, fields, replace
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

from . import db, tagging
from .themes import UNDEFINED
from .resolve import platform_label

PAGE_SIZE = 48

SEASONS = {
    "winter": ("Winter", ("12", "01", "02")),
    "spring": ("Spring", ("03", "04", "05")),
    "summer": ("Summer", ("06", "07", "08")),
    "autumn": ("Autumn", ("09", "10", "11")),
}

FORMATS = {"short": "Short-form video", "video": "Long-form video"}

# (label, phrase for the heading, from seconds, up to seconds). Bands a person
# would say out loud, not equal slices.
LENGTHS = {
    "under1": ("Under a minute", "under a minute", 0, 60),
    "1to3": ("1–3 minutes", "1–3 minutes long", 60, 180),
    "3to10": ("3–10 minutes", "3–10 minutes long", 180, 600),
    "10to30": ("10–30 minutes", "10–30 minutes long", 600, 1800),
    "over30": ("Over 30 minutes", "over 30 minutes long", 1800, None),
}

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# "On this day" is a month and day (09-27) matched across every year. The
# week version reaches three days either side -- close enough to be the same
# time of year, far enough that a quiet date still turns something up.
WEEK_REACH = 3


def day_label(day: str) -> str:
    """09-27 -> 27 September. The week option's value ("09-27~") reads the same."""
    day = day.rstrip("~")
    return f"{int(day[3:])} {MONTHS[int(day[:2]) - 1]}"


def week_days(day: str) -> set[str]:
    """The month-days within WEEK_REACH of ``day``, wrapping the new year."""
    centre = datetime.strptime("2000-" + day.rstrip("~"), "%Y-%m-%d")
    return {(centre + timedelta(days=k)).strftime("%m-%d") for k in range(-WEEK_REACH, WEEK_REACH + 1)}


def today_key(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%m-%d")


def _valid_day(raw: str) -> bool:
    if not re.fullmatch(r"\d{2}-\d{2}", raw):
        return False
    try:
        datetime.strptime("2000-" + raw, "%Y-%m-%d")  # a leap year, so 02-29 is fine
    except ValueError:
        return False
    return True


SORTS = {"relevance": "Best match", "newest": "Newest saved", "oldest": "Oldest saved"}

# How many options to list for the open-ended facets. The rest are still
# reachable -- by searching, or from an item's own page.
TOP = {"creator": 12, "tag": 20, "theme": 40, "collection": 30}


@dataclass(frozen=True)
class Filters:
    q: str = ""
    platform: str = ""
    format: str = ""
    year: str = ""
    season: str = ""
    day: str = ""    # MM-DD, in any year
    week: str = ""   # "1": within WEEK_REACH days of ``day`` rather than on it
    collection: str = ""
    creator: str = ""
    tag: str = ""
    theme: str = ""
    length: str = ""
    noted: str = ""
    sort: str = ""
    page: int = 1

    @classmethod
    def from_params(cls, params) -> "Filters":
        """Read filters from a query string, dropping anything malformed."""
        values = {}
        for f in fields(cls):
            raw = params.get(f.name)
            if raw is None:
                continue
            raw = str(raw).strip()
            if f.name == "page":
                values["page"] = max(1, int(raw)) if raw.isdigit() else 1
            else:
                values[f.name] = raw[:200]
        out = cls(**values)
        if out.season and out.season not in SEASONS:
            out = replace(out, season="")
        if out.format and out.format not in FORMATS:
            out = replace(out, format="")
        if out.length and out.length not in LENGTHS:
            out = replace(out, length="")
        if out.year and not (out.year.isdigit() and len(out.year) == 4):
            out = replace(out, year="")
        if out.day and not _valid_day(out.day):
            out = replace(out, day="")
        if out.week and (out.week != "1" or not out.day):
            out = replace(out, week="")
        if out.sort and out.sort not in SORTS:
            out = replace(out, sort="")
        if out.noted and out.noted != "1":
            out = replace(out, noted="")
        return out

    @property
    def order(self) -> str:
        if self.sort == "relevance" and not self.q:
            return "newest"
        return self.sort or ("relevance" if self.q else "newest")

    def narrowing(self) -> dict[str, str]:
        """The filters that narrow results, as name -> value."""
        skip = {"q", "sort", "page"}
        return {f.name: getattr(self, f.name) for f in fields(self)
                if f.name not in skip and getattr(self, f.name)}

    def href(self, **changes) -> str:
        """This view's address with some filters changed; ``None`` removes one.

        Changing anything but the page goes back to page 1 -- page 3 of a
        different set of results is not a place anyone meant to go.
        """
        if "page" not in changes:
            changes["page"] = 1
        merged = {f.name: getattr(self, f.name) for f in fields(self)}
        merged.update({k: ("" if v is None else v) for k, v in changes.items()})
        params = {k: v for k, v in merged.items() if v and not (k == "page" and v == 1)}
        return "/search" + (f"?{urlencode(params)}" if params else "")


# --- the query --------------------------------------------------------------

def _clauses(f: Filters, without: str = "") -> tuple[list[str], list]:
    """WHERE clauses for every filter except ``without`` (for facet counts)."""
    where: list[str] = []
    params: list = []
    if f.q and without != "q":
        match = db.fts_query(f.q)
        if match:
            where.append("i.id IN (SELECT item_id FROM items_fts WHERE items_fts MATCH ?)")
            params.append(match)
    if f.platform and without != "platform":
        where.append("i.platform = ?")
        params.append(f.platform)
    if f.format and without != "format":
        where.append("i.format = ?")
        params.append(f.format)
    if f.year and without != "year":
        where.append("substr(i.saved_at, 1, 4) = ?")
        params.append(f.year)
    if f.season and without != "season":
        months = SEASONS[f.season][1]
        where.append(f"substr(i.saved_at, 6, 2) IN ({', '.join('?' * len(months))})")
        params.extend(months)
    if f.day and without != "day":
        sql, extra = _day_clause(f.day, bool(f.week))
        where.append(sql)
        params.extend(extra)
    if f.collection and without != "collection":
        where.append("EXISTS (SELECT 1 FROM collections c WHERE c.item_id = i.id"
                     " AND c.name = ? COLLATE NOCASE)")
        params.append(f.collection)
    if f.creator and without != "creator":
        where.append("coalesce(i.creator_handle, i.creator_name) = ?")
        params.append(f.creator)
    if f.tag and without != "tag":
        where.append("EXISTS (SELECT 1 FROM json_each(i.tags) WHERE value = ?)")
        params.append(f.tag.lower().lstrip("#"))
    if f.theme and without != "theme":
        if f.theme.lower() == UNDEFINED.lower():
            where.append(_UNTHEMED)
        else:
            where.append("EXISTS (SELECT 1 FROM json_each(i.themes) WHERE value = ? COLLATE NOCASE)")
            params.append(f.theme)
    if f.length and without != "length":
        _, _, lo, hi = LENGTHS[f.length]
        where.append("i.duration >= ?" + (" AND i.duration < ?" if hi else ""))
        params.extend([lo, hi] if hi else [lo])
    if f.noted and without != "noted":
        where.append("trim(coalesce(i.note, '')) != ''")
    return where, params


def _day_clause(day: str, week: bool) -> tuple[str, list]:
    if week:
        # Distance in days within a year, wrapping at New Year, measured in a
        # leap year so 29 February has somewhere to be.
        gap = "abs(julianday('2000-' || substr(i.saved_at, 6, 5)) - julianday('2000-' || ?))"
        return f"min({gap}, 366 - {gap}) <= ?", [day, day, WEEK_REACH]
    return "substr(i.saved_at, 6, 5) = ?", [day]


def _where_sql(where: list[str]) -> str:
    return (" WHERE " + " AND ".join(where)) if where else ""


def _like_fallback(f: Filters) -> Filters:
    """FTS rejected the query: keep the other filters, search by substring."""
    return replace(f, q="")


def results(conn: sqlite3.Connection, f: Filters) -> tuple[list[dict], int]:
    """One page of matching saves, and how many match in all."""
    where, params = _clauses(f)
    try:
        return _results(conn, f, where, params)
    except sqlite3.OperationalError:
        # The search box must never produce an error page. db.fts_query quotes
        # every token, so this is belt and braces -- but it is cheap.
        g = _like_fallback(f)
        where, params = _clauses(g)
        like = f"%{f.q}%"
        where.append("(i.title LIKE ? OR i.description LIKE ? OR i.note LIKE ?"
                     " OR i.creator_name LIKE ? OR i.creator_handle LIKE ?)")
        params.extend([like] * 5)
        return _results(conn, g, where, params)


def _results(conn, f: Filters, where: list[str], params: list) -> tuple[list[dict], int]:
    sql_where = _where_sql(where)
    total = conn.execute(f"SELECT count(*) FROM items i{sql_where}", params).fetchone()[0]
    order = {
        "newest": "i.saved_at DESC, i.id DESC",
        "oldest": "i.saved_at ASC, i.id ASC",
    }.get(f.order)
    offset = (f.page - 1) * PAGE_SIZE
    if order is None:  # relevance
        match = db.fts_query(f.q)
        rows = conn.execute(
            "SELECT i.* FROM items i JOIN (SELECT item_id, rank FROM items_fts"
            " WHERE items_fts MATCH ?) hit ON hit.item_id = i.id"
            f"{sql_where} ORDER BY hit.rank, i.saved_at DESC LIMIT ? OFFSET ?",
            [match, *params, PAGE_SIZE, offset],
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT i.* FROM items i{sql_where} ORDER BY {order} LIMIT ? OFFSET ?",
            [*params, PAGE_SIZE, offset],
        ).fetchall()
    return db.rows_to_dicts(rows), int(total)


# --- the options beside the results ------------------------------------------

@dataclass
class Option:
    value: str
    label: str
    count: int
    href: str
    active: bool = False
    kind: str = ""


# Saves no theme recognises yet: the "Undefined" option.
_UNTHEMED = "json_array_length(coalesce(nullif(i.themes, ''), '[]')) = 0"


@dataclass
class Facet:
    name: str
    title: str
    options: list[Option]
    more: int = 0  # options beyond the ones listed

    @property
    def active(self) -> Optional[Option]:
        return next((o for o in self.options if o.active), None)


def _grouped(conn, f: Filters, name: str, select: str, joins: str = "",
             order: str = "n DESC, v", extra_where: str = "") -> list[tuple[str, int, str]]:
    where, params = _clauses(f, without=name)
    if extra_where:
        where.append(extra_where)
    sql = (f"SELECT {select} FROM items i{joins}{_where_sql(where)}"
           f" GROUP BY v HAVING v IS NOT NULL AND v != '' ORDER BY {order}")
    try:
        return [tuple(r) for r in conn.execute(sql, params).fetchall()]
    except sqlite3.OperationalError:
        return []


def _facet(f: Filters, name: str, title: str, rows, label=lambda v, extra: v,
           limit: Optional[int] = None, keep_order: bool = False) -> Optional[Facet]:
    current = getattr(f, name)
    options = [
        Option(value=str(v), label=label(str(v), extra), count=int(n),
               href=f.href(**{name: None if str(v).lower() == current.lower() else v}),
               active=bool(current) and str(v).lower() == current.lower())
        for v, n, extra in rows
    ]
    if not options:
        return None
    more = 0
    if limit and len(options) > limit:
        chosen = options[:limit]
        # The active option always stays visible, even if it is not a top one.
        chosen += [o for o in options[limit:] if o.active]
        more = len(options) - len(chosen)
        options = chosen
    return Facet(name=name, title=title, options=options, more=more)


def _with_undefined(conn, f: Filters, facet: Optional[Facet]) -> Optional[Facet]:
    """Put "Undefined" at the top of the themes: the saves no theme covers.

    First, not buried after thirty subjects, because it is a to-do list --
    the saves worth looking through and filing -- rather than a subject.
    """
    where, params = _clauses(f, without="theme")
    n = conn.execute("SELECT count(*) FROM items i" + _where_sql(where + [_UNTHEMED]),
                     params).fetchone()[0]
    active = f.theme.lower() == UNDEFINED.lower()
    if not n and not active:
        return facet
    undefined = Option(value=UNDEFINED, label=UNDEFINED, count=int(n), kind="undefined",
                       href=f.href(theme=None if active else UNDEFINED), active=active)
    if facet is None:
        return Facet(name="theme", title="Themes", options=[undefined])
    facet.options = [undefined] + [o for o in facet.options if o.value != UNDEFINED]
    return facet


def _day_facet(conn, f: Filters, today: str) -> Optional[Facet]:
    """On this day, and the week around it, in every year you have saved things.

    Offered for today unless another date is chosen, in which case that date
    is shown (so the chosen option is always visible and removable).
    """
    day = f.day or today
    where, params = _clauses(f, without="day")

    def count(week: bool) -> int:
        sql, extra = _day_clause(day, week)
        return int(conn.execute("SELECT count(*) FROM items i" + _where_sql(where + [sql]),
                                params + extra).fetchone()[0])

    on_day, in_week = count(False), count(True)
    on = bool(f.day) and not f.week
    week_on = bool(f.day) and bool(f.week)
    label = "On this day" if day == today else f"On {day_label(day)}"
    options = []
    if on_day or on:
        options.append(Option(value=day, label=label, count=on_day, kind="hook",
                              href=f.href(day=None, week=None) if on else f.href(day=day, week=None),
                              active=on))
    if in_week > on_day or week_on:
        options.append(Option(value=day + "~", label="This week, other years" if day == today
                              else f"Week of {day_label(day)}", count=in_week, kind="hook",
                              href=f.href(day=None, week=None) if week_on else f.href(day=day, week="1"),
                              active=week_on))
    return Facet(name="day", title="On this day", options=options) if options else None


def facets(conn: sqlite3.Connection, f: Filters, today: Optional[str] = None) -> list[Facet]:
    """The filter column, in the order people reach for it.

    Who made it and what it is about come first -- that is how a save is
    remembered. When you saved it comes after, and the season last: a nice
    question to be able to ask, not the one you usually arrive with.
    """
    out: list[Optional[Facet]] = []

    out.append(_facet(f, "platform", "Platform", _grouped(
        conn, f, "platform", "i.platform AS v, count(*) AS n, '' AS x"),
        label=lambda v, _: platform_label(v)))

    out.append(_facet(f, "creator", "Creators", _grouped(
        conn, f, "creator",
        "coalesce(i.creator_handle, i.creator_name) AS v, count(*) AS n,"
        " max(coalesce(i.creator_name, '')) AS x"),
        label=lambda v, name: name or v, limit=TOP["creator"]))

    out.append(_with_undefined(conn, f, _facet(f, "theme", "Themes", _grouped(
        conn, f, "theme", "j.value AS v, count(DISTINCT i.id) AS n, '' AS x",
        joins=", json_each(i.themes) j"), limit=TOP["theme"])))

    out.append(_facet(f, "tag", "Hashtags", _grouped(
        conn, f, "tag", "j.value AS v, count(DISTINCT i.id) AS n, '' AS x",
        joins=", json_each(i.tags) j"),
        label=lambda v, _: "#" + v, limit=TOP["tag"]))

    out.append(_facet(f, "collection", "Your categories", _grouped(
        conn, f, "collection",
        "c.name COLLATE NOCASE AS v, count(DISTINCT i.id) AS n, '' AS x",
        joins=" JOIN collections c ON c.item_id = i.id"), limit=TOP["collection"]))

    length_case = "CASE " + " ".join(
        f"WHEN i.duration >= {lo}" + (f" AND i.duration < {hi}" if hi else "") + f" THEN '{key}'"
        for key, (_, _, lo, hi) in LENGTHS.items()) + " END"
    found = {v: (n, x) for v, n, x in _grouped(
        conn, f, "length", f"{length_case} AS v, count(*) AS n, '' AS x")}
    out.append(_facet(f, "length", "Length",
                      [(k, *found[k]) for k in LENGTHS if k in found],
                      label=lambda v, _: LENGTHS[v][0]))

    out.append(_day_facet(conn, f, today or today_key()))

    out.append(_facet(f, "year", "Year saved", _grouped(
        conn, f, "year", "substr(i.saved_at, 1, 4) AS v, count(*) AS n, '' AS x",
        order="v DESC")))

    out.append(_facet(f, "format", "Kind", _grouped(
        conn, f, "format", "i.format AS v, count(*) AS n, '' AS x"),
        label=lambda v, _: FORMATS.get(v, v)))

    season_case = "CASE " + " ".join(
        f"WHEN substr(i.saved_at, 6, 2) IN ({', '.join(repr(m) for m in months)}) THEN '{key}'"
        for key, (_, months) in SEASONS.items()) + " END"
    seasons = {v: (n, x) for v, n, x in _grouped(
        conn, f, "season", f"{season_case} AS v, count(*) AS n, '' AS x")}
    out.append(_facet(f, "season", "Season saved",
                      [(k, *seasons[k]) for k in SEASONS if k in seasons],
                      label=lambda v, _: SEASONS[v][0]))

    noted_n = conn.execute(
        "SELECT count(*) FROM items i" + _where_sql(
            _clauses(f, without="noted")[0] + ["trim(coalesce(i.note, '')) != ''"]),
        _clauses(f, without="noted")[1]).fetchone()[0]
    if noted_n or f.noted:
        out.append(Facet(name="noted", title="Your notes", options=[Option(
            value="1", label="Has a note", count=int(noted_n),
            href=f.href(noted=None if f.noted else "1"), active=bool(f.noted))]))

    # A hashtag seen on a single save is noise, not an option; showing
    # hundreds of them buries the ones that recur. So is #fyp in any spelling.
    for facet in out:
        if facet and facet.name == "tag":
            facet.options = [o for o in facet.options
                             if o.active or (o.count >= 2 and not tagging.is_noise(o.value))]
    return [x for x in out if x and x.options]


def chips(f: Filters, found: list[Facet]) -> list[tuple[str, str]]:
    """(label, address without it) for each active filter, for the chip row."""
    labels = {facet.name: facet.active.label for facet in found if facet.active}
    out = []
    for name, value in f.narrowing().items():
        if name == "week":
            continue  # part of the day chip
        if name == "day":
            label = labels.get(name) or (("Week of " if f.week else "On ") + day_label(value))
            out.append((label, f.href(day=None, week=None)))
            continue
        label = labels.get(name) or {
            "tag": "#" + value.lstrip("#"),
            "season": SEASONS.get(value, (value,))[0],
            "format": FORMATS.get(value, value),
            "length": LENGTHS.get(value, (value,))[0],
            "platform": platform_label(value),
            "noted": "Has a note",
        }.get(name, value)
        out.append((label, f.href(**{name: None})))
    return out


def describe(f: Filters, found: list[Facet]) -> str:
    """The view in words: "TikTok saves tagged #cooking, from summers".

    A heading that says what you are looking at, so a bookmarked or
    half-remembered view still makes sense when you come back to it.
    """
    if not f.narrowing():
        return f"“{f.q}”" if f.q else "Everything"
    labels = {facet.name: facet.active.label for facet in found if facet.active}

    def label(name: str) -> str:
        return labels.get(name) or getattr(f, name)

    noun = "saves"
    if f.format:
        noun = {"short": "short-form videos", "video": "long-form videos"}[f.format]
    if f.platform:
        noun = f"{platform_label(f.platform)} {noun}"
    undefined = f.theme.lower() == UNDEFINED.lower()
    if undefined:
        noun = f"undefined {noun}"
    parts = [noun]
    if f.q:
        parts.append(f"matching “{f.q}”")
    if f.tag:
        parts.append(f"tagged #{f.tag.lstrip('#').lower()}")
    if f.theme and not undefined:
        parts.append(f"about {label('theme')}")
    if f.creator:
        parts.append(f"by {label('creator')}")
    if f.collection:
        parts.append(f"filed under {label('collection')}")
    if f.length:
        parts.append(LENGTHS[f.length][1])
    when = []
    if f.season:
        when.append(f"{SEASONS[f.season][0].lower()}{'' if f.year else 's'}")
    if f.year:
        when.append(f.year)
    if when:
        parts.append("from " + " ".join(when))
    if f.day:
        parts.append(("saved the week of " if f.week else "saved on ") + day_label(f.day))
    text = " ".join(parts)
    if f.noted:
        text += ", with your notes"
    return text[0].upper() + text[1:]


def pull(f: Filters, found: list[Facet], items: list[dict], limit: int = 4) -> list[dict]:
    """Where to go next from a set of results: the biggest rooms and creators
    inside them, and the same date in other years.

    Each row adds one filter to the current view (so it narrows by a
    direction you did not think of), with covers taken from the results
    already on the page.
    """
    by_name = {facet.name: facet for facet in found}
    rows: list[dict] = []

    def covers(test) -> list[dict]:
        return [i for i in items if test(i)][:3]

    theme = by_name.get("theme")
    if theme and not f.theme:
        for o in [o for o in theme.options if not o.kind][:2]:
            rows.append({"label": o.label, "sub": f"Room · {o.count} of these",
                         "href": o.href, "covers": covers(lambda i, v=o.value: v in (i.get("themes") or []))})
    creator = by_name.get("creator")
    if creator and not f.creator and creator.options and creator.options[0].count >= 2:
        o = creator.options[0]
        rows.append({"label": o.label, "sub": f"Creator · {o.count} of these", "href": o.href,
                     "covers": covers(lambda i, v=o.value: (i.get("creator_handle") or i.get("creator_name")) == v)})
    day = by_name.get("day")
    if day and not f.day and day.options:
        # On a day with nothing saved on the date itself, the only option is the
        # week around it ("10-04~").
        o = day.options[0]
        if o.value.endswith("~"):
            near = week_days(o.value)
            rows.append({"label": o.label, "sub": f"{o.count} of these were saved the week of {day_label(o.value)}",
                         "href": o.href, "covers": covers(lambda i: (i.get("saved_at") or "")[5:10] in near)})
        else:
            rows.append({"label": o.label, "sub": f"{o.count} of these were saved on {day_label(o.value)}",
                         "href": o.href, "covers": covers(lambda i, v=o.value: (i.get("saved_at") or "")[5:10] == v)})
    return rows[:limit]
