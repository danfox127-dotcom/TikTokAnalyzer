"""The Footprint web app: pages render, results stream, reports download."""

import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from footprint import store
from footprint.app import create_app
from footprint.manifest import Probe, Site


def _site(key, url, name):
    probe = Probe(source="whatsmyname", id=f"whatsmyname:{key}", url=url, found_codes=(200,),
                  found_text=('class="profile"',), missing_codes=(404,), missing_text=("No such user",),
                  known=("harborcoffee",))
    return Site(key=key, name=name, profile_url=url, probes=[probe])


SITES = {s.key: s for s in [
    _site("instagram.com", "https://www.instagram.com/{account}/", "Instagram"),
    _site("tiktok.com", "https://www.tiktok.com/@{account}", "TikTok"),
    _site("small.test", "https://small.test/{account}", "Small"),
]}

HOME = """<html><head><meta property="og:site_name" content="Harbor Coffee">
<script type="application/ld+json">{"@type":"Organization","sameAs":["https://instagram.com/harborcoffee"]}</script>
</head><body></body></html>"""


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if request.url.host == "harbor.coffee":
        return httpx.Response(200, text=HOME, headers={"content-type": "text/html"})
    if "harborcoffee" in url and request.url.host != "small.test":
        page = ('<html><head><meta property="og:title" content="Harbor Coffee (@harborcoffee)">'
                '<meta property="og:description" content="Roasters. harbor.coffee/shop"></head>'
                '<body><div class="profile"></div></body></html>')
        return httpx.Response(200, text=page, headers={"content-type": "text/html"})
    return httpx.Response(404, text="No such user")


@pytest.fixture
def client():
    conn = store.connect(":memory:")
    http = httpx.AsyncClient(transport=httpx.MockTransport(_handler))
    app = create_app(sites=SITES, client=http, conn=conn, auto_health=False)
    with TestClient(app) as tc:
        yield tc
    conn.close()


def _events(response) -> list[tuple[str, dict]]:
    out, event = [], None
    for line in response.iter_lines():
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: "):
            out.append((event, json.loads(line[6:])))
    return out


class TestPages:
    def test_search_page(self, client):
        r = client.get("/?u=harborcoffee")
        assert r.status_code == 200
        assert "Where does" in r.text and 'value="harborcoffee"' in r.text

    def test_brand_page(self, client):
        assert "one brand" in client.get("/brand").text

    def test_health_page_lists_every_site(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert "Instagram" in r.text and "untested" in r.text


class TestSearchStream:
    def test_streams_results_details_match_and_done(self, client):
        with client.stream("GET", "/search/stream?u=@harborcoffee&scope=all") as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            events = _events(r)
        kinds = [k for k, _ in events]
        assert kinds[0] == "start" and kinds[-1] == "done"
        start = events[0][1]
        assert start["total"] == 3
        assert [b["site"] for b in start["big"]] == ["tiktok.com", "instagram.com"]
        results = [d for k, d in events if k == "result"]
        assert {r["site"]: r["status"] for r in results} == {
            "instagram.com": "found", "tiktok.com": "found", "small.test": "not_found"}
        details = [d for k, d in events if k == "details"]
        assert {d["display_name"] for d in details} == {"Harbor Coffee"}
        assert "match" in kinds and "timezone" in kinds

    def test_big_only_by_default(self, client):
        with client.stream("GET", "/search/stream?u=nobody") as r:
            events = _events(r)
        assert {d["site"] for k, d in events if k == "result"} == {"instagram.com", "tiktok.com"}

    def test_impossible_usernames_are_refused(self, client):
        assert client.get("/search/stream?u=two words").status_code == 400

    def test_speed_is_remembered(self, client):
        with client.stream("GET", "/search/stream?u=x&scope=all") as r:
            _events(r)
        n = client.app.state.conn.execute("SELECT COUNT(*) FROM timings").fetchone()[0]
        assert n == 3


class TestBrand:
    def _report(self, client):
        url = "/brand/stream?name=Harbor%20Coffee&site=harbor.coffee&handles=@harborcoffee&scope=all"
        with client.stream("GET", url) as r:
            events = _events(r)
        assert events[0][0] == "website" and events[-1][0] == "report"
        return events[-1][1]

    def test_report_streams_and_saves(self, client):
        report = self._report(client)
        status = {r["site"]: r["status"] for r in report["rows"]}
        assert status["instagram.com"] == "confirmed"       # in the website's sameAs
        assert status["tiktok.com"] == "confirmed"          # links back to harbor.coffee
        assert status["small.test"] == "free"
        assert client.get(f"/brand/report/{report['id']}.json").json()["id"] == report["id"]

    def test_html_report_downloads_with_the_chosen_sameas(self, client):
        report = self._report(client)
        keep = "https://www.tiktok.com/@harborcoffee"
        r = client.get(f"/brand/report/{report['id']}",
                       params={"download": 1, "same_as": [keep, "https://evil.test/"]})
        assert r.status_code == 200
        assert 'filename="harbor-coffee-report.html"' in r.headers["content-disposition"]
        assert keep in r.text and "evil.test" not in r.text
        assert "<script src" not in r.text  # self-contained

    def test_unknown_report(self, client):
        assert client.get("/brand/report/nope").status_code == 404


class TestHealthRun:
    def test_re_check_now_runs_in_the_background(self, client):
        r = client.post("/health/run", follow_redirects=False)
        assert r.status_code == 303
        for _ in range(50):
            if not client.get("/health/progress").json()["running"]:
                break
            time.sleep(0.05)
        status = client.get("/health/progress").json()
        assert status["last_run"]
        page = client.get("/health?state=working").text
        assert "Instagram" in page
