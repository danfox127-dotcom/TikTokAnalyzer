/**
 * WP-1.1 engine port — TikTok export parser.
 * Mirror of parsers/tiktok.py (_parse_tiktok_data + all _extract_* + _detect_sessions).
 *
 * Parity choices, each of which a naive port gets wrong:
 *  - pyFalsy(): Python `not X` treats [] and {} as falsy; JS does not. The
 *    fallback-schema retries (`if not X: X = dig(...)`) use pyFalsy.
 *  - `.get(A, .get(B, ""))` chains map to `a ?? b ?? ""` — matches for absent keys
 *    AND for present empty-string values (only explicit null would diverge, which
 *    TikTok exports don't produce for these fields).
 *  - ad_interests retries on `is None` (not falsy), so an empty list is NOT retried.
 *  - detectSessions emits DATE-SORTED history (stable sort) with unparseable
 *    entries appended; avg_session_length uses round(_,1).
 *  - _safe_text is identity for valid strings (surrogate scrubbing not exercised).
 */

import { parseDate } from "./parseDate";
import { pyRound } from "./numeric";

function safeText(text: unknown): string {
  if (typeof text !== "string") return text == null ? "" : String(text);
  return text;
}

/** Python truthiness: null/undefined/false/0/"" and empty array/object are falsy. */
function pyFalsy(x: unknown): boolean {
  if (x === null || x === undefined || x === false || x === 0 || x === "") return true;
  if (Array.isArray(x)) return x.length === 0;
  if (typeof x === "object") return Object.keys(x as object).length === 0;
  return false;
}

/** Mirror of _dig: traverse nested dict keys; non-dict or missing/None → default. */
function dig(data: any, keys: string[], def: any = null): any {
  let current = data;
  for (const key of keys) {
    if (current !== null && typeof current === "object" && !Array.isArray(current)) {
      current = key in current ? current[key] : def;
    } else {
      return def;
    }
    if (current === null || current === undefined) return def;
  }
  return current;
}

const asList = (x: any): any[] => (Array.isArray(x) ? x : []);

// ── Session detection ──────────────────────────────────────────────────────
const SESSION_GAP_S = 1800;

export interface SessionResult {
  watch_history_full: any[];
  watch_history_active: any[];
  passive_videos_removed: number;
  passive_sessions_detected: number;
  active_video_count: number;
  session_count: number;
  avg_session_length_videos: number;
}

export function detectSessions(
  browsingHistory: any[],
  likes: any[],
  comments: any[],
  shares: any[],
): SessionResult {
  if (!browsingHistory || browsingHistory.length === 0) {
    return {
      watch_history_full: [], watch_history_active: [], passive_videos_removed: 0,
      passive_sessions_detected: 0, active_video_count: 0, session_count: 0,
      avg_session_length_videos: 0.0,
    };
  }

  const engagementTimes: number[] = [];
  for (const source of [likes, comments, shares]) {
    for (const item of asList(source)) {
      const dt = parseDate(item?.date ?? "");
      if (dt) engagementTimes.push(dt.getTime());
    }
  }

  interface PE { dt: Date; orig: any; idx: number; }
  const parsed: PE[] = [];
  const unparseable: any[] = [];
  browsingHistory.forEach((item, idx) => {
    const dt = parseDate(item?.date ?? "");
    if (dt) parsed.push({ dt, orig: item, idx });
    else unparseable.push(item);
  });

  parsed.sort((a, b) => a.dt.getTime() - b.dt.getTime()); // stable

  const sessions: PE[][] = [];
  if (parsed.length) {
    let current: PE[] = [parsed[0]];
    for (let i = 1; i < parsed.length; i++) {
      const gap = (parsed[i].dt.getTime() - parsed[i - 1].dt.getTime()) / 1000;
      if (gap > SESSION_GAP_S) {
        sessions.push(current);
        current = [parsed[i]];
      } else {
        current.push(parsed[i]);
      }
    }
    sessions.push(current);
  }

  const passiveIndices = new Set<number>();
  let passiveSessions = 0;
  for (const session of sessions) {
    const sStart = session[0].dt.getTime();
    const sEnd = session[session.length - 1].dt.getTime();
    const hasEngagement = engagementTimes.some((et) => et >= sStart && et <= sEnd);
    if (!hasEngagement && session.length >= 5) {
      passiveSessions++;
      for (const entry of session) passiveIndices.add(entry.idx);
    }
    for (let i = 1; i < session.length; i++) {
      const delta = (session[i].dt.getTime() - session[i - 1].dt.getTime()) / 1000;
      if (delta < 2) passiveIndices.add(session[i].idx);
    }
  }

  const watchHistoryFull = parsed.map((e) => e.orig).concat(unparseable);
  const watchHistoryActive = parsed.filter((e) => !passiveIndices.has(e.idx)).map((e) => e.orig).concat(unparseable);
  const sessionLengths = sessions.map((s) => s.length);
  const avgLen = sessions.length
    ? pyRound(sessionLengths.reduce((a, b) => a + b, 0) / sessions.length, 1)
    : 0.0;

  return {
    watch_history_full: watchHistoryFull,
    watch_history_active: watchHistoryActive,
    passive_videos_removed: passiveIndices.size,
    passive_sessions_detected: passiveSessions,
    active_video_count: watchHistoryActive.length,
    session_count: sessions.length,
    avg_session_length_videos: avgLen,
  };
}

// ── Extractors ─────────────────────────────────────────────────────────────
function extractProfile(data: any) {
  let ps = dig(data, ["Profile And Settings", "Profile Info", "ProfileMap"], {});
  if (pyFalsy(ps)) ps = dig(data, ["Profile And Settings", "ProfileMap"], {});
  return {
    username: ps.userName ?? "",
    display_name: ps.displayName ?? ps.nickName ?? "",
    birth_date: ps.birthDate ?? "",
    account_region: ps.accountRegion ?? "",
    bio: safeText(ps.bioDescription ?? ""),
    follower_count: ps.followerCount ?? 0,
    following_count: ps.followingCount ?? 0,
    inferred_gender: ps.inferredGender ?? ps.gender ?? "",
  };
}

function extractSettingsInterests(data: any): string[] {
  let s = dig(data, ["Profile And Settings", "Settings", "SettingsMap"], {});
  if (pyFalsy(s)) s = dig(data, ["Profile And Settings", "SettingsMap"], {});
  const str: string = s.Interests || s.InterestsLanguage || "";
  if (!str) return [];
  return str.split("|").map((i) => i.trim()).filter((i) => i);
}

function extractAdInterests(data: any): string[] {
  let ad = dig(data, ["Your Activity", "Ad Interests", "AdInterestCategories"], null);
  if (ad === null || ad === undefined) ad = dig(data, ["Ad Interests", "AdInterestCategories"], []);
  if (typeof ad === "string") return ad.split(",").map((i) => i.trim()).filter((i) => i);
  if (Array.isArray(ad)) {
    return ad
      .filter((item) => item && String(item).trim() && String(item).trim() !== ",")
      .map((item) => safeText(item));
  }
  return [];
}

function extractBrowsingHistory(data: any): any[] {
  let vl = dig(data, ["Your Activity", "Watch History", "VideoList"], []);
  if (pyFalsy(vl)) vl = dig(data, ["Your Activity", "Video Browsing History", "VideoList"], []);
  if (pyFalsy(vl)) vl = dig(data, ["Activity", "Video Browsing History", "VideoList"], []);
  return asList(vl).map((e) => ({
    date: e.Date ?? e.date ?? "",
    link: e.Link ?? e.VideoLink ?? e.link ?? "",
  }));
}

function extractLikes(data: any): any[] {
  let list = dig(data, ["Likes and Favorites", "Like List", "ItemFavoriteList"], []);
  if (pyFalsy(list)) list = dig(data, ["Your Activity", "Like List", "ItemFavoriteList"], []);
  if (pyFalsy(list)) list = dig(data, ["Activity", "Like List", "ItemFavoriteList"], []);
  return asList(list).map((e) => ({
    date: e.Date ?? e.date ?? "",
    link: e.Link ?? e.link ?? e.VideoLink ?? "",
  }));
}

function extractFavorites(data: any): any[] {
  let list = dig(data, ["Likes and Favorites", "Favorite Videos", "FavoriteVideoList"], []);
  if (pyFalsy(list)) list = dig(data, ["Your Activity", "Favorite Videos", "FavoriteVideoList"], []);
  if (pyFalsy(list)) list = dig(data, ["Activity", "Favorite Videos", "FavoriteVideoList"], []);
  return asList(list).map((e) => ({ date: e.Date ?? e.date ?? "", link: e.Link ?? e.link ?? "" }));
}

function extractFavoriteCollections(data: any): string[] {
  let coll = dig(data, ["Likes and Favorites", "Favorite Collection", "FavoriteCollectionList"], []);
  if (pyFalsy(coll)) coll = dig(data, ["Likes and Favorites", "Favorite Collections", "FavoriteCollectionList"], []);
  if (pyFalsy(coll)) coll = dig(data, ["Your Activity", "Favorite Collections", "FavoriteCollectionList"], []);
  const names: string[] = [];
  for (const c of asList(coll)) {
    const name = c.FavoriteCollection ?? c.Name ?? c.name ?? c.CollectionName ?? "";
    if (name) names.push(safeText(name));
  }
  return names;
}

function extractSearches(data: any): any[] {
  let list = dig(data, ["Your Activity", "Searches", "SearchList"], []);
  if (pyFalsy(list)) list = dig(data, ["Activity", "Searches", "SearchList"], []);
  if (pyFalsy(list)) list = dig(data, ["Your Activity", "Search", "SearchList"], []);
  return asList(list).map((e) => ({
    date: e.Date ?? e.date ?? "",
    term: safeText(e.SearchTerm ?? e.searchTerm ?? e.Content ?? ""),
  }));
}

function extractShares(data: any): any[] {
  let list = dig(data, ["Your Activity", "Share History", "ShareHistoryList"], []);
  if (pyFalsy(list)) list = dig(data, ["Activity", "Share History", "ShareHistoryList"], []);
  return asList(list).map((e) => ({
    date: e.Date ?? e.date ?? "",
    link: e.Link ?? e.link ?? "",
    method: e.Method ?? e.method ?? e.SharedContent ?? "",
  }));
}

function extractComments(data: any): any[] {
  let list = dig(data, ["Comment", "Comments", "CommentsList"], []);
  if (pyFalsy(list)) list = dig(data, ["Comments", "Comments", "CommentsList"], []);
  return asList(list).map((e) => ({
    date: e.Date ?? e.date ?? "",
    comment: safeText(e.Comment ?? e.comment ?? ""),
    url: e.Url ?? e.url ?? e.VideoLink ?? "",
  }));
}

function extractBlocked(data: any): any[] {
  let list = dig(data, ["Profile And Settings", "Block List", "BlockList"], []);
  if (pyFalsy(list)) list = dig(data, ["Your Activity", "Block List", "BlockList"], []);
  if (pyFalsy(list)) list = dig(data, ["Activity", "Block List", "BlockList"], []);
  return asList(list).map((e) => ({
    date: e.Date ?? e.date ?? "",
    username: e.UserName ?? e.userName ?? e.username ?? "",
  }));
}

function extractFollowing(data: any): any[] {
  let list = dig(data, ["Profile And Settings", "Following", "Following"], []);
  if (pyFalsy(list)) list = dig(data, ["Your Activity", "Following List", "Following"], []);
  if (pyFalsy(list)) list = dig(data, ["Profile And Settings", "Following List", "Following"], []);
  return asList(list).map((e) => ({
    date: e.Date ?? e.date ?? "",
    username: e.UserName ?? e.userName ?? e.username ?? "",
  }));
}

function extractFollowers(data: any): any[] {
  let list = dig(data, ["Profile And Settings", "Follower", "FansList"], []);
  if (pyFalsy(list)) list = dig(data, ["Your Activity", "Follower List", "FansList"], []);
  if (pyFalsy(list)) list = dig(data, ["Profile And Settings", "Follower List", "FansList"], []);
  return asList(list).map((e) => ({
    date: e.Date ?? e.date ?? "",
    username: e.UserName ?? e.userName ?? e.username ?? "",
  }));
}

function extractLoginHistory(data: any): [any[], any] {
  let list = dig(data, ["Your Activity", "Login History", "LoginHistoryList"], []);
  if (pyFalsy(list)) list = dig(data, ["Activity", "Login History", "LoginHistoryList"], []);
  const results: any[] = [];
  const ips = new Set<string>();
  const devices = new Set<string>();
  for (const e of asList(list)) {
    const ip = e.IP ?? e.ip ?? "";
    const deviceModel = e.DeviceModel ?? e.deviceModel ?? "";
    const deviceSystem = e.DeviceSystem ?? e.deviceSystem ?? "";
    const networkType = e.NetworkType ?? e.networkType ?? "";
    const carrier = e.Carrier ?? e.carrier ?? "";
    if (ip) ips.add(ip);
    if (deviceModel) devices.add(deviceModel);
    results.push({
      date: e.Date ?? e.date ?? "", ip, device_model: deviceModel,
      device_system: deviceSystem, network_type: networkType, carrier,
    });
  }
  const stats = {
    unique_ips: ips.size,
    unique_devices: [...devices].sort(),
    ip_locations: [...ips].sort(),
  };
  return [results, stats];
}

function extractOffTiktokActivity(data: any): any[] {
  let off = dig(data, ["Your Activity", "Off TikTok Activity", "OffTikTokActivityDataList"], []);
  if (pyFalsy(off)) off = dig(data, ["Profile And Settings", "Off TikTok Activity", "OffTikTokActivityDataList"], []);
  if (pyFalsy(off)) off = dig(data, ["Activity", "Off TikTok Activity", "OffTikTokActivityDataList"], []);
  return pyFalsy(off) ? [] : off;
}

function extractShopOrders(data: any): any[] {
  let orders = dig(data, ["TikTok Shop", "Order", "OrderList"], []);
  if (pyFalsy(orders)) orders = dig(data, ["TikTok Shop", "Orders", "OrderList"], []);

  const orderHistories = dig(data, ["TikTok Shop", "Order History", "OrderHistories"], {});
  if (orderHistories && typeof orderHistories === "object" && !Array.isArray(orderHistories)
      && Object.keys(orderHistories).length) {
    orders = Object.values(orderHistories);
  }

  const results: any[] = [];
  for (const order of asList(orders)) {
    const products: string[] = [];
    const productList = order.Products ?? order.products ?? [];
    if (Array.isArray(productList)) {
      for (const p of productList) {
        if (p && typeof p === "object") {
          const name = p.ProductName ?? p.productName ?? p.product_name ?? p.name ?? "";
          if (name) products.push(safeText(name));
        } else if (typeof p === "string") {
          products.push(safeText(p));
        }
      }
    } else if (typeof productList === "string") {
      products.push(safeText(productList));
    }
    results.push({
      date: order.Date ?? order.date ?? order.CreateTime ?? order.order_date ?? "",
      total_price: order.TotalPrice ?? order.totalPrice ?? order.TotalAmount ?? order.total_price ?? "",
      products,
    });
  }
  return results;
}

function extractProductBrowsing(data: any): any[] {
  const section = dig(data, ["TikTok Shop", "Product Browsing History", "ProductBrowsingHistories"], []);
  const results: any[] = [];
  if (Array.isArray(section)) {
    for (const e of section) {
      if (!e || typeof e !== "object") continue;
      const product = e.product_name ?? e.ProductName ?? e.productName ?? "";
      if (!product) continue;
      results.push({
        date: e.browsing_date ?? e.BrowsingDate ?? e.date ?? "",
        shop: safeText(e.shop_name ?? e.ShopName ?? e.shopName ?? ""),
        product: safeText(product),
      });
    }
  }
  return results;
}

function countDms(data: any): number {
  let dm = dig(data, ["Direct Message", "Direct Messages", "ChatHistory"], {});
  if (pyFalsy(dm)) dm = dig(data, ["Direct Messages", "Direct Messages", "ChatHistory"], {});
  let total = 0;
  if (dm && typeof dm === "object" && !Array.isArray(dm)) {
    for (const chatData of Object.values(dm) as any[]) {
      if (Array.isArray(chatData)) total += chatData.length;
      else if (chatData && typeof chatData === "object") {
        const messages = chatData.Messages ?? chatData.messages ?? [];
        if (Array.isArray(messages)) total += messages.length;
      }
    }
  } else if (Array.isArray(dm)) {
    for (const chat of dm) {
      const messages = chat.Messages ?? chat.messages ?? [];
      if (Array.isArray(messages)) total += messages.length;
    }
  }
  return total;
}

// ── Top-level ──────────────────────────────────────────────────────────────
export function parseTiktokData(data: any): Record<string, any> {
  const [loginHistory, loginStats] = extractLoginHistory(data);
  const likes = extractLikes(data);
  const comments = extractComments(data);
  const shares = extractShares(data);
  const browsingHistory = extractBrowsingHistory(data);

  const s = detectSessions(browsingHistory, likes, comments, shares);

  return {
    platform: "tiktok",
    profile: extractProfile(data),
    settings_interests: extractSettingsInterests(data),
    ad_interests: extractAdInterests(data),
    browsing_history: browsingHistory,
    watch_history_full: s.watch_history_full,
    watch_history_active: s.watch_history_active,
    session_metrics: {
      passive_videos_removed: s.passive_videos_removed,
      passive_sessions_detected: s.passive_sessions_detected,
      active_video_count: s.active_video_count,
      session_count: s.session_count,
      avg_session_length_videos: s.avg_session_length_videos,
    },
    likes,
    favorites: extractFavorites(data),
    favorite_collections: extractFavoriteCollections(data),
    searches: extractSearches(data),
    shares,
    comments,
    blocked_users: extractBlocked(data),
    following: extractFollowing(data),
    followers: extractFollowers(data),
    login_history: loginHistory,
    login_history_stats: loginStats,
    off_tiktok_activity: extractOffTiktokActivity(data),
    shop_orders: extractShopOrders(data),
    product_browsing: extractProductBrowsing(data),
    dm_count: countDms(data),
  };
}
