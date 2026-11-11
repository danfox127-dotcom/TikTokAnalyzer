"""Your TikTok stats: Rewind's month as a page to scroll -- every month at a
glance, then this one in full."""

import re
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from favorites import app as web
from favorites import rewind
from test_favorites_rewind import DECEMBER, NY, activity, conn, october, save  # noqa: F401  (fixtures)


@pytest.fixture
def client():
    with TestClient(web.app) as c:
        yield c


class TestTheNumbers:
    def test_every_month_at_a_glance(self, october):
        assert rewind.trend(october, NY) == [
            {"key": "2026-09", "name": "September", "year": 2026, "opened": 11, "liked": 0, "saved": 7, "searched": 0},
            {"key": "2026-10", "name": "October", "year": 2026, "opened": 23, "liked": 6, "saved": 4, "searched": 4}]

    def test_every_month_is_your_month(self, october):
        utc = {t["key"]: t["opened"] for t in rewind.trend(october)}
        assert utc == {"2026-09": 10, "2026-10": 24}
        assert rewind.trend(october, NY)[0]["opened"] == 11

    def test_day_by_day(self, october):
        m = rewind.month(october, "2026-10", NY, now=DECEMBER)
        assert len(m["days"]) == 31 and sum(m["days"]) == m["opened"]
        assert m["days"][9] == 5 and m["day_peak"] == 5      # Saturday the 10th, 11am and 11pm in New York
        assert m["weekday_one"] == 3                         # 1 October 2026 is a Thursday

    def test_longer_lists_for_the_page(self, conn):
        for n, who in enumerate(["@a", "@a", "@b", "@c", "@d", "@e", "@f", "@g"]):
            save(conn, f"5{n}", who, [["Comedy", "Style", "Music", "Travel", "Pets", "Sports", "Food & cooking", "Comedy"][n]],
                 f"2026-10-1{n}T12:00:00+00:00")
        activity(conn, "watch", "2026-10-02T12:00:00+00:00", "1")
        story = rewind.month(conn, "2026-10", NY, now=DECEMBER)
        page = rewind.month(conn, "2026-10", NY, now=DECEMBER, creators=10, topics=None, searches=20)
        assert len(story["creators"]) == 5 and len(page["creators"]) == 7
        assert [t["name"] for t in story["themes"]][-1] == "Everything else"
        assert len([t for t in page["themes"] if not t.get("rest")]) == 7
        assert not any(t.get("rest") for t in page["themes"])  # every video has a topic

    def test_no_months_no_trend(self, conn):
        assert rewind.trend(conn, NY) == []


class TestThePage:
    def test_with_no_export_it_says_how_to_get_one(self, client):
        page = client.get("/stats").text
        assert "Needs a TikTok export" in page and 'href="/sync#exports"' in page

    def test_it_opens_the_latest_month(self, client, october):
        r = client.get("/stats?tz=America/New_York", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/stats/2026-10?tz=America%2FNew_York"

    def test_the_month_in_full(self, client, october):
        page = client.get("/stats/2026-10?tz=America/New_York").text
        assert "<h1 class=\"rr-h-l\">October 2026</h1>" in page
        assert 'href="/rewind/2026-10">' in page and "Play as a story" in page
        # Every month, this one lit, each a way to its month.
        cols = re.findall(r'<a class="st-col( is-on)?" href="(/stats/[\d-]+)"', page)
        assert cols == [("", "/stats/2026-09"), (" is-on", "/stats/2026-10")]
        assert 'data-h-opened="100.0"' in page and 'data-n-liked="6"' in page
        assert "October 2026: 23 opened · 6 likes · 4 saves · 4 searches" in page
        # Five numbers, each against September.
        assert '<p class="val">23</p><p class="delta">↑ 109% on September</p>' in page
        assert "no likes to compare" not in page and "no September to compare" in page   # no likes in September
        # Day by day, the clock, who, what, searches; and the table.
        assert page.count('title="') >= 31 and "Busiest: Saturday 10 October, with 5." in page
        assert 'class="rw-clock"' in page and "@caseebrim" in page and "up from 3rd" in page
        assert "Biggest jump: News &amp; politics" in page and ">orzo</a>" in page
        assert "<td>23</td><td>6</td><td>4</td><td>4</td>" in page

    def test_the_measures_switch_with_a_script(self, client):
        js = client.get("/static/museum.js").text
        assert "statsTrend" in js and "data-h-" in js

    @pytest.mark.parametrize("path", ["/stats/2026-13", "/stats/2026-07"])
    def test_no_such_month(self, client, october, path):
        assert client.get(path).status_code == 404

    def test_the_ways_in(self, client, october):
        story = client.get("/rewind/2026-10?tz=America/New_York").text
        assert 'href="/stats/2026-10">' in story and "See it all on one page" in story
        assert story.count('class="rw-card') == 5
        assert 'href="/stats"' in client.get("/browse").text
