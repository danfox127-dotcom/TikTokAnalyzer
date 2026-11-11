"""What TikTok knows: a summary of what the export says TikTok keeps, kept
without the things that must never be kept, and told in plain words."""

import json
import re
import time

import pytest
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import db, known, watch
from favorites.importers import tiktok_export

#: Things in the sample that Faves must never store or show.
SECRETS = ["203.0.113.7", "198.51.100.23", "secret@example.com", "+15551234567",
           "meet me at the usual place", "a private comment, just for them", "Jane Doe Street 4"]


def export():
    return {
        "Profile And Settings": {
            "Profile Info": {"ProfileMap": {
                "userName": "dfox", "emailAddress": "secret@example.com", "telephoneNumber": "+15551234567",
                "birthDate": "1990-01-02", "accountRegion": "US", "bioDescription": "", "profilePhoto": "x.jpg"}},
            "Settings": {"SettingsMap": {"Interests": "Cooking|Comedy"}},
            "Following": {"Following": [{"Date": "2021-03-04 10:00:00", "UserName": "a"}]},
        },
        "Ad Interests": {"AdInterestCategories": "Food & Beverage, Pets,  , Home Improvement"},
        "Your Activity": {
            "Video Browsing History": {"VideoList": [
                {"Date": "2026-05-12 08:00:00", "Link": "https://www.tiktokv.com/share/video/1/"},
                {"Date": "2026-10-30 22:00:00", "Link": "https://www.tiktokv.com/share/video/2/"}]},
            "Login History": {"LoginHistoryList": [
                {"Date": "2025-01-05 09:00:00", "IP": "203.0.113.7", "DeviceModel": "iPhone15,2",
                 "DeviceSystem": "iOS 18.1", "NetworkType": "Wi-Fi", "Carrier": "Verizon"},
                {"Date": "2026-10-01 09:00:00", "IP": "198.51.100.23", "DeviceModel": "iPhone15,2",
                 "DeviceSystem": "iOS 18.1", "NetworkType": "4G", "Carrier": "Verizon"},
                {"Date": "2026-10-02 09:00:00", "IP": "203.0.113.7", "DeviceModel": "MacBookPro18,3",
                 "DeviceSystem": "macOS", "NetworkType": "Wi-Fi", "Carrier": ""}]},
            "Off TikTok Activity": {"OffTikTokActivityDataList": [
                {"TimeStamp": "2026-03-01 12:00:00", "Source": "Shopify", "Event": "ViewContent"},
                {"TimeStamp": "2026-03-01 12:05:00", "Source": "Shopify", "Event": "AddToCart"},
                {"TimeStamp": "2026-03-01 12:09:00", "Source": "Shopify", "Event": "Purchase"},
                {"TimeStamp": "2026-04-01 12:00:00", "Source": "Uber Eats", "Event": "CompletePayment"},
                {"TimeStamp": "2026-04-02 12:00:00", "Source": "Duolingo", "Event": "LaunchApp"}]},
            "Searches": {"SearchList": [{"Date": "2026-10-01 10:00:00", "SearchTerm": "orzo"}]},
        },
        "Comment": {"Comments": {"CommentsList": [
            {"Date": "2024-02-02 10:00:00", "Comment": "a private comment, just for them"}]}},
        "Direct Message": {"Direct Messages": {"ChatHistory": {
            "Chat History with friend:": [
                {"Date": "2023-06-01 10:00:00", "From": "dfox", "Content": "meet me at the usual place"},
                {"Date": "2023-06-01 10:01:00", "From": "friend", "Content": "ok"}],
            "Chat History with other:": [{"Date": "2024-01-01 10:00:00", "Content": "hi"}]}}},
        "TikTok Shop": {"Order": {"OrderList": [{"Date": "2025-12-01 10:00:00", "ShippingAddress": "Jane Doe Street 4"}]}},
    }


@pytest.fixture
def conn():
    c = db.connect()
    yield c
    c.close()


@pytest.fixture
def client():
    with TestClient(web.app) as c:
        yield c


@pytest.fixture
def dossier(conn, tmp_path):
    p = tmp_path / "user_data_tiktok.json"
    p.write_text(json.dumps(export()))
    tiktok_export.import_export(conn, p)
    return conn


class TestTheSummary:
    def test_what_it_keeps(self):
        d = tiktok_export.read_dossier(export())
        assert d["profile"] == {"held": ["birth date", "email address", "phone number", "profile photo",
                                         "region", "username"], "username": "dfox", "region": "US"}
        assert d["ad_interests"] == ["Food & Beverage", "Pets", "Home Improvement"]
        assert d["declared_interests"] == ["Cooking", "Comedy"]
        lg = d["logins"]
        assert (lg["count"], lg["addresses"]) == (3, 2)
        assert lg["devices"] == [["iPhone15,2 · iOS 18.1", 2], ["MacBookPro18,3 · macOS", 1]]
        assert lg["networks"] == [["Wi-Fi", 2], ["4G", 1]] and lg["carriers"] == [["Verizon", 2]]
        assert lg["first"].startswith("2025-01-05") and lg["last"].startswith("2026-10-02")
        off = d["off_tiktok"]
        assert (off["count"], off["source_count"]) == (5, 3)
        assert off["sources"][0] == ["Shopify", 3]
        assert d["messages"] == {"conversations": 2, "messages": 3}
        kinds = {r["kind"]: (r["count"], (r["since"] or "")[:10]) for r in d["records"]}
        assert kinds["Videos you opened"] == (2, "2026-05-12")
        assert kinds["Messages"] == (3, "2023-06-01") and kinds["Comments"] == (1, "2024-02-02")
        assert kinds["Accounts you follow"] == (1, "2021-03-04") and kinds["Shop orders"][0] == 1
        assert d["latest"].startswith("2026-10-30")

    def test_never_the_secrets(self, dossier):
        stored = json.dumps([dict(r) for r in dossier.execute("SELECT * FROM dossiers")])
        for secret in SECRETS:
            assert secret not in stored, secret

    def test_an_export_with_less_in_it(self):
        d = tiktok_export.read_dossier({"Activity": {"Video Browsing History": {"VideoList": [
            {"Date": "2026-10-30 22:00:00", "Link": "https://www.tiktokv.com/share/video/2/"}]}},
            "Your Activity": {"Ad Interests": {"AdInterestCategories": ["Pets", "Pets", "Travel"]}}})
        assert d["ad_interests"] == ["Pets", "Travel"] and d["profile"] == {"held": []}
        assert d["logins"]["count"] == 0 and d["off_tiktok"]["count"] == 0
        assert [r["kind"] for r in d["records"]] == ["Videos you opened"]

    def test_nothing_to_summarise_keeps_nothing(self, conn):
        assert tiktok_export.store_dossier(conn, tiktok_export.read_dossier({})) is None
        assert known.latest(conn) is None

    def test_the_same_export_twice_is_one_summary(self, dossier, tmp_path):
        p = tmp_path / "user_data_tiktok.json"
        tiktok_export.import_export(dossier, p)
        assert dossier.execute("SELECT count(*) FROM dossiers").fetchone()[0] == 1

    def test_an_export_already_in_downloads_is_read_for_it(self, conn, tmp_path):
        folder = tmp_path / "Downloads"
        folder.mkdir()
        p = folder / "user_data_tiktok.json"
        p.write_text(json.dumps(export()))
        conn.execute("INSERT INTO imports (key, filename, platform, imported_at, added) VALUES (?, ?, 'tiktok', ?, 0)",
                     (watch.fingerprint(p) + ":v2", p.name, "2026-11-01T08:00:00+00:00"))
        conn.commit()
        assert len(watch.scan(conn, [folder], now=time.time() + 3600)) == 1
        assert known.latest(conn)["logins"]["count"] == 3
        assert watch.last_imports(conn)["tiktok"]["at"] == "2026-11-01T08:00:00+00:00"


class TestPlainWords:
    @pytest.mark.parametrize("event, words", [
        ("AddToCart", "added something to a basket"), ("CompletePayment", "bought something"),
        ("Purchase", "bought something"), ("ViewContent", "looked at something"),
        ("LaunchApp", "opened their app"), ("SomethingNew", "something new"), ("", "something unnamed")])
    def test_events(self, event, words):
        assert known.event_words(event) == words

    def test_the_same_meaning_is_counted_once(self, dossier):
        events = dict(known.page(dossier)["off_tiktok"]["events"])
        assert events["bought something"] == 2 and events["looked at something"] == 1

    def test_dates(self):
        assert known.when("2024-05-12T08:00:00+00:00") == "May 2024"
        assert known.day("2026-11-02T08:00:00+00:00") == "2 November 2026"
        assert known.when(None) == known.day("") == ""


class TestThePage:
    def test_before_any_export(self, client):
        page = client.get("/known").text
        assert "This needs a TikTok export" in page and 'href="/sync#exports"' in page
        assert "data-rewind" not in page

    def test_the_five_cards(self, client, dossier):
        page = client.get("/known").text
        assert page.count('class="rw-card') == 5
        assert '<p class="rw-hero">17</p>' in page and 'in 8 kinds of record' in page
        assert "3 labels" in page and ">Food &amp; Beverage</span>" in page
        assert "You didn&#39;t pick these" in page or "You didn't pick these" in page
        assert "3 companies" in page and "<b>Shopify</b>" in page and "You bought something" in page
        assert "from 2 different internet addresses" in page and "iPhone15,2 · iOS 18.1" in page
        assert "Username: dfox" in page and "Email address</span>" in page
        assert "3 messages in 2 conversations" in page
        assert "Personalised ads" in page and 'href="/rewind"' in page
        assert "data-tz" not in page                               # no clock here, so no time zone asked for

    def test_the_page_shows_no_secrets(self, client, dossier):
        page = client.get("/known").text
        for secret in SECRETS:
            assert secret not in page, secret

    def test_the_ways_in(self, client, dossier):
        assert 'href="/known"' in client.get("/browse").text
        assert '<a href="/known">' in client.get("/more").text

    def test_the_script_asks_for_a_time_zone_only_for_the_clock(self, client):
        js = client.get("/static/museum.js").text
        assert "hasAttribute('data-tz')" in js
