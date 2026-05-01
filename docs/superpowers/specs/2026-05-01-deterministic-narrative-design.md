# Deterministic Narrative Block System (Part 2C)

## Goal

Add a server-side deterministic narrative layer that transforms the ghost profile into a human-readable dossier. Nine structured "blocks" — each with prose, stats, and optional charts — are embedded in the `/api/analyze` response and rendered in a new "DOSSIER" view in the frontend. No LLM required; all prose is generated from templates keyed on real behavioral signals.

## Architecture

A new `api/narratives.py` module receives the parsed export and ghost profile, produces a list of block dicts, and appends them to the existing `/api/analyze` response as `narrative_blocks`. A new `utils/ip_geo.py` module provides IP geolocation used by Block 8. The frontend gains a new `NarrativeReportView` component and a generic `BlockCard` renderer backed by Recharts.

This is additive — the existing `/api/analyze` response shape is unchanged; `narrative_blocks` is a new top-level key.

---

## Backend

### New module: `api/narratives.py`

**Exports one function:**

```python
def build_narrative_blocks(
    ghost_profile: dict,
    parsed: dict
) -> list[dict]
```

Returns an ordered list of 9 block dicts. Each block has the schema:

```python
{
    "id": str,           # snake_case identifier, e.g. "algorithmic_identity"
    "title": str,        # display title, e.g. "ALGORITHMIC IDENTITY"
    "icon": str,         # single emoji
    "prose": str,        # 2-4 sentence generated paragraph
    "accent": str,       # hex color e.g. "#4db8ff"
    "stats": [           # 0-6 key/value pairs
        {"label": str, "value": str}
    ],
    "chart": {           # optional — omitted if no chart
        "type": "bar" | "line" | "donut",
        "data": list[dict]   # Recharts-compatible array
    } | None
}
```

**Prose generation:** Template strings with conditional branches. Each block has 3-5 templates that select based on signal thresholds (e.g., high engagement ratio → "Your content finds an unusually engaged audience..."). No external dependencies, no randomness — same input always produces same output.

### The 9 Blocks

| # | id | title | icon | Chart type |
|---|-----|-------|------|------------|
| 1 | `algorithmic_identity` | ALGORITHMIC IDENTITY | 🎭 | donut (category mix) |
| 2 | `attention_signature` | ATTENTION SIGNATURE | 👁️ | bar (engagement breakdown) |
| 3 | `dayparting` | DAILY RHYTHM | 🕐 | bar (views by hour 0-23) |
| 4 | `social_graph` | SOCIAL GRAPH | 🕸️ | bar (followed vs watched top creators) |
| 5 | `share_behavior` | SHARE BEHAVIOR | 🔗 | donut (topic mix of shared videos) |
| 6 | `comment_voice` | COMMENT VOICE | 💬 | none |
| 7 | `transparency_gap` | TRANSPARENCY GAP | 🔍 | bar (data category counts) |
| 8 | `location_trace` | WHERE TIKTOK FOUND YOU | 📍 | none |
| 9 | `closing_synthesis` | CLOSING SYNTHESIS | 🧠 | none |

### Block Details

**Block 1 — ALGORITHMIC IDENTITY**
- Signals: top content categories by watch time, like ratio per category, dominant viewing mode (discovery vs. follow)
- Stats: top 3 categories, % of time in each, dominant mode label
- Chart: donut — category distribution by watch time
- Prose template selects on: creator-follow-heavy vs. FYP-heavy; niche vs. broad taste

**Block 2 — ATTENTION SIGNATURE**
- Signals: avg. video completion %, like/view ratio, comment/view ratio, share/view ratio
- Stats: completion %, like rate, comment rate, share rate
- Chart: horizontal bar — one bar per metric as % of max possible
- Prose template selects on: high completer vs. scroller; active vs. passive engager

**Block 3 — DAILY RHYTHM** (replaces "Night Mode")
- Signals: view timestamps bucketed by hour (0-23), peak hour, night-owl flag (>30% views 22:00-04:00)
- Stats: peak viewing hour, peak day-of-week, night-owl label
- Chart: bar — 24 bars, one per hour, height = view count
- Prose template selects on: morning/afternoon/evening/night dominant window; weekend vs. weekday skew

**Block 4 — SOCIAL GRAPH**
- Signals: followed creator list vs. most-watched creators (by view count); overlap %; top 5 watched-not-followed
- Stats: total followed, unique creators watched, % overlap, top unwatched-follows count
- Chart: grouped bar — top 10 creators: bars for "followed" and "watched" side by side
- Prose template selects on: high overlap (loyalty) vs. low overlap (discovery-driven); follower-count spread

**Block 5 — SHARE BEHAVIOR**
- Signals: share count, topics/categories of shared videos, share rate vs. population norm (if available), top shared creator
- Stats: total shares, top shared topic, top shared creator, share-to-like ratio
- Chart: donut — topic mix of shared content
- Prose template selects on: sharer vs. lurker; niche sharer vs. broad curator

**Block 6 — COMMENT VOICE**
- Signals: comment count, avg. comment length, question ratio (comments ending in "?"), comment topic clustering (simple keyword match on nouns)
- Stats: total comments, avg. length (words), question ratio, most-commented creator
- Chart: none
- Prose template selects on: frequent vs. rare commenter; long-form vs. short reaction; question-asker vs. reactor

**Block 7 — TRANSPARENCY GAP**
- Signals: data categories present in export vs. expected full set; number of logins, devices, IP addresses; off-platform activity signals
- Stats: data categories found, unique IPs, unique devices, login count
- Chart: bar — one bar per data category, height = record count
- Prose template selects on: data-rich export vs. sparse; many devices vs. single device; high IP diversity vs. single location

**Block 8 — WHERE TIKTOK FOUND YOU**
- Signals: login IP addresses → geolocated city/country via `utils/ip_geo.py`; first login timestamp; most frequent login city
- Stats: countries seen, cities seen, first login date, home city (most frequent)
- Chart: none
- Prose template selects on: single-location vs. frequent traveler; first login recency; international vs. domestic

**Block 9 — CLOSING SYNTHESIS**
- Signals: aggregated cross-block signals — dominant mode, engagement persona, privacy exposure level
- Stats: none (prose only)
- Chart: none
- Prose: 3-4 sentences synthesizing the profile. Template selects on combinations of: high/low engagement × discovery/loyalty mode × data-rich/sparse export

### New module: `utils/ip_geo.py`

```python
# Calls https://api.iplocation.net/?ip={ip}
# In-process dict cache (ip → result), no TTL (IPs don't change within a run)
# 2s timeout, graceful fallback: returns {"city": "Unknown", "country_name": "Unknown"}
# Uses httpx.AsyncClient

async def geolocate_ip(ip: str) -> dict:
    ...

async def enrich_logins_with_geo(logins: list[dict]) -> list[dict]:
    # Enriches each login entry that has an "ip" field
    # with "city" and "country_name" from geolocate_ip
    # Returns a new list; deduplicates IPs so each unique IP is fetched at most once
    ...
```

**Integration point:** IP geo enrichment runs in the async `/api/analyze` route handler in `main.py`, not inside `build_ghost_profile` (which remains sync). After calling `build_ghost_profile`, the route handler calls `enrich_logins_with_geo` and attaches the enriched logins back to the ghost profile before calling `build_narrative_blocks`.

### Integration in `api/main.py`

In the `/api/analyze` route, after `build_ghost_profile` and before returning:

```python
from api.narratives import build_narrative_blocks

narrative_blocks = build_narrative_blocks(ghost_profile, parsed)
return {
    **existing_response,
    "narrative_blocks": narrative_blocks
}
```

### New dependencies in `requirements.txt`

- `httpx>=0.27.0` — async HTTP for IP geolocation (replaces `requests` for async context)

---

## Frontend

### New view: `"report"` in `page.tsx`

Add `"report"` to the `View` type. TheGlassHouse gets an `onOpenReport` prop → navigates to `"report"` view. Button label: "DOSSIER →" placed next to the download button in the header. The `analysisResult` (already in page state) is passed to `NarrativeReportView` as `narrativeBlocks={analysisResult.narrative_blocks}`.

### New component: `algorithmic-mirror/app/components/NarrativeReportView.tsx`

**Props:** `{ narrativeBlocks: NarrativeBlock[]; onBack: () => void }`

**Layout:**
```
NarrativeReportView
├── Header: "DOSSIER" label + "← Back" button
├── Scrollable column (max-w-2xl, mx-auto, py-8, gap-6)
│   └── {narrativeBlocks.map(block => <BlockCard key={block.id} block={block} />)}
```

### New component: `algorithmic-mirror/app/components/BlockCard.tsx`

**Props:** `{ block: NarrativeBlock }`

**Layout (top to bottom):**
1. Left-border accent bar (4px, `block.accent` color) + icon + title row
2. Prose paragraph (monospace, `--text` color, leading-relaxed)
3. Stats row: `<dl>` with label/value pairs in a 2-3 column grid
4. Chart area (if `block.chart`): dispatches to `<BlockBarChart>`, `<BlockLineChart>`, or `<BlockDonutChart>`

**Chart subcomponents** (all in same file or a `charts/` subfolder):
- `BlockBarChart` — Recharts `<BarChart>` horizontal or vertical based on data length
- `BlockDonutChart` — Recharts `<PieChart>` with `innerRadius`
- (No `BlockLineChart` needed — no current block uses `"line"` type; `"line"` remains in the TypeScript union for future extensibility)
- All charts: dark background, `--accent` fill color, no axis lines, minimal labels

### TypeScript types

New `types/narrative.ts`:
```ts
export interface NarrativeStat {
  label: string;
  value: string;
}

export interface NarrativeChart {
  type: "bar" | "line" | "donut";
  data: Record<string, unknown>[];
}

export interface NarrativeBlock {
  id: string;
  title: string;
  icon: string;
  prose: string;
  accent: string;
  stats: NarrativeStat[];
  chart?: NarrativeChart;
}
```

### New dependency

```json
"recharts": "^2.12.0"
```

---

## Styling

Matches dark surveillance aesthetic: monospace throughout, `--bg` background, accent border per block (varies), prose in `--text`. Stats in a subtle grid with `--surface` background cells. Charts use `--accent` as primary fill, `--surface` as background, no grid lines.

---

## Out of Scope

- Editable/interactive narrative (future)
- Export to PDF or image (future)
- User annotations on blocks (future)
- Per-block LLM "expand" button (future — ties into Part 2B)
- Population-norm comparisons (requires backend aggregate data)

---

## Testing

**Backend:**
- Unit tests for each of the 9 `_build_*_block` functions in `narratives.py`
- `geolocate_ip`: mock HTTP, test cache hit, test timeout fallback
- Integration: POST a real export fixture to `/api/analyze`, assert `narrative_blocks` has 9 items with correct schema

**Frontend:**
- `BlockCard`: renders prose, stats, chart for a mock block; renders correctly when `chart` is absent
- `NarrativeReportView`: renders all blocks from mock array; Back button calls `onBack`
- Chart subcomponents: snapshot tests for bar and donut with minimal mock data
