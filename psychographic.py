import re
import sys
import os
from collections import Counter

# Ensure repo root is importable when this module is loaded directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.pillar_categories import top_category, CATEGORY_PHRASES

# Common stop words to ignore when extracting themes
STOP_WORDS = {
    "the",
    "and",
    "to",
    "of",
    "a",
    "in",
    "is",
    "for",
    "on",
    "you",
    "that",
    "this",
    "it",
    "with",
    "as",
    "at",
    "are",
    "be",
    "your",
    "my",
    "from",
    "so",
    "but",
    "not",
    "have",
    "we",
    "all",
    "can",
    "by",
    "if",
    "or",
    "an",
    "do",
    "what",
    "just",
    "about",
    "like",
    "how",
    "out",
    "up",
    "when",
    "was",
    "will",
    "they",
    "me",
    "get",
    "no",
    "one",
    "there",
    "more",
    "who",
    "has",
}


# Emoji ranges used to capture common emoji characters
EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF\U0001FA70-\U0001FAFF]",
    flags=re.UNICODE,
)


def extract_themes(titles: list[str], top_k: int = 18, top_p: int = 12) -> dict:
    """Extract top keywords and common phrase bigrams from a list of titles.

    This function additionally extracts hashtags (without the leading '#') and
    collects simple emoji tokens separately to be rendered uniquely in the HUD.
    """

    words: list[str] = []
    phrases: list[str] = []
    emojis_list: list[str] = []

    for title in titles:
        if not title or title == "Title Hidden" or title == "No Caption (Just Hashtags)":
            continue

        # Extract hashtags (keep without '#')
        hashtags = re.findall(r"#([^\s#]+)", title.lower())
        for h in hashtags:
            if h and h not in STOP_WORDS:
                words.append(h)

        # Extract emoji tokens and keep them separately
        extracted_emojis = EMOJI_PATTERN.findall(title)
        for e in extracted_emojis:
            emojis_list.append(e)

        # Basic cleanup for word tokens: remove punctuation but keep alphanumerics
        clean_title = re.sub(r"[^\w\s]", "", title.lower())
        tokens = clean_title.split()

        # build bigrams from adjacent tokens (skip stop words)
        for i in range(len(tokens) - 1):
            if tokens[i] not in STOP_WORDS and tokens[i + 1] not in STOP_WORDS:
                phrases.append(f"{tokens[i]} {tokens[i+1]}")

        # add single-word tokens (filter short words/stop words)
        for token in tokens:
            if len(token) > 2 and token not in STOP_WORDS:
                words.append(token)

    word_counts = Counter(words).most_common(top_k)
    phrase_counts = Counter(phrases).most_common(top_p)
    emoji_counts = Counter(emojis_list).most_common(top_k)

    return {
        "top_keywords": [{"term": k, "count": v} for k, v in word_counts],
        "top_phrases": [{"phrase": k, "count": v} for k, v in phrase_counts],
        "top_emojis": [{"emoji": k, "count": v} for k, v in emoji_counts],
    }


# ---------------------------------------------------------------------------
# Headline templates per pillar
# ---------------------------------------------------------------------------

_HEADLINE_TEMPLATES: dict[str, str] = {
    "psychographic": "The algorithm believes you are drawn to {category_phrase}.",
    "anti_profile":  "The algorithm tested {category_phrase} on you. You refused.",
    "sandbox":       "Currently under evaluation: {category_phrase}.",
    "night":         "After midnight, you become someone who watches {category_phrase}.",
}

# Interpretation sentence library keyed by category.
# Each entry is a 2–3 sentence second-person description.
_INTERPRETATIONS: dict[str, dict[str, str]] = {
    "psychographic": {
        "labor": (
            "You spend real time with content about work, hustle, and career. "
            "The algorithm has clocked this and is building a theory: you are someone "
            "preoccupied with how labour shapes identity."
        ),
        "relationships": (
            "You linger on content about love, connection, and the people close to you. "
            "The algorithm reads this as emotional investment — it thinks you are "
            "navigating something personal."
        ),
        "humor": (
            "You reliably pause for comedy. The algorithm has noted your appetite for "
            "absurdity and treats you as someone who uses laughter to process the world."
        ),
        "news": (
            "You stay with content about politics and current events. "
            "The algorithm classifies you as civically engaged and feeds you accordingly."
        ),
        "aesthetics": (
            "You are drawn to visual craft — the way things look and feel. "
            "The algorithm has marked you as someone with a strong aesthetic sensibility."
        ),
        "wellness": (
            "You spend time with content about mental health and self-care. "
            "The algorithm has inferred you are either struggling or actively working on yourself."
        ),
        "finance": (
            "You watch content about money, investing, and financial independence. "
            "The algorithm thinks you are anxious about or aspiring toward financial control."
        ),
        "gaming": (
            "You linger on gaming content. The algorithm has filed you under 'player' "
            "and is routing you deeper into that community."
        ),
        "food": (
            "You stay for food content — recipes, restaurants, culinary culture. "
            "The algorithm thinks you are either a cook or someone who eats with intention."
        ),
        "parenting": (
            "You spend time with content about children and family life. "
            "The algorithm has inferred that parenthood, real or anticipated, is on your mind."
        ),
        "fitness": (
            "You linger on fitness content. The algorithm has categorised you as "
            "body-aware and motivated by physical challenge."
        ),
        "tech": (
            "You watch content about technology and digital tools. "
            "The algorithm has flagged you as technically curious and early-adopter-adjacent."
        ),
        "music": (
            "You stay with music content — artists, genres, culture. "
            "The algorithm reads you as someone for whom sound is a primary emotional language."
        ),
        "fashion": (
            "You linger on style and beauty content. "
            "The algorithm has decided you care about self-presentation and how things look on a body."
        ),
        "spirituality": (
            "You spend time with content about meaning, ritual, and the metaphysical. "
            "The algorithm thinks you are searching for something beyond the material."
        ),
        "humor": (
            "You reliably pause for comedy and absurdity. "
            "The algorithm treats you as someone who uses laughter as a coping mechanism "
            "and a lens on the world."
        ),
    },
    "anti_profile": {
        "labor": (
            "Content about career hustle was served and skipped. "
            "You are not interested in being optimised."
        ),
        "relationships": (
            "Relationship content failed to hold you. "
            "You may have no patience for performed vulnerability."
        ),
        "humor": (
            "Comedy content was offered and declined. "
            "You are not here to be entertained on those terms."
        ),
        "news": (
            "News and politics content was rejected at speed. "
            "You are either over-informed or deliberately disengaged."
        ),
        "aesthetics": (
            "Visual and aesthetic content failed to land. "
            "You are not moved by beauty for its own sake right now."
        ),
        "wellness": (
            "Wellness content was skipped without lingering. "
            "You have no patience for self-help framing."
        ),
        "finance": (
            "Finance content did not hold your attention. "
            "You are either already settled on these questions or actively avoidant."
        ),
        "gaming": (
            "Gaming content was passed over quickly. "
            "This is not the community the algorithm thought it could route you into."
        ),
        "food": (
            "Food content was not for you — or not today. "
            "The algorithm misjudged this appetite."
        ),
        "parenting": (
            "Parenting content was skipped. "
            "The algorithm tested this angle and found no purchase."
        ),
        "fitness": (
            "Fitness content was declined at speed. "
            "You are not here for body optimisation."
        ),
        "tech": (
            "Tech content was offered and rejected. "
            "You are not engaging with the algorithm's model of you as a tech consumer."
        ),
        "music": (
            "Music content failed to hold you. "
            "The algorithm's read of your taste in sound was off."
        ),
        "fashion": (
            "Style and beauty content was skipped. "
            "The algorithm's attempt to route you through aesthetics did not land."
        ),
        "spirituality": (
            "Spiritual and metaphysical content was passed over. "
            "You are not interested in the algorithm's theory of your inner life."
        ),
    },
    "sandbox": {
        "labor": "The algorithm is probing whether work content can hook you. Verdict is still out.",
        "relationships": "Relationship content is being tested against your attention. No commitment yet.",
        "humor": "Comedy is being sampled. The algorithm is checking whether this is a lane you live in.",
        "news": "News content is in the trial phase. The algorithm is watching whether you bite.",
        "aesthetics": "Visual content is being evaluated. The algorithm does not know your aesthetic yet.",
        "wellness": "Wellness content is being trialled. The algorithm is probing for a soft spot.",
        "finance": "Finance content is in evaluation. The algorithm is checking whether money anxiety sticks.",
        "gaming": "Gaming content is on trial. The algorithm is trying to route you into this community.",
        "food": "Food content is being sampled. The algorithm is checking your appetite.",
        "parenting": "Parenting content is being probed. The algorithm is testing a theory about your life stage.",
        "fitness": "Fitness content is in trial. The algorithm is checking whether body content holds you.",
        "tech": "Tech content is being evaluated. The algorithm is probing your digital curiosity.",
        "music": "Music content is being sampled. The algorithm is testing its read of your taste.",
        "fashion": "Style content is in evaluation. The algorithm is trying to find your aesthetic lane.",
        "spirituality": "Spiritual content is being probed. The algorithm is testing whether meaning-content sticks.",
    },
    "night": {
        "labor": (
            "After midnight you watch work content. "
            "The algorithm has noticed that anxiety about labour surfaces when your defences are down."
        ),
        "relationships": (
            "Late at night you turn to content about love and connection. "
            "The algorithm reads this as longing or processing — something you keep private during the day."
        ),
        "humor": (
            "After midnight you reach for comedy. "
            "The algorithm has marked late-night as your window for absurdity and release."
        ),
        "news": (
            "You consume news late at night. "
            "The algorithm reads this as a form of vigilance — you need to know what is happening before you sleep."
        ),
        "aesthetics": (
            "You turn to visual and aesthetic content after midnight. "
            "The algorithm has noted that beauty is part of your wind-down."
        ),
        "wellness": (
            "Late-night you turn to mental health and self-care content. "
            "The algorithm reads this as a private ritual — the version of you that surfaces at 2am."
        ),
        "finance": (
            "After midnight you watch finance content. "
            "The algorithm has filed this under nocturnal money anxiety."
        ),
        "gaming": (
            "Late at night you watch gaming content. "
            "The algorithm reads this as your leisure mode — the self that emerges after obligations end."
        ),
        "food": (
            "After midnight you turn to food content. "
            "The algorithm has noted that appetite — for food or something else — surfaces late."
        ),
        "parenting": (
            "You watch parenting content late at night. "
            "The algorithm reads this as a private preoccupation — something you process in the quiet hours."
        ),
        "fitness": (
            "Late at night you turn to fitness content. "
            "The algorithm has noted that motivation or guilt about the body surfaces when the day is done."
        ),
        "tech": (
            "You consume tech content after midnight. "
            "The algorithm has filed you as someone who thinks about tools and systems late into the night."
        ),
        "music": (
            "After midnight you turn to music content. "
            "The algorithm reads this as your most unguarded mode — sound as a private companion."
        ),
        "fashion": (
            "Late at night you watch style and beauty content. "
            "The algorithm has noted that identity curation happens for you in the quiet hours."
        ),
        "spirituality": (
            "After midnight you turn to spiritual and metaphysical content. "
            "The algorithm reads this as your seeking mode — questions about meaning that surface when the day falls away."
        ),
    },
}

_FALLBACK_INTERPRETATION: dict[str, str] = {
    "psychographic": (
        "You have a consistent pattern of attention that the algorithm has already mapped. "
        "These are the terms it associates with you."
    ),
    "anti_profile": (
        "This content was served and skipped. "
        "What you reject reveals as much about you as what you accept."
    ),
    "sandbox": (
        "This content is in the trial phase. "
        "The algorithm is testing whether it can hook you here."
    ),
    "night": (
        "Late-night attention has its own logic. "
        "This is what you watch when the day's identity falls away."
    ),
}


def build_pillar_narrative(
    pillar: str,
    keywords: list[dict],
    phrases: list[dict],
    emojis: list[dict],
    sample_titles: list[str],
) -> dict:
    """
    Build a deterministic narrative card for a psychographic pillar.

    Parameters
    ----------
    pillar : str
        One of "psychographic", "anti_profile", "sandbox", "night".
    keywords : list[dict]
        Top keyword dicts with 'term' and 'count' keys.
    phrases : list[dict]
        Top phrase dicts with 'phrase' and 'count' keys.
    emojis : list[dict]
        Top emoji dicts with 'emoji' and 'count' keys.
    sample_titles : list[str]
        Video titles from this bucket, ranked by relevance (time_spent or skip-speed).

    Returns
    -------
    dict with keys: headline (str), interpretation (str), evidence (list[str])
    """
    pillar = pillar if pillar in _HEADLINE_TEMPLATES else "psychographic"

    category, _confidence = top_category(keywords)
    category_phrase = CATEGORY_PHRASES.get(category, "content the algorithm has catalogued")

    headline_tmpl = _HEADLINE_TEMPLATES[pillar]
    headline = headline_tmpl.format(category_phrase=category_phrase)

    pillar_library = _INTERPRETATIONS.get(pillar, {})
    interpretation = pillar_library.get(
        category,
        _FALLBACK_INTERPRETATION.get(pillar, "")
    )

    # Evidence: top 3 non-empty titles
    evidence: list[str] = []
    for t in sample_titles:
        t = t.strip()
        if t and t not in ("Title Hidden", "No Caption (Just Hashtags)"):
            evidence.append(t)
        if len(evidence) >= 3:
            break

    return {
        "headline": headline,
        "interpretation": interpretation,
        "evidence": evidence,
    }


def build_anti_profile_signature(
    anti_keywords: list[dict],
    pro_keywords: list[dict],
) -> list[dict]:
    """
    Compute the anti-profile rejection signature: terms that appear in
    graveyard content but not in the top psychographic (lingered) terms.

    If the set-difference yields fewer than 5 terms, the raw anti_keywords
    list is returned as-is (fallback to preserve information).

    Parameters
    ----------
    anti_keywords : list[dict]
        Keyword dicts from graveyard bucket (skipped content).
    pro_keywords : list[dict]
        Keyword dicts from lingered bucket (engaged content).

    Returns
    -------
    list[dict] — filtered or raw keyword dicts.
    """
    pro_terms: set[str] = {kw.get("term", "").lower() for kw in pro_keywords}

    signature = [
        kw for kw in anti_keywords
        if kw.get("term", "").lower() not in pro_terms
    ]

    if len(signature) < 5:
        return anti_keywords  # fallback: not enough contrast, return raw

    return signature
