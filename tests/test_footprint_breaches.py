"""Has a website itself had a known data breach? (Have I Been Pwned, free)"""

import httpx
import pytest
import respx

from footprint import breaches
from footprint.breaches import describe, for_domain

ADOBE = {"Name": "Adobe", "Title": "Adobe", "Domain": "adobe.com", "BreachDate": "2013-10-04",
         "AddedDate": "2013-12-04T00:00:00Z", "PwnCount": 152445165,
         "DataClasses": ["Email addresses", "Password hints", "Passwords", "Usernames"],
         "IsVerified": True, "IsFabricated": False, "IsSensitive": False, "IsSpamList": False}
LATER = {**ADOBE, "Name": "AdobeAgain", "Title": "Adobe (again)", "BreachDate": "2020-01-02",
         "PwnCount": 1000, "IsVerified": False}


def _hibp(by_domain: dict, seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        found = by_domain.get(request.url.params["domain"], [])
        if found == "down":
            return httpx.Response(503)
        return httpx.Response(200, json=found)
    return handler


async def _check(domain, by_domain):
    seen = []
    with respx.mock:
        respx.get(breaches.API).mock(side_effect=_hibp(by_domain, seen))
        async with httpx.AsyncClient() as client:
            return await for_domain(domain, client), seen


@pytest.mark.asyncio
class TestForDomain:
    async def test_breaches_newest_first(self):
        result, seen = await _check("adobe.com", {"adobe.com": [ADOBE, LATER]})
        assert result["checked"] and result["domain"] == "adobe.com"
        assert [b["name"] for b in result["breaches"]] == ["AdobeAgain", "Adobe"]
        assert result["breaches"][1]["count"] == 152445165
        # Only the domain is sent, with the User-Agent HIBP requires.
        assert seen[0].url.params["domain"] == "adobe.com"
        assert "Footprint" in seen[0].headers["user-agent"]

    async def test_none_is_checked_and_empty(self):
        result, _ = await _check("harbor.coffee", {})
        assert result["checked"] and result["breaches"] == []

    async def test_a_subdomain_is_also_checked_under_its_parent(self):
        result, seen = await _check("shop.adobe.com", {"adobe.com": [ADOBE]})
        assert result["domain"] == "adobe.com" and len(result["breaches"]) == 1
        assert [r.url.params["domain"] for r in seen] == ["shop.adobe.com", "adobe.com"]

    async def test_trouble_is_never_read_as_no_breaches(self):
        result, _ = await _check("adobe.com", {"adobe.com": "down"})
        assert result["checked"] is False
        assert "Couldn't reach" in result["error"]

    async def test_a_connection_error(self):
        with respx.mock:
            respx.get(breaches.API).mock(side_effect=httpx.ConnectError("offline"))
            async with httpx.AsyncClient() as client:
                result = await for_domain("adobe.com", client)
        assert result["checked"] is False


def test_describe():
    b = breaches._plain(ADOBE)
    assert describe(b) == ("Adobe, Oct 2013: 152,445,165 accounts — email addresses, "
                           "password hints, passwords, usernames")
    assert describe(breaches._plain(LATER)).endswith("(not verified by HIBP)")
