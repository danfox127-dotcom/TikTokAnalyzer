# SYS.TEARDOWN Part 1 — Backend Enrichment
**Date:** 2026-04-30
**Scope:** Tasks 1–5 (session scrubbing, engagement weights, comment voice, share behavior, transparency gap) + Task 6 backend (LLM export generation)
**Part 2 covers:** Task 6 frontend (download button), Task 7 (API key + in-app LLM), Task 8 (narrative UI layers)

---

## Goals

The analyzer currently under-characterizes users because:
1. Behavioral metrics are contaminated by passive/accidental viewing
2. A search and a comment contribute equally to interest inference
3. Comment behavior (how the user engages) is entirely unused
4. Share method is not surfaced
5. There is no comparison between what TikTok officially declares vs. what behavior reveals
6. There is no export pathway for LLM narrative synthesis

---

## Data Flow

```
tiktok.py: parse → _detect_sessions() → watch_history_active
ghost_profile.py: build_ghost_profile(parsed)
  → _run_stopwatch(watch_history_active)         [Task 1 wire-up]
  → _mine_text_footprint(parsed)                 [Task 2, new]
  → analyze_comment_voice(comments)              [Task 3, new]
  → _analyze_share_behavior(shares)              [Task 4, new]
  → calculate_transparency_gap(parsed, profile)  [Task 5, new]
exporters/llm_export.py: generate_llm_export(parsed, profile)  [Task 6]
api/main.py: POST /api/export/llm                              [Task 6]
```

---

## Task 1 — Session-Aware Watch History Scrubbing

**File:** `parsers/tiktok.py`

### New function: `_detect_sessions(browsing_history, likes, comments, shares) -> dict`

1. Build an engagement timestamp set from parsed datetimes of all likes, comments, and shares.
2. Walk `browsing_history` chronologically. Split into sessions on any gap > 30 minutes between consecutive videos.
3. Flag a video as **passive** if it meets either criterion:
   - Delta from the previous video < 2 seconds (autoplay artifact)
   - It belongs to a session where zero engagement timestamps fall within the session's time window AND the session contains 5+ consecutive videos

Note: "watch duration < 3s" from the original spec is dropped — TikTok exports do not include watch duration, only timestamps. The delta-based rules cover the same intent.

4. Return:
   - `watch_history_active` — passive videos filtered out
   - `watch_history_full` — all videos (original list)
   - Stats dict: `passive_videos_removed`, `passive_sessions_detected`, `active_video_count`, `session_count`, `avg_session_length_videos`

### Integration

- `_parse_tiktok_data()` calls `_detect_sessions()` after extracting all engagement lists.
- Output dict gains `watch_history_active`, `watch_history_full` keys.
- `browsing_history` key is preserved as an alias pointing to `watch_history_full` for backward compatibility.
- Session stats are merged into `behavioral_analysis`.
- `night_shift_ratio` is computed against the full history (not active), with `night_shift_passive_adjusted: True` added to signal the correction.

### Ghost profile wire-up

`build_ghost_profile()` updated:
```python
active = parsed.get("watch_history_active") or parsed.get("browsing_history", [])
sw = _run_stopwatch(active, exclude_hours=exclude_hours)
```
Falls back gracefully if session scrubbing data is absent.

---

## Task 2 — Engagement-Weighted Interest Scoring

**File:** `ghost_profile.py`

### New function: `_mine_text_footprint(parsed) -> dict`

Builds a weighted text corpus from all available signal types:

| Source | Weight | Text extracted |
|---|---|---|
| Comments authored | 10 | comment text |
| Favorites/saved | 7 | link URL (keyword hints) |
| Shares via DM | 8 | link URL |
| Shares public | 4 | link URL |
| Account follows | 6 | username |
| Searches | 5 | search term |
| Likes | 3 | link URL |

Each text item is repeated N times (its weight) before joining into a single corpus string. A `source_type` tag travels with each item.

**DM vs. public share classification:** method field values `{"chat_head", "dm", "message", "whatsapp", "instagram", "line", "kakaotalk", "telegram"}` → DM. All others → public. This same classification is reused in Task 4.

### Output: `interest_clusters`

Top 20 keywords + top 10 phrases, each with:
```json
{"term": "finance", "count": 47, "dominant_source": "search"}
```

Added to `build_ghost_profile()` return dict as `interest_clusters`.

---

## Task 3 — Comment Voice Analysis

**File:** `ghost_profile.py`

### New function: `analyze_comment_voice(comments, active_video_count) -> dict`

**Metrics computed:**
- `total_comments`, `avg_length_chars`, `long_comments_count` (>150 chars), `long_comment_pct`
- `top_20_longest`: list of raw comment strings (sorted by length descending)
- `references_detected`: `{category: [matched_terms]}` using keyword dict covering sports teams, TV shows, musicians, political figures, films — same pattern as `NICHE_MAP` in `psychographic.py`
- `emoji_density`: emoji chars / total chars

**Engagement style label derivation (priority order):**
1. Comments < 0.5% of `active_video_count` → `"Lurker"`
2. Avg length > 100, emoji density < 0.05 → `"Analytical Commenter"`
3. Avg length < 40, high comment frequency → `"Reactive Commenter"`
4. Low comment count + high DM share count (passed in) → `"Curator"`
5. Default → `"Community Participant"`

Added to ghost profile output as `comment_voice`. `top_20_longest` is also included directly in `_evidence` for LLM export access.

---

## Task 4 — Share Behavior Analysis

**File:** `ghost_profile.py`

### New function: `_analyze_share_behavior(shares) -> dict`

Uses DM/public classification defined in Task 2.

**Output:**
- `total_shares`, `share_methods: {method: count}`, `primary_share_method`
- `share_behavior_type`:
  - > 70% DM methods → `"Private Curator"`
  - > 50% public methods → `"Public Broadcaster"`
  - Otherwise → `"Mixed Sharer"`

Added to ghost profile output as `share_behavior`. DM share count passed to `analyze_comment_voice()` for Curator label detection.

---

## Task 5 — Transparency Gap Calculation

**File:** `ghost_profile.py`

### New function: `calculate_transparency_gap(parsed, profile) -> dict`

Compares:
- `official_ad_interests`: `parsed.get("ad_interests", [])`
- `behavioral_interest_count`: `len(profile.get("interest_clusters", []))`

**Gap interpretation (three cases):**
1. Official empty AND behavioral > 5 clusters → privacy opt-out message
2. `official_count < behavioral_count * 0.5` → "Significant gap: ~X% underrepresentation"
3. Roughly equal → "Official interests roughly match behavioral profile"

**Output:**
```json
{
  "official_ad_interest_count": 12,
  "behavioral_interest_count": 20,
  "gap_interpretation": "Significant gap: ..."
}
```

Added to ghost profile output as `transparency_gap`. Called after `_mine_text_footprint()` since it needs the interest cluster count.

---

## Task 6 — LLM Export (Backend)

**File:** `exporters/llm_export.py` (new file, new `exporters/` directory)

### Function: `generate_llm_export(parsed, ghost_profile) -> dict`

**PII exclusion rules:**
- Excluded: `watch_history_full`, `watch_history_active`, `browsing_history` (URLs), `login_history` (IPs), `digital_footprint.ip_locations`, `digital_footprint.recent_logins`, any key named `ip`, `email`, `phone`, `dm_count`
- Excluded from `_evidence`: raw link lists

**Included:**
- All ghost_profile fields except excluded above
- `comment_voice` (including `top_20_longest`)
- `share_behavior`, `transparency_gap`, `interest_clusters`
- `behavioral_analysis` summary stats (passive counts, session stats, skip/linger rates)

**`_meta` block:**
```json
{
  "privacy_note": "No watch history URLs, IPs, or personal identifiers are included.",
  "tool_version": "1.0",
  "generated_at": "<ISO timestamp>",
  "instructions_for_llm": "<verbatim from spec>",
  "suggested_opening": "Here is my TikTok behavioral profile...",
  "followup_prompts": [
    "Which vibe vector is being most actively exploited and how?",
    "What does my comment voice reveal that the algorithm doesn't capture?",
    "What content am I likely being served that I'm not aware of?",
    "What does the transparency gap tell you about how TikTok treats my data?"
  ]
}
```

### FastAPI endpoint

`POST /api/export/llm` in `api/main.py`:
- Same file upload interface as `/api/analyze`
- Runs `parse → build_ghost_profile → generate_llm_export`
- Returns JSON with `Content-Disposition: attachment; filename="tiktok_analysis_<date>.json"`

---

## Graceful Degradation

All new fields degrade to empty/zero if source data is absent:
- No comments → `comment_voice` with zero counts, label `"Lurker"`
- No shares → `share_behavior` with `total_shares: 0`, type `"Mixed Sharer"`
- No engagement actions → session scrubbing marks all sessions passive, `watch_history_active` equals full history
- No ad interests → transparency gap uses "likely opt-out" interpretation

---

## Testing

Each task independently testable against the existing `user_data_tiktok.json`:
- Task 1: verify `active_video_count` < `total_videos`, `passive_videos_removed` > 0
- Task 2: verify `interest_clusters` reflects comment terms more heavily than searches
- Task 3: verify `engagement_style_label` feels accurate; inspect `top_20_longest`
- Task 4: verify `share_methods` counts match raw share history
- Task 5: verify gap interpretation matches manually-counted ad_interests
- Task 6: verify export JSON contains no URLs, IPs, or raw history

---

## Out of Scope (Part 2)

- Download button in Next.js frontend
- API key input + in-app LLM analysis panel
- Layered narrative UI restructure (Layers 0–6)
