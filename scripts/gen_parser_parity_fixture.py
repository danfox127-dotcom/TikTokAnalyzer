"""
Golden parity fixture for the WP-1.1 parser port (parsers/tiktok.py).

Two layers:
  - parse_cases: full _parse_tiktok_data on hand-built raw exports (primary key
    schema, the alternate/fallback schema, and empty) — exercises every _extract_*
    and its fallback chain end-to-end.
  - session_cases: _detect_sessions directly (passive sessions, autoplay <2s,
    30-min gap splits, unparseable dates, engagement rescue).

Parity notes: watch_history_* come out DATE-SORTED (stable) with unparseable
entries appended; avg_session_length uses round(_,1); _safe_text is identity for
normal strings (lone-surrogate handling is not exercised).

Run from repo root:  python3 scripts/gen_parser_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.tiktok import _parse_tiktok_data, _detect_sessions  # noqa: E402


def primary_export():
    return {
        "Profile And Settings": {
            "Profile Info": {"ProfileMap": {
                "userName": "danfox", "displayName": "Dan", "birthDate": "1990-01-01",
                "accountRegion": "US", "bioDescription": "hello bio",
                "followerCount": 12, "followingCount": 34, "inferredGender": "male",
            }},
            "Settings": {"SettingsMap": {"Interests": "gaming | cooking |  travel "}},
            "Following": {"Following": [{"Date": "2024-01-01 10:00:00", "UserName": "creator_a"}]},
            "Follower": {"FansList": [{"Date": "2024-01-02 10:00:00", "UserName": "fan_b"}]},
            "Block List": {"BlockList": [{"Date": "2024-01-03 10:00:00", "UserName": "blocked_c"}]},
        },
        "Your Activity": {
            "Watch History": {"VideoList": [
                {"Date": "2024-03-01 10:00:00", "Link": "https://www.tiktok.com/@a/video/1"},
                {"Date": "2024-03-01 10:01:00", "Link": "https://www.tiktok.com/@a/video/2"},
            ]},
            "Searches": {"SearchList": [{"Date": "2024-03-01 09:00:00", "SearchTerm": "sourdough"}]},
            "Share History": {"ShareHistoryList": [
                {"Date": "2024-03-01 09:30:00", "Link": "https://www.tiktok.com/@a/video/9", "Method": "whatsapp"},
            ]},
            "Login History": {"LoginHistoryList": [
                {"Date": "2024-03-01 08:00:00", "IP": "1.2.3.4", "DeviceModel": "iPhone",
                 "DeviceSystem": "iOS 17", "NetworkType": "wifi", "Carrier": "ATT"},
                {"Date": "2024-03-02 08:00:00", "IP": "1.2.3.4", "DeviceModel": "iPad",
                 "DeviceSystem": "iPadOS", "NetworkType": "5g", "Carrier": "ATT"},
            ]},
            "Off TikTok Activity": {"OffTikTokActivityDataList": [{"a": 1}, {"b": 2}]},
            "Ad Interests": {"AdInterestCategories": ["Beauty", "Gaming", ",", "  "]},
        },
        "Likes and Favorites": {
            "Like List": {"ItemFavoriteList": [{"Date": "2024-03-01 10:00:30", "Link": "https://www.tiktok.com/@a/video/1"}]},
            "Favorite Videos": {"FavoriteVideoList": [{"Date": "2024-02-01 10:00:00", "Link": "https://www.tiktok.com/@x/video/7"}]},
            "Favorite Collection": {"FavoriteCollectionList": [{"FavoriteCollection": "Recipes"}]},
        },
        "Comment": {"Comments": {"CommentsList": [
            {"Date": "2024-03-01 10:00:20", "Comment": "great video", "Url": "https://www.tiktok.com/@a/video/1"},
        ]}},
        "TikTok Shop": {
            "Order": {"OrderList": [
                {"Date": "2024-02-15", "TotalPrice": "19.99", "Products": [{"ProductName": "Blender"}]},
            ]},
            "Product Browsing History": {"ProductBrowsingHistories": [
                {"browsing_date": "2024-02-10", "shop_name": "KitchenCo", "product_name": "Whisk"},
            ]},
        },
        "Direct Message": {"Direct Messages": {"ChatHistory": {
            "chat_a": [{"m": 1}, {"m": 2}],
            "chat_b": {"Messages": [{"m": 3}]},
        }}},
    }


def fallback_export():
    # Alternate key names to hit the second/third fallback branches.
    return {
        "Profile And Settings": {"ProfileMap": {"userName": "fb", "nickName": "FB Nick", "gender": "female"}},
        "Activity": {
            "Video Browsing History": {"VideoList": [
                {"date": "2024-04-01 12:00:00", "VideoLink": "https://www.tiktok.com/@b/video/5"},
            ]},
            "Searches": {"SearchList": [{"date": "2024-04-01 11:00:00", "Content": "lofi beats"}]},
            "Login History": {"LoginHistoryList": [{"date": "2024-04-01 07:00:00", "ip": "9.9.9.9", "deviceModel": "Pixel"}]},
        },
        "Ad Interests": {"AdInterestCategories": "Sports, Travel, Food"},
        "Comments": {"Comments": {"CommentsList": [{"date": "2024-04-01 12:00:30", "comment": "nice"}]}},
        "TikTok Shop": {"Order History": {"OrderHistories": {
            "o1": {"order_date": "2024-04-02", "total_price": "5.00", "products": "Single Product String"},
        }}},
    }


def parse_cases():
    return [
        ("primary_schema", primary_export()),
        ("fallback_schema", fallback_export()),
        ("empty", {}),
    ]


def _vid(date, link="https://www.tiktok.com/@a/video/1"):
    return {"date": date, "link": link}


def session_cases():
    D = "2024-03-01"
    return [
        ("passive_5plus_zero_engagement", [
            _vid(f"{D} 02:00:00"), _vid(f"{D} 02:03:00"), _vid(f"{D} 02:06:00"),
            _vid(f"{D} 02:09:00"), _vid(f"{D} 02:12:00"),
        ], [], [], []),
        ("autoplay_under_2s", [
            _vid(f"{D} 10:00:00"), _vid(f"{D} 10:00:01"), _vid(f"{D} 10:01:00"),
        ], [{"date": f"{D} 10:00:30"}], [], []),
        ("session_split_gap", [
            _vid(f"{D} 10:00:00"), _vid(f"{D} 10:05:00"),
            _vid(f"{D} 14:00:00"), _vid(f"{D} 14:05:00"),
        ], [{"date": f"{D} 10:02:00"}], [], []),
        ("unparseable_dates_kept", [
            _vid("not-a-date"), _vid(f"{D} 10:00:00"), _vid(f"{D} 10:03:00"),
        ], [], [], []),
        ("engagement_rescues_session", [
            _vid(f"{D} 03:00:00"), _vid(f"{D} 03:03:00"), _vid(f"{D} 03:06:00"),
            _vid(f"{D} 03:09:00"), _vid(f"{D} 03:12:00"),
        ], [], [{"date": f"{D} 03:05:00"}], []),
        ("empty", [], [], [], []),
    ]


def main():
    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 parser port. Regenerate only "
                    "on an intentional Python change: python3 scripts/gen_parser_parity_fixture.py",
        "parse_cases": [
            {"name": n, "input": {"data": raw}, "expected": _parse_tiktok_data(raw)}
            for n, raw in parse_cases()
        ],
        "session_cases": [
            {"name": n, "input": {"browsing_history": bh, "likes": lk, "comments": cm, "shares": sh},
             "expected": _detect_sessions(bh, lk, cm, sh)}
            for n, bh, lk, cm, sh in session_cases()
        ],
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "parser_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    n = len(payload["parse_cases"]) + len(payload["session_cases"])
    print(f"wrote {n} cases → {out_path}")


if __name__ == "__main__":
    main()
