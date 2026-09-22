"""Resolution: the part that turns a shared link into a catalogue entry."""

import httpx
import pytest
import respx

from favorites.resolve import (
    canonical_form, detect_platform, extract_url, resolve, strip_tracking,
)

TIKTOK_OEMBED = {
    "title": "the zoning meeting went sideways #localgov #housing",
    "author_name": "City Desk",
    "author_unique_id": "citydesk",
    "author_url": "https://www.tiktok.com/@citydesk",
    "thumbnail_url": "https://p16.tiktokcdn.com/thumb.jpg",
}

OG_PAGE = """
<html><head>
<title>Ignored when og:title exists</title>
<meta property="og:title" content="What the new zoning code actually does">
<meta property="og:description" content="A short guide to the rewrite.">
<meta property="og:image" content="https://example.com/cover.png">
<meta property="og:site_name" content="Cityscape">
</head><body>...</body></html>
"""


class TestExtractUrl:
    def test_finds_url_inside_shared_sentence(self):
        # Share sheets rarely send a bare link; TikTok sends the caption too.
        shared = "Check this out https://vm.tiktok.com/ZMabc123/ on TikTok"
        assert extract_url(shared) == "https://vm.tiktok.com/ZMabc123/"

    def test_strips_sentence_punctuation(self):
        assert extract_url("see https://example.com/a-post.") == "https://example.com/a-post"

    def test_returns_none_without_a_url(self):
        assert extract_url("just some text") is None
        assert extract_url("") is None


class TestPlatform:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.tiktok.com/@a/video/1", "tiktok"),
        ("https://vm.tiktok.com/ZM1/", "tiktok"),
        ("https://youtu.be/abc", "youtube"),
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://www.instagram.com/reel/XYZ/", "instagram"),
        ("https://x.com/user/status/12", "x"),
        ("https://old.reddit.com/r/x/comments/1/t/", "reddit"),
        ("https://someones.blog/post", "web"),
    ])
    def test_detects_platform_from_host(self, url, expected):
        assert detect_platform(url) == expected


class TestCanonicalForm:
    def test_strips_share_session_parameters(self):
        # These differ on every share, so leaving them in would defeat dedupe.
        dirty = "https://www.tiktok.com/@citydesk/video/7123?_t=8abc&_r=1&utm_source=x"
        assert strip_tracking(dirty) == "https://www.tiktok.com/@citydesk/video/7123"

    def test_every_way_a_tiktok_can_arrive_resolves_to_one_identity(self):
        # The handle is deliberately not part of the identity. A data export
        # strips it and serves from tiktokv.com; a share sheet includes it. If
        # identity depended on the handle, importing your history and later
        # sharing the same video would file it twice.
        forms = [
            "https://www.tiktok.com/@citydesk/video/7123?_t=1&is_from_webapp=1",
            "https://m.tiktok.com/@citydesk/video/7123/?_t=999",
            "https://www.tiktokv.com/share/video/7123/",
            "https://www.tiktok.com/video/7123",
        ]
        results = {canonical_form(u, detect_platform(u)) for u in forms}
        assert results == {("https://www.tiktok.com/video/7123", "7123")}

    def test_export_links_are_recognised_as_tiktok(self):
        # Exports serve from tiktokv.com, which is a different host entirely.
        assert detect_platform("https://www.tiktokv.com/share/video/7123/") == "tiktok"

    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
        "https://youtu.be/dQw4w9WgXcQ?si=tracking",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    ])
    def test_youtube_forms_collapse_to_one_id(self, url):
        canonical, external = canonical_form(url, "youtube")
        assert canonical == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert external == "dQw4w9WgXcQ"

    def test_instagram_reels_and_reel_are_the_same_thing(self):
        a, _ = canonical_form("https://www.instagram.com/reel/ABC123/?igshid=zz", "instagram")
        b, _ = canonical_form("https://www.instagram.com/reels/ABC123/", "instagram")
        assert a == b == "https://www.instagram.com/reel/ABC123"


@pytest.mark.asyncio
class TestResolve:
    @respx.mock
    async def test_tiktok_via_oembed(self):
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=TIKTOK_OEMBED))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://www.tiktok.com/@citydesk/video/7123?_t=9", client)
        assert item.resolve_status == "ok"
        assert item.platform == "tiktok"
        assert item.external_id == "7123"
        assert item.creator_name == "City Desk"
        assert item.creator_handle == "@citydesk"
        # On TikTok the caption is the only body text there is, so it has to
        # survive into the description as well as the title.
        assert "zoning" in item.description

    @respx.mock
    async def test_falls_back_to_opengraph_for_a_plain_web_page(self):
        respx.get(host="example.com").mock(
            return_value=httpx.Response(200, text=OG_PAGE,
                                        headers={"content-type": "text/html"}))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://example.com/zoning", client)
        assert item.resolve_status == "ok"
        assert item.platform == "web"
        assert item.title == "What the new zoning code actually does"
        assert item.description == "A short guide to the rewrite."
        assert item.thumbnail_url == "https://example.com/cover.png"
        assert item.creator_name == "Cityscape"

    @respx.mock
    async def test_opengraph_rescues_a_failed_oembed(self):
        # Instagram has no open oEmbed endpoint, and TikTok's sometimes 403s.
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(403))
        respx.get(host="www.tiktok.com", path__startswith="/video").mock(
            return_value=httpx.Response(200, text=OG_PAGE,
                                        headers={"content-type": "text/html"}))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://www.tiktok.com/@citydesk/video/7123", client)
        assert item.resolve_status == "ok"
        assert item.title == "What the new zoning code actually does"

    @respx.mock
    async def test_a_dead_link_is_still_worth_keeping(self):
        # The URL and your own note are the irreplaceable parts, so a total
        # resolution failure must still produce a storable item.
        respx.route(host="gone.example").mock(side_effect=httpx.ConnectError("nope"))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://gone.example/thing", client)
        assert item.resolve_status == "unresolved"
        assert item.canonical_url == "https://gone.example/thing"
        assert item.title == "https://gone.example/thing"

    @respx.mock
    async def test_shortener_is_expanded_before_identity_is_decided(self):
        full = "https://www.tiktok.com/@citydesk/video/7123"
        canonical = "https://www.tiktok.com/video/7123"
        respx.head(host="vm.tiktok.com").mock(
            return_value=httpx.Response(301, headers={"location": full}))
        respx.head(host="www.tiktok.com").mock(return_value=httpx.Response(200))
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=TIKTOK_OEMBED))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://vm.tiktok.com/ZMabc/", client)
        assert item.canonical_url == canonical
        assert item.external_id == "7123"

    @respx.mock
    async def test_non_shortener_links_are_not_pre_fetched(self):
        # Chasing every link would register a view on the creator's analytics.
        head = respx.head(host="example.com").mock(return_value=httpx.Response(200))
        respx.get(host="example.com").mock(
            return_value=httpx.Response(200, text=OG_PAGE,
                                        headers={"content-type": "text/html"}))
        async with httpx.AsyncClient() as client:
            await resolve("https://example.com/post", client)
        assert not head.called

    async def test_empty_input_does_not_raise(self):
        async with httpx.AsyncClient() as client:
            item = await resolve("   ", client)
        assert item.resolve_status == "failed"
        assert item.canonical_url == ""


PLACEHOLDER_PAGE = "<html><head><title>TikTok</title></head><body></body></html>"


@pytest.mark.asyncio
class TestPlaceholderPagesAreNotResolutions:
    """A deleted video still answers 200 with a well-formed page.

    Its title is just "TikTok". Accepting that as a resolution produces an item
    that looks catalogued and describes nothing -- and reports a 100% success
    rate over a library where a seventh of the links are dead.
    """

    @respx.mock
    async def test_a_dead_video_page_does_not_count_as_resolved(self):
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(404))
        respx.get(host="www.tiktok.com", path__startswith="/video").mock(
            return_value=httpx.Response(200, text=PLACEHOLDER_PAGE,
                                        headers={"content-type": "text/html"}))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://www.tiktok.com/video/7123", client)
        assert item.resolve_status == "unresolved"
        assert item.title != "TikTok"

    @respx.mock
    async def test_an_empty_oembed_is_not_rescued_by_the_placeholder_page(self):
        # This is the subtler half: oEmbed answers 200 but carries no title, so
        # the OpenGraph fallback runs and fills the gap with "TikTok".
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json={"title": "", "author_name": ""}))
        respx.get(host="www.tiktok.com", path__startswith="/video").mock(
            return_value=httpx.Response(200, text=PLACEHOLDER_PAGE,
                                        headers={"content-type": "text/html"}))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://www.tiktok.com/video/7123", client)
        assert item.title != "TikTok"
        assert item.resolve_status == "unresolved"

    @respx.mock
    async def test_a_real_video_still_resolves(self):
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=TIKTOK_OEMBED))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://www.tiktok.com/video/7123", client)
        assert item.resolve_status == "ok"
        assert item.creator_handle == "@citydesk"

    @respx.mock
    async def test_a_page_whose_only_metadata_is_a_real_title_still_resolves(self):
        # Don't over-correct: a blog with no OpenGraph tags but a genuine
        # <title> is a perfectly good resolution.
        page = "<html><head><title>What the zoning code does</title></head></html>"
        respx.get(host="someones.blog").mock(
            return_value=httpx.Response(200, text=page,
                                        headers={"content-type": "text/html"}))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://someones.blog/post", client)
        assert item.resolve_status == "ok"
        assert item.title == "What the zoning code does"

    @respx.mock
    async def test_a_site_name_title_is_also_a_placeholder(self):
        # Some platforms answer with og:site_name rather than the bare host.
        page = ('<html><head><title>Cityscape</title>'
                '<meta property="og:site_name" content="Cityscape"></head></html>')
        respx.get(host="example.com").mock(
            return_value=httpx.Response(200, text=page,
                                        headers={"content-type": "text/html"}))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://example.com/gone", client)
        assert item.resolve_status == "unresolved"
