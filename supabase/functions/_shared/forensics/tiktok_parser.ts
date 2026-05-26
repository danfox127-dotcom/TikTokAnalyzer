/**
 * TikTok Data Export Parser (TypeScript Port)
 * Handles deep-nested JSON traversal and behavioral session detection.
 */

export interface VideoEntry {
  date: string;
  link: string;
}

export interface ParseResult {
  platform: "tiktok";
  profile: any;
  settings_interests: string[];
  ad_interests: string[];
  watch_history_full: VideoEntry[];
  watch_history_active: VideoEntry[];
  session_metrics: {
    passive_videos_removed: number;
    passive_sessions_detected: number;
    active_video_count: number;
    session_count: number;
    avg_session_length_videos: number;
  };
  likes: VideoEntry[];
  favorites: VideoEntry[];
  favorite_collections: string[];
  searches: { date: string; term: string }[];
  shares: { date: string; link: string; method: string }[];
  comments: { date: string; comment: string; url: string }[];
  blocked_users: { date: string; username: string }[];
  following: { date: string; username: string }[];
  followers: { date: string; username: string }[];
  login_history: any[];
  login_history_stats: any;
  off_tiktok_activity: any[];
  shop_orders: any[];
  dm_count: number;
}

const SESSION_GAP_S = 1800; // 30 minutes

export function parseDate(dateStr: string): Date | null {
  if (!dateStr) return null;
  
  // Try several formats
  const formats = [
    // 2024-05-22 14:30:00
    /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/,
    // 2024-05-22T14:30:00
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})$/,
    // 2024-05-22T14:30:00.000
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d+)$/,
    // 2024-05-22
    /^(\d{4})-(\d{2})-(\d{2})$/,
  ];

  for (const regex of formats) {
    const match = dateStr.match(regex);
    if (match) {
      const [_, y, m, d, h = 0, min = 0, s = 0] = match;
      return new Date(Date.UTC(Number(y), Number(m) - 1, Number(d), Number(h), Number(min), Number(s)));
    }
  }

  const d = new Date(dateStr);
  return isNaN(d.getTime()) ? null : d;
}

function detectSessions(
  browsingHistory: VideoEntry[],
  likes: VideoEntry[],
  comments: any[],
  shares: any[]
) {
  if (!browsingHistory.length) {
    return {
      watch_history_full: [],
      watch_history_active: [],
      passive_videos_removed: 0,
      passive_sessions_detected: 0,
      active_video_count: 0,
      session_count: 0,
      avg_session_length_videos: 0,
    };
  }

  // Build engagement timestamp list
  const engagementTimes: number[] = [];
  [likes, comments, shares].forEach(source => {
    source.forEach((item: any) => {
      const d = parseDate(item.date);
      if (d) engagementTimes.push(d.getTime());
    });
  });

  // Parse and index history
  const parsedEntries: { dt: number; orig: VideoEntry; idx: number }[] = [];
  const unparseable: VideoEntry[] = [];
  
  browsingHistory.forEach((item, idx) => {
    const d = parseDate(item.date);
    if (d) {
      parsedEntries.push({ dt: d.getTime(), orig: item, idx });
    } else {
      unparseable.push(item);
    }
  });

  parsedEntries.sort((a, b) => a.dt - b.dt);

  // Split into sessions
  const sessions: typeof parsedEntries[] = [];
  if (parsedEntries.length) {
    let current: typeof parsedEntries = [parsedEntries[0]];
    for (let i = 1; i < parsedEntries.length; i++) {
      const gap = (parsedEntries[i].dt - parsedEntries[i - 1].dt) / 1000;
      if (gap > SESSION_GAP_S) {
        sessions.push(current);
        current = [parsedEntries[i]];
      } else {
        current.push(parsedEntries[i]);
      }
    }
    sessions.push(current);
  }

  const passiveIndices = new Set<number>();
  let passiveSessions = 0;

  sessions.forEach(session => {
    const sStart = session[0].dt;
    const sEnd = session[session.length - 1].dt;

    const hasEngagement = engagementTimes.some(et => et >= sStart && et <= sEnd);
    if (!hasEngagement && session.length >= 5) {
      passiveSessions++;
      session.forEach(e => passiveIndices.add(e.idx));
    }

    // Autoplay artifacts (< 2s)
    for (let i = 1; i < session.length; i++) {
      const delta = (session[i].dt - session[i - 1].dt) / 1000;
      if (delta < 2) {
        passiveIndices.add(session[i].idx);
      }
    }
  });

  const watch_history_full = parsedEntries.map(e => e.orig).concat(unparseable);
  const watch_history_active = parsedEntries
    .filter(e => !passiveIndices.has(e.idx))
    .map(e => e.orig)
    .concat(unparseable);

  const session_lengths = sessions.map(s => s.length);
  const avgLen = sessions.length ? session_lengths.reduce((a, b) => a + b, 0) / sessions.length : 0;

  return {
    watch_history_full,
    watch_history_active,
    passive_videos_removed: passiveIndices.size,
    passive_sessions_detected: passiveSessions,
    active_video_count: watch_history_active.length,
    session_count: sessions.length,
    avg_session_length_videos: Math.round(avgLen * 10) / 10,
  };
}

function dig(data: any, ...keys: string[]) {
  let current = data;
  for (const key of keys) {
    if (current && typeof current === 'object') {
      current = current[key];
    } else {
      return null;
    }
  }
  return current;
}

export function parseTiktokData(data: any): ParseResult {
  // Extraction helpers (ports of Python _extract_* functions)
  const extractProfile = () => {
    const profile = dig(data, "Profile And Settings", "Profile Info", "ProfileMap") || 
                    dig(data, "Profile And Settings", "ProfileMap") || {};
    return {
      username: profile.userName || "",
      display_name: profile.displayName || profile.nickName || "",
      birth_date: profile.birthDate || "",
      account_region: profile.accountRegion || "",
      bio: profile.bioDescription || "",
      follower_count: Number(profile.followerCount || 0),
      following_count: Number(profile.followingCount || 0),
      inferred_gender: profile.inferredGender || profile.gender || "",
    };
  };

  const extractAdInterests = () => {
    const adSection = dig(data, "Your Activity", "Ad Interests", "AdInterestCategories") || 
                      dig(data, "Ad Interests", "AdInterestCategories") || [];
    if (typeof adSection === 'string') return adSection.split(",").map(i => i.trim()).filter(Boolean);
    if (Array.isArray(adSection)) return adSection.filter(i => i && String(i).trim() !== ",");
    return [];
  };

  const extractBrowsingHistory = () => {
    const videoList = dig(data, "Your Activity", "Watch History", "VideoList") ||
                      dig(data, "Your Activity", "Video Browsing History", "VideoList") ||
                      dig(data, "Activity", "Video Browsing History", "VideoList") || [];
    return videoList.map((e: any) => ({
      date: e.Date || e.date || "",
      link: e.Link || e.VideoLink || e.link || ""
    }));
  };

  const extractLikes = () => {
    const list = dig(data, "Likes and Favorites", "Like List", "ItemFavoriteList") ||
                 dig(data, "Your Activity", "Like List", "ItemFavoriteList") ||
                 dig(data, "Activity", "Like List", "ItemFavoriteList") || [];
    return list.map((e: any) => ({
      date: e.Date || e.date || "",
      link: e.Link || e.link || e.VideoLink || ""
    }));
  };

  const extractLoginHistory = () => {
    const list = dig(data, "Your Activity", "Login History", "LoginHistoryList") ||
                 dig(data, "Activity", "Login History", "LoginHistoryList") || [];
    const results: any[] = [];
    const ips = new Set<string>();
    const devices = new Set<string>();
    
    list.forEach((e: any) => {
      const ip = e.IP || e.ip || "";
      const device = e.DeviceModel || e.deviceModel || "";
      if (ip) ips.add(ip);
      if (device) devices.add(device);
      results.push({
        date: e.Date || e.date || "",
        ip,
        device_model: device,
        device_system: e.DeviceSystem || e.deviceSystem || "",
        network_type: e.NetworkType || e.networkType || "",
        carrier: e.Carrier || e.carrier || "",
      });
    });

    return {
      results,
      stats: {
        unique_ips: ips.size,
        unique_devices: Array.from(devices).sort(),
        ip_locations: Array.from(ips).sort(),
      }
    };
  };

  const browsingHistory = extractBrowsingHistory();
  const likes = extractLikes();
  const comments = (dig(data, "Comment", "Comments", "CommentsList") || 
                    dig(data, "Comments", "Comments", "CommentsList") || []).map((e: any) => ({
                      date: e.Date || e.date || "",
                      comment: e.Comment || e.comment || "",
                      url: e.Url || e.url || e.VideoLink || ""
                    }));
  const shares = (dig(data, "Your Activity", "Share History", "ShareHistoryList") || 
                  dig(data, "Activity", "Share History", "ShareHistoryList") || []).map((e: any) => ({
                    date: e.Date || e.date || "",
                    link: e.Link || e.link || "",
                    method: e.Method || e.method || e.SharedContent || ""
                  }));

  const sessionResult = detectSessions(browsingHistory, likes, comments, shares);

  return {
    platform: "tiktok",
    profile: extractProfile(),
    settings_interests: (dig(data, "Profile And Settings", "Settings", "SettingsMap", "Interests") || "").split("|").filter(Boolean),
    ad_interests: extractAdInterests(),
    watch_history_full: sessionResult.watch_history_full,
    watch_history_active: sessionResult.watch_history_active,
    session_metrics: {
      passive_videos_removed: sessionResult.passive_videos_removed,
      passive_sessions_detected: sessionResult.passive_sessions_detected,
      active_video_count: sessionResult.active_video_count,
      session_count: sessionResult.session_count,
      avg_session_length_videos: sessionResult.avg_session_length_videos,
    },
    likes,
    favorites: (dig(data, "Likes and Favorites", "Favorite Videos", "FavoriteVideoList") || []).map((e: any) => ({
      date: e.Date || e.date || "",
      link: e.Link || e.link || ""
    })),
    favorite_collections: [], // simplify for now
    searches: (dig(data, "Your Activity", "Searches", "SearchList") || []).map((e: any) => ({
      date: e.Date || e.date || "",
      term: e.SearchTerm || e.searchTerm || e.Content || ""
    })),
    shares,
    comments,
    blocked_users: [],
    following: (dig(data, "Profile And Settings", "Following", "Following") || []).map((e: any) => ({
      date: e.Date || e.date || "",
      username: e.UserName || e.userName || e.username || ""
    })),
    followers: (dig(data, "Profile And Settings", "Follower", "FansList") || []).map((e: any) => ({
      date: e.Date || e.date || "",
      username: e.UserName || e.userName || e.username || ""
    })),
    ...extractLoginHistory(), // results -> login_history, stats -> login_history_stats
    off_tiktok_activity: dig(data, "Your Activity", "Off TikTok Activity", "OffTikTokActivityDataList") || [],
    shop_orders: [], // simplify for now
    dm_count: 0, // simplify for now
  } as any;
}
