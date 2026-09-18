"""The front door: the digest sentences and the rotating shelves."""

from datetime import datetime, timedelta, timezone

import pytest

from favorites import db, museum

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


def save(conn, n, *, days_ago=1, platform="tiktok", creator="City Desk",
         handle="@citydesk", tags=(), terms=(), note=None, title=None):
    when = (NOW - timedelta(days=days_ago)).replace(microsecond=0).isoformat()
    db.upsert_item(conn, {
        "canonical_url": f"https://example.com/{platform}/{n}",
        "shared_url": f"https://example.com/{platform}/{n}",
        "platform": platform,
        "title": title or f"item {n}",
        "creator_name": creator,
        "creator_handle": handle,
        "tags": list(tags),
        "terms": list(terms),
        "note": note,
        "saved_at": when,
    })


class TestDigestProse:
    def test_an_empty_library_says_so_plainly(self, conn):
        assert museum.digest(conn, now=NOW)["prose"] == "Nothing saved this past month."

    def test_a_drop_to_zero_is_reported_against_the_previous_month(self, conn):
        for i in range(3):
            save(conn, i, days_ago=45)
        assert museum.digest(conn, now=NOW)["prose"] == (
            "Nothing saved this past month, after 3 the month before."
        )

    def test_growth_is_stated_as_a_comparison(self, conn):
        # A bare count says nothing; "up from" is the sentence that tells you
        # something has shifted.
        for i in range(8):
            save(conn, i, days_ago=5)
        for i in range(3):
            save(conn, 100 + i, days_ago=45)
        assert museum.digest(conn, now=NOW)["prose"].startswith("8 saves this past month, up from 3.")

    def test_a_single_save_is_not_pluralised(self, conn):
        save(conn, 1)
        assert museum.digest(conn, now=NOW)["prose"].startswith("1 save this past month.")

    def test_a_single_platform_is_reported_as_such(self, conn):
        for i in range(3):
            save(conn, i)
        assert "All of it from TikTok." in museum.digest(conn, now=NOW)["prose"]

    def test_a_majority_platform_is_reported_as_mostly(self, conn):
        for i in range(4):
            save(conn, i, platform="tiktok")
        for i in range(2):
            save(conn, 10 + i, platform="youtube", handle="@transit", creator="Transit")
        assert "Mostly TikTok (4), with YouTube." in museum.digest(conn, now=NOW)["prose"]

    def test_a_flat_mix_is_not_described_as_mostly_anything(self, conn):
        # Three platforms at two saves each is not "mostly" the first one.
        for i, platform in enumerate(["tiktok", "youtube", "instagram"] * 2):
            save(conn, i, platform=platform, handle=f"@{platform}", creator=platform)
        prose = museum.digest(conn, now=NOW)["prose"]
        assert "Mostly" not in prose
        assert "Spread across TikTok (2), YouTube (2) and Instagram (2)." in prose

    def test_a_recurring_theme_is_named(self, conn):
        for i in range(4):
            save(conn, i, tags=["housing"])
        assert "housing" in museum.digest(conn, now=NOW)["prose"]

    def test_creators_new_to_the_library_are_called_out(self, conn):
        save(conn, 1, days_ago=200, creator="Old Hand", handle="@old")
        save(conn, 2, days_ago=2, creator="Old Hand", handle="@old")
        save(conn, 3, days_ago=2, creator="Fresh Face", handle="@fresh")
        prose = museum.digest(conn, now=NOW)["prose"]
        assert "One creator is new to the library: Fresh Face." in prose
        assert "Old Hand" not in prose.split("new to the library")[-1]

    def test_missing_notes_are_nudged_only_when_most_are_missing(self, conn):
        for i in range(6):
            save(conn, i, note=None)
        assert "have no note yet" in museum.digest(conn, now=NOW)["prose"]

        other = db.connect(":memory:")
        for i in range(6):
            save(other, i, note="a reason")
        assert "no note yet" not in museum.digest(other, now=NOW)["prose"]
        other.close()

    def test_components_are_returned_alongside_the_prose(self, conn):
        # An optional model should be able to rewrite the summary without
        # having to re-derive any of the numbers.
        for i in range(3):
            save(conn, i, tags=["housing"])
        d = museum.digest(conn, now=NOW)
        assert d["count"] == 3
        assert d["platforms"] == [("TikTok", 3)]
        assert ("housing", 3) in d["themes"]


class TestShelves:
    def test_a_nearly_empty_library_shows_only_recent(self, conn):
        for i in range(3):
            save(conn, i)
        shelves = museum.shelves(conn, now=NOW)
        assert [s["kind"] for s in shelves] == ["recent"]

    def test_recent_is_always_the_front_of_the_room(self, conn):
        for i in range(30):
            save(conn, i, days_ago=i + 1, tags=["housing"])
        assert museum.shelves(conn, now=NOW)[0]["kind"] == "recent"

    def test_the_arrangement_is_stable_within_a_day(self, conn):
        for i in range(30):
            save(conn, i, days_ago=i * 10 + 1, tags=["housing"])
        first = [s["title"] for s in museum.shelves(conn, now=NOW)]
        second = [s["title"] for s in museum.shelves(conn, now=NOW)]
        assert first == second

    def test_the_arrangement_changes_the_next_day(self, conn):
        for i in range(40):
            save(conn, i, days_ago=i * 8 + 1, tags=[f"theme{i % 4}"],
                 handle=f"@c{i % 5}", creator=f"Creator {i % 5}")
        by_day = {
            tuple(s["title"] for s in museum.shelves(conn, now=NOW + timedelta(days=d)))
            for d in range(6)
        }
        assert len(by_day) > 1, "the front page should not look the same every day"

    def test_no_two_shelves_of_the_same_kind(self, conn):
        for i in range(40):
            save(conn, i, days_ago=i * 8 + 1, tags=[f"theme{i % 4}"],
                 handle=f"@c{i % 5}", creator=f"Creator {i % 5}")
        kinds = [s["kind"] for s in museum.shelves(conn, now=NOW)]
        assert len(kinds) == len(set(kinds))

    def test_the_current_month_is_not_repeated_as_a_month_shelf(self, conn):
        # It is already the "recently saved" shelf.
        for i in range(12):
            save(conn, i, days_ago=1)
        titles = [s["title"] for s in museum.shelves(conn, now=NOW)]
        assert "September 2026" not in titles

    def test_shelf_count_is_capped(self, conn):
        for i in range(60):
            save(conn, i, days_ago=i * 6 + 1, tags=[f"t{i % 6}"],
                 handle=f"@c{i % 8}", creator=f"Creator {i % 8}")
        assert len(museum.shelves(conn, now=NOW, max_shelves=4)) <= 4


class TestMonthTitle:
    def test_reads_as_a_month(self):
        assert museum._month_title("2026-09") == "September 2026"

    def test_a_malformed_key_is_returned_unchanged(self):
        assert museum._month_title("nonsense") == "nonsense"


class TestSharedTerms:
    def test_a_term_unique_to_one_item_is_not_offered(self, conn):
        # A pill that leads back to the item you are already on is a dead end.
        save(conn, 1, terms=["went sideways", "housing policy"])
        save(conn, 2, terms=["housing policy"])
        item = db.rows_to_dicts(db.recent(conn, limit=10))[-1]
        assert museum.shared_terms(conn, item) == ["housing policy"]

    def test_ordered_by_how_widely_shared(self, conn):
        save(conn, 1, terms=["common thread", "rare thread"])
        for i in range(2, 6):
            save(conn, i, terms=["common thread"])
        save(conn, 9, terms=["rare thread"])
        item = [i for i in db.rows_to_dicts(db.recent(conn, limit=20))
                if "rare thread" in i["terms"] and "common thread" in i["terms"]][0]
        assert museum.shared_terms(conn, item) == ["common thread", "rare thread"]

    def test_a_lone_item_offers_nothing(self, conn):
        save(conn, 1, terms=["zoning code"])
        item = db.rows_to_dicts(db.recent(conn, limit=1))[0]
        assert museum.shared_terms(conn, item) == []
