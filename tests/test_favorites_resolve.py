"""Resolution: the part that turns a shared link into a catalogue entry."""

import json

import httpx
import pytest
import respx

from favorites import platforms
from favorites.resolve import (
    browsable_url, canonical_form, detect_platform, extract_url, resolve,
    strip_tracking,
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
        respx.get(host="www.tiktok.com", path="/@citydesk/video/7123").mock(
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
        respx.get(host="www.tiktokv.com", path="/share/video/7123/").mock(
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
        respx.get(host="www.tiktokv.com", path="/share/video/7123/").mock(
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

    @respx.mock
    async def test_tiktoks_slogan_page_is_a_placeholder(self):
        # What a share link opened to from the cloud: no oEmbed, and a page
        # about TikTok in place of the video. Left unresolved, the Mac's
        # helper looks it up again from home, where TikTok answers properly.
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(400))
        respx.get(host="www.tiktok.com", path__startswith="/t/").mock(
            return_value=httpx.Response(200, text=SLOGAN_PAGE,
                                        headers={"content-type": "text/html"}))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://www.tiktok.com/t/ZTf7W8jhW/", client)
        assert item.resolve_status == "unresolved"
        assert item.title != "TikTok - Make Your Day"
        assert item.description is None
        assert item.creator_name is None


@pytest.mark.asyncio
class TestTikToksBareAnswer:
    """Since late October TikTok's oEmbed can answer with a player and the
    video's number, and nothing else: no caption, creator or picture."""

    BARE = {"version": "1.0", "type": "video", "width": "325", "height": "578",
            "html": '<iframe src="https://www.tiktok.com/player/v1/7300000000000000001"></iframe>',
            "provider_url": "https://www.tiktok.com", "provider_name": "TikTok",
            "embed_product_id": "7300000000000000001", "embed_type": "video"}

    def page(self, item=None):
        data = {"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": item}}}}
        script = ('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
                  + json.dumps(data) + "</script>") if item else ""
        return httpx.Response(200, text=SLOGAN_PAGE.replace("</head>", script + "</head>"),
                              headers={"content-type": "text/html"})

    def answers(self, page):
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=self.BARE))
        respx.get(host="www.tiktok.com", path__startswith="/t/").mock(return_value=page)

    @respx.mock
    async def test_the_page_supplies_the_caption_creator_and_picture(self):
        self.answers(self.page({
            "id": "7300000000000000001", "desc": "the zoning meeting went sideways #localgov",
            "author": {"uniqueId": "citydesk", "nickname": "City Desk"},
            "video": {"duration": 58, "cover": "https://p16.tiktokcdn.com/cover.jpg"}}))
        async with httpx.AsyncClient() as client:
            item = await resolve("https://www.tiktok.com/t/ZTf7W8jhW/", client)
        assert item.resolve_status == "ok"
        assert item.title == "the zoning meeting went sideways #localgov"
        assert item.description == item.title  # the caption, not the slogan
        assert (item.creator_handle, item.creator_name) == ("@citydesk", "City Desk")
        assert item.thumbnail_url == "https://p16.tiktokcdn.com/cover.jpg"
        assert item.external_id == "7300000000000000001"

    @respx.mock
    async def test_without_the_pages_data_it_waits_but_keeps_the_videos_number(self):
        # Unresolved, so the Mac asks again; the number already plays it in Faves.
        self.answers(self.page())
        async with httpx.AsyncClient() as client:
            item = await resolve("https://www.tiktok.com/t/ZTf7W8jhW/", client)
        assert item.resolve_status == "unresolved"
        assert item.external_id == "7300000000000000001"
        assert item.description is None

    @respx.mock
    async def test_an_imported_save_reads_its_page_through_the_share_link(self):
        # An export's save is stored as tiktok.com/video/<id>, which is no page
        # at all. Its share link is, and leads to the video's own.
        vid = "7300000000000000001"
        respx.get(host="www.tiktok.com", path="/oembed").mock(
            return_value=httpx.Response(200, json=self.BARE))
        respx.get(host="www.tiktok.com", path=f"/video/{vid}").mock(return_value=httpx.Response(404))
        respx.get(host="www.tiktokv.com", path=f"/share/video/{vid}/").mock(return_value=self.page({
            "id": vid, "desc": "how dry cleaning actually works", "author": {"uniqueId": "citydesk"},
            "video": {"cover": "https://p16.tiktokcdn.com/cover.jpg"}}))
        async with httpx.AsyncClient() as client:
            item = await resolve(f"https://www.tiktok.com/video/{vid}", client)
        assert item.resolve_status == "ok"
        assert (item.title, item.creator_handle) == ("how dry cleaning actually works", "@citydesk")
        assert item.canonical_url == f"https://www.tiktok.com/video/{vid}"  # the same save


class TestTikTokPage:
    """Where a TikTok save's own page is read."""

    def test_an_imported_save_uses_its_share_link(self):
        assert platforms._tiktok_page({"canonical_url": "https://www.tiktok.com/video/71",
                                       "external_id": "71"}) == "https://www.tiktokv.com/share/video/71/"

    def test_with_the_creator_known_it_uses_the_videos_own_address(self):
        assert platforms._tiktok_page({"canonical_url": "https://www.tiktok.com/video/71",
                                       "external_id": "71", "creator_handle": "@a"}) == \
            "https://www.tiktok.com/@a/video/71"

    def test_a_link_as_shared_is_read_as_it_is(self):
        assert platforms._tiktok_page({"canonical_url": "https://www.tiktok.com/t/ZTf7W8jhW",
                                       "external_id": "71"}) is None


class TestTikTokPageDetails:
    def page(self, item):
        data = {"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": item}}}}
        return ('<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
                + json.dumps(data) + "</script></html>")

    def test_it_prefers_the_full_size_cover(self):
        found = platforms._tiktok_details(self.page({
            "id": "71", "desc": "a caption", "author": {"uniqueId": "a", "nickname": ""},
            "video": {"cover": "small.jpg", "originCover": "full.jpg"}}))
        assert found == {"title": "a caption", "creator_handle": "@a",
                         "thumbnail_url": "full.jpg", "external_id": "71"}

    def test_an_author_given_by_handle_alone(self):
        assert platforms._tiktok_details(self.page({"author": "citydesk"})) == {
            "creator_handle": "@citydesk"}

    @pytest.mark.parametrize("html", ["", "<html><title>TikTok - Make Your Day</title></html>",
                                      '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">{not json'
                                      "</script>"])
    def test_a_page_without_the_data_says_nothing(self, html):
        assert platforms._tiktok_details(html) == {}


SLOGAN_PAGE = (
    '<html><head><title>TikTok - Make Your Day</title>'
    '<meta property="og:title" content="TikTok - Make Your Day">'
    '<meta property="og:description" content="TikTok - Make Your Day">'
    '<meta property="og:site_name" content="TikTok"></head></html>')


class TestBrowsableUrl:
    """The identity key and the link you click are different values.

    TikTok identity deliberately drops the @handle so an export and a share
    sheet file the same video once. But tiktok.com/video/<id> is not a route
    TikTok serves, so using the identity as the outbound link 404s every item
    in the library.
    """

    TIKTOK = {
        "platform": "tiktok",
        "external_id": "7123",
        "canonical_url": "https://www.tiktok.com/video/7123",
        "shared_url": "https://www.tiktokv.com/share/video/7123/",
    }

    def test_the_identity_key_is_never_the_link(self):
        assert browsable_url(self.TIKTOK) != self.TIKTOK["canonical_url"]

    def test_a_resolved_tiktok_links_to_the_real_url(self):
        item = {**self.TIKTOK, "creator_handle": "@citydesk"}
        assert browsable_url(item) == "https://www.tiktok.com/@citydesk/video/7123"

    def test_a_bare_handle_is_handled(self):
        item = {**self.TIKTOK, "creator_handle": "citydesk"}
        assert browsable_url(item) == "https://www.tiktok.com/@citydesk/video/7123"

    def test_an_unresolved_tiktok_falls_back_to_its_share_link(self):
        # No creator means it never resolved. The export's own share URL still
        # redirects, so it is the best link available.
        assert browsable_url(self.TIKTOK) == "https://www.tiktokv.com/share/video/7123/"

    def test_other_platforms_use_their_canonical_form(self):
        item = {"platform": "youtube", "external_id": "abc",
                "canonical_url": "https://www.youtube.com/watch?v=abc",
                "shared_url": "https://youtu.be/abc?si=tracking"}
        assert browsable_url(item) == "https://www.youtube.com/watch?v=abc"

    def test_an_item_with_nothing_does_not_raise(self):
        assert browsable_url({"platform": "tiktok"}) == ""
        assert browsable_url({}) == ""
