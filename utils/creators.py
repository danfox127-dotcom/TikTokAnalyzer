"""
Creator Registry — high-fidelity mapping of TikTok handles to archetypes and genres.
This enables deterministic identification of the 'vibe' without requiring an LLM.
"""

# Handle (lowercase, no @) -> (Genre, Archetype, Confidence)
CREATOR_REGISTRY: dict[str, tuple[str, str, float]] = {
    # Sports
    "chelseafc": ("sports", "The Dedicated Fan", 1.0),
    "premierleague": ("sports", "The Global Spectator", 1.0),
    "nba": ("sports", "The Courtside Analyst", 1.0),
    "masonmount": ("sports", "The Player Tracker", 0.9),
    "reece_james": ("sports", "The Player Tracker", 0.9),
    
    # Local Life / NYC
    "brooklyn.beckham": ("fashion", "The Lifestyle Observer", 0.5), # Noise example
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
    """Enrich the vibe cluster with registry data."""
    enriched = []
    for entry in vibe_cluster:
        handle = entry.get("handle", "")
        meta = get_creator_meta(handle)
        if meta:
            enriched.append({**entry, **meta})
        else:
            enriched.append({**entry, "genre": "unknown", "archetype": "unknown", "confidence": 0.0})
    return enriched
