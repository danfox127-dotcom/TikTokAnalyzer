"""Deterministic tests for the YouTube cross-platform bridge prototype.

Mocks httpx so the channel-page parsing + match logic is verified without network.
A separate live smoke (utils/youtube_bridge against real handles) is exercised
manually; these tests pin the parsing contract.
"""
import asyncio
import pytest

from utils import youtube_bridge as yb


class _FakeResp:
    def __init__(self, status_code, text="", url="https://www.youtube.com/@x"):
        self.status_code = status_code
        self.text = text
        self.url = url


class _FakeClient:
    """Returns a queued response per get() call."""
    def __init__(self, resp):
        self._resp = resp

    async def get(self, url, **kwargs):
        return self._resp


_CHANNEL_HTML = (
    '<meta property="og:title" content="Marques Brownlee">'
    '<meta property="og:description" content="MKBHD: Quality Tech Videos | Consumer Electronics">'
    '<meta name="keywords" content="MKBHD, Marques Brownlee, tech reviews">'
    '"subscriberCountText":{"accessibility":{},"simpleText":"19.5M subscribers"}'
)

_DEFAULT_KW_HTML = (
    '<meta property="og:title" content="Some Small Channel">'
    '<meta property="og:description" content="hi">'
    '<meta name="keywords" content="video, sharing, camera phone, video phone, free, upload">'
)


@pytest.fixture(autouse=True)
def _clear_cache():
    yb._cache.clear()
    yield
    yb._cache.clear()


def _run(coro):
    return asyncio.run(coro)


def test_keyless_parses_channel_and_verifies_name(monkeypatch):
    monkeypatch.setattr(yb, "YT_API_KEY", None)
    client = _FakeClient(_FakeResp(200, _CHANNEL_HTML))
    r = _run(yb.resolve_handle("@mkbhd", client, display_name="Marques Brownlee"))
    assert r["status"] == "ok"
    assert r["match"] == "name_verified"        # display name matches og:title
    assert r["data"]["channel_title"] == "Marques Brownlee"
    assert "tech reviews" in r["data"]["topics"]
    assert r["data"]["subscriber_text"] == "19.5M subscribers"


def test_keyless_handle_only_when_no_name(monkeypatch):
    monkeypatch.setattr(yb, "YT_API_KEY", None)
    client = _FakeClient(_FakeResp(200, _CHANNEL_HTML))
    r = _run(yb.resolve_handle("@mkbhd", client))   # no display name supplied
    assert r["status"] == "ok"
    assert r["match"] == "handle_only"


def test_default_youtube_keywords_are_filtered(monkeypatch):
    monkeypatch.setattr(yb, "YT_API_KEY", None)
    client = _FakeClient(_FakeResp(200, _DEFAULT_KW_HTML))
    r = _run(yb.resolve_handle("@small", client))
    assert r["status"] == "ok"
    assert r["data"]["topics"] == []   # boilerplate dropped, not surfaced as topics


def test_404_is_not_found(monkeypatch):
    monkeypatch.setattr(yb, "YT_API_KEY", None)
    client = _FakeClient(_FakeResp(404))
    r = _run(yb.resolve_handle("@nope", client))
    assert r["status"] == "not_found"


def test_normalize_handle_strips_noise():
    assert yb.normalize_handle("@dakota.johnson") == "dakota.johnson"
    assert yb.normalize_handle("Dakota Johnson 🎬") == "DakotaJohnson"
