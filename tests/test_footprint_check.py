"""Footprint's engine: verdicts, confidence, ordering, time limits and memory."""

import asyncio
import json

import httpx
import pytest
import respx

from footprint import check, store
from footprint.check import judge, plan, search
from footprint.manifest import Probe, Site

WMN = Probe(source="whatsmyname", id="whatsmyname:Ex", url="https://ex.test/{account}",
            found_codes=(200,), found_text=('class="profile"',),
            missing_codes=(404,), missing_text=("No such user",), known=("blue",))
SAME_CODE = Probe(source="whatsmyname", id="whatsmyname:Same", url="https://same.test/{account}",
                  found_codes=(200,), found_text=("Posts - See photos",),
                  missing_codes=(200,), missing_text=('"routePath":null',))
SHERLOCK_MSG = Probe(source="sherlock", id="sherlock:Ex", url="https://ex.test/{account}",
                     missing_text=("Sorry, nobody goes by that name",))
SHERLOCK_STATUS = Probe(source="sherlock", id="sherlock:St", url="https://st.test/{account}",
                        method="HEAD", missing_if_not_2xx=True)


class TestJudge:
    def test_both_signs_agree_on_found(self):
        v = judge(WMN, 200, '<div class="profile">Marisol</div>')
        assert (v.status, v.confidence) == ("found", "confirmed")
        assert "class=" in v.reason

    def test_both_signs_agree_on_missing(self):
        v = judge(WMN, 404, "<h1>No such user</h1>")
        assert (v.status, v.confidence) == ("not_found", "confirmed")

    def test_a_page_matching_neither_sign_is_unclear_not_found(self):
        # This is Sherlock's false-positive case: a redesigned or broken page.
        v = judge(WMN, 200, "<html>Something went wrong</html>")
        assert v.status == "unclear"
        assert "may have changed" in v.reason

    def test_a_page_matching_both_signs_is_unclear(self):
        v = judge(SAME_CODE, 200, 'Posts - See photos ... "routePath":null')
        assert v.status == "unclear"

    def test_a_bot_wall_is_never_found(self):
        v = judge(SHERLOCK_MSG, 200, '<span id="challenge-error-text">Checking your browser')
        assert v.status == "unclear"
        assert "Cloudflare" in v.reason

    def test_a_refusal_is_unclear(self):
        assert judge(WMN, 403, "").status == "unclear"
        assert judge(SHERLOCK_STATUS, 429, "").status == "unclear"

    def test_one_sided_missing_text_is_likely_not_found(self):
        v = judge(SHERLOCK_MSG, 200, "Sorry, nobody goes by that name.")
        assert (v.status, v.confidence) == ("not_found", "likely")

    def test_one_sided_absence_is_only_likely_found(self):
        v = judge(SHERLOCK_MSG, 200, "<html>a profile</html>")
        assert (v.status, v.confidence) == ("found", "likely")
        assert "not confirmed" in v.reason

    def test_one_sided_server_error_is_unclear_not_found(self):
        # Sherlock would call this "found": no error text on a 500 page.
        assert judge(SHERLOCK_MSG, 500, "Internal error").status == "unclear"

    def test_status_only_sites(self):
        assert judge(SHERLOCK_STATUS, 200, "").status == "found"
        assert judge(SHERLOCK_STATUS, 404, "").status == "not_found"

    def test_errors_are_unclear(self):
        v = judge(WMN, None, error="No answer within 10 seconds")
        assert v.status == "unclear" and "10 seconds" in v.reason


class TestScanner:
    def test_stops_once_the_verdict_cannot_change(self):
        s = check._Scanner(WMN, 200)
        assert s.pending()
        s.feed('<div class="prof')
        s.feed('ile">')  # a sign split across two chunks still counts
        assert not s.pending()

    def test_keeps_reading_when_found_and_missing_share_a_status_code(self):
        # Instagram-style: both answers are 200, so the missing sign must be
        # ruled out before "found" is sure.
        s = check._Scanner(SAME_CODE, 200)
        s.feed("Posts - See photos")
        assert s.pending()


def _site(key, probe, name=None, nsfw=False):
    url = f"https://{key}/{{account}}"
    probe = Probe(**{**probe.__dict__, "url": url, "id": f"{probe.source}:{key}"})
    return Site(key=key, name=name or key, profile_url=url, probes=[probe], nsfw=nsfw)


def _sites(*sites):
    return {s.key: s for s in sites}


@pytest.fixture
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


class TestPlan:
    def test_big_platforms_first_then_fastest(self, conn):
        store.record_timings(conn, [("slow.test", 4000, "ok")] * 3 + [("fast.test", 200, "ok")] * 3)
        sites = _sites(_site("slow.test", WMN), _site("fast.test", WMN), _site("github.com", WMN),
                       _site("tiktok.com", WMN))
        order = [p.site.key for p in plan("marisol", sites, conn)]
        assert order == ["tiktok.com", "github.com", "fast.test", "slow.test"]

    def test_big_only(self, conn):
        sites = _sites(_site("tiktok.com", WMN), _site("small.test", WMN))
        assert [p.site.key for p in plan("m", sites, conn, big_only=True)] == ["tiktok.com"]

    def test_nsfw_sites_are_off_by_default(self, conn):
        sites = _sites(_site("adult.test", WMN, nsfw=True), _site("ok.test", WMN))
        assert [p.site.key for p in plan("m", sites, conn)] == ["ok.test"]
        assert len(plan("m", sites, conn, include_nsfw=True)) == 2

    def test_slow_lane_goes_last_with_a_short_limit(self, conn):
        store.record_timings(conn, [("laggard.test", None, "timeout")] * 3)
        sites = _sites(_site("laggard.test", WMN), _site("other.test", WMN))
        planned = plan("m", sites, conn)
        assert [p.site.key for p in planned] == ["other.test", "laggard.test"]
        assert planned[-1].lane == "slow" and planned[-1].timeout == store.SLOW_LANE_TIMEOUT

    def test_learned_time_limit(self, conn):
        store.record_timings(conn, [("s.test", ms, "ok") for ms in (500, 800, 1000, 2500)])
        (p,) = plan("m", _sites(_site("s.test", WMN)), conn)
        assert p.timeout == 5.0  # twice the 90th-percentile answer

    def test_names_a_site_cannot_have_are_not_asked(self, conn):
        strict = Probe(**{**WMN.__dict__, "allowed": "^[a-z]+$"})
        (p,) = plan("Has Spaces", _sites(_site("strict.test", strict)), conn)
        assert p.skip.status == "cant_exist"

    def test_health_check_picks_a_working_recipe(self, conn):
        site = Site(key="ex.test", name="Ex", profile_url="https://ex.test/{account}",
                    probes=[WMN, SHERLOCK_MSG])
        store.save_health(conn, [("ex.test", WMN.id, "false_found", "says made-up names exist")])
        (p,) = plan("m", {"ex.test": site}, conn)
        assert p.probe.id == SHERLOCK_MSG.id

    def test_a_site_with_no_working_recipe_is_set_aside(self, conn):
        site = Site(key="ex.test", name="Ex", profile_url="https://ex.test/{account}", probes=[WMN])
        store.save_health(conn, [("ex.test", WMN.id, "misses_real", "can't see a known account")])
        (p,) = plan("m", {"ex.test": site}, conn)
        assert p.skip.status == "skipped"
        assert "can't see a known account" in p.skip.reason


async def _collect(gen):
    return [r async for r in gen]


@pytest.mark.asyncio
class TestSearch:
    @respx.mock
    async def test_answers_arrive_in_the_order_sites_reply(self, conn):
        async def slow(request):
            await asyncio.sleep(0.3)
            return httpx.Response(200, text='<div class="profile">')

        respx.get("https://tiktok.com/marisol").mock(side_effect=slow)
        respx.get("https://quick.test/marisol").mock(
            return_value=httpx.Response(404, text="No such user"))
        sites = _sites(_site("tiktok.com", WMN), _site("quick.test", WMN))
        async with httpx.AsyncClient() as client:
            results = await _collect(search("@marisol", sites, client, conn=conn))
        # TikTok was asked first but answered last; it doesn't hold up the rest.
        assert [r.site for r in results] == ["quick.test", "tiktok.com"]
        assert results[1].status == "found" and results[1].confidence == "confirmed"
        assert results[1].big and not results[0].big
        assert results[1].url == "https://tiktok.com/marisol"

    @respx.mock
    async def test_a_slow_site_times_out_and_is_remembered(self, conn, monkeypatch):
        async def stuck(request):
            await asyncio.sleep(5)
            return httpx.Response(200)

        monkeypatch.setattr(store, "MIN_TIMEOUT", 0.2)  # keep the test quick
        respx.get("https://stuck.test/m").mock(side_effect=stuck)
        store.record_timings(conn, [("stuck.test", 50, "ok")] * 3)  # a fast site, so a short limit
        sites = _sites(_site("stuck.test", WMN))
        assert plan("m", sites, conn)[0].timeout == 0.2
        async with httpx.AsyncClient() as client:
            (r,) = await _collect(search("m", sites, client, conn=conn))
        assert r.status == "unclear" and r.outcome == "timeout"
        rows = conn.execute("SELECT outcome FROM timings WHERE site='stuck.test' "
                            "ORDER BY rowid DESC LIMIT 1").fetchall()
        assert rows[0]["outcome"] == "timeout"

    @respx.mock
    async def test_names_a_site_cannot_have_never_cost_a_request(self, conn):
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200))
        strict = Probe(**{**WMN.__dict__, "allowed": "^[a-z]+$"})
        async with httpx.AsyncClient() as client:
            (r,) = await _collect(search("No Way", _sites(_site("strict.test", strict)), client))
        assert r.status == "cant_exist"
        assert not route.called

    @respx.mock
    async def test_status_only_sites_get_a_head_request(self, conn):
        route = respx.head("https://st.test/m").mock(return_value=httpx.Response(404))
        async with httpx.AsyncClient() as client:
            (r,) = await _collect(search("m", _sites(_site("st.test", SHERLOCK_STATUS)), client))
        assert route.called and r.status == "not_found"

    @respx.mock
    async def test_post_bodies_carry_the_name_safely(self):
        poster = Probe(source="whatsmyname", id="whatsmyname:P", url="https://post.test/api",
                       method="POST", body='{"username":"{account}"}',
                       found_codes=(200,), found_text=("taken",),
                       missing_codes=(200,), missing_text=("available",))
        seen = {}

        def capture(request):
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, text="available")

        respx.post("https://post.test/api").mock(side_effect=capture)
        site = Site(key="post.test", name="P", profile_url="https://post.test/{account}", probes=[poster])
        async with httpx.AsyncClient() as client:
            (r,) = await _collect(search('a"b', {"post.test": site}, client))
        assert seen["body"] == {"username": 'a"b'}
        assert r.status == "not_found"

    @respx.mock
    async def test_connection_errors_are_unclear(self):
        respx.get("https://down.test/m").mock(side_effect=httpx.ConnectError("refused"))
        async with httpx.AsyncClient() as client:
            (r,) = await _collect(search("m", _sites(_site("down.test", WMN)), client))
        assert r.status == "unclear" and r.outcome == "error"

    @respx.mock
    async def test_no_more_than_the_per_site_limit_at_once(self):
        live = {"now": 0, "most": 0}

        async def count(request):
            live["now"] += 1
            live["most"] = max(live["most"], live["now"])
            await asyncio.sleep(0.05)
            live["now"] -= 1
            return httpx.Response(404, text="No such user")

        respx.get(url__regex=r"https://one\.host/.*").mock(side_effect=count)
        sites = {}
        for i in range(10):
            p = Probe(**{**WMN.__dict__, "id": f"w:{i}", "url": f"https://one.host/{i}/{{account}}"})
            sites[f"s{i}.test"] = Site(key=f"s{i}.test", name=str(i),
                                       profile_url=f"https://s{i}.test/{{account}}", probes=[p])
        async with httpx.AsyncClient() as client:
            results = await _collect(search("m", sites, client, per_host=4))
        assert len(results) == 10
        assert live["most"] <= 4


class TestSpeedMemory:
    def test_keeps_only_the_last_twenty_answers(self, conn):
        store.record_timings(conn, [("a.test", i, "ok") for i in range(30)])
        n = conn.execute("SELECT COUNT(*) FROM timings WHERE site='a.test'").fetchone()[0]
        assert n == store.KEEP_TIMINGS

    def test_limit_is_clamped(self, conn):
        store.record_timings(conn, [("fast.test", 50, "ok")] * 3 + [("glacial.test", 30000, "ok")] * 3)
        s = store.speeds(conn)
        assert s["fast.test"].timeout == store.MIN_TIMEOUT
        assert s["glacial.test"].timeout == store.MAX_TIMEOUT

    def test_a_site_leaves_the_slow_lane_when_it_answers_again(self, conn):
        store.record_timings(conn, [("l.test", None, "timeout")] * 3)
        assert store.speeds(conn)["l.test"].slow_lane
        store.record_timings(conn, [("l.test", 300, "ok")] * 3)
        assert not store.speeds(conn)["l.test"].slow_lane
