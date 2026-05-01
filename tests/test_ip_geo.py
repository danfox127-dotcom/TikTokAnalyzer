import pytest
import httpx
import respx

# Reset the module-level cache between tests
import importlib


@pytest.fixture(autouse=True)
def clear_cache():
    import utils.ip_geo as m
    m._CACHE.clear()
    yield
    m._CACHE.clear()


@pytest.mark.asyncio
async def test_geolocate_ip_success():
    from utils.ip_geo import geolocate_ip
    with respx.mock:
        respx.get("https://api.iplocation.net/?ip=1.2.3.4").mock(
            return_value=httpx.Response(200, json={"city": "Paris", "country_name": "France"})
        )
        result = await geolocate_ip("1.2.3.4")
    assert result == {"city": "Paris", "country_name": "France"}


@pytest.mark.asyncio
async def test_geolocate_ip_cache_hit():
    from utils.ip_geo import geolocate_ip, _CACHE
    _CACHE["5.6.7.8"] = {"city": "Berlin", "country_name": "Germany"}
    # No HTTP mock — if it tries to call the API it will raise
    result = await geolocate_ip("5.6.7.8")
    assert result == {"city": "Berlin", "country_name": "Germany"}


@pytest.mark.asyncio
async def test_geolocate_ip_fallback_on_error():
    from utils.ip_geo import geolocate_ip
    with respx.mock:
        respx.get("https://api.iplocation.net/?ip=9.9.9.9").mock(
            side_effect=httpx.ConnectTimeout("timeout")
        )
        result = await geolocate_ip("9.9.9.9")
    assert result == {"city": "Unknown", "country_name": "Unknown"}


@pytest.mark.asyncio
async def test_geolocate_ip_empty_string():
    from utils.ip_geo import geolocate_ip
    # Should return fallback without hitting network
    result = await geolocate_ip("")
    assert result == {"city": "Unknown", "country_name": "Unknown"}


@pytest.mark.asyncio
async def test_enrich_logins_with_geo():
    from utils.ip_geo import enrich_logins_with_geo
    logins = [
        {"date": "2024-01-01", "ip": "1.2.3.4", "device": "iPhone"},
        {"date": "2024-01-02", "ip": "1.2.3.4", "device": "iPhone"},  # same IP, should deduplicate fetch
        {"date": "2024-01-03", "ip": "5.6.7.8", "device": "Android"},
    ]
    call_count = 0
    with respx.mock:
        def make_response(request):
            nonlocal call_count
            call_count += 1
            ip = str(request.url).split("ip=")[1]
            data = {
                "1.2.3.4": {"city": "Paris", "country_name": "France"},
                "5.6.7.8": {"city": "Berlin", "country_name": "Germany"},
            }
            return httpx.Response(200, json=data.get(ip, {"city": "Unknown", "country_name": "Unknown"}))
        respx.get(url__startswith="https://api.iplocation.net/").mock(side_effect=make_response)
        result = await enrich_logins_with_geo(logins)

    # 2 unique IPs → 2 HTTP calls
    assert call_count == 2
    assert result[0]["city"] == "Paris"
    assert result[1]["city"] == "Paris"   # same IP reused from cache
    assert result[2]["city"] == "Berlin"
    assert all("country_name" in r for r in result)
