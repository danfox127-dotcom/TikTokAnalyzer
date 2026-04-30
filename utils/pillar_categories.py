"""
Pillar Categories — static keyword → category map for narrative generation.

~80 entries covering major content verticals. Used by psychographic.py to
infer which category best characterises a keyword cluster, then select the
matching interpretation sentence from the library.

Public API
----------
    categorize(keyword: str) -> str | None
    top_category(keywords: list[dict]) -> tuple[str, float]
        Returns (category_name, confidence_0_to_1).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Keyword → Category map
# Each keyword is lowercased. Partial-match logic handled in categorize().
# ---------------------------------------------------------------------------

KEYWORD_CATEGORY: dict[str, str] = {
    # labor / work
    "work": "labor",
    "job": "labor",
    "boss": "labor",
    "salary": "labor",
    "career": "labor",
    "office": "labor",
    "hustle": "labor",
    "grind": "labor",
    "freelance": "labor",
    "startup": "labor",
    "entrepreneur": "labor",
    "corporate": "labor",
    "layoff": "labor",
    "interview": "labor",
    "resume": "labor",

    # relationships
    "love": "relationships",
    "dating": "relationships",
    "relationship": "relationships",
    "boyfriend": "relationships",
    "girlfriend": "relationships",
    "marriage": "relationships",
    "breakup": "relationships",
    "toxic": "relationships",
    "situationship": "relationships",
    "heartbreak": "relationships",
    "crush": "relationships",
    "romance": "relationships",
    "couple": "relationships",

    # humor
    "funny": "humor",
    "comedy": "humor",
    "meme": "humor",
    "prank": "humor",
    "skit": "humor",
    "roast": "humor",
    "joke": "humor",
    "lol": "humor",
    "lmao": "humor",
    "humor": "humor",
    "parody": "humor",

    # news / politics
    "news": "news",
    "politics": "news",
    "election": "news",
    "government": "news",
    "protest": "news",
    "policy": "news",
    "senate": "news",
    "congress": "news",
    "democracy": "news",
    "rights": "news",
    "war": "news",
    "climate": "news",
    "trump": "news",
    "biden": "news",

    # aesthetics / art
    "aesthetic": "aesthetics",
    "art": "aesthetics",
    "photography": "aesthetics",
    "design": "aesthetics",
    "vintage": "aesthetics",
    "minimalist": "aesthetics",
    "cottagecore": "aesthetics",
    "dark": "aesthetics",
    "grunge": "aesthetics",
    "anime": "aesthetics",
    "illustration": "aesthetics",

    # wellness / mental health
    "wellness": "wellness",
    "anxiety": "wellness",
    "depression": "wellness",
    "therapy": "wellness",
    "mindfulness": "wellness",
    "selfcare": "wellness",
    "healing": "wellness",
    "mentalhealth": "wellness",
    "meditation": "wellness",
    "burnout": "wellness",
    "trauma": "wellness",

    # finance
    "money": "finance",
    "investing": "finance",
    "stocks": "finance",
    "crypto": "finance",
    "budget": "finance",
    "debt": "finance",
    "savings": "finance",
    "finance": "finance",
    "wealth": "finance",
    "taxes": "finance",
    "real estate": "finance",
    "frugal": "finance",

    # gaming
    "gaming": "gaming",
    "game": "gaming",
    "minecraft": "gaming",
    "fortnite": "gaming",
    "roblox": "gaming",
    "fps": "gaming",
    "rpg": "gaming",
    "esports": "gaming",
    "twitch": "gaming",
    "streamer": "gaming",
    "playstation": "gaming",
    "xbox": "gaming",
    "nintendo": "gaming",

    # food
    "food": "food",
    "recipe": "food",
    "cooking": "food",
    "baking": "food",
    "restaurant": "food",
    "vegan": "food",
    "foodie": "food",
    "meal": "food",
    "snack": "food",
    "dessert": "food",
    "coffee": "food",
    "kitchen": "food",

    # parenting
    "parenting": "parenting",
    "mom": "parenting",
    "dad": "parenting",
    "baby": "parenting",
    "toddler": "parenting",
    "pregnancy": "parenting",
    "motherhood": "parenting",
    "fatherhood": "parenting",
    "kids": "parenting",
    "children": "parenting",

    # fitness
    "fitness": "fitness",
    "workout": "fitness",
    "gym": "fitness",
    "weightlifting": "fitness",
    "running": "fitness",
    "yoga": "fitness",
    "pilates": "fitness",
    "bodybuilding": "fitness",
    "cardio": "fitness",
    "diet": "fitness",
    "nutrition": "fitness",

    # tech
    "tech": "tech",
    "coding": "tech",
    "programming": "tech",
    "software": "tech",
    "developer": "tech",
    "ai": "tech",
    "robot": "tech",
    "iphone": "tech",
    "android": "tech",
    "apple": "tech",
    "google": "tech",
    "cybersecurity": "tech",
    "hacking": "tech",

    # music
    "music": "music",
    "song": "music",
    "album": "music",
    "artist": "music",
    "rap": "music",
    "hiphop": "music",
    "pop": "music",
    "indie": "music",
    "concert": "music",
    "playlist": "music",
    "spotify": "music",
    "lyrics": "music",

    # fashion
    "fashion": "fashion",
    "style": "fashion",
    "outfit": "fashion",
    "clothes": "fashion",
    "ootd": "fashion",
    "thrift": "fashion",
    "streetwear": "fashion",
    "luxury": "fashion",
    "skincare": "fashion",
    "makeup": "fashion",
    "beauty": "fashion",
    "nails": "fashion",

    # spirituality
    "spirituality": "spirituality",
    "astrology": "spirituality",
    "zodiac": "spirituality",
    "tarot": "spirituality",
    "manifestation": "spirituality",
    "universe": "spirituality",
    "faith": "spirituality",
    "prayer": "spirituality",
    "god": "spirituality",
    "witch": "spirituality",
    "ritual": "spirituality",
    "chakra": "spirituality",
}

# Human-readable display phrases for each category (used in headline templates)
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
}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def categorize(keyword: str) -> str | None:
    """
    Return the category for a keyword, or None if unrecognised.
    Matching is case-insensitive. Tries exact match first, then
    checks whether the keyword contains any known key as a substring.
    """
    kw = keyword.lower().strip()
    if kw in KEYWORD_CATEGORY:
        return KEYWORD_CATEGORY[kw]
    # Substring fallback: keyword contains a known map key
    for key, cat in KEYWORD_CATEGORY.items():
        if key in kw:
            return cat
    return None


def top_category(keywords: list[dict]) -> tuple[str, float]:
    """
    Given a list of keyword dicts with 'term' and 'count' keys,
    return the (category, confidence) tuple where confidence is the
    fraction of total keyword weight accounted for by that category.

    Falls back to ("humor", 0.0) when no keywords match any category.
    """
    from collections import defaultdict

    category_weight: dict[str, float] = defaultdict(float)
    total_weight: float = 0.0

    for kw in keywords:
        term = kw.get("term", "")
        count = float(kw.get("count", 1))
        cat = categorize(term)
        total_weight += count
        if cat:
            category_weight[cat] += count

    if not category_weight:
        return ("humor", 0.0)

    best_cat = max(category_weight, key=lambda c: category_weight[c])
    confidence = category_weight[best_cat] / total_weight if total_weight else 0.0
    return (best_cat, round(confidence, 3))
