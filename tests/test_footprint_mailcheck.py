"""Can email from a domain be faked? Read from its public MX, SPF and DMARC records."""

import httpx
import pytest
import respx

from footprint import mailcheck
from footprint.mailcheck import MailCheck, check, judge, parse_dmarc

SPF = "v=spf1 include:_spf.google.com ~all"


def _dns(answers: dict):
    """A stand-in for dns.google. ``answers[(name, type)]`` is a list of
    records, or ``"fail"`` for a lookup that errors; anything missing is
    "no such name"."""
    codes = {"MX": 15, "TXT": 16}

    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.params["name"]
        rtype = request.url.params["type"]
        found = answers.get((name, rtype))
        if found == "fail":
            return httpx.Response(200, json={"Status": 2})  # SERVFAIL
        if found is None:
            return httpx.Response(200, json={"Status": 3})  # NXDOMAIN
        return httpx.Response(200, json={"Status": 0, "Answer": [
            {"name": name + ".", "type": codes[rtype], "data": data} for data in found]})

    return handler


async def _check(domain, answers):
    with respx.mock:
        respx.get(mailcheck.DOH).mock(side_effect=_dns(answers))
        async with httpx.AsyncClient() as client:
            return await check(domain, client)


def _base(domain="brand.com", dmarc=None, mx=("10 aspmx.l.google.com.",), spf=SPF):
    answers = {(domain, "MX"): list(mx), (domain, "TXT"): [spf] if spf else []}
    if dmarc is not None:
        answers[("_dmarc." + domain, "TXT")] = [dmarc]
    return answers


@pytest.mark.asyncio
class TestCheck:
    async def test_reject_is_protected(self):
        c = await _check("brand.com", _base(dmarc="v=DMARC1; p=reject; rua=mailto:x@brand.com"))
        assert c.verdict == "protected"
        assert "refused" in c.summary
        assert c.provider == "Google Workspace"
        assert c.receives_mail is True
        assert c.spf == SPF

    async def test_quarantine_is_protected_but_says_spam(self):
        c = await _check("brand.com", _base(dmarc="v=DMARC1; p=quarantine"))
        assert c.verdict == "protected" and "spam" in c.summary

    async def test_a_partial_percentage_is_partly(self):
        c = await _check("brand.com", _base(dmarc="v=DMARC1; p=reject; pct=25"))
        assert c.verdict == "partly" and "25%" in c.summary

    async def test_none_only_watches(self):
        c = await _check("brand.com", _base(dmarc="v=DMARC1; p=none; rua=mailto:r@brand.com"))
        assert c.verdict == "watching"
        assert "quarantine or reject" in c.advice

    async def test_no_dmarc_is_open(self):
        c = await _check("brand.com", _base())
        assert c.verdict == "open"
        assert "Anyone can send" in c.summary
        assert "DMARC" in c.advice

    async def test_a_subdomain_inherits_its_parent_record_through_sp(self):
        answers = _base("news.brand.com")
        answers[("_dmarc.brand.com", "TXT")] = ["v=DMARC1; p=reject; sp=none"]
        c = await _check("news.brand.com", answers)
        assert c.dmarc_from == "brand.com"
        assert c.policy == "none" and c.verdict == "watching"

    async def test_long_records_split_into_pieces_are_joined(self):
        c = await _check("brand.com", _base(dmarc='"v=DMARC1; p=rej" "ect"'))
        assert c.policy == "reject"

    async def test_a_domain_that_takes_no_mail(self):
        c = await _check("parked.com", _base("parked.com", mx=("0 .",), spf="v=spf1 -all",
                                             dmarc="v=DMARC1; p=reject"))
        assert c.receives_mail is False
        assert any("can't receive email" in n for n in c.notes)

    async def test_spf_that_allows_anyone_is_called_out(self):
        c = await _check("brand.com", _base(spf="v=spf1 +all", dmarc="v=DMARC1; p=reject"))
        assert any("+all" in n for n in c.notes)

    async def test_a_domain_that_does_not_exist(self):
        c = await _check("no-such-brand.com", {})
        assert c.verdict == "no_domain"
        assert "doesn't exist" in c.summary

    async def test_a_failed_lookup_is_unknown_never_open(self):
        answers = _base(dmarc="v=DMARC1; p=reject")
        answers[("_dmarc.brand.com", "TXT")] = "fail"
        c = await _check("brand.com", answers)
        assert c.verdict == "unknown"
        assert "Couldn't look up" in c.summary

    async def test_the_lookup_sends_only_the_domain(self):
        seen = []

        def handler(request):
            seen.append(request.url.params["name"])
            return httpx.Response(200, json={"Status": 0, "Answer": []})

        with respx.mock:
            respx.get(mailcheck.DOH).mock(side_effect=handler)
            async with httpx.AsyncClient() as client:
                await check("Brand.com.", client)
        assert set(seen) == {"brand.com", "_dmarc.brand.com"}


class TestParts:
    def test_parse_dmarc(self):
        assert parse_dmarc("v=DMARC1; p=reject; pct=50; rua=mailto:a@b.c") == {
            "v": "DMARC1", "p": "reject", "pct": "50", "rua": "mailto:a@b.c"}

    def test_a_record_without_a_usable_policy_is_open(self):
        c = judge(MailCheck(domain="b.com", dmarc="v=DMARC1; rua=mailto:x@b.com", policy=None,
                            spf=SPF, receives_mail=True))
        assert c.verdict == "open"

    def test_provider_from_mail_servers(self):
        assert mailcheck.provider_of(["brand-com.mail.protection.outlook.com"]) == "Microsoft 365"
        assert mailcheck.provider_of(["mx.unknown-host.net"]) is None
