"""Looking up an email address or a phone number: what is it linked to?"""

import hashlib

import httpx
import pytest
import respx

from footprint import lookup, phone
from footprint.lookup import kind, local_handle, webmail
from footprint.manifest import Probe, Site

EMAIL = "Marisol@Marisol.Kitchen"
HASH = hashlib.sha256(EMAIL.lower().encode()).hexdigest()


def _site(key, url, name):
    probe = Probe(source="whatsmyname", id=f"whatsmyname:{key}", url=url)
    return Site(key=key, name=name, profile_url=url, probes=[probe])


SITES = {s.key: s for s in [
    _site("x.com", "https://x.com/{account}", "X (Twitter)"),
    _site("instagram.com", "https://www.instagram.com/{account}/", "Instagram"),
    _site("github.com", "https://github.com/{account}", "GitHub"),
]}

GRAVATAR = {
    "profile_url": "https://gravatar.com/marisolcooks", "display_name": "Marisol Reyes",
    "location": "Brooklyn, NY", "description": "Weeknight recipes.", "job_title": "Cook",
    "company": "Marisol Kitchen", "avatar_url": "https://0.gravatar.com/avatar/abc",
    "verified_accounts": [
        {"service_label": "X", "url": "https://x.com/marisolcooks", "is_hidden": False},
        {"service_label": "Instagram", "url": "https://instagram.com/marisol.cooks", "is_hidden": False},
        {"service_label": "Secret", "url": "https://example.org/hidden", "is_hidden": True},
    ],
}


def _commit(login, repo, date="2026-03-01T10:00:00Z", name="Marisol Reyes"):
    return {"author": {"login": login, "avatar_url": "https://a.test/x.png"} if login else None,
            "commit": {"author": {"name": name, "date": date}},
            "repository": {"full_name": repo}}


class TestKind:
    @pytest.mark.parametrize("text,expected", [
        ("marisol@marisol.kitchen", "email"),
        ("  First.Last+news@sub.example.co.uk ", "email"),
        ("+1 (212) 555-0100", "phone"),
        ("212.555.0100", "phone"),
        ("@marisol.cooks", "username"),
        ("marisol_cooks", "username"),
        ("not an @ address", None),
        ("", None),
    ])
    def test_kind(self, text, expected):
        assert kind(text) == expected

    def test_webmail(self):
        assert webmail("gmail.com") == "Gmail"
        assert webmail("yahoo.co.uk") == "Yahoo Mail"
        assert webmail("marisol.kitchen") is None

    def test_local_handle(self):
        assert local_handle("marisol.cooks+news@x.com") == "marisol.cooks"
        assert local_handle("12@x.com") is None
        assert local_handle("hello@marisol.kitchen") is None  # a shared inbox, not a username


@pytest.mark.asyncio
class TestGravatar:
    @respx.mock
    async def test_found_with_verified_accounts_only(self):
        route = respx.get(lookup.GRAVATAR_API + HASH).mock(return_value=httpx.Response(200, json=GRAVATAR))
        async with httpx.AsyncClient() as client:
            g = await lookup.gravatar(EMAIL, client)
        assert route.called  # asked by the hash of the lower-cased address
        assert g["found"] and g["display_name"] == "Marisol Reyes"
        assert [a["url"] for a in g["accounts"]] == [
            "https://x.com/marisolcooks", "https://instagram.com/marisol.cooks"]

    @respx.mock
    async def test_no_profile(self):
        respx.get(lookup.GRAVATAR_API + HASH).mock(return_value=httpx.Response(404))
        async with httpx.AsyncClient() as client:
            assert (await lookup.gravatar(EMAIL, client)) == {"found": False}

    @respx.mock
    async def test_trouble_is_reported_not_hidden(self):
        respx.get(lookup.GRAVATAR_API + HASH).mock(side_effect=httpx.ConnectError("down"))
        async with httpx.AsyncClient() as client:
            g = await lookup.gravatar(EMAIL, client)
        assert g["found"] is None and "Couldn't reach Gravatar" in g["error"]



def test_gravatar_as_a_profile_links_to_the_verified_accounts():
    g = {"found": True, "profile_url": "https://gravatar.com/m", "display_name": "M",
         "accounts": [{"label": "X", "url": "https://x.com/m"}], "links": []}
    p = lookup.gravatar_profile(g)
    assert p.site == "gravatar.com" and p.links == ["https://x.com/m"]


@pytest.mark.asyncio
class TestGitHub:
    @respx.mock
    async def test_commits_tied_to_an_account(self):
        respx.get(lookup.GITHUB_COMMITS).mock(return_value=httpx.Response(200, json={
            "total_count": 3, "items": [
                _commit("marisol", "marisol/recipes"), _commit("marisol", "marisol/site"),
                _commit(None, "someone/else", date="2038-01-19T03:14:07Z")]}))
        async with httpx.AsyncClient() as client:
            gh = await lookup.github(EMAIL, client)
        (acct,) = gh["accounts"]
        assert acct["login"] == "marisol" and acct["commits"] == 2
        assert gh["unlinked"] == 1
        assert gh["last_seen"] == "2026-03-01T10:00:00+00:00"  # the impossible 2038 date is ignored

    @respx.mock
    async def test_an_owner_of_most_commits_is_only_likely(self):
        respx.get(lookup.GITHUB_COMMITS).mock(return_value=httpx.Response(200, json={
            "total_count": 4, "items": [_commit(None, "marisol/a"), _commit(None, "marisol/b"),
                                        _commit(None, "marisol/c"), _commit(None, "friend/x")]}))
        async with httpx.AsyncClient() as client:
            gh = await lookup.github(EMAIL, client)
        assert gh["accounts"] == []
        assert gh["likely_owner"]["login"] == "marisol"

    @respx.mock
    async def test_the_search_limit_says_so(self):
        respx.get(lookup.GITHUB_COMMITS).mock(return_value=httpx.Response(403))
        async with httpx.AsyncClient() as client:
            assert "limit" in (await lookup.github(EMAIL, client))["error"]


@pytest.mark.asyncio
class TestWebFinger:
    @respx.mock
    async def test_the_domain_says_whose_profile(self):
        respx.get("https://marisol.kitchen/.well-known/webfinger").mock(return_value=httpx.Response(
            200, json={"links": [{"rel": "http://webfinger.net/rel/profile-page",
                                  "href": "https://mastodon.social/@marisol"}]}))
        async with httpx.AsyncClient() as client:
            f = await lookup.webfinger(EMAIL, client)
        assert f == {"found": True, "profile_url": "https://mastodon.social/@marisol", "subject": None}

    @respx.mock
    async def test_big_webmail_domains_are_never_asked(self):
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        async with httpx.AsyncClient() as client:
            assert await lookup.webfinger("someone@gmail.com", client) is None
        assert not route.called


class TestPhone:
    def test_a_us_landline(self):
        f = phone.facts("(212) 555-0100")
        assert f["valid"] and f["assumed_region"] == "US"
        assert f["international"] == "+1 212-555-0100"
        assert f["area"] == "New York, NY" and f["country"] == "United States"
        assert f["time_zones"] == ["America/New_York"]

    def test_a_mobile_with_its_first_carrier(self):
        f = phone.facts("+33 6 12 34 56 78")
        assert f["type"] == "Mobile" and f["carrier"] == "SFR" and f["assumed_region"] is None

    def test_toll_free_has_no_meaningful_time_zone(self):
        f = phone.facts("+1 800 555 0199")
        assert f["type"] == "Toll-free" and f["time_zones"] == []

    def test_invalid_numbers_say_how_to_fix_them(self):
        f = phone.facts("020 7946 0958")
        assert not f["valid"]
        assert "start it with +" in f["summary"]

    def test_region_setting(self, monkeypatch):
        monkeypatch.setenv("FOOTPRINT_PHONE_REGION", "gb")
        f = phone.facts("020 7946 0958")
        assert f["valid"] and f["country"] == "United Kingdom"

    def test_find_in_text(self):
        assert phone.find_in("Call (212) 555-0100 or +44 20 7946 0958. Since 2009.") == [
            "(212) 555-0100", "+44 20 7946 0958"]


def _internet(request: httpx.Request) -> httpx.Response:
    """The whole outside world for one lookup."""
    host, path = request.url.host, request.url.path
    if host == "api.gravatar.com":
        return httpx.Response(200, json=GRAVATAR)
    if host == "api.github.com" and path == "/search/commits":
        return httpx.Response(200, json={"total_count": 1, "items": [_commit("marisol", "marisol/recipes")]})
    if host == "dns.google":
        return httpx.Response(200, json={"Status": 0, "Answer": []})
    if host in ("x.com", "www.instagram.com", "instagram.com", "github.com"):
        page = ('<html><head><meta property="og:title" content="Marisol Reyes">'
                '<meta property="og:description" content="Weeknight recipes. Brooklyn."></head></html>')
        return httpx.Response(200, text=page, headers={"content-type": "text/html"})
    return httpx.Response(404)


@pytest.mark.asyncio
class TestRun:
    @respx.mock
    async def test_an_email_streams_its_links_details_and_scores(self):
        respx.route().mock(side_effect=_internet)
        async with httpx.AsyncClient() as client:
            events = [e async for e in lookup.run(EMAIL, SITES, client)]
        kinds = [k for k, _ in events]
        assert kinds[0] == "kind" and kinds[-1] == "done"
        assert {"mail", "gravatar", "github", "linked", "details", "match", "handles"} <= set(kinds)
        linked = {a["url"]: a for a in dict(events)["linked"]["accounts"]}
        assert linked["https://x.com/marisolcooks"]["site"] == "x.com"
        assert linked["https://x.com/marisolcooks"]["strength"] == "verified"
        assert linked["https://github.com/marisol"]["sources"] == [
            "GitHub ties 1 public commit with this address to this account"]
        handles = [h["handle"] for h in dict(events)["handles"]["handles"]]
        assert "marisolcooks" in handles and "marisol" in handles

    @respx.mock
    async def test_a_phone_number_never_leaves_the_computer(self):
        route = respx.route().mock(return_value=httpx.Response(200))
        async with httpx.AsyncClient() as client:
            events = [e async for e in lookup.run("+1 212 555 0100", SITES, client)]
        assert [k for k, _ in events] == ["kind", "phone", "done"]
        assert not route.called

    @respx.mock
    async def test_a_webmail_address_gets_no_faking_verdict(self):
        respx.route().mock(return_value=httpx.Response(404))
        async with httpx.AsyncClient() as client:
            events = dict([e async for e in lookup.run("someone@gmail.com", SITES, client)])
        assert events["mail"]["verdict"] == "webmail" and events["mail"]["provider"] == "Gmail"
