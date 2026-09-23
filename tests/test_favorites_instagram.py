"""Importing Instagram saves from a Meta data export.

The fixtures mirror the layout of a real 2026 export (values invented): a list
of posts, each with a timestamp and label_values holding URL, Caption, Title
and groups titled Owner, Hashtags and Brand partner.
"""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from favorites import db, platforms
from favorites.app import app
from favorites.importers import instagram_export as ig
from favorites.resolve import browsable_url

T_2024 = 1717243200  # 2024-06-01T12:00:00Z
T_2019 = 1559390400  # 2019-06-01T12:00:00Z


def post(code="C1abcDEF", kind="p", ts=T_2024, caption="Folding dumplings #dumplings #cooking",
         name="Kitchen Desk", username="kitchendesk", hashtags=("dumplings", "cooking"),
         captions=1):
    url = f"https://www.instagram.com/{kind}/{code}/"
    values = [{"label": "URL", "value": url, "href": url}]
    values += [{"label": "Caption", "value": caption}] * (captions if caption else 0)
    values += [{"label": "Title", "value": ""}]
    values.append({"title": "Owner", "dict": [{"title": "", "dict": [
        {"label": "URL", "value": "https://linktr.ee/somebody"},
        {"label": "Name", "value": name},
        {"label": "Username", "value": username},
    ]}]})
    values.append({"title": "Hashtags", "dict": [
        {"title": "", "dict": [{"label": "Name", "value": h}]} for h in hashtags]})
    values.append({"title": "Brand partner", "dict": []})
    return {"timestamp": ts, "media": [], "label_values": values, "fbid": code}


def write(tmp_path, posts, name="saved_posts.json"):
    path = tmp_path / name
    path.write_text(json.dumps(posts), encoding="utf-8")
    return path


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "lib.db"))
    yield c
    c.close()


class TestReading:
    def test_the_current_layout(self, tmp_path):
        [p] = ig.read_saved(write(tmp_path, [post()]))
        assert p == {
            "url": "https://www.instagram.com/p/C1abcDEF/",
            "saved_at": "2024-06-01T12:00:00+00:00",
            "caption": "Folding dumplings #dumplings #cooking",
            "owner_name": "Kitchen Desk", "owner_username": "kitchendesk",
            "hashtags": ["dumplings", "cooking"],
        }

    def test_a_duplicated_caption_is_read_once(self, tmp_path):
        [p] = ig.read_saved(write(tmp_path, [post(captions=2)]))
        assert p["caption"] == "Folding dumplings #dumplings #cooking"

    def test_a_post_with_no_caption_still_has_its_author(self, tmp_path):
        [p] = ig.read_saved(write(tmp_path, [post(caption=None)]))
        assert p["caption"] is None and p["owner_username"] == "kitchendesk"

    def test_the_older_layout(self, tmp_path):
        older = {"saved_saved_media": [{"title": "kitchendesk", "string_map_data": {
            "Saved on": {"href": "https://www.instagram.com/p/OLD123/", "timestamp": T_2019}}}]}
        [p] = ig.read_saved(write(tmp_path, older))
        assert p["url"] == "https://www.instagram.com/p/OLD123/"
        assert p["saved_at"] == "2019-06-01T12:00:00+00:00"
        assert p["owner_username"] == "kitchendesk" and p["caption"] is None

    def test_millisecond_timestamps_are_understood(self, tmp_path):
        [p] = ig.read_saved(write(tmp_path, [post(ts=T_2024 * 1000)]))
        assert p["saved_at"] == "2024-06-01T12:00:00+00:00"

    def test_found_inside_an_unzipped_export_folder(self, tmp_path):
        folder = tmp_path / "instagram-export" / "your_instagram_activity" / "saved"
        folder.mkdir(parents=True)
        write(folder, [post()])
        assert len(ig.read_saved(tmp_path / "instagram-export")) == 1

    def test_found_inside_the_zip(self, tmp_path):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("your_instagram_activity/saved/saved_posts.json", json.dumps([post()]))
        (tmp_path / "export.zip").write_bytes(buf.getvalue())
        assert len(ig.read_saved(tmp_path / "export.zip")) == 1

    def test_something_else_entirely_is_refused_plainly(self, tmp_path):
        with pytest.raises(ValueError):
            ig.read_saved(write(tmp_path, {"unrelated": True}))


class TestImporting:
    def test_a_post_arrives_described_and_ready_to_shelve(self, conn):
        ig.import_saved(conn, [ig._current(post())])
        row = db.rows_to_dicts(db.recent(conn))[0]
        assert row["platform"] == "instagram"
        assert row["canonical_url"] == "https://www.instagram.com/p/C1abcDEF"
        assert row["external_id"] == "C1abcDEF"
        assert row["title"] == row["description"] == "Folding dumplings #dumplings #cooking"
        assert row["creator_name"] == "Kitchen Desk"
        assert row["creator_handle"] == "@kitchendesk"
        assert row["creator_url"] == "https://www.instagram.com/kitchendesk/"  # not the linktree
        assert {"dumplings", "cooking"} <= set(row["tags"])
        assert row["saved_at"] == "2024-06-01T12:00:00+00:00"
        assert row["resolve_status"] == "ok"   # no lookup can beat the export
        assert row["source"] == "instagram-export"
        assert browsable_url(row) == "https://www.instagram.com/p/C1abcDEF"

    def test_a_reel_is_short_form_and_a_post_is_not_assumed_either_way(self, conn):
        ig.import_saved(conn, [ig._current(post(code="R1", kind="reel")),
                               ig._current(post(code="P1", kind="p"))])
        formats = {r["external_id"]: r["format"] for r in db.rows_to_dicts(db.recent(conn))}
        assert formats == {"R1": "short", "P1": None}

    def test_hashtags_only_in_the_export_still_become_tags(self, conn):
        ig.import_saved(conn, [ig._current(post(caption="no tags in here", hashtags=("brooklyn",)))])
        assert "brooklyn" in db.rows_to_dicts(db.recent(conn))[0]["tags"]

    def test_the_caption_and_the_author_are_searchable(self, conn):
        ig.import_saved(conn, [ig._current(post())])
        assert len(db.search(conn, "dumplings")) == 1
        assert len(db.search(conn, "kitchendesk")) == 1

    def test_an_existing_item_is_left_alone(self, conn):
        item_id, _ = db.upsert_item(conn, {
            "canonical_url": "https://www.instagram.com/p/C1abcDEF", "shared_url": "x",
            "platform": "instagram", "title": "from the share sheet", "note": "keep this",
            "resolve_status": "ok", "saved_at": "2025-01-01T00:00:00+00:00"})
        stats = ig.import_saved(conn, [ig._current(post())])
        assert stats["already_present"] == 1 and stats["imported"] == 0
        row = db.get_item(conn, item_id)
        assert (row["title"], row["note"]) == ("from the share sheet", "keep this")

    def test_importing_twice_changes_nothing(self, conn):
        posts = [ig._current(post())]
        ig.import_saved(conn, posts)
        assert ig.import_saved(conn, posts) == {
            "imported": 0, "already_present": 1, "undated": 0, "not_instagram": 0}
        assert db.count(conn) == 1

    def test_undated_and_foreign_links_are_counted_not_imported(self, conn):
        undated = ig._current(post(ts=None))
        foreign = dict(ig._current(post()), url="https://example.com/p/X/")
        stats = ig.import_saved(conn, [undated, foreign])
        assert (stats["undated"], stats["not_instagram"], db.count(conn)) == (1, 1, 0)

    def test_a_post_with_neither_caption_nor_author_waits_for_a_lookup(self, conn):
        bare = ig._current(post(caption=None, username="", name=""))
        ig.import_saved(conn, [bare])
        assert db.rows_to_dicts(db.recent(conn))[0]["resolve_status"] == "pending"


class TestCommand:
    def test_list_reads_and_imports_nothing(self, tmp_path, capsys):
        path = write(tmp_path, [post(), post(code="R1", kind="reel", ts=T_2019)])
        lib = tmp_path / "lib.db"
        assert ig.main([str(path), "--list", "--db", str(lib)]) == 0
        out = capsys.readouterr().out
        assert "saved posts in export: 2" in out
        assert "saved between      : 2019-06-01 and 2024-06-01" in out
        assert "reels / posts      : 1 / 1" in out
        assert not lib.exists()

    def test_import_names_the_library_and_counts(self, tmp_path, capsys):
        path = write(tmp_path, [post()])
        lib = tmp_path / "lib.db"
        assert ig.main([str(path), "--db", str(lib)]) == 0
        out = capsys.readouterr().out
        assert f"library: {lib}" in out and "posts imported       : 1" in out

    def test_a_missing_file_says_so_plainly(self, tmp_path, capsys):
        assert ig.main([str(tmp_path / "nope.json")]) == 1
        assert "Point this at saved_posts.json" in capsys.readouterr().out


def test_imported_posts_show_in_the_museum_straight_away(tmp_path, monkeypatch):
    monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "favorites.db"))
    c = db.connect()
    ig.import_saved(c, [ig._current(post())])
    c.close()
    with TestClient(app) as client:
        assert "Folding dumplings" in client.get("/all").text


def test_the_registry_knows_a_reel_is_short_form():
    from urllib.parse import urlparse
    fmt = platforms.get("instagram").format_from_url
    assert fmt(urlparse("https://www.instagram.com/reel/ABC/")) == "short"
    assert fmt(urlparse("https://www.instagram.com/reels/ABC/")) == "short"
    assert fmt(urlparse("https://www.instagram.com/p/ABC/")) is None
