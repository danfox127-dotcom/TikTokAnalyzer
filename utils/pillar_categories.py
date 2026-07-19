"""
Pillar Categories & Automated Category Detection.
Maps keywords to content verticals for narrative generation.
"""
from __future__ import annotations

import json
import anthropic
import google.generativeai as genai
from collections import defaultdict

# ---------------------------------------------------------------------------
# Static Fallback Map
# ---------------------------------------------------------------------------

KEYWORD_CATEGORY: dict[str, str] = {
    "work": "labor", "job": "labor", "salary": "labor", "career": "labor",
    "love": "relationships", "dating": "relationships", "toxic": "relationships",
    "funny": "humor", "comedy": "humor", "meme": "humor", "joke": "humor",
    "news": "news", "politics": "news", "election": "news",
    "art": "aesthetics", "design": "aesthetics", "aesthetic": "aesthetics",
    "wellness": "wellness", "anxiety": "wellness", "therapy": "wellness",
    "money": "finance", "investing": "finance", "crypto": "finance",
    "gaming": "gaming", "game": "gaming", "minecraft": "gaming",
    "food": "food", "recipe": "food", "cooking": "food",
    "parenting": "parenting", "baby": "parenting", "kids": "parenting",
    "fitness": "fitness", "workout": "fitness", "gym": "fitness",
    "tech": "tech", "coding": "tech", "ai": "tech", "software": "tech",
    "music": "music", "song": "music", "artist": "music",
    "style": "fashion", "outfit": "fashion", "makeup": "fashion",
    "spirituality": "spirituality", "zodiac": "spirituality",
    "sports": "sports", "football": "sports", "basketball": "sports",
}

CATEGORY_PHRASES: dict[str, str] = {
    "labor": "the hustle and the grind",
    "relationships": "love, longing, and the people in your life",
    "humor": "comedy and absurdity",
    "news": "the state of the world",
    "aesthetics": "visual worlds and artistic sensibility",
    "wellness": "mental health and self-care",
    "finance": "money and financial independence",
    "gaming": "games and virtual worlds",
    "food": "food, cooking, and culinary culture",
    "parenting": "parenthood and family life",
    "fitness": "body, movement, and physical challenge",
    "tech": "technology and digital tools",
    "music": "sound and musical culture",
    "fashion": "style, beauty, and self-expression",
    "spirituality": "meaning, ritual, and the metaphysical",
    "sports": "competition, teams, and the arena",
    "hobbies": "niche interests and personal craft",
    "local_life": "the physical world and local neighborhoods",
}

# ---------------------------------------------------------------------------
# Public Functions
# ---------------------------------------------------------------------------

def categorize(keyword: str) -> str | None:
    """Return the category for a keyword (static fallback)."""
    kw = keyword.lower().strip()
    if kw in KEYWORD_CATEGORY:
        return KEYWORD_CATEGORY[kw]
    for key, cat in KEYWORD_CATEGORY.items():
        if key in kw:
            return cat
    return None

def top_category(keywords: list[dict]) -> tuple[str, float]:
    """Identify the dominant category from a weighted keyword list."""
    category_weight: dict[str, float] = defaultdict(float)
    total_weight: float = 0.0

    for kw in keywords:
        term, count = kw.get("term", ""), float(kw.get("count", 1))
        total_weight += count
        cat = categorize(term)
        if cat:
            category_weight[cat] += count

    if not category_weight:
        return ("humor", 0.0)

    best_cat = max(category_weight, key=lambda c: category_weight[c])
    confidence = category_weight[best_cat] / total_weight if total_weight else 0.0
    return (best_cat, round(confidence, 3))

async def generate_pillars_llm(
    vibe_cluster: list[dict],
    graveyard: list[dict],
    interest_clusters: list[dict],
    api_key: str,
    provider: str = "claude",
) -> list[dict]:
    """
    Send the behavioral fingerprint to an LLM and get back 2-4 named pillars,
    each with evidence (what fed it), the advertiser consequence, and the misfire.
    """
    if not vibe_cluster:
        return []

    vibe_lines = "\n".join(
        f"- {c.get('handle', '?')} ({c.get('genre', '?')}): {c.get('linger_count', 0)} lingered"
        for c in vibe_cluster[:15]
    )
    grave_lines = "\n".join(
        f"- {c.get('handle', '?')} ({c.get('genre', '?')}): {c.get('skip_count', 0)} skips"
        for c in graveyard[:10]
    )
    topic_lines = ", ".join(c.get("term", "") for c in interest_clusters[:20])

    prompt = f"""You are analyzing someone's TikTok behavioral data to identify how the algorithm has profiled them.

CREATORS THEY LINGERED ON (watched 15+ seconds):
{vibe_lines}

CREATORS THEY IMMEDIATELY SKIPPED (<3 seconds):
{grave_lines}

TOP TOPICS (from searches and comments):
{topic_lines}

Based on this, identify 2 to 4 "Pillars" — the core identity buckets TikTok has placed this person in. Each pillar should explain what category TikTok has them in, why, what kind of ads that unlocks, and where the algorithm gets it wrong.

Use plain, direct language. No jargon. Write like you're explaining it to a smart 16-year-old.

Respond with a JSON array only — no explanation, no markdown, just the JSON:
[
  {{
    "label": "Short, punchy pillar name (5 words or less)",
    "description": "2-3 sentences. What TikTok thinks you are based on this pillar. Be concrete.",
    "contributing_creators": ["@handle1", "@handle2"],
    "contributing_topics": ["topic1", "topic2"],
    "ad_tier": "One sentence on what kind of ads this pillar unlocks for advertisers.",
    "misfire": "One sentence on what the algorithm gets wrong about you because of this pillar."
  }}
]"""

    try:
        if provider == "claude":
            client = anthropic.AsyncAnthropic(api_key=api_key)
            response = await client.messages.create(
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
                model="claude-haiku-4-5",
            )
            raw_text = response.content[0].text
        elif provider.startswith("gemini"):
            genai.configure(api_key=api_key)
            model_name = "gemini-2.0-flash" if "flash" in provider else "gemini-2.0-pro"
            model = genai.GenerativeModel(model_name)
            response = await model.generate_content_async(prompt)
            raw_text = response.text
        else:
            return []

        start = raw_text.find("[")
        end = raw_text.rfind("]") + 1
        if start != -1 and end > start:
            return json.loads(raw_text[start:end])
        return []
    except Exception as e:
        print(f"Pillar Generation Error: {e}")
        return []


async def categorize_keywords_llm(
    keywords: list[dict], 
    api_key: str, 
    provider: str = "claude"
) -> dict[str, str]:
    """
    Use an LLM to assign categories to a list of keywords.
    Returns a map of keyword -> category.
    """
    terms = [kw.get("term") for kw in keywords if kw.get("term")]
    if not terms:
        return {}

    prompt = f"""
Assign one of these categories to each keyword: 
labor, relationships, humor, news, aesthetics, wellness, finance, gaming, food, parenting, fitness, tech, music, fashion, spirituality, sports, hobbies, local_life.

KEYWORDS: {", ".join(terms)}

RESPONSE FORMAT (JSON):
{{ "keyword": "category" }}
"""

    try:
        if provider == "claude":
            client = anthropic.AsyncAnthropic(api_key=api_key)
            response = await client.messages.create(
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
                model="claude-haiku-4-5",
            )
            raw_text = response.content[0].text
        elif provider.startswith("gemini"):
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-3-flash")
            response = await model.generate_content_async(prompt)
            raw_text = response.text
        else:
            return {}

        start, end = raw_text.find("{"), raw_text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(raw_text[start:end])
        return {}
    except Exception as e:
        print(f"Keyword Categorization Error: {e}")
        return {}
