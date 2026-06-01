"""Tests for incremental creator resolution: map injection + durable fill."""
import asyncio
import pytest

from api.ghost_profile import _count_creators, _handle_from_link, _echo_chamber_index
from utils import creator_map


# --------------------------------------------------------------------------- #
# Map injection into the counting logic
# --------------------------------------------------------------------------- #
def _link(vid):
    return f"https://www.tiktokv.com/share/video/{vid}/"


def test_handle_from_link_prefers_url_then_map():
    # URL with @handle wins outright
    assert _handle_from_link("https://www.tiktok.com/@alice/video/1/") == "@alice"
    # handle-stripped link falls back to the resolved map (and gets @-prefixed)
    assert _handle_from_link(_link("111"), {"111": "bob"}) == "@bob"
    # no map, no @handle -> None
    assert _handle_from_link(_link("111")) is None


def test_count_creators_aggregates_by_handle_via_map():
    links = {_link("111"), _link("222"), _link("333")}
    handle_map = {"111": "alice", "222": "alice", "333": "bob"}
    result = _count_creators(links, limit=10, count_key="linger_count", link_handle_map=handle_map)
    by_handle = {c["handle"]: c["linger_count"] for c in result}
    assert by_handle == {"@alice": 2, "@bob": 1}   # real creator aggregation, not per-video


def test_count_creators_without_map_is_all_unknown():
    links = {_link("111"), _link("222")}
    result = _count_creators(links, limit=10, count_key="linger_count")
    assert all(c["handle"] == "Unknown" for c in result)   # the pre-resolution reality


def test_echo_chamber_is_handle_based_over_full_set():
    # 8 lingered videos: alice x4, bob x2, carol/dave x1 -> top5 = all 8 -> 100%
    links = [_link(str(i)) for i in range(8)]
    hmap = {"0": "alice", "1": "alice", "2": "alice", "3": "alice",
            "4": "bob", "5": "bob", "6": "carol", "7": "dave"}
    r = _echo_chamber_index(links, hmap)
    assert r["basis"] == 8 and r["distinct_creators"] == 4
    assert r["pct"] == 100.0
    # Make alice dominate among >5 creators so top-5 < total.
    links2 = [_link(str(i)) for i in range(10)]
    hmap2 = {"0": "a", "1": "a", "2": "a", "3": "a", "4": "a", "5": "a",  # a=6
             "6": "b", "7": "c", "8": "d", "9": "e"}                      # 4 singletons
    r2 = _echo_chamber_index(links2, hmap2)        # top5 = a(6)+b+c+d+e(4) = 10 of 10
    assert r2["basis"] == 10 and r2["distinct_creators"] == 5
    assert r2["pct"] == 100.0


def test_echo_chamber_unmeasurable_without_resolution():
    # Handle-stripped links + no map -> nothing resolves -> honest 0, not an artifact.
    links = [_link(str(i)) for i in range(20)]
    r = _echo_chamber_index(links, None)
    assert r == {"pct": 0.0, "basis": 0, "distinct_creators": 0}


# --------------------------------------------------------------------------- #
# Durable map: incremental fill + no re-pay
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolate_map(monkeypatch):
    monkeypatch.setattr(creator_map, "_redis", None)   # force in-memory fallback
    creator_map._local.clear()
    yield
    creator_map._local.clear()


def _fake_fetch_factory(handle_for):
    async def _fake_fetch_many(video_ids, concurrency=8):
        out = []
        for vid in video_ids:
            h = handle_for.get(vid)
            if h:
                out.append({"video_id": vid, "status": "ok",
                            "data": {"author": h, "author_name": h.title(), "thumbnail": ""}})
            else:
                out.append({"video_id": vid, "status": "failed", "data": {"author": "Unknown"}})
        return out
    return _fake_fetch_many


def test_resolve_and_fill_resolves_and_caches(monkeypatch):
    monkeypatch.setattr(creator_map.oembed, "fetch_many",
                        _fake_fetch_factory({"111": "alice", "222": "bob"}))
    vids = ["111", "222", "333"]   # 333 will miss

    r1 = asyncio.run(creator_map.resolve_and_fill(vids, budget=10))
    assert r1["handles"] == {"111": "alice", "222": "bob"}
    assert r1["resolved"] == 2 and r1["total"] == 3 and r1["newly_resolved"] == 2
    assert r1["pct"] == round(2 / 3 * 100, 1)

    # Second run: everything is cached (hits + miss), so nothing new is attempted.
    r2 = asyncio.run(creator_map.resolve_and_fill(vids, budget=10))
    assert r2["newly_resolved"] == 0
    assert r2["attempted"] == 0          # no re-pay for known videos
    assert r2["handles"] == {"111": "alice", "222": "bob"}


def test_budget_caps_attempts(monkeypatch):
    monkeypatch.setattr(creator_map.oembed, "fetch_many",
                        _fake_fetch_factory({str(i): f"c{i}" for i in range(20)}))
    vids = [str(i) for i in range(20)]
    r = asyncio.run(creator_map.resolve_and_fill(vids, budget=5))
    assert r["attempted"] == 5            # only the budget is fetched this run
    assert r["newly_resolved"] == 5
    assert r["resolved"] == 5 and r["total"] == 20
