"""
Golden parity fixture for the WP-1.1 orchestrator (build_ghost_profile).

End-to-end: feed a hand-built `parsed` dict, capture the FULL payload from the
frozen oracle, compare against the TS orchestrator.

The parsed fixture is engineered so creator counts are DISTINCT (linger @a=4,
@b=3, @c=2, @g=1; skip @d=2, @e=1) → vibe_cluster/graveyard ordering (and thus
top_creator_handles, inferred_creator_handles) is fixed by count, not by Python's
set-iteration order. The two genuinely-unordered fields — per-creator
sample_titles and enrichment_targets.following_usernames — are sorted here (and
on the TS side) before comparison.

Run from repo root:  PYTHONHASHSEED=0 python3 scripts/gen_orchestrator_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.ghost_profile import build_ghost_profile  # noqa: E402


def _v(dt, handle, vid, title=None):
    e = {"date": dt, "link": f"https://www.tiktok.com/@{handle}/video/{vid}"}
    if title is not None:
        e["title"] = title
    return e


def watch_history():
    wh = []
    # Block L (lingers, 60s apart): @a x4, @b x3, @c x2
    labels = [("a", 4), ("b", 3), ("c", 3)]
    t, vid = 0, 1
    for handle, n in labels:
        for _ in range(n):
            mm, ss = divmod(t, 60)
            wh.append(_v(f"2024-01-05 10:{mm:02d}:{ss:02d}", handle, vid, f"{handle} title {vid}"))
            t += 60
            vid += 1
    # Block G (graveyard skips, 1s apart): @d x2, @e x1
    wh += [
        _v("2024-01-05 11:00:00", "d", 20), _v("2024-01-05 11:00:01", "d", 21),
        _v("2024-01-05 11:00:02", "e", 22), _v("2024-01-05 11:00:03", "e", 23),
    ]
    # Block S (sandbox, 5s apart): @f re-tested
    wh += [
        _v("2024-01-05 12:00:00", "f", 30), _v("2024-01-05 12:00:05", "f", 31),
        _v("2024-01-05 12:00:10", "f", 32),
    ]
    # Night block (02:00): @g x1 night linger
    wh += [_v("2024-01-06 02:00:00", "g", 40), _v("2024-01-06 02:01:00", "g", 41)]
    return wh


def rich_parsed():
    return {
        "watch_history_active": watch_history(),
        "following": [{"username": "a"}, {"username": "somebodyelse"}],
        "followers": [{"username": "fan1"}, {"username": "fan2"}, {"username": "fan3"}],
        "likes": [
            {"date": "2024-01-05 10:00:30", "link": "https://www.tiktok.com/@a/video/1"},
            {"date": "2024-01-05 10:30:00", "link": "https://www.tiktok.com/@b/video/4"},
        ],
        "comments": [
            {"date": "2024-01-05 10:15:00", "comment": "love this baking content 🔥"},
            {"date": "2024-01-06 09:00:00", "comment": "the lakers are unstoppable"},
        ],
        "shares": [
            {"date": "2024-01-05 09:00:00", "link": "https://www.tiktok.com/@a/video/1", "method": "whatsapp"},
            {"date": "2024-01-05 09:05:00", "link": "https://www.tiktok.com/@b/video/4", "method": "copy_link"},
        ],
        "searches": [
            {"term": "sourdough starter", "date": "2024-01-04 09:00:00"},
            {"term": "crypto crash", "date": "2024-01-03 22:00:00"},
            {"term": "gaming setup", "date": "2024-01-02 14:00:00"},
        ],
        "ad_interests": ["Beauty", "Gaming"],
        "settings_interests": ["cooking", "travel"],
        "login_history": [
            {"date": "2024-01-01 08:00:00", "ip": "1.2.3.4", "device_model": "iPhone",
             "device_system": "iOS", "network_type": "wifi", "carrier": "ATT"},
            {"date": "2024-01-02 08:00:00", "ip": "5.6.7.8", "device_model": "iPad",
             "device_system": "iPadOS", "network_type": "5g", "carrier": "Verizon"},
        ],
        "login_history_stats": {"unique_ips": 2, "unique_devices": ["iPad", "iPhone"],
                                "ip_locations": ["1.2.3.4", "5.6.7.8"]},
        "off_tiktok_activity": [{"x": 1}, {"y": 2}, {"z": 3}],
        "shop_orders": [{"date": "2024-01-01", "total_price": "19.99", "products": ["Blender", "Whisk"]}],
        "product_browsing": [{"date": "2024-01-02", "shop": "KitchenCo", "product": "Spatula"}],
    }


def _normalize(payload):
    """Sort the genuinely-unordered fields so the fixture is canonical and the
    comparison is order-insensitive where Python is non-deterministic."""
    ce = payload.get("creator_entities", {})
    for key in ("vibe_cluster", "graveyard"):
        for entry in ce.get(key, []):
            if "sample_titles" in entry:
                entry["sample_titles"] = sorted(entry["sample_titles"])
    et = payload.get("enrichment_targets", {})
    if "following_usernames" in et:
        et["following_usernames"] = sorted(et["following_usernames"])
    # stopwatch_metrics._*_links come from list(set(...)) → arbitrary order
    sm = payload.get("stopwatch_metrics", {})
    for k in ("_graveyard_links", "_sandbox_links", "_linger_links", "_deep_dive_links"):
        if k in sm:
            sm[k] = sorted(sm[k])
    return payload


def main():
    cases = [
        ("rich", rich_parsed()),
        ("empty", {}),
    ]
    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 orchestrator. Regenerate with "
                    "PYTHONHASHSEED=0 python3 scripts/gen_orchestrator_parity_fixture.py",
        "cases": [
            {"name": n, "input": {"parsed": p}, "expected": _normalize(build_ghost_profile(p))}
            for n, p in cases
        ],
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "orchestrator_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(payload['cases'])} cases → {out_path}")


if __name__ == "__main__":
    main()
