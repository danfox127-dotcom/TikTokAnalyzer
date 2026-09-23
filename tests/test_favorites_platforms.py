"""The platform registry: one descriptor per platform, and the rules it must keep.

The bug this module exists to prevent: TikTok's identity rule changed in one
function while the link builder kept its own TikTok branch, and every link in a
real library 404'd. Both halves now live in one descriptor, and
:data:`WORKED_EXAMPLES` asserts they still agree.
"""

import pytest

from favorites import platforms, transcript
from favorites.platforms import PLATFORMS, Platform
from favorites.resolve import (
    browsable_url, canonical_form, detect_platform, platform_label,
    strip_tracking, _handle_from_url,
)

# (shared url, platform, canonical url, external id, browsable url)
#
# One row per platform that derives an identity from a URL. The browsable
# column is the link a person clicks; where it differs from the canonical
# column, that difference is the whole reason the platform needs a `link`.
WORKED_EXAMPLES = [
    ("https://www.tiktok.com/@citydesk/video/7123456789?_t=8abc&_r=1",
     "tiktok", "https://www.tiktok.com/video/7123456789", "7123456789",
     "https://www.tiktok.com/@citydesk/video/7123456789"),
    ("https://www.tiktok.com/@citydesk/photo/7123456789",
     "tiktok", "https://www.tiktok.com/video/7123456789", "7123456789",
     "https://www.tiktok.com/@citydesk/video/7123456789"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30",
     "youtube", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ",
     "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ",
     "youtube", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ",
     "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("https://www.instagram.com/reels/ABC-123/?igshid=9",
     "instagram", "https://www.instagram.com/reel/ABC-123", "ABC-123",
     "https://www.instagram.com/reel/ABC-123"),
    ("https://twitter.com/citydesk/status/9988776655?s=20",
     "x", "https://x.com/citydesk/status/9988776655", "9988776655",
     "https://x.com/citydesk/status/9988776655"),
]


@pytest.mark.parametrize("shared,platform,canonical,external_id,browsable", WORKED_EXAMPLES)
def test_identity_and_link_agree(shared, platform, canonical, external_id, browsable):
    assert detect_platform(shared) == platform
    assert canonical_form(shared, platform) == (canonical, external_id)

    item = {
        "platform": platform, "canonical_url": canonical, "shared_url": shared,
        "external_id": external_id,
        "creator_handle": _handle_from_url(shared, platform),
    }
    assert browsable_url(item) == browsable


def test_a_platform_that_rebuilds_links_falls_back_when_it_cannot():
    """An unresolved item has no handle, so the original share link stands."""
    item = {
        "platform": "tiktok",
        "canonical_url": "https://www.tiktok.com/video/7123456789",
        "shared_url": "https://vm.tiktok.com/ZM1abc/",
        "external_id": "7123456789", "creator_handle": None,
    }
    assert browsable_url(item) == "https://vm.tiktok.com/ZM1abc/"


# (url, platform, handle) -- the display handle recovered from a URL alone,
# before any oEmbed response gets a say. Covers the generic "/@name" rule and
# every platform that needs its own.
HANDLE_EXAMPLES = [
    ("https://www.tiktok.com/@citydesk/video/7123", "tiktok", "@citydesk"),
    ("https://www.tiktok.com/@city.desk-1/video/7123", "tiktok", "@city.desk-1"),
    ("https://www.instagram.com/reel/ABC123", "instagram", None),
    ("https://x.com/citydesk/status/9988776655", "x", "@citydesk"),
    ("https://twitter.com/citydesk/status/9988776655", "x", "@citydesk"),
    ("https://x.com/citydesk", "x", None),
    ("https://www.reddit.com/r/urbanplanning/comments/abc/title/", "reddit", "r/urbanplanning"),
    ("https://www.reddit.com/user/someone", "reddit", None),
    ("https://some-blog.example/posts/1", "web", None),
]


@pytest.mark.parametrize("url,platform,handle", HANDLE_EXAMPLES)
def test_handles_are_recovered_from_the_url(url, platform, handle):
    assert _handle_from_url(url, platform) == handle


def test_transcripts_are_offered_exactly_where_the_registry_says():
    declared = {p.name for p in PLATFORMS if p.transcripts}
    assert declared == transcript.SUPPORTED
    # Downloading media to run speech recognition is what the terms forbid, so
    # a platform without a published caption track must not claim support.
    assert declared == {"youtube"}
    assert transcript.fetch("tiktok", "7123456789") is None


# --- registry integrity -----------------------------------------------------

def test_every_platform_is_uniquely_named_and_labelled():
    names = [p.name for p in PLATFORMS]
    labels = [p.label for p in PLATFORMS]
    assert len(names) == len(set(names)), "two descriptors share a name"
    assert len(labels) == len(set(labels)), "two descriptors share a label"
    assert all(p.name and p.name == p.name.lower() for p in PLATFORMS)
    assert all(p.label for p in PLATFORMS)


def test_no_host_is_claimed_by_two_platforms():
    seen: dict[str, str] = {}
    for p in PLATFORMS:
        for host in p.hosts:
            assert host not in seen, f"{host} claimed by {seen.get(host)} and {p.name}"
            seen[host] = p.name


def test_hosts_and_shorteners_are_bare_lowercase_hostnames():
    for p in PLATFORMS:
        for host in (*p.hosts, *p.shorteners):
            assert host == host.lower().strip()
            assert "/" not in host and ":" not in host, f"{host} is not a hostname"


def test_every_platform_resolves_from_each_of_its_own_hosts():
    for p in PLATFORMS:
        for host in p.hosts:
            assert detect_platform(f"https://{host}/x") == p.name
            assert detect_platform(f"https://www.{host}/x") == p.name
            assert detect_platform(f"https://sub.{host}/x") == p.name


def test_a_platform_that_normalises_its_host_does_so_from_all_of_them():
    for p in PLATFORMS:
        if not p.host_canonical:
            continue
        for host in p.hosts:
            stripped = strip_tracking(f"https://{host}/video/7123")
            assert stripped.startswith(f"https://{p.host_canonical}/")


def test_platform_owned_shorteners_are_followed():
    for p in PLATFORMS:
        for host in p.shorteners:
            assert host in platforms.SHORTENERS


def test_oembed_endpoints_are_absolute_https_urls():
    for p in PLATFORMS:
        if p.oembed:
            assert p.oembed.startswith("https://"), p.name


def test_lookup_of_something_unregistered_is_the_generic_web_platform():
    assert platforms.for_host("some-blog.example").name == "web"
    assert platforms.for_host("").name == "web"
    assert platforms.get("peertube").name == "web"


def test_an_unregistered_platform_name_still_gets_a_readable_label():
    """A row stored before a platform was renamed should not read as "Web"."""
    assert platform_label("peertube") == "Peertube"
    assert platform_label("tiktok") == "TikTok"


# --- the point of the exercise ----------------------------------------------

def test_adding_a_platform_takes_only_a_descriptor(monkeypatch):
    """No branch anywhere else: hosts, label, identity, link, handle, oEmbed."""
    import re

    def identity(parts):
        m = re.search(r"/c/(\w+)", parts.path)
        return (f"https://vidsite.example/c/{m.group(1)}", m.group(1)) if m else None

    fake = Platform(
        name="vidsite", label="VidSite", hosts=("vidsite.example",),
        shorteners=("vid.example",), oembed="https://vidsite.example/oembed",
        host_canonical="vidsite.example", identity=identity,
        link=lambda item: f"https://vidsite.example/u/{item['creator_handle'].lstrip('@')}"
                          f"/c/{item['external_id']}",
        handle=lambda path: "@" + path.split("/")[2] if "/u/" in path else None,
    )
    monkeypatch.setattr(platforms, "PLATFORMS", (*PLATFORMS, fake))
    monkeypatch.setattr(platforms, "BY_NAME", {**platforms.BY_NAME, "vidsite": fake})
    monkeypatch.setattr(
        platforms, "HOST_TABLE", (*platforms.HOST_TABLE, ("vidsite.example", fake)))

    url = "https://vidsite.example/u/citydesk/c/42?utm_source=share"
    assert detect_platform(url) == "vidsite"
    assert platform_label("vidsite") == "VidSite"
    assert canonical_form(url, "vidsite") == ("https://vidsite.example/c/42", "42")
    assert _handle_from_url(url, "vidsite") == "@citydesk"
    assert platforms.get("vidsite").oembed == "https://vidsite.example/oembed"
    assert browsable_url({
        "platform": "vidsite", "canonical_url": "https://vidsite.example/c/42",
        "shared_url": url, "external_id": "42", "creator_handle": "@citydesk",
    }) == "https://vidsite.example/u/citydesk/c/42"
