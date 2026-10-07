"""Footprint's site list: reading Sherlock's and WhatsMyName's, and merging them."""

import json
import os
import time

import httpx
import pytest
import respx

from footprint import manifest
from footprint.manifest import PLACEHOLDER, from_sherlock, from_whatsmyname, merge, site_key

SHERLOCK = {
    "$schema": "data.schema.json",
    "Example": {
        "url": "https://www.example.com/u/{}",
        "urlMain": "https://www.example.com/",
        "errorType": "message",
        "errorMsg": ["Sorry, nobody goes by that name"],
        "regexCheck": "^[a-z0-9_]{3,20}$",
        "username_claimed": "blue",
    },
    "StatusSite": {
        "url": "https://status.test/{}",
        "urlMain": "https://status.test/",
        "errorType": "status_code",
        "username_claimed": "red",
    },
    "Redirector": {
        "url": "https://redirect.test/{}",
        "urlMain": "https://redirect.test/",
        "errorType": "response_url",
        "username_claimed": "green",
    },
    "Poster": {
        "url": "https://poster.test/{}",
        "urlProbe": "https://api.poster.test/check",
        "urlMain": "https://poster.test/",
        "errorType": "status_code",
        "request_method": "POST",
        "request_payload": {"name": "{}"},
        "username_claimed": "teal",
    },
    "Excluded": {
        "url": "https://excluded.test/{}",
        "urlMain": "https://excluded.test/",
        "errorType": "status_code",
        "username_claimed": "x",
    },
    "Adult": {
        "url": "https://adult.test/{}",
        "urlMain": "https://adult.test/",
        "errorType": "status_code",
        "username_claimed": "x",
        "isNSFW": True,
    },
}

WMN = {
    "license": [],
    "authors": ["a"],
    "categories": ["social"],
    "sites": [
        {
            "name": "Example Profiles",
            "uri_check": "https://api.example.com/users/{account}",
            "uri_pretty": "https://example.com/u/{account}",
            "e_code": 200, "e_string": '"profile":', "m_code": 404, "m_string": "not found",
            "known": ["blue", "pink"], "cat": "social",
            "protection": ["cloudflare"],
        },
        {
            "name": "OnlyWMN",
            "uri_check": "https://onlywmn.test/{account}",
            "e_code": 200, "e_string": "<h1 class=\"user\">", "m_code": 404, "m_string": "",
            "known": ["k"], "cat": "hobby",
        },
        {
            "name": "Post Site",
            "uri_check": "https://post.test/api",
            "uri_pretty": "https://post.test/{account}",
            "post_body": "{\"username\":\"{account}\"}",
            "headers": {"Content-Type": "application/json"},
            "e_code": 200, "e_string": "taken", "m_code": 200, "m_string": "available",
            "known": ["p"], "cat": "misc", "strip_bad_char": ".",
        },
        {
            "name": "Spicy",
            "uri_check": "https://spicy.test/{account}",
            "e_code": 200, "e_string": "x", "m_code": 404, "m_string": "",
            "known": ["s"], "cat": "xx NSFW xx",
        },
    ],
}


class TestSiteKey:
    def test_strips_www_and_keeps_the_domain(self):
        assert site_key("https://www.tiktok.com/@{account}") == "tiktok.com"

    def test_ignores_the_username_subdomain(self):
        assert site_key("https://{account}.substack.com/") == "substack.com"

    def test_old_names_become_the_current_one(self):
        assert site_key("https://twitter.com/{account}") == "x.com"
        assert site_key("https://www.threads.net/@{account}") == "threads.com"


class TestSherlock:
    def setup_method(self):
        self.pairs = {site.name: probe for site, probe in from_sherlock(SHERLOCK, ["Excluded"])}

    def test_placeholder_becomes_account(self):
        probe = self.pairs["Example"]
        assert PLACEHOLDER in probe.url and "{}" not in probe.url

    def test_message_sites_read_the_page_for_the_missing_text(self):
        probe = self.pairs["Example"]
        assert probe.method == "GET"
        assert probe.missing_text == ("Sorry, nobody goes by that name",)
        assert not probe.two_sided

    def test_status_only_sites_need_just_a_head_request(self):
        probe = self.pairs["StatusSite"]
        assert probe.method == "HEAD"
        assert probe.missing_if_not_2xx

    def test_response_url_sites_do_not_follow_redirects(self):
        assert self.pairs["Redirector"].follow_redirects is False

    def test_probe_url_method_and_payload_are_kept(self):
        probe = self.pairs["Poster"]
        assert probe.method == "POST"
        assert probe.url == "https://api.poster.test/check"
        assert probe.json_body == {"name": PLACEHOLDER}

    def test_published_exclusions_are_dropped(self):
        assert "Excluded" not in self.pairs

    def test_username_pattern_decides_what_could_exist(self):
        probe = self.pairs["Example"]
        assert probe.accepts("marisol_cooks")
        assert not probe.accepts("Marisol Cooks!")

    def test_known_account_kept_for_the_health_check(self):
        assert self.pairs["Example"].known == ("blue",)


class TestWhatsMyName:
    def setup_method(self):
        self.sites = {site.name: (site, probe) for site, probe in from_whatsmyname(WMN)}

    def test_both_signs_are_kept(self):
        _, probe = self.sites["Example Profiles"]
        assert probe.two_sided
        assert probe.found_codes == (200,) and probe.found_text == ('"profile":',)
        assert probe.missing_codes == (404,) and probe.missing_text == ("not found",)

    def test_profile_address_is_the_pretty_one(self):
        site, _ = self.sites["Example Profiles"]
        assert site.profile_url == "https://example.com/u/{account}"
        assert site.key == "example.com"

    def test_an_empty_missing_text_means_the_code_alone_decides(self):
        _, probe = self.sites["OnlyWMN"]
        assert probe.missing_text == ()

    def test_post_body_makes_a_post(self):
        _, probe = self.sites["Post Site"]
        assert probe.method == "POST" and probe.body == '{"username":"{account}"}'

    def test_stripped_characters_are_removed_before_asking(self):
        _, probe = self.sites["Post Site"]
        assert probe.username_for("mari.sol") == "marisol"

    def test_nsfw_category_is_flagged(self):
        site, _ = self.sites["Spicy"]
        assert site.nsfw


class TestMerge:
    def test_one_site_per_domain_with_both_recipes(self):
        sites = merge(from_sherlock(SHERLOCK), from_whatsmyname(WMN))
        site = sites["example.com"]
        assert {p.source for p in site.probes} == {"sherlock", "whatsmyname"}
        # The first list passed names the site.
        assert site.name == "Example"
        assert site.profile_url == "https://www.example.com/u/{account}"
        assert site.category == "social"
        assert site.protection == ("cloudflare",)

    def test_two_sided_recipes_are_preferred(self):
        sites = merge(from_sherlock(SHERLOCK), from_whatsmyname(WMN))
        assert sites["example.com"].preferred_probes()[0].source == "whatsmyname"


def _write_lists(home):
    (home / "sherlock.json").write_text(json.dumps(SHERLOCK))
    (home / "whatsmyname.json").write_text(json.dumps(WMN))
    (home / "sherlock-exclusions.txt").write_text("Excluded\n")


@pytest.mark.asyncio
class TestDownload:
    @respx.mock
    async def test_first_run_downloads_every_list(self):
        sh = respx.get(manifest.SHERLOCK_URL).mock(return_value=httpx.Response(200, json=SHERLOCK))
        wm = respx.get(manifest.WMN_URL).mock(return_value=httpx.Response(200, json=WMN))
        ex = respx.get(manifest.EXCLUSIONS_URL).mock(return_value=httpx.Response(200, text="Excluded\n"))
        async with httpx.AsyncClient() as client:
            sites = await manifest.load(client)
        assert sh.called and wm.called and ex.called
        assert "example.com" in sites and "excluded.test" not in sites
        assert (manifest.home() / "sherlock.json").exists()

    @respx.mock
    async def test_a_fresh_copy_is_not_downloaded_again(self):
        _write_lists(manifest.home())
        route = respx.get(manifest.SHERLOCK_URL).mock(return_value=httpx.Response(200, json=SHERLOCK))
        async with httpx.AsyncClient() as client:
            await manifest.load(client)
        assert not route.called

    @respx.mock
    async def test_a_week_old_copy_is_refreshed(self):
        home = manifest.home()
        _write_lists(home)
        old = time.time() - 8 * 24 * 3600
        for name in ("sherlock.json", "whatsmyname.json", "sherlock-exclusions.txt"):
            os.utime(home / name, (old, old))
        route = respx.get(manifest.SHERLOCK_URL).mock(return_value=httpx.Response(200, json=SHERLOCK))
        respx.get(manifest.WMN_URL).mock(return_value=httpx.Response(200, json=WMN))
        respx.get(manifest.EXCLUSIONS_URL).mock(return_value=httpx.Response(200, text=""))
        async with httpx.AsyncClient() as client:
            await manifest.load(client)
        assert route.called

    @respx.mock
    async def test_a_failed_refresh_keeps_the_old_copy(self):
        home = manifest.home()
        _write_lists(home)
        old = time.time() - 8 * 24 * 3600
        for name in ("sherlock.json", "whatsmyname.json", "sherlock-exclusions.txt"):
            os.utime(home / name, (old, old))
        respx.get(manifest.SHERLOCK_URL).mock(return_value=httpx.Response(200, text="{not json"))
        respx.get(manifest.WMN_URL).mock(side_effect=httpx.ConnectError("offline"))
        respx.get(manifest.EXCLUSIONS_URL).mock(side_effect=httpx.ConnectError("offline"))
        async with httpx.AsyncClient() as client:
            sites = await manifest.load(client)
        assert "example.com" in sites
        assert json.loads((home / "sherlock.json").read_text()) == SHERLOCK

    @respx.mock
    async def test_no_list_at_all_says_so_plainly(self):
        respx.get(url__regex=r".*").mock(side_effect=httpx.ConnectError("offline"))
        async with httpx.AsyncClient() as client:
            with pytest.raises(RuntimeError, match="No site list yet"):
                await manifest.load(client)
