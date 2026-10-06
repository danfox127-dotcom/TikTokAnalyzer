"""Public profile details, the same-person score, and the time-zone hint."""

import io
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from PIL import Image, ImageDraw

from footprint import match, profile
from footprint.profile import Profile, clean_title
from footprint.timezone import hint


# ------------------------------------------------------------------ profiles --

GITHUB_USER = {
    "login": "marisol", "name": "Marisol Reyes", "bio": "Weeknight recipes. Also at https://marisol.kitchen",
    "blog": "marisol.kitchen", "location": "Brooklyn, NY", "avatar_url": "https://avatars.test/m.png",
    "created_at": "2015-03-02T10:00:00Z", "twitter_username": "marisolcooks",
}

OG_PROFILE = """<html><head>
<meta property="og:title" content="Marisol Reyes (@marisol) &bull; Instagram photos and videos">
<meta property="og:description" content="Weeknight recipes from Brooklyn. linktr.ee/marisol">
<meta property="og:image" content="https://cdn.test/avatar.jpg">
</head></html>"""


class TestCleanTitle:
    @pytest.mark.parametrize("title,expected", [
        ("Marisol Reyes (@marisol) • Instagram photos and videos", "Marisol Reyes"),
        ("Marisol Reyes (@marisol) | TikTok", "Marisol Reyes"),
        ("Marisol Reyes - YouTube", "Marisol Reyes"),
        ("Instagram", None),
        ("", None),
    ])
    def test_platform_decoration_is_removed(self, title, expected):
        assert clean_title(title, "Instagram", "marisol") == expected


@pytest.mark.asyncio
class TestFetch:
    @respx.mock
    async def test_github_gives_location_links_and_post_times(self):
        respx.get("https://api.github.com/users/marisol").mock(
            return_value=httpx.Response(200, json=GITHUB_USER))
        respx.get("https://api.github.com/users/marisol/social_accounts").mock(
            return_value=httpx.Response(200, json=[{"provider": "bluesky",
                                                    "url": "https://bsky.app/profile/marisol.bsky.social"}]))
        respx.get("https://api.github.com/users/marisol/events/public").mock(
            return_value=httpx.Response(200, json=[{"created_at": "2026-09-01T14:00:00Z"},
                                                   {"created_at": "2026-09-03T15:30:00Z"}]))
        respx.get("https://github.com/marisol").mock(return_value=httpx.Response(200, text="<html></html>"))
        async with httpx.AsyncClient() as client:
            p = await profile.fetch("github.com", "GitHub", "marisol", "https://github.com/marisol", client)
        assert p.display_name == "Marisol Reyes"
        assert p.location == "Brooklyn, NY"
        assert p.sources["location"] == "GitHub's public API"
        assert "https://marisol.kitchen" in p.links
        assert "https://x.com/marisolcooks" in p.links
        assert "https://bsky.app/profile/marisol.bsky.social" in p.links
        assert p.last_active == "2026-09-03T15:30:00+00:00"
        assert p.sources["post_times"] == "2 public posts"

    @respx.mock
    async def test_bluesky(self):
        base = "https://public.api.bsky.app/xrpc"
        respx.get(f"{base}/app.bsky.actor.getProfile").mock(return_value=httpx.Response(200, json={
            "displayName": "Marisol", "description": "Cooking. https://marisol.kitchen",
            "avatar": "https://cdn.bsky.test/a.jpg", "createdAt": "2023-05-01T00:00:00Z"}))
        respx.get(f"{base}/app.bsky.feed.getAuthorFeed").mock(return_value=httpx.Response(200, json={
            "feed": [{"post": {"record": {"createdAt": "2026-10-01T12:00:00Z"}}},
                     {"post": {"record": {"createdAt": "2026-10-02T12:00:00Z"}}, "reason": {"$type": "repost"}}]}))
        respx.get(url__regex=r"https://bsky\.app/.*").mock(return_value=httpx.Response(200, text=""))
        async with httpx.AsyncClient() as client:
            p = await profile.fetch("bsky.app", "Bluesky", "marisol",
                                    "https://bsky.app/profile/marisol.bsky.social", client)
        assert p.display_name == "Marisol"
        assert p.links == ["https://marisol.kitchen"]
        assert p.post_times == ["2026-10-01T12:00:00+00:00"]  # reposts aren't their posts

    @respx.mock
    async def test_mastodon_location_field(self):
        respx.get("https://mastodon.social/api/v1/accounts/lookup").mock(return_value=httpx.Response(200, json={
            "id": "42", "display_name": "Marisol", "note": "<p>Recipes</p>", "avatar": "https://m.test/a.png",
            "fields": [{"name": "Location", "value": "Brooklyn"},
                       {"name": "Site", "value": '<a href="https://marisol.kitchen">marisol.kitchen</a>'}]}))
        respx.get("https://mastodon.social/api/v1/accounts/42/statuses").mock(
            return_value=httpx.Response(200, json=[{"created_at": "2026-10-01T09:00:00.000Z"}]))
        respx.get("https://mastodon.social/@marisol").mock(return_value=httpx.Response(200, text=""))
        async with httpx.AsyncClient() as client:
            p = await profile.fetch("mastodon.social", "Mastodon", "marisol",
                                    "https://mastodon.social/@marisol", client)
        assert p.location == "Brooklyn"
        assert "https://marisol.kitchen" in p.links
        assert p.bio == "Recipes"

    @respx.mock
    async def test_opengraph_for_everything_else(self):
        respx.get("https://www.instagram.com/marisol/").mock(
            return_value=httpx.Response(200, text=OG_PROFILE, headers={"content-type": "text/html"}))
        async with httpx.AsyncClient() as client:
            p = await profile.fetch("instagram.com", "Instagram", "marisol",
                                    "https://www.instagram.com/marisol/", client)
        assert p.display_name == "Marisol Reyes"
        assert p.avatar_url == "https://cdn.test/avatar.jpg"
        assert "https://linktr.ee/marisol" in p.links
        assert p.location is None  # nothing self-reported on this page

    @respx.mock
    async def test_tiktok_embedded_data(self):
        page = ('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
                + json.dumps({"__DEFAULT_SCOPE__": {"webapp.user-detail": {"userInfo": {"user": {
                    "nickname": "Marisol", "signature": "recipes", "avatarLarger": "https://t.test/a.jpg",
                    "bioLink": {"link": "marisol.kitchen"}}}}}}) + "</script>")
        respx.get("https://www.tiktok.com/@marisol").mock(
            return_value=httpx.Response(200, text=page, headers={"content-type": "text/html"}))
        async with httpx.AsyncClient() as client:
            p = await profile.fetch("tiktok.com", "TikTok", "marisol", "https://www.tiktok.com/@marisol", client)
        assert p.display_name == "Marisol"
        assert p.links == ["https://marisol.kitchen"]
        assert p.sources["display_name"] == "TikTok's page data"

    @respx.mock
    async def test_login_walls_are_respected_not_worked_around(self):
        respx.get("https://www.instagram.com/marisol/").mock(return_value=httpx.Response(
            302, headers={"location": "https://www.instagram.com/accounts/login/"}))
        respx.get("https://www.instagram.com/accounts/login/").mock(
            return_value=httpx.Response(200, text="<html>Log in</html>", headers={"content-type": "text/html"}))
        async with httpx.AsyncClient() as client:
            p = await profile.fetch("instagram.com", "Instagram", "marisol",
                                    "https://www.instagram.com/marisol/", client)
        assert p.hidden
        assert "signed-in" in p.note
        assert p.display_name is None


# -------------------------------------------------------------------- match --

def _picture(seed: int) -> bytes:
    img = Image.new("RGB", (200, 200), (240, 230, 210))
    d = ImageDraw.Draw(img)
    for i in range(6):
        x = (seed * 37 + i * 53) % 160
        y = (seed * 91 + i * 29) % 160
        d.ellipse([x, y, x + 40, y + 40], fill=((seed * 50 + i * 40) % 255, 80, 140))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def _resized_jpeg(png: bytes, size: int) -> bytes:
    img = Image.open(io.BytesIO(png)).convert("RGB").resize((size, size))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=60)
    return out.getvalue()


def _p(site, name=None, **kw):
    return Profile(site=site, name=name or site, username="marisol", url=f"https://{site}/marisol", **kw)


class TestPhotos:
    def test_the_same_photo_recompressed_still_matches(self):
        original = _picture(3)
        a = match.dhash(original)
        b = match.dhash(_resized_jpeg(original, 120))
        assert match.distance(a, b) <= match.PHOTO_MATCH_BITS

    def test_different_photos_do_not(self):
        assert match.distance(match.dhash(_picture(3)), match.dhash(_picture(11))) > match.PHOTO_MATCH_BITS

    def test_a_blank_picture_is_not_compared(self):
        out = io.BytesIO()
        Image.new("RGB", (50, 50), (255, 255, 255)).save(out, "PNG")
        assert match.dhash(out.getvalue()) is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_fingerprint_keeps_a_thumbnail_for_reports(self):
        respx.get("https://cdn.test/a.png").mock(return_value=httpx.Response(200, content=_picture(5)))
        p = _p("x.com", avatar_url="https://cdn.test/a.png")
        async with httpx.AsyncClient() as client:
            await match.fingerprint(p, client)
        assert p.photo_hash and p.photo_thumb.startswith("data:image/jpeg;base64,")


class TestScore:
    def test_a_direct_link_is_strong_evidence(self):
        ig = _p("instagram.com", "Instagram", links=["https://www.tiktok.com/@marisol"])
        tt = _p("tiktok.com", "TikTok")
        pair = match.score(ig, tt)
        assert pair.score == 40
        assert pair.reasons == ["Instagram links to their TikTok (+40)"]

    def test_shared_outside_link_and_name(self):
        a = _p("instagram.com", display_name="Marisol Reyes", links=["https://linktr.ee/marisol"])
        b = _p("tiktok.com", display_name="Marisol Reyes", links=["linktr.ee/marisol/"])
        pair = match.score(a, b)
        assert pair.score == 40 and pair.band == "possibly"
        assert any("linktr.ee/marisol" in r for r in pair.reasons)

    def test_a_bare_platform_link_proves_nothing(self):
        a = _p("instagram.com", links=["https://linktr.ee"])
        b = _p("tiktok.com", links=["https://linktr.ee/"])
        assert match.score(a, b).score == 0

    def test_a_display_name_that_is_just_the_handle_proves_nothing(self):
        a = _p("instagram.com", display_name="marisol")
        b = _p("tiktok.com", display_name="Marisol")
        assert match.score(a, b).score == 0

    def test_bios_locations_and_photos(self):
        a = _p("github.com", bio="Weeknight recipes, braising and sourdough experiments",
               location="Brooklyn, NY", photo_hash="f0f0f0f0f0f0f0f0")
        b = _p("bsky.app", bio="sourdough experiments + weeknight recipes. braising forever",
               location="brooklyn", photo_hash="f0f0f0f0f0f0f0f1")
        pair = match.score(a, b)
        assert pair.score == 40  # photo 25 + bio 10 + location 5
        assert any("Profile photos match" in r for r in pair.reasons)

    def test_different_locations_are_noted_not_penalised(self):
        pair = match.score(_p("a.test", location="Lisbon"), _p("b.test", location="Toronto"))
        assert pair.score == 0 and "Locations differ" in pair.notes[0]


class TestAssess:
    def test_groups_the_same_person_and_flags_the_stranger(self):
        ig = _p("instagram.com", "Instagram", display_name="Marisol Reyes",
                links=["https://www.tiktok.com/@marisol", "https://marisol.kitchen"])
        tt = _p("tiktok.com", "TikTok", display_name="Marisol Reyes", links=["https://marisol.kitchen"])
        stranger = _p("pinterest.com", "Pinterest", display_name="M. Smith", bio="cars")
        result = match.assess([ig, tt, stranger])
        assert result["main"] == ["tiktok.com", "instagram.com"]
        assert result["profiles"]["tiktok.com"]["band"] == "very_likely"
        assert result["profiles"]["pinterest.com"]["band"] == "no_evidence"

    def test_hidden_profiles_are_left_out(self):
        result = match.assess([_p("a.test", hidden=True), _p("b.test")])
        assert set(result["profiles"]) == {"b.test"}


# ----------------------------------------------------------------- timezone --

def _posts(offset_hours: int, n: int = 60):
    """n posts spread over a person's waking hours (08:00-23:00 local)."""
    tz = timezone(timedelta(hours=offset_hours))
    start = datetime(2026, 9, 1, tzinfo=tz)
    awake = list(range(8, 24))
    return [(start + timedelta(days=i % 20, hours=awake[i % len(awake)])).isoformat() for i in range(n)]


class TestTimezone:
    @pytest.mark.parametrize("offset", [-5, 0, 1, 9])
    def test_the_quiet_hours_give_the_offset_away(self, offset):
        h = hint(_posts(offset), ["GitHub"])
        assert h.low <= offset <= h.high
        assert h.strength == "clear"
        assert "±2 hours" in h.summary

    def test_too_few_posts_means_no_guess(self):
        h = hint(_posts(-5, n=10))
        assert h.offset is None
        assert "Not enough public posts" in h.summary

    def test_round_the_clock_posting_is_unclear(self):
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        h = hint([(start + timedelta(hours=i)).isoformat() for i in range(96)])
        assert h.strength == "unclear"
        assert "no clear daily rhythm" in h.summary
