"""
Report generator for SYS.TEARDOWN.
Combines parsed TikTok and Instagram data into a single JSON report
consumed by the dashboard.
"""
import json
from datetime import datetime


def _trim_tiktok_for_report(data: dict) -> dict:
    """
    Prepare TikTok data for the report.
    Exclude full browsing_history, full likes, and full comments (too large).
    Include behavioral stats, heatmap, trends, and sampled links.
    """
    ba = data.get("behavioral_analysis", {})

    # Limit linger/skip links to 100 most recent for potential creator resolution
    linger_links = ba.get("top_linger_links", [])[-100:]
    skip_links = ba.get("top_skip_links", [])[-100:]

    search_terms = [s.get("term", "") for s in data.get("searches", []) if s.get("term")]

    return {
        "platform": "tiktok",
        "profile": data.get("profile", {}),
        "settings_interests": data.get("settings_interests", []),
        "ad_interests": data.get("ad_interests", []),
        "behavioral_analysis": {
            "total_videos": ba.get("total_videos", 0),
            "valid_sessions": ba.get("valid_sessions", 0),
            "skip_count": ba.get("skip_count", 0),
            "casual_count": ba.get("casual_count", 0),
            "linger_count": ba.get("linger_count", 0),
            "skip_rate": ba.get("skip_rate", 0),
            "linger_rate": ba.get("linger_rate", 0),
            "night_shift_ratio": ba.get("night_shift_ratio", 0),
            "hourly_heatmap": ba.get("hourly_heatmap", {}),
            "monthly_skip_rates": ba.get("monthly_skip_rates", {}),
            "top_linger_links": linger_links,
            "top_skip_links": skip_links,
        },
        "favorite_collections": data.get("favorite_collections", []),
        "search_terms": search_terms,
        "likes_count": len(data.get("likes", [])),
        "favorites_count": len(data.get("favorites", [])),
        "comments_count": len(data.get("comments", [])),
        "shares_count": len(data.get("shares", [])),
        "following_count": len(data.get("following", [])),
        "followers_count": len(data.get("followers", [])),
        "blocked_count": len(data.get("blocked_users", [])),
        "login_history_stats": data.get("login_history_stats", {}),
        "off_tiktok_activity": data.get("off_tiktok_activity", []),
        "shop_orders": data.get("shop_orders", []),
        "dm_count": data.get("dm_count", 0),
    }


def _compute_cross_platform(tiktok_data: dict | None, instagram_data: dict | None) -> dict:
    """Compute cross-platform comparison metrics."""
    cross = {
        "profile_comparison": {},
        "interest_overlap": [],
        "combined_device_count": 0,
        "combined_advertiser_reach": 0,
    }

    tk_username = ""
    ig_username = ""
    shared_email = False
    shared_phone = False

    if tiktok_data:
        tk_profile = tiktok_data.get("profile", {})
        tk_username = tk_profile.get("username", "")

    if instagram_data:
        ig_profile = instagram_data.get("profile", {})
        ig_username = ig_profile.get("username", "")

    if tiktok_data and instagram_data:
        ig_profile = instagram_data.get("profile", {})
        ig_email = ig_profile.get("email", "")
        ig_phone = ig_profile.get("phone", "")
        shared_email = bool(ig_email)
        shared_phone = bool(ig_phone)

    cross["profile_comparison"] = {
        "tiktok_username": tk_username,
        "instagram_username": ig_username,
        "shared_email": shared_email,
        "shared_phone": shared_phone,
    }

    # Interest overlap
    tk_interests = set()
    ig_interests = set()
    if tiktok_data:
        for interest in tiktok_data.get("settings_interests", []):
            tk_interests.add(interest.lower().strip())
        for interest in tiktok_data.get("ad_interests", []):
            tk_interests.add(interest.lower().strip())
    if instagram_data:
        for topic in instagram_data.get("recommended_topics", []):
            ig_interests.add(topic.lower().strip())
        for cat in instagram_data.get("ad_categories", []):
            ig_interests.add(cat.lower().strip())

    overlap = sorted(tk_interests & ig_interests)
    cross["interest_overlap"] = overlap

    # Device count
    device_count = 0
    if tiktok_data:
        stats = tiktok_data.get("login_history_stats", {})
        device_count += len(stats.get("unique_devices", []))
    if instagram_data:
        device_count += len(instagram_data.get("devices", []))
    cross["combined_device_count"] = device_count

    # Advertiser reach
    if instagram_data:
        cross["combined_advertiser_reach"] = instagram_data.get("advertiser_count", 0)

    return cross


def generate_report(
    tiktok_data: dict = None,
    instagram_data: dict = None,
    output_path: str = "report.json",
) -> str:
    """
    Generate a combined JSON report from parsed platform data.

    Args:
        tiktok_data: Parsed TikTok data dict (from parse_tiktok_export).
        instagram_data: Parsed Instagram data dict (from parse_instagram_export).
        output_path: Path to write the report JSON file.

    Returns:
        The output file path.
    """
    report = {
        "generated_at": datetime.now().isoformat(),
        "platforms": {},
        "cross_platform": {},
    }

    if tiktok_data:
        report["platforms"]["tiktok"] = _trim_tiktok_for_report(tiktok_data)

    if instagram_data:
        report["platforms"]["instagram"] = instagram_data

    report["cross_platform"] = _compute_cross_platform(tiktok_data, instagram_data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    return output_path
