"""Moving the Mac's library into the cloud: everything arrives, nothing on the
Mac changes, and running it again is harmless."""

import hashlib
import io
import json
import os
import stat
import subprocess
import urllib.parse

import pytest
from PIL import Image

from favorites import cloud_move, db, thumbnails

needs_postgres = pytest.mark.skipif(
    not os.environ.get("FAVES_TEST_DATABASE_URL"),
    reason="moves into Postgres; set FAVES_TEST_DATABASE_URL to run")


def picture(width: int, height: int, fmt: str = "PNG") -> bytes:
    im = Image.new("RGB", (width, height), (40, 90, 160))
    for x in range(0, width, 7):  # enough detail that it doesn't compress to nothing
        im.putpixel((x, (x * 13) % height), (250, 250, 250))
    out = io.BytesIO()
    im.save(out, fmt)
    return out.getvalue()


def save(conn, n: int, **extra) -> int:
    return db.upsert_item(conn, {
        "canonical_url": f"https://www.tiktok.com/video/{n}", "external_id": str(n),
        "shared_url": f"https://www.tiktok.com/@citydesk/video/{n}", "platform": "tiktok",
        "creator_handle": "@citydesk", "title": f"Save number {n}", "resolve_status": "ok",
        "saved_at": "2025-05-01T12:00:00+00:00", **extra})[0]


@pytest.fixture
def mac(tmp_path, monkeypatch):
    """A library file as the Mac keeps it -- built in SQLite even where the
    tests' own library is in Postgres -- and the cloud library, open."""
    cloud_url = os.environ.get("DATABASE_URL")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    path = tmp_path / "favorites.db"
    conn = db.connect(str(path))
    zoning = save(conn, 1, title="The zoning meeting", note="ask about the parking minimums",
                  tags=["civic"], description="A café owner speaks")
    soup = save(conn, 2, title="Five minute soup", creator_handle="@cook")
    save(conn, 3, title="Not looked up yet", resolve_status="failed")
    db.file_under(conn, soup, "Recipes", "2025-05-02T00:00:00+00:00")
    db.set_rooms(conn, zoning, ["Music"])
    db.teach_tag(conn, "civic", "Politics & civics")
    thumbnails.store(conn, soup, (picture(1500, 2000), "image/png"), "https://example.com/soup.png")
    db.set_meta(conn, "snooze_tiktok", "2030-01-01T00:00:00+00:00")
    conn.execute("INSERT INTO imports (key, filename, platform, imported_at, added)"
                 " VALUES ('k1', 'favorites.json', 'tiktok', '2025-01-01', 3)")
    conn.execute("INSERT INTO inbox_seen (line_hash, seen_at) VALUES ('h1', '2025-01-01')")
    conn.commit()
    conn.close()
    if cloud_url:
        monkeypatch.setenv("DATABASE_URL", cloud_url)
    return path, {"zoning": zoning, "soup": soup}


def run(path, capsys) -> tuple[int, str]:
    code = cloud_move.main(["--from", str(path)])
    return code, capsys.readouterr().out


def cloud_id(conn, n: int) -> int:
    return conn.execute("SELECT id FROM items WHERE canonical_url = ?",
                        (f"https://www.tiktok.com/video/{n}",)).fetchone()[0]


def dump(conn) -> dict:
    return {t: sorted(tuple(map(repr, r)) for r in conn.execute(f"SELECT * FROM {t}").fetchall())
            for t in ("items", "collections", "theme_rules", "thumbnails", "imports",
                      "inbox_seen", "items_fts")}


@needs_postgres
class TestTheMove:
    def test_everything_on_the_mac_arrives(self, mac, capsys):
        path, mac_ids = mac
        cloud = db.connect()
        save(cloud, 99, title="Saved on the phone first")  # so the Mac's numbers are taken
        cloud.close()

        code, out = run(path, capsys)
        assert code == 0, out
        assert "Everything on this Mac is in the cloud." in out
        cloud = db.connect()
        assert db.count(cloud) == 4
        zoning, soup = cloud_id(cloud, 1), cloud_id(cloud, 2)
        assert zoning != mac_ids["zoning"]
        assert db.get_item(cloud, zoning)["note"] == "ask about the parking minimums"
        assert db.collections_for(cloud, soup) == ["Recipes"]
        # A room chosen for a save follows the save to its new number.
        assert ("item", str(zoning), "Music", "add") in [
            tuple(r) for r in cloud.execute("SELECT kind, key, theme, action FROM theme_rules")]
        assert "Music" in db.themes_of(cloud, zoning)
        assert [r["id"] for r in db.search(cloud, "cafe")] == [zoning]
        assert [r["id"] for r in db.search(cloud, "recipes")] == [soup]
        kept = thumbnails.get(cloud, soup)
        assert kept["content_type"] == "image/webp"
        assert max(Image.open(io.BytesIO(bytes(kept["data"]))).size) <= thumbnails.SHRINK_TO
        assert db.get_meta(cloud, "snooze_tiktok") == "2030-01-01T00:00:00+00:00"
        cloud.close()

    def test_the_cloud_works_its_rooms_out_as_the_mac_did(self, mac, capsys):
        path, _ = mac
        assert run(path, capsys)[0] == 0
        src = cloud_move.open_readonly(str(path))
        on_mac = {r["canonical_url"]: json.loads(r["themes"])
                  for r in src.execute("SELECT canonical_url, themes FROM items")}
        src.close()
        cloud = db.connect()
        in_cloud = {r["canonical_url"]: json.loads(r["themes"])
                    for r in cloud.execute("SELECT canonical_url, themes FROM items")}
        cloud.close()
        assert in_cloud == on_mac

    def test_running_it_again_changes_nothing(self, mac, capsys):
        path, _ = mac
        assert run(path, capsys)[0] == 0
        cloud = db.connect()
        first = dump(cloud)
        cloud.close()
        code, out = run(path, capsys)
        assert code == 0, out
        cloud = db.connect()
        assert dump(cloud) == first
        cloud.close()

    def test_what_the_cloud_already_has_wins_and_the_mac_fills_the_gaps(self, mac, capsys):
        path, _ = mac
        cloud = db.connect()
        # Saved again on the phone: a later date, its own note, its own category.
        later = save(cloud, 1, note="from the phone", saved_at="2025-09-09T00:00:00+00:00",
                     title="The zoning meeting")
        db.file_under(cloud, later, "Civic")
        # Shared on the phone but not looked up yet: the Mac's lookup fills it in.
        cloud.execute("UPDATE items SET title = NULL, resolve_status = 'failed',"
                      " resolve_error = 'blocked' WHERE id = ?", (save(cloud, 2),))
        cloud.commit()
        cloud.close()

        assert run(path, capsys)[0] == 0
        cloud = db.connect()
        assert db.count(cloud) == 3
        zoning = db.get_item(cloud, cloud_id(cloud, 1))
        assert zoning["note"] == "from the phone"
        assert zoning["saved_at"] == "2025-05-01T12:00:00+00:00"  # the first save's date
        assert db.collections_for(cloud, zoning["id"]) == ["Civic"]
        soup = db.get_item(cloud, cloud_id(cloud, 2))
        assert (soup["title"], soup["resolve_status"], soup["resolve_error"]) == (
            "Five minute soup", "ok", None)
        assert db.collections_for(cloud, soup["id"]) == ["Recipes"]
        cloud.close()

    def test_a_category_joins_the_clouds_spelling(self, mac, capsys):
        path, _ = mac
        cloud = db.connect()
        db.file_under(cloud, save(cloud, 50), "recipes")
        cloud.close()
        assert run(path, capsys)[0] == 0
        cloud = db.connect()
        assert db.collection_counts(cloud) == [("recipes", 2)]
        cloud.close()

    def test_the_file_on_the_mac_is_left_exactly_as_it_was(self, mac, capsys):
        path, _ = mac
        before = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
        code, out = run(path, capsys)
        assert code == 0
        assert (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns) == before
        assert "Nothing on this Mac was changed" in out

    def test_it_says_what_it_moved(self, mac, capsys):
        path, _ = mac
        _, out = run(path, capsys)
        assert f"from  {path}  (3 saves, 1 pictures)" in out
        assert "(0 saves there now)" in out
        assert "1 pictures copied" in out and "of the free plan's 500 MB" in out
        notes = next(line for line in out.splitlines() if line.strip().startswith("notes"))
        assert notes.split()[-2:] == ["1", "1"]

    def test_a_picture_stored_in_the_cloud_is_phone_sized(self):
        conn = db.connect()
        item = save(conn, 7)
        thumbnails.store(conn, item, (picture(2000, 3000), "image/png"), None)
        kept = thumbnails.get(conn, item)
        conn.close()
        assert kept["content_type"] == "image/webp"
        assert max(Image.open(io.BytesIO(bytes(kept["data"]))).size) == thumbnails.SHRINK_TO


def test_without_a_cloud_library_it_refuses_and_reads_nothing(mac, monkeypatch, capsys):
    path, _ = mac
    monkeypatch.delenv("DATABASE_URL", raising=False)
    code, out = run(path, capsys)
    assert code == 2
    assert "DATABASE_URL isn't set" in out and "Copying" not in out


def test_a_missing_library_file_is_named(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example.com:5432/postgres")
    code, out = run(tmp_path / "nowhere.db", capsys)
    assert code == 2 and "There's no library at" in out


@pytest.mark.parametrize("url, problem, host", [
    ("postgresql://postgres.abc:s3cret@aws-0-us-west-2.pooler.supabase.com:5432/postgres",
     None, "aws-0-us-west-2.pooler.supabase.com"),
    ("postgresql://postgres.abc:[YOUR-PASSWORD]@aws-0-us-west-2.pooler.supabase.com:5432/postgres",
     "still says [YOUR-PASSWORD]", ""),
    ("postgresql://postgres.abc:s3cret@aws-0-us-west-2.pooler.supabase.com:6543/postgres",
     "Transaction pooler", "aws-0-us-west-2.pooler.supabase.com"),
])
def test_the_address_is_checked_and_its_password_never_shown(url, problem, host):
    found, where = cloud_move.where_to(url)
    assert where == host and "s3cret" not in (found or "") + where
    assert (found is None) if problem is None else (problem in found)


class TestTheAddress:
    """The first time, the move asks for the cloud library's address rather
    than leaving you to edit a hidden settings file."""

    def test_the_password_goes_in_with_its_symbols_intact(self):
        assert cloud_move.fill_password(
            "postgresql://postgres.abc:[YOUR-PASSWORD]@h.pooler.supabase.com:5432/postgres",
            "p@ss w'rd/#1") == (
            "postgresql://postgres.abc:p%40ss%20w%27rd%2F%231@h.pooler.supabase.com:5432/postgres")

    def test_it_is_kept_where_start_command_reads_it(self, tmp_path):
        env = tmp_path / ".favorites.env"
        env.write_text('FAVORITES_TOKEN="abc"\n')
        address = "postgresql://postgres.abc:p%40ss@aws-0-us-west-2.pooler.supabase.com:5432/postgres"
        cloud_move.remember(address, env)
        assert stat.S_IMODE(env.stat().st_mode) == 0o600
        read = subprocess.run(["bash", "-c", f'set -a; . "{env}"; printf %s "$DATABASE_URL"'],
                              capture_output=True, text=True, check=True).stdout
        assert read == address

    @needs_postgres
    def test_it_is_saved_only_once_it_has_connected(self, tmp_path, capsys):
        env = tmp_path / ".favorites.env"
        real = urllib.parse.urlsplit(os.environ["FAVES_TEST_DATABASE_URL"])
        password = real.password or "anything"
        placeholder = real._replace(
            netloc=f"{real.username}:[YOUR-PASSWORD]@{real.hostname}:{real.port}").geturl()
        answers = iter(["my library", "postgresql://u:x@127.0.0.1:1/postgres", placeholder])
        got = cloud_move.setup(env, ask=lambda _: next(answers), ask_secret=lambda _: password)
        out = capsys.readouterr().out
        assert got == cloud_move.fill_password(placeholder, password)
        assert "isn't it" in out and "Couldn't connect" in out
        assert env.read_text().count("DATABASE_URL=") == 1
        assert got not in out  # the address with the password in it is never shown

    def test_nothing_is_saved_when_it_never_connects(self, tmp_path, capsys):
        env = tmp_path / ".favorites.env"
        got = cloud_move.setup(env, ask=lambda _: "postgresql://u:x@127.0.0.1:1/postgres",
                               ask_secret=lambda _: "", tries=2)
        assert got is None and not env.exists()


class TestShrink:
    def test_a_big_picture_becomes_a_phone_sized_webp(self):
        big = picture(3000, 4000)
        data, ctype = thumbnails.shrink(big, "image/png")
        assert ctype == "image/webp" and len(data) < len(big)
        assert Image.open(io.BytesIO(data)).size == (540, 720)

    def test_a_picture_already_phone_sized_and_light_is_left_alone(self):
        small = picture(600, 400, "JPEG")
        assert thumbnails.shrink(small, "image/jpeg") == (small, "image/jpeg")

    def test_a_heavy_picture_is_made_lighter_even_at_phone_size(self):
        heavy = Image.effect_noise((700, 700), 90).convert("RGB")
        out = io.BytesIO()
        heavy.save(out, "PNG")
        data, ctype = thumbnails.shrink(out.getvalue(), "image/png")
        assert ctype == "image/webp" and len(data) < len(out.getvalue())

    def test_something_that_isnt_a_picture_comes_back_unchanged(self):
        assert thumbnails.shrink(b"<html>not a picture</html>", "text/html") == (
            b"<html>not a picture</html>", "text/html")

    def test_the_mac_keeps_its_originals(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        conn = db.connect(str(tmp_path / "lib.db"))
        item = save(conn, 8)
        big = picture(2000, 3000)
        thumbnails.store(conn, item, (big, "image/png"), None)
        assert bytes(thumbnails.get(conn, item)["data"]) == big
        conn.close()
