import pytest
import httpx
import respx

from oembed import fetch_oembed, fetch_many


@pytest.mark.asyncio
async def test_fetch_oembed_ok():
    url = "https://www.tiktok.com/oembed?url=https://www.tiktok.com/@user/video/12345"
    expected = {
        "title": "Test video",
        "author_unique_id": "creator",
        "author_name": "Creator Name",
        "thumbnail_url": "https://example.com/thumb.jpg",
    }

    async with respx.mock(assert_all_mocked=False) as rsps:
        rsps.get(url).respond(200, json=expected)
        async with httpx.AsyncClient() as client:
            res = await fetch_oembed("12345", client)
            assert res["status"] == "ok"
            assert res["data"]["title"] == "Test video"
            assert res["video_id"] == "12345"


@pytest.mark.asyncio
async def test_fetch_many_mixed():
    # ensure fetch_many returns same-length list and contains statuses
    url1 = "https://www.tiktok.com/oembed?url=https://www.tiktok.com/@user/video/1"
    url2 = "https://www.tiktok.com/oembed?url=https://www.tiktok.com/@user/video/2"

    async with respx.mock(assert_all_mocked=False) as rsps:
        rsps.get(url1).respond(200, json={"title": "A"})
        rsps.get(url2).respond(404, json={})
        results = await fetch_many(["1", "2"], concurrency=2)
        assert len(results) == 2
        assert any(r.get("status") == "ok" for r in results)
        assert any(r.get("status") == "failed" for r in results)
