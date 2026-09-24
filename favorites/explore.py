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

import sqlite3
from dataclasses import dataclass, fields, replace
from typing import Optional
from urllib.parse import urlencode

from . import db
from .resolve import platform_label

PAGE_SIZE = 48

SEASONS = {
    "winter": ("Winter", ("12", "01", "02")),
    "spring": ("Spring", ("03", "04", "05")),
    "summer": ("Summer", ("06", "07", "08")),
    "autumn": ("Autumn", ("09", "10", "11")),
}

FORMATS = {"short": "Short-form video", "video": "Long-form video"}

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
    collection: str = ""
    creator: str = ""
    tag: str = ""
    theme: str = ""
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
        if out.year and not (out.year.isdigit() and len(out.year) == 4):
            out = replace(out, year="")
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
        where.append("EXISTS (SELECT 1 FROM json_each(i.themes) WHERE value = ? COLLATE NOCASE)")
        params.append(f.theme)
    if f.noted and without != "noted":
        where.append("trim(coalesce(i.note, '')) != ''")
    return where, params


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


def facets(conn: sqlite3.Connection, f: Filters) -> list[Facet]:
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

    out.append(_facet(f, "theme", "Themes", _grouped(
        conn, f, "theme", "j.value AS v, count(DISTINCT i.id) AS n, '' AS x",
        joins=", json_each(i.themes) j"), limit=TOP["theme"]))

    out.append(_facet(f, "tag", "Hashtags", _grouped(
        conn, f, "tag", "j.value AS v, count(DISTINCT i.id) AS n, '' AS x",
        joins=", json_each(i.tags) j"),
        label=lambda v, _: "#" + v, limit=TOP["tag"]))

    out.append(_facet(f, "collection", "Your categories", _grouped(
        conn, f, "collection",
        "c.name COLLATE NOCASE AS v, count(DISTINCT i.id) AS n, '' AS x",
        joins=" JOIN collections c ON c.item_id = i.id"), limit=TOP["collection"]))

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
    # hundreds of them buries the ones that recur.
    for facet in out:
        if facet and facet.name == "tag":
            facet.options = [o for o in facet.options if o.count >= 2 or o.active]
    return [x for x in out if x and x.options]


def chips(f: Filters, found: list[Facet]) -> list[tuple[str, str]]:
    """(label, address without it) for each active filter, for the chip row."""
    labels = {facet.name: facet.active.label for facet in found if facet.active}
    out = []
    for name, value in f.narrowing().items():
        label = labels.get(name) or {
            "tag": "#" + value.lstrip("#"),
            "season": SEASONS.get(value, (value,))[0],
            "format": FORMATS.get(value, value),
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
    parts = [noun]
    if f.q:
        parts.append(f"matching “{f.q}”")
    if f.tag:
        parts.append(f"tagged #{f.tag.lstrip('#').lower()}")
    if f.theme:
        parts.append(f"about {label('theme')}")
    if f.creator:
        parts.append(f"by {label('creator')}")
    if f.collection:
        parts.append(f"filed under {label('collection')}")
    when = []
    if f.season:
        when.append(f"{SEASONS[f.season][0].lower()}{'' if f.year else 's'}")
    if f.year:
        when.append(f.year)
    if when:
        parts.append("from " + " ".join(when))
    text = " ".join(parts)
    if f.noted:
        text += ", with your notes"
    return text[0].upper() + text[1:]
