"""Importing a TikTok export, and resolving what it leaves behind."""

import json

import httpx
import pytest
import respx

from favorites import backfill, db
from favorites.importers import tiktok_export

OEMBED = {
    "title": "the zoning meeting went sideways #localgov",
    "author_name": "City Desk",
    "author_unique_id": "citydesk",
    "author_url": "https://www.tiktok.com/@citydesk",
    "thumbnail_url": "https://p16.tiktokcdn.com/thumb.jpg",
}


def export_file(tmp_path, favorites=(), likes=()):
    payload = {
        "Likes and Favorites": {
            "Favorite Videos": {"FavoriteVideoList": [
                {"Date": d, "Link": f"https://www.tiktokv.com/share/video/{v}/"}
                for d, v in favorites
            ]},
            # The like list really does use lowercase keys in the same file.
            "Like List": {"ItemFavoriteList": [
                {"date": d, "link": f"https://www.tiktokv.com/share/video/{v}/"}
                for d, v in likes
            ]},
        }
    }
    path = tmp_path / "user_data_tiktok.json"
    path.write_text(json.dumps(payload))
    return path


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(str(tmp_path / "lib.db"))
    yield connection
    connection.close()


class TestImport:
    def test_favourites_are_imported_unresolved(self, conn, tmp_path):
        path = export_file(tmp_path, favorites=[("2021-04-02 10:00:00", "7001")])
        result = tiktok_export.import_export(conn, path)
        assert result["favorites"]["imported"] == 1

        row = db.rows_to_dicts(db.recent(conn))[0]
        assert row["platform"] == "tiktok"
        assert row["external_id"] == "7001"
        assert row["resolve_status"] == "pending"
        assert row["source"] == "export"
        assert row["title"] is None

    def test_the_export_date_becomes_the_save_date(self, conn, tmp_path):
        # Years of real dates are the whole reason to bother importing.
        path = export_file(tmp_path, favorites=[("2020-11-24 08:30:00", "7001")])
        tiktok_export.import_export(conn, path)
        assert db.rows_to_dicts(db.recent(conn))[0]["saved_at"] == "2020-11-24T08:30:00+00:00"

    def test_likes_are_left_out_unless_asked_for(self, conn, tmp_path):
        path = export_file(tmp_path,
                           favorites=[("2021-04-02 10:00:00", "7001")],
                           likes=[("2026-01-02 10:00:00", "8001")])
        result = tiktok_export.import_export(conn, path)
        assert result["likes"] is None
        assert db.count(conn) == 1

    def test_likes_are_tagged_separately_when_included(self, conn, tmp_path):
        path = export_file(tmp_path,
                           favorites=[("2021-04-02 10:00:00", "7001")],
                           likes=[("2026-01-02 10:00:00", "8001")])
        tiktok_export.import_export(conn, path, include_likes=True)
        sources = {r["source"] for r in db.rows_to_dicts(db.recent(conn, limit=10))}
        assert sources == {"export", "export-like"}

    def test_an_export_link_and_a_share_link_are_the_same_item(self, conn, tmp_path):
        # The export strips the @handle; a share sheet includes it. If these did
        # not collapse to one row, every re-share would duplicate your history.
        db.upsert_item(conn, {
            "canonical_url": "https://www.tiktok.com/video/7001",
            "shared_url": "https://www.tiktok.com/@citydesk/video/7001",
            "platform": "tiktok", "external_id": "7001",
            "title": "already known", "note": "why I kept it",
            "resolve_status": "ok", "source": "share",
        })
        path = export_file(tmp_path, favorites=[("2021-04-02 10:00:00", "7001")])
        result = tiktok_export.import_export(conn, path)

        assert result["favorites"]["imported"] == 0
        assert result["favorites"]["skipped_existing"] == 1
        assert db.count(conn) == 1

    def test_an_existing_item_keeps_its_note_and_title(self, conn, tmp_path):
        db.upsert_item(conn, {
            "canonical_url": "https://www.tiktok.com/video/7001",
            "shared_url": "x", "platform": "tiktok", "external_id": "7001",
            "title": "already known", "note": "why I kept it",
            "resolve_status": "ok",
        })
        path = export_file(tmp_path, favorites=[("2021-04-02 10:00:00", "7001")])
        tiktok_export.import_export(conn, path)
        row = db.rows_to_dicts(db.recent(conn))[0]
        assert row["note"] == "why I kept it"
        assert row["title"] == "already known"
        assert row["resolve_status"] == "ok"

    def test_rows_without_a_usable_link_or_date_are_counted_not_crashed_on(self, conn, tmp_path):
        path = tmp_path / "e.json"
        path.write_text(json.dumps({"Likes and Favorites": {"Favorite Videos": {
            "FavoriteVideoList": [
                {"Date": "2021-04-02 10:00:00", "Link": "https://example.com/not-a-video"},
                {"Date": "nonsense", "Link": "https://www.tiktokv.com/share/video/7002/"},
                {"Date": "2021-04-02 10:00:00", "Link": "https://www.tiktokv.com/share/video/7003/"},
            ]}}}))
        result = tiktok_export.import_export(conn, path)
        assert result["favorites"] == {
            "imported": 1, "skipped_existing": 0, "skipped_unusable": 2}

    def test_importing_twice_is_a_no_op(self, conn, tmp_path):
        path = export_file(tmp_path, favorites=[("2021-04-02 10:00:00", "7001")])
        tiktok_export.import_export(conn, path)
        second = tiktok_export.import_export(conn, path)
        assert second["favorites"]["imported"] == 0
        assert db.count(conn) == 1

    def test_an_export_with_no_favourites_is_not_an_error(self, conn, tmp_path):
        path = tmp_path / "e.json"
        path.write_text(json.dumps({"Likes and Favorites": {}}))
        result = tiktok_export.import_export(conn, path)
        assert result["favorites"]["imported"] == 0


def seed_pending(conn, ids_and_dates):
    for vid, date in ids_and_dates:
        db.upsert_item(conn, {
            "canonical_url": f"https://www.tiktok.com/video/{vid}",
            "shared_url": f"https://www.tiktokv.com/share/video/{vid}/",
            "platform": "tiktok", "external_id": vid,
            "saved_at": date, "resolve_status": "pending", "source": "export",
        })


class TestQueue:
    def test_newest_first(self, conn):
        # Recent videos are likeliest to still exist and are what the digest
        # needs, so they must be spent first when the budget is limited.
        seed_pending(conn, [("7001", "2021-01-01T00:00:00+00:00"),
                            ("7002", "2026-01-01T00:00:00+00:00"),
                            ("7003", "2023-01-01T00:00:00+00:00")])
        assert [i["external_id"] for i in backfill.pending(conn)] == ["7002", "7003", "7001"]

    def test_resolved_items_are_not_requeued(self, conn):
        seed_pending(conn, [("7001", "2021-01-01T00:00:00+00:00")])
        conn.execute("UPDATE items SET resolve_status = 'ok'")
        assert backfill.pending(conn) == []

    def test_items_that_keep_failing_are_eventually_left_alone(self, conn):
        seed_pending(conn, [("7001", "2021-01-01T00:00:00+00:00")])
        conn.execute("UPDATE items SET resolve_attempts = ?", (backfill.MAX_ATTEMPTS,))
        assert backfill.pending(conn) == []
        assert backfill.stats(conn)["gave_up"] == 1

    def test_the_budget_is_respected(self, conn):
        seed_pending(conn, [(str(7000 + i), f"20{20 + i}-01-01T00:00:00+00:00")
                            for i in range(5)])
        assert len(backfill.pending(conn, limit=2)) == 2


@pytest.mark.asyncio
class TestResolve:
    @respx.mock
    async def test_a_resolved_item_gains_its_metadata(self, conn):
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=OEMBED))
        respx.route().mock(return_value=httpx.Response(404))
        seed_pending(conn, [("7001", "2021-04-02T10:00:00+00:00")])

        result = await backfill.run(conn, limit=10, quiet=True)
        assert result == {"attempted": 1, "resolved": 1, "failed": 0,
                          "seconds": result["seconds"]}

        row = db.rows_to_dicts(db.recent(conn))[0]
        assert row["creator_handle"] == "@citydesk"
        assert row["creator_name"] == "City Desk"
        assert row["resolve_status"] == "ok"
        assert "localgov" in row["tags"]

    @respx.mock
    async def test_resolution_never_overwrites_the_export_date(self, conn):
        # The date you saved it is what the museum arranges itself by, and the
        # resolver has no idea what it is.
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=OEMBED))
        respx.route().mock(return_value=httpx.Response(404))
        seed_pending(conn, [("7001", "2020-11-24T08:30:00+00:00")])

        await backfill.run(conn, limit=10, quiet=True)
        assert db.rows_to_dicts(db.recent(conn))[0]["saved_at"] == "2020-11-24T08:30:00+00:00"

    @respx.mock
    async def test_a_note_survives_resolution(self, conn):
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=OEMBED))
        respx.route().mock(return_value=httpx.Response(404))
        seed_pending(conn, [("7001", "2021-04-02T10:00:00+00:00")])
        item_id = db.rows_to_dicts(db.recent(conn))[0]["id"]
        db.set_note(conn, item_id, "for the housing piece")

        await backfill.run(conn, limit=10, quiet=True)
        assert db.get_item(conn, item_id)["note"] == "for the housing piece"

    @respx.mock
    async def test_a_deleted_video_is_kept_and_counted(self, conn):
        # Thousands of these are expected. The row stays -- the link and date are
        # still yours -- and the attempt is recorded so it is not retried forever.
        respx.route().mock(return_value=httpx.Response(404))
        seed_pending(conn, [("7001", "2021-04-02T10:00:00+00:00")])

        result = await backfill.run(conn, limit=10, quiet=True)
        assert (result["resolved"], result["failed"]) == (0, 1)

        row = db.rows_to_dicts(db.recent(conn))[0]
        assert row["resolve_attempts"] == 1
        assert row["resolve_status"] == "unresolved"
        assert db.count(conn) == 1

    @respx.mock
    async def test_a_network_failure_does_not_lose_the_row(self, conn):
        respx.route().mock(side_effect=httpx.ConnectError("down"))
        seed_pending(conn, [("7001", "2021-04-02T10:00:00+00:00")])
        await backfill.run(conn, limit=10, quiet=True)
        assert db.count(conn) == 1
        assert db.rows_to_dicts(db.recent(conn))[0]["resolve_attempts"] == 1

    @respx.mock
    async def test_a_run_picks_up_where_the_last_one_stopped(self, conn):
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=OEMBED))
        respx.route().mock(return_value=httpx.Response(404))
        seed_pending(conn, [(str(7000 + i), f"202{i}-01-01T00:00:00+00:00")
                            for i in range(4)])

        first = await backfill.run(conn, limit=2, quiet=True)
        second = await backfill.run(conn, limit=2, quiet=True)
        third = await backfill.run(conn, limit=2, quiet=True)

        assert (first["attempted"], second["attempted"], third["attempted"]) == (2, 2, 0)
        assert backfill.stats(conn)["resolved"] == 4

    async def test_an_empty_queue_is_not_an_error(self, conn):
        result = await backfill.run(conn, limit=10, quiet=True)
        assert result["attempted"] == 0


class TestStats:
    def test_hit_rate_is_reported(self, conn):
        seed_pending(conn, [(str(7000 + i), "2021-01-01T00:00:00+00:00") for i in range(4)])
        conn.execute("UPDATE items SET resolve_status = 'ok' WHERE external_id IN ('7000','7001')")
        s = backfill.stats(conn)
        assert (s["total"], s["resolved"], s["remaining"]) == (4, 2, 2)
        assert s["hit_rate"] == 0.5


class TestRepairingFalseResolutions:
    """Correcting rows an earlier, too-lenient check marked resolved.

    A library that reports itself fully resolved will never retry those items,
    so the failure stays invisible until someone notices the shelves are full
    of things called "TikTok".
    """

    def resolved(self, conn, vid, title, creator=None):
        db.upsert_item(conn, {
            "canonical_url": f"https://www.tiktok.com/video/{vid}",
            "shared_url": "x", "platform": "tiktok", "external_id": vid,
            "title": title, "creator_handle": creator,
            "saved_at": "2023-01-01T00:00:00+00:00",
            "resolve_status": "ok", "source": "export",
        })

    def test_a_placeholder_row_goes_back_in_the_queue(self, conn):
        self.resolved(conn, "7001", "TikTok")
        assert backfill.requeue_placeholders(conn) == {
            "cleared_titles": 1, "requeued": 1}

        row = db.rows_to_dicts(db.recent(conn))[0]
        assert row["title"] is None
        assert row["resolve_status"] == "pending"
        assert row["resolve_attempts"] == 0

    def test_a_placeholder_title_over_a_real_creator_is_cleared_not_requeued(self, conn):
        # oEmbed gave a creator but no caption, so the junk page supplied the
        # title. The creator is real; only the title has to go.
        self.resolved(conn, "7001", "TikTok", creator="@citydesk")
        assert backfill.requeue_placeholders(conn) == {
            "cleared_titles": 1, "requeued": 0}

        row = db.rows_to_dicts(db.recent(conn))[0]
        assert row["title"] is None
        assert row["creator_handle"] == "@citydesk"
        assert row["resolve_status"] == "ok"

    def test_genuine_rows_are_untouched(self, conn):
        self.resolved(conn, "7001", "the zoning meeting went sideways", "@citydesk")
        assert backfill.requeue_placeholders(conn) == {
            "cleared_titles": 0, "requeued": 0}
        assert db.rows_to_dicts(db.recent(conn))[0]["title"] == \
            "the zoning meeting went sideways"

    def test_the_repair_restores_an_honest_hit_rate(self, conn):
        # Mirrors the real shape: mostly genuine, a block of junk pages, and a
        # few that kept a creator. Before the repair the library claims 100%.
        for i in range(70):
            self.resolved(conn, f"7{i:03d}", f"a real caption {i}", f"@creator{i % 9}")
        for i in range(25):
            self.resolved(conn, f"8{i:03d}", "TikTok")
        for i in range(5):
            self.resolved(conn, f"9{i:03d}", "TikTok", creator="@citydesk")

        assert backfill.stats(conn)["hit_rate"] == 1.0

        assert backfill.requeue_placeholders(conn) == {
            "cleared_titles": 30, "requeued": 25}
        after = backfill.stats(conn)
        assert after["resolved"] == 75
        assert after["remaining"] == 25
        assert round(after["hit_rate"], 2) == 0.75

    def test_the_repair_is_idempotent(self, conn):
        self.resolved(conn, "7001", "TikTok")
        backfill.requeue_placeholders(conn)
        assert backfill.requeue_placeholders(conn) == {
            "cleared_titles": 0, "requeued": 0}
