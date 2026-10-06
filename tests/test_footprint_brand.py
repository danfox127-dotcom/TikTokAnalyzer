"""The brand consistency report: the website as the source of truth."""

import json
from datetime import datetime, timezone

import httpx
import pytest
import respx

from footprint import brand
from footprint.brand import Website, build, parse_website, profile_from_link
from footprint.manifest import Probe, Site
from footprint.profile import Profile


def _site(key, url, **probe_kw):
    probe = Probe(**{"source": "whatsmyname", "id": f"whatsmyname:{key}", "url": url,
                     "found_codes": (200,), "found_text": ('class="profile"',),
                     "missing_codes": (404,), "missing_text": ("No such user",), **probe_kw})
    return Site(key=key, name=key.split(".")[0].capitalize(), profile_url=url, probes=[probe])


SITES = {s.key: s for s in [
    _site("instagram.com", "https://www.instagram.com/{account}/"),
    _site("tiktok.com", "https://www.tiktok.com/@{account}"),
    _site("x.com", "https://x.com/{account}"),
    _site("substack.com", "https://{account}.substack.com/"),
    _site("pinterest.com", "https://www.pinterest.com/{account}/"),
    _site("youtube.com", "https://www.youtube.com/@{account}"),
]}

HOME_PAGE = """<html><head>
<title>Harbor Coffee</title>
<meta property="og:site_name" content="Harbor Coffee">
<meta name="description" content="Small-batch coffee roasters on the harbor since 2009.">
<link rel="me" href="https://www.tiktok.com/@harborcoffee">
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "Organization", "name": "Harbor Coffee",
   "sameAs": ["https://instagram.com/harborcoffee/", "https://twitter.com/harbor_coffee"]}]}
</script>
</head><body>
<a href="https://www.instagram.com/harborcoffee">Instagram</a>
<a href="https://harborcoffee.substack.com/">Newsletter</a>
<a href="https://www.facebook.com/sharer/sharer.php?u=x">Share</a>
<a href="/about">About</a>
</body></html>"""


class TestLinks:
    @pytest.mark.parametrize("link,expected", [
        ("https://instagram.com/harborcoffee/", ("instagram.com", "harborcoffee")),
        ("https://www.tiktok.com/@harborcoffee?lang=en", ("tiktok.com", "harborcoffee")),
        ("https://twitter.com/harbor_coffee", ("x.com", "harbor_coffee")),  # old name, current site
        ("https://harborcoffee.substack.com/", ("substack.com", "harborcoffee")),
        ("https://www.youtube.com/@HarborCoffee", ("youtube.com", "HarborCoffee")),
        ("https://www.instagram.com/p/C123/", None),  # a post, not a profile
        ("https://unknown.test/harbor", None),
        ("/about", None),
    ])
    def test_profile_from_link(self, link, expected):
        assert profile_from_link(link, SITES) == expected


class TestWebsite:
    def test_reads_sameas_rel_me_and_plain_links(self):
        site = parse_website(HOME_PAGE, "https://harbor.coffee/", SITES)
        assert site.domain == "harbor.coffee"
        assert site.name == "Harbor Coffee"
        found = {(p["site"], p["username"]): p["how"] for p in site.profiles}
        assert found == {
            ("instagram.com", "harborcoffee"): "sameAs",
            ("x.com", "harbor_coffee"): "sameAs",
            ("tiktok.com", "harborcoffee"): "rel=me",
            ("substack.com", "harborcoffee"): "link",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_an_unreachable_website_is_reported_not_fatal(self):
        respx.get("https://harbor.coffee").mock(side_effect=httpx.ConnectError("down"))
        async with httpx.AsyncClient() as client:
            site = await brand.read_website("harbor.coffee", SITES, client)
        assert site.error and "Couldn't open" in site.error


def _result(site, username, status, big=True, confidence="confirmed"):
    s = SITES[site]
    return dict(site=site, name=s.name, username=username, url=s.profile_for(username),
                status=status, confidence=confidence, reason="r", big=big)


def _profile(site, username, **kw):
    return Profile(site=site, name=SITES[site].name, username=username,
                   url=SITES[site].profile_for(username), **kw)


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


class TestBuild:
    def setup_method(self):
        self.website = parse_website(HOME_PAGE, "https://harbor.coffee/", SITES)

    def _report(self, results, profiles):
        return build("Harbor Coffee", ["harborcoffee"], self.website, results,
                     {(p.site, p.username): p for p in profiles}, now=NOW)

    def test_row_statuses(self):
        results = [
            _result("instagram.com", "harborcoffee", "found"),     # on the website
            _result("youtube.com", "harborcoffee", "found"),       # links back
            _result("pinterest.com", "harborcoffee", "found"),     # a stranger
            _result("tiktok.com", "harborcoffee", "not_found"),    # website links to it, gone
            _result("x.com", "harborcoffee", "not_found"),
            _result("x.com", "harbor_coffee", "unclear", confidence=""),  # listed, platform won't say
            _result("substack.com", "harborcoffee", "found"),
        ]
        profiles = [
            _profile("instagram.com", "harborcoffee", display_name="Harbor Coffee"),
            _profile("youtube.com", "harborcoffee", display_name="Harbor Coffee",
                     links=["https://harbor.coffee/shop"]),
            _profile("pinterest.com", "harborcoffee", display_name="Jen's boards", bio="quilts"),
            _profile("substack.com", "harborcoffee", display_name="Harbor Coffee"),
        ]
        report = self._report(results, profiles)
        status = {(r["site"], r["username"]): r["status"] for r in report["rows"]}
        assert status[("instagram.com", "harborcoffee")] == "confirmed"
        assert status[("youtube.com", "harborcoffee")] == "confirmed"
        assert status[("pinterest.com", "harborcoffee")] == "taken"
        assert status[("tiktok.com", "harborcoffee")] == "dead_link"
        assert status[("x.com", "harbor_coffee")] == "confirmed"
        assert ("x.com", "harborcoffee") not in status  # the listed handle is the row for X
        evidence = next(r for r in report["rows"] if r["site"] == "youtube.com")["evidence"]
        assert evidence == ["Links back to harbor.coffee"]

    def test_a_lookalike_with_matching_evidence_is_probably_ours(self):
        website = Website(url="https://harbor.coffee/", domain="harbor.coffee", name="Harbor Coffee",
                          profiles=[dict(site="instagram.com", username="harborcoffee",
                                         url="https://instagram.com/harborcoffee", how="sameAs")])
        ig = _profile("instagram.com", "harborcoffee", display_name="Harbor Coffee",
                      photo_hash="0123456789abcdef", links=["https://www.tiktok.com/@harborcoffee"])
        tt = _profile("tiktok.com", "harborcoffee", display_name="Harbor Coffee",
                      photo_hash="0123456789abcdee")
        report = build("Harbor Coffee", ["harborcoffee"], website,
                       [_result("instagram.com", "harborcoffee", "found"),
                        _result("tiktok.com", "harborcoffee", "found")],
                       {("instagram.com", "harborcoffee"): ig, ("tiktok.com", "harborcoffee"): tt}, now=NOW)
        row = next(r for r in report["rows"] if r["site"] == "tiktok.com")
        assert row["status"] == "probably"
        assert any("links to their" in e for e in row["evidence"])
        assert any(f["title"] == "Probably yours, but not on your website" for f in report["findings"])
        assert "https://www.tiktok.com/@harborcoffee" in report["same_as"]

    def test_free_and_not_allowed(self):
        website = Website(url="https://harbor.coffee/", domain="harbor.coffee")
        report = build("H", ["harborcoffee"], website,
                       [_result("pinterest.com", "harborcoffee", "not_found"),
                        _result("tiktok.com", "harborcoffee", "cant_exist")], {}, now=NOW)
        assert [r["status"] for r in report["rows"]] == ["not_allowed", "free"]
        assert any(f["title"] == "Free to claim" for f in report["findings"])

    def test_consistency_findings(self):
        results = [_result("instagram.com", "harborcoffee", "found"),
                   _result("substack.com", "harborcoffee", "found")]
        profiles = [
            _profile("instagram.com", "harborcoffee", display_name="Harbor Coffee",
                     location="Portland, ME", photo_hash="ffff0000ffff0000",
                     last_active="2026-01-01T00:00:00+00:00"),
            _profile("substack.com", "harborcoffee", display_name="Harbor Coffee Roasters",
                     location="Boston", photo_hash="00ff00ff00ff00ff",
                     links=["https://harbor.coffee"]),
        ]
        titles = {f["title"]: f for f in self._report(results, profiles)["findings"]}
        assert "Your profiles use different names" in titles
        assert "2 different profile photos" in titles
        assert "Profiles give different locations" in titles
        assert "Instagram looks dormant" in titles
        assert titles["Not linking back to harbor.coffee"]["detail"] == "Instagram"

    def test_jsonld_is_valid_and_lists_ours(self):
        report = self._report([_result("instagram.com", "harborcoffee", "found")],
                              [_profile("instagram.com", "harborcoffee")])
        body = report["jsonld"].split(">", 1)[1].rsplit("</", 1)[0]
        data = json.loads(body)
        assert data["@type"] == "Organization"
        assert data["url"] == "https://harbor.coffee/"
        assert data["sameAs"] == ["https://www.instagram.com/harborcoffee/"]


def _honest(request):
    if "harborcoffee" in str(request.url):
        return httpx.Response(200, text='<div class="profile">')
    return httpx.Response(404, text="No such user")


@pytest.mark.asyncio
class TestRun:
    @respx.mock
    async def test_streams_the_search_then_the_report(self):
        respx.get("https://harbor.coffee").mock(return_value=httpx.Response(200, text=HOME_PAGE))
        respx.get(url__regex=r"https://(www\.)?(instagram|tiktok|pinterest|youtube)\.com/.*").mock(
            side_effect=_honest)
        respx.get(url__regex=r"https://x\.com/.*").mock(side_effect=_honest)
        respx.get(url__regex=r"https://.*\.substack\.com/.*").mock(side_effect=_honest)
        sites = {k: SITES[k] for k in ("instagram.com", "tiktok.com", "x.com")}
        async with httpx.AsyncClient() as client:
            events = [e async for e in brand.run("Harbor Coffee", ["@harborcoffee"], "harbor.coffee",
                                                 sites, client)]
        kinds = [k for k, _ in events]
        assert kinds[0] == "website" and kinds[-1] == "report"
        assert "result" in kinds and "details" in kinds
        report = events[-1][1]
        assert report["id"]
        status = {(r["site"], r["username"]): r["status"] for r in report["rows"]}
        # X was checked under the handle the website lists, too.
        assert ("x.com", "harbor_coffee") in status
        assert status[("instagram.com", "harborcoffee")] == "confirmed"
