"""
Instagram/Meta data export parser.
Parses an Instagram data export directory (JSON format) into a structured analysis dict.
"""
import json
import os
from datetime import datetime
from collections import defaultdict


def _decode_meta_string(s: str) -> str:
    """
    Decode Meta's double-encoded UTF-8 strings.
    Meta exports sometimes encode UTF-8 bytes as Latin-1 unicode escapes,
    e.g. \\u00c3\\u00a9 for e-acute. This detects and fixes that.
    """
    if not isinstance(s, str):
        return str(s) if s is not None else ""
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def _decode_value(obj):
    """Recursively decode Meta strings in a JSON structure."""
    if isinstance(obj, str):
        return _decode_meta_string(obj)
    if isinstance(obj, list):
        return [_decode_value(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _decode_value(v) for k, v in obj.items()}
    return obj


def _load_json(dir_path: str, *path_parts) -> dict | list | None:
    """Safely load a JSON file from the export directory."""
    file_path = os.path.join(dir_path, *path_parts)
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _decode_value(data)
    except (json.JSONDecodeError, OSError):
        return None


def _ts_to_str(ts) -> str:
    """Convert a Unix timestamp to ISO date string."""
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return str(ts)


def _extract_profile(dir_path: str) -> dict:
    """Extract profile info from personal_information."""
    data = _load_json(dir_path, "personal_information", "personal_information", "personal_information.json")
    if not data:
        return {}
    profile_data = {}
    if isinstance(data, dict):
        info_list = data.get("profile_user", [])
        if isinstance(info_list, list) and info_list:
            user = info_list[0]
            sm = user.get("string_map_data", {})
            profile_data = {
                "username": sm.get("Username", {}).get("value", ""),
                "name": sm.get("Name", {}).get("value", ""),
                "email": sm.get("Email", {}).get("value", sm.get("Email address", {}).get("value", "")),
                "phone": sm.get("Phone Number", {}).get("value", sm.get("Phone number", {}).get("value", "")),
                "bio": sm.get("Bio", {}).get("value", ""),
                "gender": sm.get("Gender", {}).get("value", ""),
                "date_of_birth": sm.get("Date of birth", {}).get("value", sm.get("Date of Birth", {}).get("value", "")),
                "private_account": sm.get("Private Account", {}).get("value", sm.get("Private account", {}).get("value", "")),
            }
    return profile_data


def _extract_profile_location(dir_path: str) -> str:
    """Extract profile-based-in location."""
    data = _load_json(dir_path, "personal_information", "information_about_you", "profile_based_in.json")
    if not data:
        return ""
    try:
        inferred = data.get("inferred_data_primary_location", [])
        if inferred and isinstance(inferred, list):
            entry = inferred[0]
            sm = entry.get("string_map_data", {})
            city_region = sm.get("City Name", {}).get("value", "")
            if not city_region:
                city_region = sm.get("Region", {}).get("value", "")
            return city_region
    except (KeyError, IndexError, TypeError):
        pass
    return ""


def _extract_locations_of_interest(dir_path: str) -> list[str]:
    """Extract locations of interest."""
    data = _load_json(dir_path, "personal_information", "information_about_you", "locations_of_interest.json")
    if not data:
        return []
    locations = []
    try:
        # Format: label_values[0].vec[].value (same pattern as ad categories)
        label_values = data.get("label_values", [])
        if label_values and isinstance(label_values, list):
            for lv in label_values:
                if isinstance(lv, dict):
                    vec = lv.get("vec", [])
                    for item in vec:
                        if isinstance(item, dict):
                            val = item.get("value", "")
                            if val:
                                locations.append(val)
        # Fallback: older format
        if not locations:
            topics = data.get("inferred_data_ig_interest_location", [])
            for entry in topics:
                sm = entry.get("string_map_data", {})
                name_val = sm.get("Name", {}).get("value", "")
                if name_val:
                    locations.append(name_val)
    except (KeyError, TypeError):
        pass
    return locations


def _extract_ad_categories(dir_path: str) -> list[str]:
    """Extract ad targeting categories Meta assigns to you."""
    data = _load_json(dir_path, "ads_information", "instagram_ads_and_businesses", "other_categories_used_to_reach_you.json")
    if not data:
        return []
    categories = []
    try:
        label_values = data.get("label_values", [])
        # Format: label_values is a list with one entry containing {label: "Name", vec: [{value: "..."}, ...]}
        if label_values and isinstance(label_values, list):
            for lv in label_values:
                if isinstance(lv, dict):
                    vec = lv.get("vec", [])
                    for item in vec:
                        if isinstance(item, dict):
                            val = item.get("value", "")
                            if val:
                                categories.append(val)
                elif isinstance(lv, str):
                    categories.append(lv)
        # Fallback: try other known keys
        if not categories:
            cat_list = data.get("ig_custom_audiences_all_types", [])
            for entry in cat_list:
                if isinstance(entry, str):
                    categories.append(entry)
                elif isinstance(entry, dict):
                    sm = entry.get("string_map_data", {})
                    name = sm.get("Name", {}).get("value", "")
                    if name:
                        categories.append(name)
    except (KeyError, TypeError):
        pass
    return categories


def _extract_advertisers(dir_path: str) -> tuple[int, list[str], dict]:
    """Extract advertisers using your data."""
    data = _load_json(dir_path, "ads_information", "instagram_ads_and_businesses", "advertisers_using_your_activity_or_information.json")
    if not data:
        return 0, [], {}

    all_advertisers = []
    data_types = defaultdict(int)

    try:
        ig_data = data.get("ig_custom_audiences_all_types", [])
        if not ig_data:
            ig_data = data.get("custom_audiences_all_types", [])
        for entry in ig_data:
            if isinstance(entry, dict):
                # Flat format: {advertiser_name: "...", has_data_file_custom_audience: true, ...}
                name = entry.get("advertiser_name", "")
                if not name:
                    # Fallback: string_map_data format
                    sm = entry.get("string_map_data", {})
                    name = sm.get("Advertiser", {}).get("value", sm.get("Name", {}).get("value", ""))
                if name:
                    all_advertisers.append(name)

                # Check data types — flat boolean format
                if entry.get("has_data_file_custom_audience") is True:
                    data_types["has_data_file_custom_audience"] += 1
                if entry.get("has_remarketing_custom_audience") is True:
                    data_types["has_remarketing_custom_audience"] += 1
                if entry.get("has_in_person_store_visit") is True:
                    data_types["has_in_person_store_visit"] += 1

                # Fallback: string_map_data format
                if "string_map_data" in entry:
                    sm = entry["string_map_data"]
                    if sm.get("Has data file custom audience", {}).get("value", "").lower() == "true":
                        data_types["has_data_file_custom_audience"] += 1
                    if sm.get("Has remarketing custom audience", {}).get("value", "").lower() == "true":
                        data_types["has_remarketing_custom_audience"] += 1
                    if sm.get("Has in-person store visit", {}).get("value", "").lower() == "true":
                        data_types["has_in_person_store_visit"] += 1
    except (KeyError, TypeError):
        pass

    count = len(all_advertisers)
    sample = all_advertisers[:50]
    return count, sample, dict(data_types)


def _extract_recommended_topics(dir_path: str) -> list[str]:
    """Extract recommended/inferred topics."""
    data = _load_json(dir_path, "preferences", "your_topics", "recommended_topics.json")
    if not data:
        return []
    topics = []
    try:
        topic_list = data.get("topics_your_topics", [])
        for entry in topic_list:
            if isinstance(entry, str):
                topics.append(entry)
            elif isinstance(entry, dict):
                sm = entry.get("string_map_data", {})
                name = sm.get("Name", {}).get("value", "")
                if name:
                    topics.append(name)
    except (KeyError, TypeError):
        pass
    return topics


def _extract_off_meta_activity(dir_path: str) -> list[dict]:
    """Extract off-Meta activity from third-party sites/apps."""
    # Try the nested path first (apps_and_websites subdirectory)
    data = _load_json(dir_path, "apps_and_websites_off_of_instagram", "apps_and_websites", "your_activity_off_meta_technologies.json")
    if not data:
        data = _load_json(dir_path, "apps_and_websites_off_of_instagram", "your_activity_off_meta_technologies.json")
    if not data:
        data = _load_json(dir_path, "apps_and_websites_off_of_instagram", "off_meta_activity.json")
    if not data:
        return []

    aggregated = defaultdict(lambda: {"events": [], "count": 0})
    try:
        activities = data.get("apps_and_websites_off_meta_activity", [])
        if not activities:
            activities = data.get("off_meta_activity_all_activity", [])
        if not activities:
            activities = data.get("off_facebook_activity_v2", [])
        if not activities:
            activities = data.get("off_meta_activity", [])
        for entry in activities:
            if isinstance(entry, dict):
                source = entry.get("name", entry.get("advertiser_name", ""))
                events = entry.get("events", [])
                if isinstance(events, list):
                    timestamps = []
                    for ev in events:
                        ts = ev.get("timestamp", 0)
                        if ts:
                            timestamps.append(ts)
                    aggregated[source]["count"] += len(events)
                    aggregated[source]["events"].extend(timestamps)
    except (KeyError, TypeError):
        pass

    results = []
    for source, info in sorted(aggregated.items(), key=lambda x: -x[1]["count"]):
        date_range = ""
        if info["events"]:
            sorted_ts = sorted(info["events"])
            start = _ts_to_str(sorted_ts[0])
            end = _ts_to_str(sorted_ts[-1])
            date_range = f"{start} to {end}"
        results.append({
            "source": source,
            "event_count": info["count"],
            "date_range": date_range,
        })
    return results


def _extract_devices(dir_path: str) -> list[dict]:
    """Extract device information."""
    data = _load_json(dir_path, "personal_information", "device_information", "devices.json")
    if not data:
        return []
    devices = []
    try:
        device_list = data.get("devices_devices", [])
        for entry in device_list:
            if isinstance(entry, dict):
                sm = entry.get("string_map_data", {})
                # Parse User Agent string to extract meaningful device info
                user_agent = sm.get("User Agent", {}).get("value", "")
                device_type = _parse_user_agent(user_agent)
                last_login_ts = sm.get("Last Login", {}).get("timestamp", sm.get("Last login", {}).get("timestamp", 0))
                last_login = _ts_to_str(last_login_ts) if last_login_ts else ""
                # Fallback to Type/OS fields if User Agent is empty
                if not device_type:
                    device_type = sm.get("Type", {}).get("value", sm.get("Device", {}).get("value", ""))
                devices.append({
                    "device_type": device_type or "Unknown",
                    "os": user_agent[:80] if user_agent else "",
                    "last_login": last_login,
                })
    except (KeyError, TypeError):
        pass
    return devices


def _parse_user_agent(ua: str) -> str:
    """Extract a human-readable device name from a User Agent string."""
    if not ua:
        return ""
    ua_lower = ua.lower()
    if "instagram" in ua_lower and "iphone" in ua_lower:
        # Extract iPhone model from Instagram UA
        import re
        match = re.search(r'(iPhone\d+,\d+)', ua)
        model = match.group(1) if match else "iPhone"
        ios_match = re.search(r'iOS (\d+)', ua)
        ios_ver = f" (iOS {ios_match.group(1)})" if ios_match else ""
        return f"{model}{ios_ver} — Instagram App"
    if "instagram" in ua_lower and "ipad" in ua_lower:
        import re
        match = re.search(r'(iPad\d+,\d+)', ua)
        model = match.group(1) if match else "iPad"
        return f"{model} — Instagram App"
    if "firefox" in ua_lower:
        import re
        match = re.search(r'Firefox/([\d.]+)', ua)
        ver = match.group(1) if match else ""
        if "macintosh" in ua_lower:
            return f"Firefox {ver} on Mac"
        if "windows" in ua_lower:
            return f"Firefox {ver} on Windows"
        return f"Firefox {ver}"
    if "chrome" in ua_lower and "safari" in ua_lower:
        import re
        match = re.search(r'Chrome/([\d.]+)', ua)
        ver = match.group(1).split('.')[0] if match else ""
        if "macintosh" in ua_lower:
            return f"Chrome {ver} on Mac"
        if "windows" in ua_lower:
            return f"Chrome {ver} on Windows"
        return f"Chrome {ver}"
    if "safari" in ua_lower and "chrome" not in ua_lower:
        if "iphone" in ua_lower:
            return "Safari on iPhone"
        if "ipad" in ua_lower:
            return "Safari on iPad"
        if "macintosh" in ua_lower:
            return "Safari on Mac"
        return "Safari"
    return ua[:50]


def _extract_searches(dir_path: str) -> list[dict]:
    """Extract search history."""
    data = _load_json(dir_path, "logged_information", "recent_searches", "word_or_phrase_searches.json")
    if not data:
        return []
    searches = []
    try:
        search_list = data.get("searches_keyword", [])
        if not search_list:
            search_list = data.get("searches_user", [])
        for entry in search_list:
            if isinstance(entry, dict):
                sm = entry.get("string_map_data", {})
                term = sm.get("Search", {}).get("value", sm.get("Query", {}).get("value", ""))
                ts = sm.get("Time", {}).get("timestamp", sm.get("Search Time", {}).get("timestamp", 0))
                searches.append({
                    "date": _ts_to_str(ts),
                    "term": term,
                })
    except (KeyError, TypeError):
        pass
    return searches


def _extract_link_history(dir_path: str) -> list[dict]:
    """Extract link history."""
    data = _load_json(dir_path, "logged_information", "link_history", "link_history.json")
    if not data:
        return []
    links = []
    try:
        link_list = data.get("label_values", [])
        if not link_list:
            link_list = data.get("link_history", [])
        for entry in link_list:
            if isinstance(entry, dict):
                sm = entry.get("string_map_data", {})
                url = sm.get("URL", {}).get("value", sm.get("Url", {}).get("value", ""))
                ts = sm.get("Time", {}).get("timestamp", sm.get("Timestamp", {}).get("timestamp", 0))
                links.append({
                    "url": url,
                    "timestamp": _ts_to_str(ts),
                })
    except (KeyError, TypeError):
        pass
    return links


def _count_items(dir_path: str, *path_parts, key: str = "") -> int:
    """Count items in a list from a JSON file."""
    data = _load_json(dir_path, *path_parts)
    if not data:
        return 0
    if key:
        items = data.get(key, [])
    else:
        for k, v in data.items():
            if isinstance(v, list):
                return len(v)
        return 0
    return len(items) if isinstance(items, list) else 0


def _extract_lead_submissions(dir_path: str) -> list[dict]:
    """Extract information submitted to advertisers."""
    data = _load_json(dir_path, "ads_information", "instagram_ads_and_businesses", "information_you've_submitted_to_advertisers.json")
    if not data:
        data = _load_json(dir_path, "ads_information", "instagram_ads_and_businesses", "information_you_ve_submitted_to_advertisers.json")
    if not data:
        return []
    leads = []
    try:
        lead_list = data.get("ig_lead_gen_info", [])
        if not lead_list:
            for k, v in data.items():
                if isinstance(v, list):
                    lead_list = v
                    break
        for entry in lead_list:
            if isinstance(entry, dict):
                sm = entry.get("string_map_data", {})
                label_data = entry.get("label", "")
                advertiser = label_data if label_data else sm.get("Advertiser", {}).get("value", "")
                submitted = []
                for field_key, field_val in sm.items():
                    if isinstance(field_val, dict) and field_val.get("value"):
                        submitted.append(f"{field_key}: {field_val['value']}")
                leads.append({
                    "advertiser": advertiser,
                    "data_submitted": submitted,
                })
    except (KeyError, TypeError):
        pass
    return leads


def parse_instagram_export(dir_path: str) -> dict:
    """
    Parse an Instagram/Meta data export directory into a structured analysis dict.

    Args:
        dir_path: Path to the Instagram export directory.

    Returns:
        dict with all extracted data.
    """
    result = {"platform": "instagram"}

    try:
        result["profile"] = _extract_profile(dir_path)
    except Exception:
        result["profile"] = {}

    try:
        result["profile_location"] = _extract_profile_location(dir_path)
    except Exception:
        result["profile_location"] = ""

    try:
        result["locations_of_interest"] = _extract_locations_of_interest(dir_path)
    except Exception:
        result["locations_of_interest"] = []

    try:
        result["ad_categories"] = _extract_ad_categories(dir_path)
    except Exception:
        result["ad_categories"] = []

    try:
        count, sample, data_types = _extract_advertisers(dir_path)
        result["advertiser_count"] = count
        result["advertisers_sample"] = sample
        result["advertiser_data_types"] = data_types
    except Exception:
        result["advertiser_count"] = 0
        result["advertisers_sample"] = []
        result["advertiser_data_types"] = {}

    try:
        result["recommended_topics"] = _extract_recommended_topics(dir_path)
    except Exception:
        result["recommended_topics"] = []

    try:
        result["off_meta_activity"] = _extract_off_meta_activity(dir_path)
    except Exception:
        result["off_meta_activity"] = []

    try:
        result["devices"] = _extract_devices(dir_path)
    except Exception:
        result["devices"] = []

    try:
        result["searches"] = _extract_searches(dir_path)
    except Exception:
        result["searches"] = []

    try:
        result["link_history"] = _extract_link_history(dir_path)
    except Exception:
        result["link_history"] = []

    try:
        result["ads_viewed_count"] = _count_items(
            dir_path, "your_instagram_activity", "ads_and_content", "ads_viewed.json",
            key="impressions_history_ads_seen"
        )
    except Exception:
        result["ads_viewed_count"] = 0

    try:
        result["posts_viewed_count"] = _count_items(
            dir_path, "your_instagram_activity", "ads_and_content", "posts_viewed.json",
            key="impressions_history_posts_seen"
        )
    except Exception:
        result["posts_viewed_count"] = 0

    try:
        result["videos_watched_count"] = _count_items(
            dir_path, "your_instagram_activity", "ads_and_content", "videos_watched.json",
            key="impressions_history_videos_watched"
        )
    except Exception:
        result["videos_watched_count"] = 0

    try:
        result["lead_submissions"] = _extract_lead_submissions(dir_path)
    except Exception:
        result["lead_submissions"] = []

    return result
