"""
Creator Registry & Automated Vibe Detection.
Identifies genres and archetypes for TikTok creators using engagement context.
"""
from __future__ import annotations

import json
import anthropic
import google.generativeai as genai

# Handle (lowercase, no @) -> (Genre, Archetype, Confidence)
CREATOR_REGISTRY: dict[str, tuple[str, str, float]] = {
    # Sports
    "chelseafc": ("sports", "The Dedicated Fan", 1.0),
    "premierleague": ("sports", "The Global Spectator", 1.0),
    "nba": ("sports", "The Courtside Analyst", 1.0),
    "masonmount": ("sports", "The Player Tracker", 0.9),
    "reece_james": ("sports", "The Player Tracker", 0.9),

    # Local Life / NYC
    "brooklyn.beckham": ("fashion", "The Lifestyle Observer", 0.5),
    "newyorkcity": ("local_life", "The Urban Resident", 0.8),
    "timeoutnewyork": ("local_life", "The City Curator", 0.9),

    # Parenting
    "uppababy": ("parenting", "The Gear Researcher", 1.0),
    "disney": ("parenting", "The Family Entertainer", 0.7),

    # Tech / Productivity
    "cursor_ai": ("tech", "The AI Optimizer", 1.0),
    "firebase": ("tech", "The Backend Architect", 1.0),
    "marquesbrownlee": ("tech", "The Gadget Guru", 1.0),

    # Humor
    "khaby.lame": ("humor", "The Silent Reactant", 0.9),
}

def get_creator_meta(handle: str) -> dict | None:
    """Return genre and archetype for a given handle if known."""
    clean_handle = handle.lower().lstrip("@")
    if clean_handle in CREATOR_REGISTRY:
        genre, archetype, conf = CREATOR_REGISTRY[clean_handle]
        return {
            "handle": handle,
            "genre": genre,
            "archetype": archetype,
            "confidence": conf
        }
    return None

def resolve_vibe_cluster(vibe_cluster: list[dict]) -> list[dict]:
    """Enrich the vibe cluster with static registry data."""
    enriched = []
    for entry in vibe_cluster:
        handle = entry.get("handle", "")
        meta = get_creator_meta(handle)
        if meta:
            enriched.append({**entry, **meta})
        else:
            enriched.append({**entry, "genre": "unknown", "archetype": "unknown", "confidence": 0.0})
    return enriched

async def enrich_creators_with_llm(
    vibe_cluster: list[dict], 
    api_key: str, 
    provider: str = "claude"
) -> list[dict]:
    """
    Dynamically identify genres and archetypes using creator handles and sample titles.
    """
    targets = [
        c for c in vibe_cluster 
        if c.get("genre") == "unknown" or not c.get("genre")
    ]
    
    if not targets:
        return vibe_cluster

    creator_context = []
    for t in targets:
        titles = ", ".join(t.get("sample_titles", []))
        creator_context.append(f"{t.get('handle')} (Titles: {titles})")

    prompt = f"""
You are a social media forensic analyst. Based on the handles and the titles of videos the user lingered on,
identify the content genre and a 3-word behavioral archetype for each creator.

CONTEXT:
{chr(10).join(creator_context)}

RESPONSE FORMAT (JSON):
{{
  "@handle": {{ "genre": "one-word", "archetype": "Three Word Archetype" }}
}}

STRICT RULES:
1. Return ONLY valid JSON.
2. Archetypes should be evocative (e.g., "The Doomscrolling Catalyst", "The Aspiring Minimalist").
3. Genres: tech, sports, humor, fashion, food, news, wellness, parenting, labor, aesthetics, travel, gaming.
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
            return vibe_cluster

        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start != -1 and end > start:
            llm_results = json.loads(raw_text[start:end])
            # Case- and prefix-insensitive lookup so "@ChelseaFC", "ChelseaFC",
            # "@chelseafc" all match the same vibe_cluster entry.
            normalized = {
                (k or "").lower().lstrip("@"): v for k, v in llm_results.items()
            }
            for c in vibe_cluster:
                key = (c.get("handle") or "").lower().lstrip("@")
                if key and key in normalized:
                    c["genre"] = normalized[key].get("genre", "unknown")
                    c["archetype"] = normalized[key].get("archetype", "unknown")
                    c["confidence"] = 0.8

        return vibe_cluster
    except Exception as e:
        print(f"Creator Enrichment Error: {e}")
        return vibe_cluster

async def cluster_creators_llm(
    vibe_cluster: list[dict],
    api_key: str,
    provider: str = "claude"
) -> list[dict]:
    """
    Identify thematic "Shadow Clusters" across the top creators.
    """
    if not vibe_cluster:
        return []

    creator_summary = []
    for c in vibe_cluster[:15]:
        creator_summary.append(f"- {c.get('handle')}: {c.get('genre')} / {c.get('archetype')}")

    prompt = f"""
Analyze this list of creators the user engages with. Group them into 2-3 "Shadow Clusters" — high-level thematic or psychological patterns the algorithm is using to model the user.

CREATORS:
{chr(10).join(creator_summary)}

RESPONSE FORMAT (JSON Array):
[
  {{
    "label": "Evocative Cluster Name",
    "description": "1-2 sentences on what this pattern suggests about the user's inferred identity (hedged/probabilistic).",
    "creators": ["@handle1", "@handle2"]
  }}
]

Tone: Forensic, Noir, Dark Deco. Use hedged claims (e.g. "suggests a model of", "indicates a potential preference for").
"""

    try:
        if provider == "claude":
            client = anthropic.AsyncAnthropic(api_key=api_key)
            response = await client.messages.create(
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
                model="claude-sonnet-4-5",
            )
            raw_text = response.content[0].text
        elif provider.startswith("gemini"):
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-3-pro")
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
        print(f"Shadow Clustering Error: {e}")
        return []
