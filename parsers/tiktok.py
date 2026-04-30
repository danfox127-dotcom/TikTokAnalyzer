"""
TikTok data export parser.
Parses the user_data_tiktok.json file into a structured analysis dict.
"""
import json
from datetime import datetime
from collections import defaultdict


def _parse_date(date_str: str) -> datetime | None:
    """Parse TikTok date strings. They use several formats."""
    if not date_str:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _compute_night_shift_ratio(history: list[dict]) -> float:
    """Night-shift ratio from raw history (23:00–04:00). Used on full history, not active."""
    night = total = 0
    for item in history:
        dt = _parse_date(item.get("date", ""))
        if dt:
            total += 1
            if 23 <= dt.hour or dt.hour < 4:
                night += 1
    return round(night / total * 100, 1) if total > 0 else 0.0


_SESSION_GAP_S = 1800   # 30 minutes → new session
_DM_METHODS = {
    "chat_head", "dm", "message", "whatsapp", "instagram",
    "line", "kakaotalk", "telegram",
}


def _detect_sessions(
    browsing_history: list[dict],
    likes: list[dict],
    comments: list[dict],
    shares: list[dict],
) -> dict:
    """
    Split browsing_history into sessions and flag passive videos.

    A video is passive if:
    - It follows the previous video by < 2 seconds (autoplay artifact), OR
    - It belongs to a session of 5+ videos with zero engagement actions.

    Returns watch_history_active (passive removed) and watch_history_full (original).
    Items with unparseable dates are included in both lists unconditionally (treated as active).
    active_video_count therefore includes unparseable items.
    """
    if not browsing_history:
        return {
            "watch_history_full": [],
            "watch_history_active": [],
            "passive_videos_removed": 0,
            "passive_sessions_detected": 0,
            "active_video_count": 0,
            "session_count": 0,
            "avg_session_length_videos": 0.0,
        }

    # Build engagement timestamp list (likes + comments + shares)
    engagement_times: list[datetime] = []
    for source in (likes, comments, shares):
        for item in source:
            dt = _parse_date(item.get("date", ""))
            if dt:
                engagement_times.append(dt)

    # Parse and index history; items without datetimes are kept as-is (active)
    parsed_entries: list[dict] = []
    unparseable: list[dict] = []
    for idx, item in enumerate(browsing_history):
        dt = _parse_date(item.get("date", ""))
        if dt:
            parsed_entries.append({"_dt": dt, "_orig": item, "_idx": idx})
        else:
            unparseable.append(item)

    parsed_entries.sort(key=lambda e: e["_dt"])

    # Split into sessions on gaps > 30 minutes
    sessions: list[list[dict]] = []
    if parsed_entries:
        current: list[dict] = [parsed_entries[0]]
        for i in range(1, len(parsed_entries)):
            gap = (parsed_entries[i]["_dt"] - parsed_entries[i - 1]["_dt"]).total_seconds()
            if gap > _SESSION_GAP_S:
                sessions.append(current)
                current = [parsed_entries[i]]
            else:
                current.append(parsed_entries[i])
        sessions.append(current)

    # Determine which entries are passive
    passive_indices: set[int] = set()
    passive_sessions = 0

    for session in sessions:
        s_start = session[0]["_dt"]
        s_end = session[-1]["_dt"]

        # Zero-engagement session with 5+ videos → whole session is passive
        has_engagement = any(s_start <= et <= s_end for et in engagement_times)
        if not has_engagement and len(session) >= 5:
            passive_sessions += 1
            for entry in session:
                passive_indices.add(entry["_idx"])

        # Autoplay artifacts: video follows previous by < 2 seconds
        for i in range(1, len(session)):
            delta = (session[i]["_dt"] - session[i - 1]["_dt"]).total_seconds()
            if delta < 2:
                passive_indices.add(session[i]["_idx"])

    watch_history_full = [e["_orig"] for e in parsed_entries] + unparseable
    watch_history_active = [
        e["_orig"] for e in parsed_entries if e["_idx"] not in passive_indices
    ] + unparseable

    session_lengths = [len(s) for s in sessions]
    avg_len = round(sum(session_lengths) / len(session_lengths), 1) if sessions else 0.0

    return {
        "watch_history_full": watch_history_full,
        "watch_history_active": watch_history_active,
        "passive_videos_removed": len(passive_indices),
        "passive_sessions_detected": passive_sessions,
        "active_video_count": len(watch_history_active),
        "session_count": len(sessions),
        "avg_session_length_videos": avg_len,
    }


def _safe_text(text: str) -> str:
    """
    Sanitize text, stripping lone surrogates that cause UnicodeEncodeError.
    TikTok exports sometimes embed broken emoji encoded as lone UTF-16
    surrogates (e.g. \\uD83D without a following \\uDC00). The utf-16
    surrogatepass roundtrip discards them cleanly.
    """
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    try:
        return text.encode("utf-16", "surrogatepass").decode("utf-16")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text.encode("utf-8", errors="replace").decode("utf-8")


def _dig(data: dict, *keys, default=None):
    """Safely traverse nested dict keys."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
        if current is None:
            return default
    return current


def _extract_profile(data: dict) -> dict:
    """Extract profile information from Profile And Settings."""
    profile_section = _dig(data, "Profile And Settings", "Profile Info", "ProfileMap", default={})
    if not profile_section:
        profile_section = _dig(data, "Profile And Settings", "ProfileMap", default={})
    return {
        "username": profile_section.get("userName", ""),
        "display_name": profile_section.get("displayName", profile_section.get("nickName", "")),
        "birth_date": profile_section.get("birthDate", ""),
        "account_region": profile_section.get("accountRegion", ""),
        "bio": _safe_text(profile_section.get("bioDescription", "")),
        "follower_count": profile_section.get("followerCount", 0),
        "following_count": profile_section.get("followingCount", 0),
        "inferred_gender": profile_section.get("inferredGender", profile_section.get("gender", "")),
    }


def _extract_settings_interests(data: dict) -> list[str]:
    """Extract declared interests from Settings, split on pipe delimiter."""
    settings = _dig(data, "Profile And Settings", "Settings", "SettingsMap", default={})
    if not settings:
        settings = _dig(data, "Profile And Settings", "SettingsMap", default={})
    interests_str = settings.get("Interests", "") or settings.get("InterestsLanguage", "")
    if not interests_str:
        return []
    return [i.strip() for i in interests_str.split("|") if i.strip()]


def _extract_ad_interests(data: dict) -> list[str]:
    """Extract ad interests from Ad Interests section."""
    ad_section = _dig(data, "Your Activity", "Ad Interests", "AdInterestCategories", default=None)
    if ad_section is None:
        ad_section = _dig(data, "Ad Interests", "AdInterestCategories", default=[])
    if isinstance(ad_section, str):
        items = [i.strip() for i in ad_section.split(",") if i.strip()]
        return items
    if isinstance(ad_section, list):
        return [_safe_text(item) for item in ad_section if item and str(item).strip() and str(item).strip() != ","]
    return []


def _extract_browsing_history(data: dict) -> list[dict]:
    """Extract and sort video browsing history."""
    video_list = _dig(data, "Your Activity", "Watch History", "VideoList", default=[])
    if not video_list:
        video_list = _dig(data, "Your Activity", "Video Browsing History", "VideoList", default=[])
    if not video_list:
        video_list = _dig(data, "Activity", "Video Browsing History", "VideoList", default=[])
    history = []
    for entry in video_list:
        date_str = entry.get("Date", entry.get("date", ""))
        link = entry.get("Link", entry.get("VideoLink", entry.get("link", "")))
        dt = _parse_date(date_str)
        history.append({
            "date": date_str,
            "link": link,
            "_dt": dt,
        })
    history.sort(key=lambda x: x["_dt"] or datetime.min)
    for item in history:
        del item["_dt"]
    return history


def _compute_behavioral_analysis(browsing_history: list[dict]) -> dict:
    """
    Compute behavioral analysis from browsing history timestamps.
    Uses timestamp-delta approach: for consecutive videos, compute the time delta.
    If delta > 300s or < 0, skip (AFK/session break).
    Otherwise bucket: <3s = skip, 3-15s = casual, >15s = linger.
    """
    parsed = []
    for entry in browsing_history:
        dt = _parse_date(entry.get("date", ""))
        if dt:
            parsed.append({"dt": dt, "link": entry.get("link", "")})

    parsed.sort(key=lambda x: x["dt"])
    total_videos = len(parsed)

    skip_count = 0
    casual_count = 0
    linger_count = 0
    valid_sessions = 0
    night_count = 0
    hourly_heatmap = defaultdict(int)
    monthly_data = defaultdict(lambda: {"skip": 0, "total": 0})
    linger_links = []
    skip_links = []

    for i in range(len(parsed) - 1):
        current = parsed[i]
        next_item = parsed[i + 1]
        delta = (next_item["dt"] - current["dt"]).total_seconds()

        if delta < 0:
            continue

        # 20-minute upper bound: phone left open while sleeping / accidental.
        # These are not valid behavioral signals — discard entirely.
        if delta >= 1200:
            continue

        # 0s–1199s: bucket normally.

        valid_sessions += 1
        hour = current["dt"].hour
        hourly_heatmap[hour] += 1
        month_key = current["dt"].strftime("%Y-%m")

        if 23 <= hour or hour < 4:
            night_count += 1

        if delta < 3:
            skip_count += 1
            skip_links.append(current["link"])
            monthly_data[month_key]["skip"] += 1
            monthly_data[month_key]["total"] += 1
        elif delta <= 15:
            casual_count += 1
            monthly_data[month_key]["total"] += 1
        else:
            linger_count += 1
            linger_links.append(current["link"])
            monthly_data[month_key]["total"] += 1

    skip_rate = (skip_count / valid_sessions * 100) if valid_sessions > 0 else 0
    linger_rate = (linger_count / valid_sessions * 100) if valid_sessions > 0 else 0
    night_shift_ratio = (night_count / valid_sessions * 100) if valid_sessions > 0 else 0

    hourly_dict = {str(h): hourly_heatmap.get(h, 0) for h in range(24)}

    monthly_skip_rates = {}
    for month_key in sorted(monthly_data.keys()):
        md = monthly_data[month_key]
        if md["total"] > 0:
            monthly_skip_rates[month_key] = round(md["skip"] / md["total"] * 100, 1)
        else:
            monthly_skip_rates[month_key] = 0.0

    return {
        "total_videos": total_videos,
        "valid_sessions": valid_sessions,
        "skip_count": skip_count,
        "casual_count": casual_count,
        "linger_count": linger_count,
        "skip_rate": round(skip_rate, 1),
        "linger_rate": round(linger_rate, 1),
        "night_shift_ratio": round(night_shift_ratio, 1),
        "hourly_heatmap": hourly_dict,
        "monthly_skip_rates": monthly_skip_rates,
        "top_linger_links": linger_links,
        "top_skip_links": skip_links,
    }


def _extract_likes(data: dict) -> list[dict]:
    """Extract liked videos."""
    like_list = _dig(data, "Likes and Favorites", "Like List", "ItemFavoriteList", default=[])
    if not like_list:
        like_list = _dig(data, "Your Activity", "Like List", "ItemFavoriteList", default=[])
    if not like_list:
        like_list = _dig(data, "Activity", "Like List", "ItemFavoriteList", default=[])
    results = []
    for entry in like_list:
        results.append({
            "date": entry.get("Date", entry.get("date", "")),
            "link": entry.get("Link", entry.get("link", entry.get("VideoLink", ""))),
        })
    return results


def _extract_favorites(data: dict) -> list[dict]:
    """Extract favorite videos."""
    fav_list = _dig(data, "Likes and Favorites", "Favorite Videos", "FavoriteVideoList", default=[])
    if not fav_list:
        fav_list = _dig(data, "Your Activity", "Favorite Videos", "FavoriteVideoList", default=[])
    if not fav_list:
        fav_list = _dig(data, "Activity", "Favorite Videos", "FavoriteVideoList", default=[])
    results = []
    for entry in fav_list:
        results.append({
            "date": entry.get("Date", entry.get("date", "")),
            "link": entry.get("Link", entry.get("link", "")),
        })
    return results


def _extract_favorite_collections(data: dict) -> list[str]:
    """Extract favorite collection names."""
    collections = _dig(data, "Likes and Favorites", "Favorite Collection", "FavoriteCollectionList", default=[])
    if not collections:
        collections = _dig(data, "Likes and Favorites", "Favorite Collections", "FavoriteCollectionList", default=[])
    if not collections:
        collections = _dig(data, "Your Activity", "Favorite Collections", "FavoriteCollectionList", default=[])
    names = []
    for coll in collections:
        name = coll.get("FavoriteCollection", coll.get("Name", coll.get("name", coll.get("CollectionName", ""))))
        if name:
            names.append(_safe_text(name))
    return names


def _extract_searches(data: dict) -> list[dict]:
    """Extract search history."""
    search_list = _dig(data, "Your Activity", "Searches", "SearchList", default=[])
    if not search_list:
        search_list = _dig(data, "Activity", "Searches", "SearchList", default=[])
    if not search_list:
        search_list = _dig(data, "Your Activity", "Search", "SearchList", default=[])
    results = []
    for entry in search_list:
        results.append({
            "date": entry.get("Date", entry.get("date", "")),
            "term": _safe_text(entry.get("SearchTerm", entry.get("searchTerm", entry.get("Content", "")))),
        })
    return results


def _extract_shares(data: dict) -> list[dict]:
    """Extract share history."""
    share_list = _dig(data, "Your Activity", "Share History", "ShareHistoryList", default=[])
    if not share_list:
        share_list = _dig(data, "Activity", "Share History", "ShareHistoryList", default=[])
    results = []
    for entry in share_list:
        results.append({
            "date": entry.get("Date", entry.get("date", "")),
            "link": entry.get("Link", entry.get("link", "")),
            "method": entry.get("Method", entry.get("method", entry.get("SharedContent", ""))),
        })
    return results


def _extract_comments(data: dict) -> list[dict]:
    """Extract comments."""
    comment_section = _dig(data, "Comment", "Comments", "CommentsList", default=[])
    if not comment_section:
        comment_section = _dig(data, "Comments", "Comments", "CommentsList", default=[])
    results = []
    for entry in comment_section:
        results.append({
            "date": entry.get("Date", entry.get("date", "")),
            "comment": _safe_text(entry.get("Comment", entry.get("comment", ""))),
            "url": entry.get("Url", entry.get("url", entry.get("VideoLink", ""))),
        })
    return results


def _extract_blocked(data: dict) -> list[dict]:
    """Extract block list."""
    block_list = _dig(data, "Profile And Settings", "Block List", "BlockList", default=[])
    if not block_list:
        block_list = _dig(data, "Your Activity", "Block List", "BlockList", default=[])
    if not block_list:
        block_list = _dig(data, "Activity", "Block List", "BlockList", default=[])
    results = []
    for entry in block_list:
        results.append({
            "date": entry.get("Date", entry.get("date", "")),
            "username": entry.get("UserName", entry.get("userName", entry.get("username", ""))),
        })
    return results


def _extract_following(data: dict) -> list[dict]:
    """Extract following list."""
    following_list = _dig(data, "Profile And Settings", "Following", "Following", default=[])
    if not following_list:
        following_list = _dig(data, "Your Activity", "Following List", "Following", default=[])
    if not following_list:
        following_list = _dig(data, "Profile And Settings", "Following List", "Following", default=[])
    results = []
    for entry in following_list:
        results.append({
            "date": entry.get("Date", entry.get("date", "")),
            "username": entry.get("UserName", entry.get("userName", entry.get("username", ""))),
        })
    return results


def _extract_followers(data: dict) -> list[dict]:
    """Extract follower list."""
    follower_list = _dig(data, "Profile And Settings", "Follower", "FansList", default=[])
    if not follower_list:
        follower_list = _dig(data, "Your Activity", "Follower List", "FansList", default=[])
    if not follower_list:
        follower_list = _dig(data, "Profile And Settings", "Follower List", "FansList", default=[])
    results = []
    for entry in follower_list:
        results.append({
            "date": entry.get("Date", entry.get("date", "")),
            "username": entry.get("UserName", entry.get("userName", entry.get("username", ""))),
        })
    return results


def _extract_login_history(data: dict) -> tuple[list[dict], dict]:
    """Extract login history and compute stats."""
    login_list = _dig(data, "Your Activity", "Login History", "LoginHistoryList", default=[])
    if not login_list:
        login_list = _dig(data, "Activity", "Login History", "LoginHistoryList", default=[])
    results = []
    ips = set()
    devices = set()
    for entry in login_list:
        ip = entry.get("IP", entry.get("ip", ""))
        device_model = entry.get("DeviceModel", entry.get("deviceModel", ""))
        device_system = entry.get("DeviceSystem", entry.get("deviceSystem", ""))
        network_type = entry.get("NetworkType", entry.get("networkType", ""))
        carrier = entry.get("Carrier", entry.get("carrier", ""))
        if ip:
            ips.add(ip)
        if device_model:
            devices.add(device_model)
        results.append({
            "date": entry.get("Date", entry.get("date", "")),
            "ip": ip,
            "device_model": device_model,
            "device_system": device_system,
            "network_type": network_type,
            "carrier": carrier,
        })
    stats = {
        "unique_ips": len(ips),
        "unique_devices": sorted(list(devices)),
        "ip_locations": sorted(list(ips)),
    }
    return results, stats


def _extract_off_tiktok_activity(data: dict) -> list:
    """Extract off-TikTok activity (usually empty if user opted out of tracking)."""
    off_activity = _dig(data, "Your Activity", "Off TikTok Activity", "OffTikTokActivityDataList", default=[])
    if not off_activity:
        off_activity = _dig(data, "Profile And Settings", "Off TikTok Activity", "OffTikTokActivityDataList", default=[])
    if not off_activity:
        off_activity = _dig(data, "Activity", "Off TikTok Activity", "OffTikTokActivityDataList", default=[])
    return off_activity if off_activity else []


def _extract_shop_orders(data: dict) -> list[dict]:
    """Extract TikTok Shop orders."""
    # Try list format first
    orders_section = _dig(data, "TikTok Shop", "Order", "OrderList", default=[])
    if not orders_section:
        orders_section = _dig(data, "TikTok Shop", "Orders", "OrderList", default=[])

    # Also try dict format (OrderHistories keyed by order ID)
    order_histories = _dig(data, "TikTok Shop", "Order History", "OrderHistories", default={})
    if isinstance(order_histories, dict) and order_histories:
        orders_section = list(order_histories.values())

    results = []
    for order in orders_section:
        products = []
        product_list = order.get("Products", order.get("products", []))
        if isinstance(product_list, list):
            for p in product_list:
                if isinstance(p, dict):
                    name = p.get("ProductName", p.get("productName", p.get("name", "")))
                    if name:
                        products.append(_safe_text(name))
                elif isinstance(p, str):
                    products.append(_safe_text(p))
        elif isinstance(product_list, str):
            products.append(_safe_text(product_list))
        results.append({
            "date": order.get("Date", order.get("date", order.get("CreateTime", order.get("order_date", "")))),
            "total_price": order.get("TotalPrice", order.get("totalPrice", order.get("TotalAmount", order.get("total_price", "")))),
            "products": products,
        })
    return results


def _count_dms(data: dict) -> int:
    """Count total DMs across all chats."""
    dm_section = _dig(data, "Direct Message", "Direct Messages", "ChatHistory", default={})
    if not dm_section:
        dm_section = _dig(data, "Direct Messages", "Direct Messages", "ChatHistory", default={})
    total = 0
    if isinstance(dm_section, dict):
        for chat_key, chat_data in dm_section.items():
            if isinstance(chat_data, list):
                total += len(chat_data)
            elif isinstance(chat_data, dict):
                messages = chat_data.get("Messages", chat_data.get("messages", []))
                if isinstance(messages, list):
                    total += len(messages)
    elif isinstance(dm_section, list):
        for chat in dm_section:
            messages = chat.get("Messages", chat.get("messages", []))
            if isinstance(messages, list):
                total += len(messages)
    return total


def _parse_tiktok_data(data: dict) -> dict:
    """Core parsing logic, shared by file and bytes entry points."""

    profile = _extract_profile(data)
    settings_interests = _extract_settings_interests(data)
    ad_interests = _extract_ad_interests(data)
    browsing_history = _extract_browsing_history(data)
    likes = _extract_likes(data)
    favorites = _extract_favorites(data)
    favorite_collections = _extract_favorite_collections(data)
    searches = _extract_searches(data)
    shares = _extract_shares(data)
    comments = _extract_comments(data)
    session_result = _detect_sessions(browsing_history, likes, comments, shares)
    watch_history_active = session_result["watch_history_active"]
    behavioral_analysis = _compute_behavioral_analysis(watch_history_active)
    behavioral_analysis["night_shift_ratio"] = _compute_night_shift_ratio(browsing_history)
    behavioral_analysis["night_shift_passive_adjusted"] = True
    behavioral_analysis.update({
        "passive_videos_removed": session_result["passive_videos_removed"],
        "passive_sessions_detected": session_result["passive_sessions_detected"],
        "active_video_count": session_result["active_video_count"],
        "session_count": session_result["session_count"],
        "avg_session_length_videos": session_result["avg_session_length_videos"],
    })
    blocked_users = _extract_blocked(data)
    following = _extract_following(data)
    followers = _extract_followers(data)
    login_history, login_stats = _extract_login_history(data)
    off_tiktok_activity = _extract_off_tiktok_activity(data)
    shop_orders = _extract_shop_orders(data)
    dm_count = _count_dms(data)

    return {
        "platform": "tiktok",
        "profile": profile,
        "settings_interests": settings_interests,
        "ad_interests": ad_interests,
        "browsing_history": browsing_history,
        "watch_history_full": session_result["watch_history_full"],
        "watch_history_active": watch_history_active,
        "behavioral_analysis": behavioral_analysis,
        "likes": likes,
        "favorites": favorites,
        "favorite_collections": favorite_collections,
        "searches": searches,
        "shares": shares,
        "comments": comments,
        "blocked_users": blocked_users,
        "following": following,
        "followers": followers,
        "login_history": login_history,
        "login_history_stats": login_stats,
        "off_tiktok_activity": off_tiktok_activity,
        "shop_orders": shop_orders,
        "dm_count": dm_count,
    }


def parse_tiktok_export(file_path: str) -> dict:
    """
    Parse a TikTok user_data_tiktok.json file into a structured analysis dict.

    Args:
        file_path: Path to the user_data_tiktok.json file.

    Returns:
        dict with all extracted and computed data.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    return _parse_tiktok_data(data)


def parse_tiktok_export_from_bytes(raw: bytes) -> dict:
    """
    Parse a TikTok export from raw bytes (e.g. an HTTP file upload).
    Decodes with surrogate replacement so malformed emoji never raise.

    Args:
        raw: Raw bytes of the user_data_tiktok.json file.

    Returns:
        dict with all extracted and computed data.
    """
    text = raw.decode("utf-8", errors="replace")
    data = json.loads(text)
    return _parse_tiktok_data(data)
