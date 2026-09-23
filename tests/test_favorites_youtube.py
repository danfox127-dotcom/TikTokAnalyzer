"""YouTube: a Takeout backfill, Shorts, and the categories you file things into.

YouTube's save button offers the same choice TikTok's does -- just save it
(Watch later), or file it under something (a playlist). The library keeps that
distinction: Watch later arrives uncategorised, every other playlist becomes a
collection, and a Short opens in the Shorts player rather than letterboxed.
"""

import asyncio
import io
import sqlite3
import zipfile

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from favorites import backfill, db, museum
from favorites.app import app
from favorites.importers import youtube_takeout as yt
from favorites.resolve import _is_placeholder_title, browsable_url, resolve

A, B, C, D = "aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc", "ddddddddddd"

YT_OEMBED = {
    "title": "How to fold a dumpling",
    "author_name": "Kitchen Desk",
    "author_url": "https://www.youtube.com/@kitchendesk",
    "thumbnail_url": "https://i.ytimg.com/vi/aaaaaaaaaaa/hqdefault.jpg",
}


def new_format(*rows):
    """The current Takeout layout: one CSV per playlist, two columns."""
    lines = ["Video ID,Playlist Video Creation Timestamp"]
    lines += [f"{v},{t}" for v, t in rows]
    return "\n".join(lines) + "\n"


def old_format(title, *rows, playlist_id="PLxyz"):
    """The older layout: a metadata block, a blank line, then the videos."""
    lines = [
        "Playlist Id,Channel Id,Time Created,Time Updated,Title,Description,Visibility",
        f"{playlist_id},UCabc,2019-01-01 00:00:00 UTC,2019-06-01 00:00:00 UTC,{title},,Private",
        "",
        "Video Id,Time Added",
    ]
    lines += [f"{v},{t}" for v, t in rows]
    return "\n".join(lines) + "\n"


def takeout(tmp_path, files: dict[str, str]):
    """Lay files out the way an unzipped Takeout does."""
    root = tmp_path / "Takeout" / "YouTube and YouTube Music"
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path / "Takeout"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "lib.db"))
    yield c
    c.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "favorites.db"))
    monkeypatch.delenv("FAVORITES_TOKEN", raising=False)
    with TestClient(app) as c:
        yield c


# --- reading a Takeout ------------------------------------------------------

class TestReadingTakeout:
    def test_the_current_layout(self):
        pl = yt.parse_playlist_csv(
            new_format((A, "2024-03-01T10:00:00+00:00")), "Watch later-videos.csv")
        assert pl.name == "Watch later"
        assert pl.kind == "watch-later"
        assert pl.entries == [(A, "2024-03-01T10:00:00+00:00")]

    def test_the_older_layout_takes_its_name_from_the_metadata(self):
        pl = yt.parse_playlist_csv(
            old_format("Dumplings", (A, "2019-02-03 04:05:06 UTC")), "whatever.csv")
        assert pl.name == "Dumplings"
        assert pl.kind == "category"
        assert pl.entries == [(A, "2019-02-03T04:05:06+00:00")]

    def test_the_playlist_index_is_not_mistaken_for_a_playlist(self):
        index = "Playlist ID,Playlist Title (Original),Playlist Visibility\nPL1,Dumplings,Private\n"
        assert yt.parse_playlist_csv(index, "playlists.csv") is None

    @pytest.mark.parametrize("raw,expected", [
        ("2019-02-03 04:05:06 UTC", "2019-02-03T04:05:06+00:00"),
        ("2024-03-01T10:00:00+00:00", "2024-03-01T10:00:00+00:00"),
        ("2024-03-01T10:00:00.123456+00:00", "2024-03-01T10:00:00+00:00"),
        ("2024-03-01T10:00:00Z", "2024-03-01T10:00:00+00:00"),
        ("2024-03-01T12:00:00+02:00", "2024-03-01T10:00:00+00:00"),
        ("not a date", None),
        ("", None),
    ])
    def test_timestamps(self, raw, expected):
        assert yt.parse_timestamp(raw) == expected

    def test_rows_that_are_not_video_ids_are_counted_not_imported(self):
        pl = yt.parse_playlist_csv(
            new_format((A, "2024-03-01T10:00:00+00:00"), ("", ""), ("nope", "x")), "X-videos.csv")
        assert [v for v, _ in pl.entries] == [A]
        assert pl.unusable == 1  # the blank row is skipped silently, "nope" is not

    def test_only_the_playlists_folder_is_read(self, tmp_path):
        # comments.csv has a Video ID column too. Read naively, every video you
        # ever commented on would become a category called "comments".
        root = takeout(tmp_path, {
            "playlists/Watch later-videos.csv": new_format((A, "2024-03-01T10:00:00+00:00")),
            "comments/comments.csv": "Comment ID,Video ID,Comment Text\nc1,bbbbbbbbbbb,hi\n",
        })
        assert [p.name for p in yt.read_takeout(root)] == ["Watch later"]

    def test_the_downloaded_zip_is_read_directly(self, tmp_path):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("Takeout/YouTube and YouTube Music/playlists/Dumplings-videos.csv",
                       new_format((A, "2024-03-01T10:00:00+00:00")))
            z.writestr("Takeout/YouTube and YouTube Music/comments/comments.csv",
                       "Comment ID,Video ID\nc1,bbbbbbbbbbb\n")
        path = tmp_path / "takeout.zip"
        path.write_bytes(buf.getvalue())
        assert [p.name for p in yt.read_takeout(path)] == ["Dumplings"]

    def test_pointing_at_the_playlists_folder_itself_works(self, tmp_path):
        root = takeout(tmp_path, {"playlists/Dumplings-videos.csv":
                                  new_format((A, "2024-03-01T10:00:00+00:00"))})
        folder = root / "YouTube and YouTube Music" / "playlists"
        assert [p.name for p in yt.read_takeout(folder)] == ["Dumplings"]


# --- importing --------------------------------------------------------------

def playlists(**named):
    out = []
    for name, rows in named.items():
        out.append(yt.Playlist(name=name.replace("_", " "), entries=list(rows)))
    return out


class TestImporting:
    def test_watch_later_arrives_as_just_saved(self, conn):
        yt.import_playlists(conn, playlists(Watch_later=[(A, "2024-03-01T10:00:00+00:00")]))
        row = db.rows_to_dicts(db.recent(conn))[0]
        assert row["platform"] == "youtube"
        assert row["external_id"] == A
        assert row["resolve_status"] == "pending"
        assert row["source"] == "youtube-takeout"
        assert row["saved_at"] == "2024-03-01T10:00:00+00:00"
        assert db.collections_for(conn, row["id"]) == []

    def test_a_playlist_you_made_becomes_a_category(self, conn):
        yt.import_playlists(conn, playlists(Dumplings=[(A, "2024-03-01T10:00:00+00:00")]))
        item_id = db.rows_to_dicts(db.recent(conn))[0]["id"]
        assert db.collections_for(conn, item_id) == ["Dumplings"]

    def test_one_video_in_two_places_is_one_item_filed_where_you_filed_it(self, conn):
        stats = yt.import_playlists(conn, playlists(
            Watch_later=[(A, "2024-05-01T00:00:00+00:00")],
            Dumplings=[(A, "2023-01-01T00:00:00+00:00")],
        ))
        assert stats["imported"] == 1
        row = db.rows_to_dicts(db.recent(conn))[0]
        assert row["saved_at"] == "2023-01-01T00:00:00+00:00"  # the earliest keep
        assert db.collections_for(conn, row["id"]) == ["Dumplings"]

    def test_a_like_date_does_not_backdate_a_keep(self, conn):
        pls = playlists(Watch_later=[(A, "2024-05-01T00:00:00+00:00")])
        pls += [yt.Playlist(name="Liked videos", entries=[(A, "2019-01-01T00:00:00+00:00")])]
        yt.import_playlists(conn, pls)
        assert db.rows_to_dicts(db.recent(conn))[0]["saved_at"] == "2024-05-01T00:00:00+00:00"

    def test_likes_are_left_out_unless_asked_for(self):
        pls = playlists(Watch_later=[(A, "t")])
        pls += [yt.Playlist(name="Liked videos", entries=[(B, "t")])]
        assert [p.name for p in yt._selected(pls, include_likes=False)] == ["Watch later"]
        assert len(yt._selected(pls, include_likes=True)) == 2

    def test_likes_by_playlist_id_are_recognised_in_any_language(self):
        assert yt.Playlist(name="Vidéos J'aime", playlist_id="LL").kind == "likes"
        assert yt.Playlist(name="À regarder plus tard", playlist_id="WL").kind == "watch-later"

    def test_liked_only_videos_are_tagged_so_they_can_be_told_apart(self, conn):
        yt.import_playlists(conn, [yt.Playlist(
            name="Liked videos", entries=[(B, "2024-01-01T00:00:00+00:00")])])
        assert db.rows_to_dicts(db.recent(conn))[0]["source"] == "youtube-takeout-like"

    def test_only_and_skip(self):
        pls = playlists(Watch_later=[(A, "t")], Dumplings=[(B, "t")], Music=[(C, "t")])
        assert [p.name for p in yt._selected(pls, False, only=["watch later"])] == ["Watch later"]
        assert [p.name for p in yt._selected(pls, False, skip=["Music"])] == ["Watch later", "Dumplings"]

    def test_an_existing_item_keeps_its_note_but_still_gets_filed(self, conn):
        item_id, _ = db.upsert_item(conn, {
            "canonical_url": f"https://www.youtube.com/watch?v={A}",
            "shared_url": f"https://youtu.be/{A}", "platform": "youtube",
            "external_id": A, "title": "Dumpling fold", "note": "the pleat trick",
            "resolve_status": "ok", "saved_at": "2025-01-01T00:00:00+00:00",
        })
        stats = yt.import_playlists(conn, playlists(Dumplings=[(A, "2023-01-01T00:00:00+00:00")]))
        assert stats == {"imported": 0, "already_present": 1, "undated": 0, "filings": 1}
        row = db.get_item(conn, item_id)
        assert row["note"] == "the pleat trick"
        assert row["title"] == "Dumpling fold"
        assert row["saved_at"] == "2025-01-01T00:00:00+00:00"
        assert db.collections_for(conn, item_id) == ["Dumplings"]

    def test_an_undated_video_is_counted_rather_than_given_a_fake_date(self, conn):
        stats = yt.import_playlists(conn, playlists(Watch_later=[(A, None)]))
        assert stats["undated"] == 1
        assert db.count(conn) == 0

    def test_importing_twice_changes_nothing(self, conn):
        pls = playlists(Dumplings=[(A, "2024-01-01T00:00:00+00:00")])
        yt.import_playlists(conn, pls)
        yt.import_playlists(conn, pls)
        assert db.count(conn) == 1
        assert db.collection_counts(conn) == [("Dumplings", 1)]

    def test_list_imports_nothing(self, tmp_path, capsys):
        root = takeout(tmp_path, {"playlists/Watch later-videos.csv":
                                  new_format((A, "2024-03-01T10:00:00+00:00"))})
        lib = tmp_path / "lib.db"
        assert yt.main([str(root), "--list", "--db", str(lib)]) == 0
        assert "Watch later" in capsys.readouterr().out
        assert not lib.exists()

    def test_a_path_that_is_not_there_yet_says_so_plainly(self, tmp_path, capsys):
        # Pointing at a folder that is still unzipping used to print a traceback.
        assert yt.main([str(tmp_path / "Takeout 2"), "--list"]) == 1
        out = capsys.readouterr().out
        assert "Nothing at" in out and "still unzipping" in out

    def test_a_half_downloaded_zip_says_so_plainly(self, tmp_path, capsys):
        partial = tmp_path / "takeout-001.zip"
        partial.write_bytes(b"PK\x03\x04 not finished")
        assert yt.main([str(partial), "--list"]) == 1
        assert "still be downloading" in capsys.readouterr().out

    def test_an_export_with_no_playlists_points_at_the_other_part(self, tmp_path, capsys):
        # What a split export looks like: the first part is only the index page.
        (tmp_path / "Takeout").mkdir()
        (tmp_path / "Takeout" / "archive_browser.html").write_text("<html></html>")
        assert yt.main([str(tmp_path / "Takeout"), "--list"]) == 1
        assert "Takeout 2" in capsys.readouterr().out

    def test_end_to_end_from_a_folder(self, tmp_path, capsys):
        root = takeout(tmp_path, {
            "playlists/Watch later-videos.csv": new_format((A, "2024-03-01T10:00:00+00:00")),
            "playlists/Dumplings-videos.csv": new_format((B, "2024-02-01T10:00:00+00:00")),
            "playlists/Liked videos-videos.csv": new_format((C, "2024-02-01T10:00:00+00:00")),
        })
        lib = tmp_path / "lib.db"
        assert yt.main([str(root), "--db", str(lib)]) == 0
        out = capsys.readouterr().out
        assert "not imported (--include-likes to add)" in out
        c = db.connect(str(lib))
        assert db.count(c) == 2
        assert db.collection_counts(c) == [("Dumplings", 1)]
        c.close()


# --- Shorts -----------------------------------------------------------------

def mock_youtube(probe=None):
    respx.get(host="www.youtube.com", path="/oembed").mock(
        return_value=httpx.Response(200, json=YT_OEMBED))
    route = respx.head(host="www.youtube.com", path__startswith="/shorts/")
    if isinstance(probe, Exception):
        route.mock(side_effect=probe)
    elif probe is not None:
        route.mock(return_value=probe)
    return route


@pytest.mark.asyncio
class TestShorts:
    @respx.mock
    async def test_a_shorts_link_is_a_short_without_asking(self):
        probe = mock_youtube(httpx.Response(200))
        async with httpx.AsyncClient() as client:
            item = await resolve(f"https://youtube.com/shorts/{A}?si=abc", client)
        assert item.format == "short"
        # Identity is unchanged: the same Short shared from a desktop files once.
        assert item.canonical_url == f"https://www.youtube.com/watch?v={A}"
        assert not probe.called

    @respx.mock
    async def test_a_watch_link_asks_and_learns_it_is_a_short(self):
        mock_youtube(httpx.Response(200))
        async with httpx.AsyncClient() as client:
            item = await resolve(f"https://www.youtube.com/watch?v={A}", client)
        assert item.format == "short"

    @respx.mock
    async def test_a_redirect_to_the_watch_page_means_long_form(self):
        mock_youtube(httpx.Response(303, headers={"location": f"https://www.youtube.com/watch?v={A}"}))
        async with httpx.AsyncClient() as client:
            item = await resolve(f"https://youtu.be/{A}", client)
        assert item.format == "video"

    @pytest.mark.parametrize("answer", [
        httpx.Response(302, headers={"location": "https://consent.youtube.com/m?continue=x"}),
        httpx.Response(429),
        httpx.ConnectError("offline"),
    ])
    @respx.mock
    async def test_an_ambiguous_answer_is_left_unknown_not_guessed(self, answer):
        mock_youtube(answer)
        async with httpx.AsyncClient() as client:
            item = await resolve(f"https://www.youtube.com/watch?v={A}", client)
        assert item.resolve_status == "ok"
        assert item.format is None

    @respx.mock
    async def test_a_dead_video_is_not_probed(self):
        respx.get(host="www.youtube.com", path="/oembed").mock(return_value=httpx.Response(404))
        respx.get(host="www.youtube.com", path="/watch").mock(return_value=httpx.Response(
            200, text="<html><head><title> - YouTube</title></head></html>",
            headers={"content-type": "text/html"}))
        probe = respx.head(host="www.youtube.com", path__startswith="/shorts/").mock(
            return_value=httpx.Response(200))
        async with httpx.AsyncClient() as client:
            item = await resolve(f"https://www.youtube.com/watch?v={A}", client)
        assert item.resolve_status == "unresolved"
        assert not probe.called


class TestShortLinks:
    def item(self, fmt):
        return {"platform": "youtube", "external_id": A, "format": fmt,
                "canonical_url": f"https://www.youtube.com/watch?v={A}",
                "shared_url": f"https://youtu.be/{A}"}

    def test_a_short_opens_in_the_shorts_player(self):
        assert browsable_url(self.item("short")) == f"https://www.youtube.com/shorts/{A}"

    @pytest.mark.parametrize("fmt", ["video", None])
    def test_anything_else_opens_at_its_watch_url(self, fmt):
        assert browsable_url(self.item(fmt)) == f"https://www.youtube.com/watch?v={A}"

    def test_an_inconclusive_re_resolve_does_not_forget_a_short(self, conn):
        payload = {"canonical_url": f"https://www.youtube.com/watch?v={A}",
                   "shared_url": "x", "platform": "youtube", "format": "short"}
        item_id, _ = db.upsert_item(conn, payload)
        db.upsert_item(conn, {**payload, "format": None})
        assert db.get_item(conn, item_id)["format"] == "short"

    def test_a_definite_answer_can_still_correct_it(self, conn):
        payload = {"canonical_url": f"https://www.youtube.com/watch?v={A}",
                   "shared_url": "x", "platform": "youtube", "format": "short"}
        item_id, _ = db.upsert_item(conn, payload)
        db.upsert_item(conn, {**payload, "format": "video"})
        assert db.get_item(conn, item_id)["format"] == "video"


class TestYouTubePlaceholder:
    """The TikTok lesson, again: an unavailable video's page is not a title."""

    @pytest.mark.parametrize("title", [" - YouTube", "- YouTube", "YouTube", "YouTube -"])
    def test_the_site_name_with_an_empty_slot_is_a_placeholder(self, title):
        assert _is_placeholder_title(title, "youtube")

    @pytest.mark.parametrize("title", ["How to fold a dumpling - YouTube", "YouTube Rewind 2018"])
    def test_a_real_title_ending_or_starting_with_the_site_name_is_kept(self, title):
        assert not _is_placeholder_title(title, "youtube")

    def test_the_tiktok_guard_still_holds(self):
        assert _is_placeholder_title("TikTok", "tiktok")
        assert not _is_placeholder_title("the zoning meeting went sideways", "tiktok")


# --- backfill ---------------------------------------------------------------

class TestBackfill:
    @respx.mock
    def test_an_imported_short_resolves_and_learns_its_format(self, conn):
        mock_youtube(httpx.Response(200))
        yt.import_playlists(conn, playlists(Watch_later=[(A, "2024-03-01T10:00:00+00:00")]))
        result = asyncio.run(backfill.run(conn, None, quiet=True))
        assert result["resolved"] == 1
        row = db.rows_to_dicts(db.recent(conn))[0]
        assert row["title"] == "How to fold a dumpling"
        assert row["format"] == "short"
        assert row["saved_at"] == "2024-03-01T10:00:00+00:00"  # your date, not today's
        assert browsable_url(row) == f"https://www.youtube.com/shorts/{A}"

    @respx.mock
    def test_stats_show_the_shorts_split_so_a_bad_probe_is_visible(self, conn, capsys):
        mock_youtube(httpx.Response(200))
        yt.import_playlists(conn, playlists(Watch_later=[(A, "2024-03-01T10:00:00+00:00")]))
        asyncio.run(backfill.run(conn, None, quiet=True))
        s = backfill.stats(conn)
        assert s["youtube_formats"] == {"short": 1}
        backfill._print_stats(s)
        assert "1 Shorts, 0 long videos, 0 not yet known" in capsys.readouterr().out

    def test_stats_stay_quiet_about_youtube_when_there_is_none(self, conn, capsys):
        backfill._print_stats(backfill.stats(conn))
        assert "YouTube" not in capsys.readouterr().out

    @respx.mock
    def test_transcripts_can_be_switched_off_for_a_big_run(self, conn, monkeypatch):
        mock_youtube(httpx.Response(200))
        calls = []
        monkeypatch.setattr(backfill.transcript, "fetch",
                            lambda *a, **k: calls.append(a) or "spoken words")
        yt.import_playlists(conn, playlists(Watch_later=[(A, "2024-03-01T10:00:00+00:00")]))
        asyncio.run(backfill.run(conn, None, quiet=True, transcripts=False))
        assert calls == []
        assert db.rows_to_dicts(db.recent(conn))[0]["transcript"] is None

    @respx.mock
    def test_transcripts_are_still_fetched_by_default(self, conn, monkeypatch):
        mock_youtube(httpx.Response(200))
        monkeypatch.setattr(backfill.transcript, "fetch", lambda *a, **k: "spoken words")
        yt.import_playlists(conn, playlists(Watch_later=[(A, "2024-03-01T10:00:00+00:00")]))
        asyncio.run(backfill.run(conn, None, quiet=True))
        assert db.rows_to_dicts(db.recent(conn))[0]["transcript"] == "spoken words"


# --- collections ------------------------------------------------------------

def resolved(conn, vid, collection=None, title="A dumpling video", saved="2024-01-01T00:00:00+00:00"):
    item_id, _ = db.upsert_item(conn, {
        "canonical_url": f"https://www.youtube.com/watch?v={vid}", "shared_url": "x",
        "platform": "youtube", "external_id": vid, "title": title,
        "resolve_status": "ok", "saved_at": saved,
    })
    if collection:
        db.file_under(conn, item_id, collection, saved)
    return item_id


class TestCollections:
    def test_names_match_whatever_case_you_type(self, conn):
        a = resolved(conn, A, "Dumplings")
        b = resolved(conn, B)
        assert db.file_under(conn, b, "  dumplings ") == "Dumplings"
        assert db.collection_counts(conn) == [("Dumplings", 2)]
        assert db.collections_for(conn, a) == ["Dumplings"]

    def test_the_earliest_filing_date_wins(self, conn):
        item_id = resolved(conn, A)
        db.file_under(conn, item_id, "Dumplings", "2024-05-01T00:00:00+00:00")
        db.file_under(conn, item_id, "Dumplings", "2023-01-01T00:00:00+00:00")
        db.file_under(conn, item_id, "Dumplings", None)
        added = conn.execute("SELECT added_at FROM collections").fetchone()[0]
        assert added == "2023-01-01T00:00:00+00:00"

    def test_a_blank_name_files_nothing(self, conn):
        assert db.file_under(conn, resolved(conn, A), "   ") is None
        assert db.collection_counts(conn) == []

    def test_a_category_name_is_searchable(self, conn):
        resolved(conn, A, "Weeknight dinners", title="untitled")
        assert len(db.search(conn, "weeknight")) == 1

    def test_deleting_an_item_takes_its_filings_with_it(self, conn):
        item_id = resolved(conn, A, "Dumplings")
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        assert db.collection_counts(conn) == []

    def test_a_category_you_made_gets_a_shelf(self, conn):
        for i, vid in enumerate([A, B, C, D]):
            resolved(conn, vid, "Dumplings" if i < 2 else None,
                     saved=f"2024-0{i + 1}-01T00:00:00+00:00")
        found = [s for day in range(1, 29)
                 for s in museum.shelves(conn, now=museum.datetime(2024, 6, day,
                                                                  tzinfo=museum.timezone.utc),
                                         max_shelves=10)
                 if s["kind"] == "collection"]
        assert found, "no collection shelf across a month of rotations"
        shelf = found[0]
        assert shelf["title"] == "Dumplings"
        assert shelf["href"] == "/collection/Dumplings"
        assert len(shelf["entries"]) == 2

    def test_unresolved_items_do_not_make_a_shelf_look_fuller_than_it_is(self, conn):
        resolved(conn, A, "Dumplings")
        pending_id, _ = db.upsert_item(conn, {
            "canonical_url": f"https://www.youtube.com/watch?v={B}", "shared_url": "x",
            "platform": "youtube", "resolve_status": "pending"})
        db.file_under(conn, pending_id, "Dumplings")
        assert db.collection_counts(conn, resolved_only=True) == [("Dumplings", 1)]
        assert db.collection_counts(conn) == [("Dumplings", 2)]


class TestCollectionsInTheApp:
    @respx.mock
    def test_a_share_can_file_into_a_category_in_one_step(self, client):
        mock_youtube(httpx.Response(200))
        resp = client.post("/save", json={
            "url": f"https://youtube.com/shorts/{A}?si=x", "collection": "Dumplings"})
        assert resp.status_code == 201
        assert resp.json()["collection"] == "Dumplings"
        # ...and a plain share is still just a save.
        resp = client.post("/save", json={"url": f"https://youtube.com/shorts/{B}"})
        assert resp.json()["collection"] is None

    @respx.mock
    def test_the_shortcut_can_fetch_your_categories_as_a_menu(self, client):
        mock_youtube(httpx.Response(200))
        for vid, name in [(A, "Dumplings"), (B, "Dumplings"), (C, "Knife skills")]:
            client.post("/save", json={"url": f"https://youtu.be/{vid}", "collection": name})
        assert client.get("/collections.json").json() == ["Dumplings", "Knife skills"]

    def test_the_menu_is_behind_the_token_like_save_is(self, client, monkeypatch):
        monkeypatch.setenv("FAVORITES_TOKEN", "secret")
        assert client.get("/collections.json").status_code == 401
        assert client.get("/collections.json",
                          headers={"Authorization": "Bearer secret"}).status_code == 200

    @respx.mock
    def test_a_collection_has_its_own_page_and_the_item_says_where_it_is_filed(self, client):
        mock_youtube(httpx.Response(200))
        item_id = client.post("/save", json={
            "url": f"https://youtube.com/shorts/{A}", "collection": "Knife skills"}).json()["id"]
        page = client.get("/collection/Knife skills")
        assert page.status_code == 200
        assert "How to fold a dumpling" in page.text
        detail = client.get(f"/item/{item_id}").text
        assert "Filed under" in detail
        assert "/collection/Knife%20skills" in detail
        assert "Watch the Short" in detail
        assert f"https://www.youtube.com/shorts/{A}" in detail

    @respx.mock
    def test_something_just_saved_can_be_filed_and_unfiled_later(self, client):
        mock_youtube(httpx.Response(200))
        item_id = client.post("/save", json={"url": f"https://youtu.be/{A}"}).json()["id"]
        resp = client.post(f"/item/{item_id}/file", data={"name": "Dumplings"},
                           follow_redirects=False)
        assert resp.status_code == 303
        assert "/collection/Dumplings" in client.get(f"/item/{item_id}").text

        client.post(f"/item/{item_id}/unfile", data={"name": "dumplings"})
        assert "Filed under" not in client.get(f"/item/{item_id}").text
        assert client.get("/collections.json").json() == []

    def test_filing_a_missing_item_is_a_404(self, client):
        assert client.post("/item/999/file", data={"name": "x"}).status_code == 404
        assert client.post("/item/999/unfile", data={"name": "x"}).status_code == 404

    @respx.mock
    def test_the_item_page_suggests_categories_it_is_not_already_in(self, client):
        mock_youtube(httpx.Response(200))
        client.post("/save", json={"url": f"https://youtu.be/{A}", "collection": "Dumplings"})
        item_id = client.post("/save", json={"url": f"https://youtu.be/{B}",
                                             "collection": "Knife skills"}).json()["id"]
        page = client.get(f"/item/{item_id}").text
        datalist = page.split('<datalist id="all-collections">')[1].split("</datalist>")[0]
        assert '<option value="Dumplings">' in datalist
        assert "Knife skills" not in datalist

    def test_an_unknown_collection_is_a_404(self, client):
        assert client.get("/collection/nothing-here").status_code == 404


def test_an_existing_library_gains_the_new_column_and_table(tmp_path):
    # The items table as the first release wrote it: today's, minus every
    # column that has since been added by migration. No collections table.
    first_release = "\n".join(
        line for line in db.SCHEMA.split("CREATE INDEX")[0].splitlines()
        if line.strip().split(" ")[0] not in db.MIGRATIONS
    )
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(first_release)
    assert "format" not in {r[1] for r in old.execute("PRAGMA table_info(items)")}
    old.execute("INSERT INTO items (canonical_url, shared_url, platform, saved_at, note)"
                " VALUES ('u', 'u', 'tiktok', '2021-01-01', 'kept for a reason')")
    old.commit()
    old.close()

    conn = db.connect(str(path))
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(items)")}
    assert "format" in cols
    assert conn.execute("SELECT note FROM items").fetchone()[0] == "kept for a reason"
    assert db.file_under(conn, 1, "Dumplings") == "Dumplings"
    conn.close()
