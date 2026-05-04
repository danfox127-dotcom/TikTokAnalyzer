"""
Async IP geolocation via api.iplocation.net.
In-process cache; 2s timeout; graceful fallback on any error.
"""
from __future__ import annotations

import httpx

_CACHE: dict[str, dict] = {}
_TIMEOUT = 2.0
_FALLBACK = {"city": "Unknown", "country_name": "Unknown"}


async def geolocate_ip(ip: str) -> dict:
    """
    Return {"city": str, "country_name": str} for the given IP.
    Using ip-api.com (JSON) for better city-level precision.
    """
    if not ip or ip in ("127.0.0.1", "localhost"):
        return _FALLBACK.copy()
    if ip in _CACHE:
        return _CACHE[ip]
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(f"http://ip-api.com/json/{ip}")
            r.raise_for_status()
            data = r.json()
            if data.get("status") == "success":
                result = {
                    "city": data.get("city") or "Unknown",
                    "country_name": data.get("country") or "Unknown",
                }
                _CACHE[ip] = result
            else:
                result = _FALLBACK.copy()
    except Exception:
        result = _FALLBACK.copy()
    return result


async def enrich_logins_with_geo(logins: list[dict]) -> list[dict]:
    """
    Enrich each login entry that has an "ip" key with "city" and "country_name".
    Deduplicates IPs so each unique IP is fetched at most once.
    Returns a new list; originals are not mutated.
    """
    unique_ips = {login["ip"] for login in logins if login.get("ip")}
    geo_map: dict[str, dict] = {}
    for ip in unique_ips:
        geo_map[ip] = await geolocate_ip(ip)

    enriched = []
    for login in logins:
        ip = login.get("ip", "")
        geo = geo_map.get(ip, _FALLBACK)
        enriched.append({**login, "city": geo["city"], "country_name": geo["country_name"]})
    return enriched
