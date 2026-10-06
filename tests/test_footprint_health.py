"""The daily health check: broken recipes are found, set aside, and restored."""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from footprint import health, store
from footprint.check import Result, plan
from footprint.manifest import Probe, Site


def _probe(key, **kw):
    base = dict(source="whatsmyname", id=f"whatsmyname:{key}", url=f"https://{key}/{{account}}",
                found_codes=(200,), found_text=('class="profile"',),
                missing_codes=(404,), missing_text=("No such user",), known=("realperson",))
    base.update(kw)
    return Probe(**base)


def _site(key, *probes):
    return Site(key=key, name=key, profile_url=f"https://{key}/{{account}}",
                probes=list(probes) or [_probe(key)])


def _honest(request):
    """A site that tells the truth: only 'realperson' exists."""
    if request.url.path.strip("/") == "realperson":
        return httpx.Response(200, text='<div class="profile">')
    return httpx.Response(404, text="No such user")


@pytest.fixture
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


def _r(status, outcome="ok", reason="x"):
    return Result(site="s", name="s", url="u", status=status, outcome=outcome, reason=reason)


class TestClassify:
    def test_working(self):
        assert health.classify(_r("found"), _r("not_found"))[0] == "working"

    def test_a_made_up_name_that_exists_is_a_false_found(self):
        assert health.classify(_r("found"), _r("found"))[0] == "false_found"

    def test_a_known_account_that_vanished(self):
        assert health.classify(_r("not_found"), _r("not_found"))[0] == "misses_real"

    def test_bot_walls_and_refusals_are_blocked(self):
        state, _ = health.classify(_r("unclear", reason="Blocked by a Cloudflare bot check"),
                                   _r("not_found"))
        assert state == "blocked"

    def test_a_page_matching_neither_sign_means_the_site_changed(self):
        state, _ = health.classify(_r("unclear", reason="looks like neither"), _r("not_found"))
        assert state == "changed"

    def test_timeouts(self):
        assert health.classify(_r("unclear", "timeout"), _r("not_found"))[0] == "too_slow"

    def test_no_known_account_is_only_partly_tested(self):
        assert health.classify(None, _r("not_found"))[0] == "partly"


@pytest.mark.asyncio
class TestRun:
    @respx.mock
    async def test_broken_sites_are_set_aside_and_working_ones_kept(self, conn):
        respx.get(url__regex=r"https://good\.test/.*").mock(side_effect=_honest)
        # Says everyone exists: Sherlock's classic false positive.
        respx.get(url__regex=r"https://liar\.test/.*").mock(
            return_value=httpx.Response(200, text='<div class="profile">'))
        sites = {"good.test": _site("good.test"), "liar.test": _site("liar.test")}
        async with httpx.AsyncClient() as client:
            progress = await health.run(sites, conn, client)
        assert progress.done == progress.total == 2 and not progress.running
        assert progress.counts == {"working": 1, "false_found": 1}

        planned = {p.site.key: p for p in plan("someone", sites, conn)}
        assert planned["good.test"].skip is None
        assert planned["liar.test"].skip.status == "skipped"
        assert "made-up names" in planned["liar.test"].skip.reason

    @respx.mock
    async def test_a_working_second_recipe_rescues_a_site(self, conn):
        broken = _probe("two.test", id="whatsmyname:two", url="https://two.test/api/{account}")
        backup = Probe(source="sherlock", id="sherlock:two", url="https://two.test/{account}",
                       missing_text=("No such user",), known=("realperson",))
        respx.get(url__regex=r"https://two\.test/api/.*").mock(return_value=httpx.Response(500))
        respx.get(url__regex=r"https://two\.test/[a-z]+$").mock(side_effect=_honest)
        sites = {"two.test": _site("two.test", broken, backup)}
        async with httpx.AsyncClient() as client:
            await health.run(sites, conn, client)
        (p,) = plan("someone", sites, conn)
        assert p.probe.id == "sherlock:two"

    @respx.mock
    async def test_a_site_that_recovers_comes_back(self, conn):
        store.save_health(conn, [("good.test", "whatsmyname:good.test", "changed", "broke")])
        respx.get(url__regex=r"https://good\.test/.*").mock(side_effect=_honest)
        sites = {"good.test": _site("good.test")}
        assert plan("x", sites, conn)[0].skip is not None
        async with httpx.AsyncClient() as client:
            await health.run(sites, conn, client)
        assert plan("x", sites, conn)[0].skip is None

    @respx.mock
    async def test_a_network_outage_does_not_wipe_good_results(self, conn):
        sites = {f"s{i}.test": _site(f"s{i}.test") for i in range(25)}
        store.save_health(conn, [(k, f"whatsmyname:{k}", "working", "ok") for k in sites])
        respx.get(url__regex=r".*").mock(side_effect=httpx.ConnectError("offline"))
        async with httpx.AsyncClient() as client:
            progress = await health.run(sites, conn, client)
        assert "network problem" in progress.note
        assert all(rows[f"whatsmyname:{k}"]["state"] == "working"
                   for k, rows in store.health(conn).items())


class TestDaily:
    def test_due_when_never_run_or_a_day_old(self, conn):
        assert health.due(conn)
        store.set_meta(conn, "health_last_run", store.now_iso())
        assert not health.due(conn)
        later = datetime.now(timezone.utc) + timedelta(hours=25)
        assert health.due(conn, now=later)

    @pytest.mark.asyncio
    @respx.mock
    async def test_starts_once_in_the_background(self, conn):
        async def slow(request):
            await asyncio.sleep(0.05)
            return _honest(request)

        respx.get(url__regex=r"https://good\.test/.*").mock(side_effect=slow)
        daily = health.Daily()
        sites = {"good.test": _site("good.test")}
        async with httpx.AsyncClient() as client:
            assert daily.start(sites, conn, client)
            assert not daily.start(sites, conn, client, force=True)  # already running
            await daily.task
            assert not daily.start(sites, conn, client)  # ran today
            assert daily.last(conn)["counts"] == {"working": 1}
