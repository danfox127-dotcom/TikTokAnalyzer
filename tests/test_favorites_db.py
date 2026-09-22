"""Storage, de-duplication and search."""

import pytest

from favorites import db


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


def item(**over):
    base = {
        "canonical_url": "https://www.tiktok.com/@citydesk/video/1",
        "shared_url": "https://vm.tiktok.com/ZM1/",
        "platform": "tiktok",
        "external_id": "1",
        "title": "the zoning meeting went sideways",
        "creator_name": "City Desk",
        "creator_handle": "@citydesk",
        "tags": ["localgov", "housing"],
        "terms": ["zoning meeting", "council"],
    }
    base.update(over)
    return base


class TestUpsert:
    def test_insert_then_read_back(self, conn):
        item_id, created = db.upsert_item(conn, item())
        assert created is True
        row = db.get_item(conn, item_id)
        assert row["title"] == "the zoning meeting went sideways"
        assert db.loads_list(row["tags"]) == ["localgov", "housing"]

    def test_resaving_the_same_link_updates_rather_than_duplicates(self, conn):
        first, created_a = db.upsert_item(conn, item())
        second, created_b = db.upsert_item(conn, item(title="a better title"))
        assert (created_a, created_b) == (True, False)
        assert first == second
        assert db.count(conn) == 1
        assert db.get_item(conn, first)["title"] == "a better title"

    def test_a_note_survives_a_re_save(self, conn):
        # The note is the only field that cannot be recovered by re-resolving,
        # so a later blank must never clear it.
        item_id, _ = db.upsert_item(conn, item(note="use this in the newsletter"))
        db.upsert_item(conn, item(note=None))
        assert db.get_item(conn, item_id)["note"] == "use this in the newsletter"

    def test_original_save_date_is_kept_on_re_save(self, conn):
        item_id, _ = db.upsert_item(conn, item(saved_at="2026-01-05T09:00:00+00:00"))
        db.upsert_item(conn, item(saved_at="2026-09-18T09:00:00+00:00"))
        assert db.get_item(conn, item_id)["saved_at"] == "2026-01-05T09:00:00+00:00"

    def test_unknown_fields_are_ignored(self, conn):
        # Resolver payloads carry fields the table does not have; they must not
        # blow up the insert.
        item_id, _ = db.upsert_item(conn, item(nonsense="x", raw={"oembed": {"a": 1}}))
        assert db.get_item(conn, item_id) is not None


class TestSearch:
    @pytest.fixture
    def stocked(self, conn):
        db.upsert_item(conn, item())
        db.upsert_item(conn, item(
            canonical_url="https://www.youtube.com/watch?v=abc", platform="youtube",
            title="How transit funding works", creator_name="Transit Explained",
            creator_handle="@transit", tags=["transit"], terms=["funding formula"],
            transcript="the funding formula rewards ridership not coverage",
        ))
        db.upsert_item(conn, item(
            canonical_url="https://example.com/post", platform="web",
            title="An essay", creator_name="Someone", creator_handle=None,
            tags=[], terms=[], note="reminded me of the zoning thread",
        ))
        return conn

    def test_finds_by_title(self, stocked):
        assert len(db.search(stocked, "zoning")) == 2  # title and note

    def test_finds_by_creator(self, stocked):
        hits = db.search(stocked, "transit")
        assert [h["platform"] for h in hits] == ["youtube"]

    def test_finds_inside_a_transcript(self, stocked):
        hits = db.search(stocked, "ridership")
        assert len(hits) == 1

    def test_finds_by_your_own_note(self, stocked):
        # The note is indexed because it is the most deliberate text in the row.
        assert any(h["title"] == "An essay" for h in db.search(stocked, "reminded"))

    def test_partial_last_word_matches_while_typing(self, stocked):
        assert len(db.search(stocked, "zon")) >= 1

    def test_editing_a_note_reindexes_it(self, stocked):
        item_id = db.search(stocked, "zoning")[0]["id"]
        db.set_note(stocked, item_id, "referendum in November")
        assert any(h["id"] == item_id for h in db.search(stocked, "referendum"))

    @pytest.mark.parametrize("query", ['unbalanced "quote', "a OR", "NEAR(", "*", "-", "()"])
    def test_syntax_that_would_break_fts_returns_results_not_an_error(self, stocked, query):
        # Raw input is not a valid MATCH expression. A search box must never
        # 500 because someone typed a quote mark.
        assert isinstance(db.search(stocked, query), list)

    def test_empty_query_returns_nothing(self, stocked):
        assert db.search(stocked, "   ") == []


class TestFtsQuery:
    def test_tokens_are_quoted_and_anded(self):
        assert db.fts_query("zoning code") == '"zoning" AND "code"*'

    def test_punctuation_is_discarded(self):
        assert db.fts_query('what?! "the"') == '"what" AND "the"*'

    def test_nothing_to_search_for(self):
        assert db.fts_query("!!!") == ""
