"""
Golden parity fixture for the WP-1.1 psychographic-primitives port.

Covers the deterministic text/category functions:
  - psychographic.extract_themes  (hashtags, bigrams, word tokens, emojis)
  - pillar_categories.categorize   (exact then ordered-substring keyword map)
  - pillar_categories.top_category (weighted dominant category + confidence)

Parity notes baked into the scenario design:
  - extract_themes uses Counter.most_common(n) == stable sort by count desc, ties
    by first-insertion order. Cases keep counts DISTINCT among returned items so
    ordering + truncation are unambiguous; one explicit tie case is compared
    order-insensitively on the TS side.
  - categorize's substring fallback is order-dependent on KEYWORD_CATEGORY
    insertion order (e.g. "workouts" hits "work"->labor before "workout"->fitness).
  - top_category's max() tie-breaks to the first-inserted category.

Run from repo root:  python3 scripts/gen_psychographic_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.psychographic import extract_themes  # noqa: E402
from utils.pillar_categories import categorize, top_category  # noqa: E402


def theme_scenarios():
    return [
        ("hashtags_and_words", [
            "Minecraft speedrun world record #gaming #minecraft",
            "Another minecraft tutorial for beginners",
        ]),
        ("bigrams_distinct", [
            "sourdough starter recipe tips",
            "sourdough starter recipe tips",
            "sourdough starter guide",
        ]),
        ("emojis", [
            "love this dance 🔥🔥 so good 🎯",
            "another one 🔥 vibes 🧿",
        ]),
        ("stopword_and_shortword_filter", [
            "the cat is on the mat go",  # 'go','the','is','on' filtered from words; short 'go'<=2? len 2 -> filtered
            "a big red fox runs fast",
        ]),
        ("skipped_titles", [
            "", "Title Hidden", "No Caption (Just Hashtags)",
            "real content here about baking",
        ]),
        ("unicode_word_chars", [
            "café résumé naïve baking",   # accented letters are \w in Python (\p{L} in TS)
            "日本 ramen tutorial ramen",   # CJK letters kept
        ]),
        ("hashtag_punctuation", [
            "check this #fyp! #foryou content creator",
        ]),
        ("ties_order_insensitive", [   # apple & mango both count 1 -> tie
            "apple mango banana banana",
        ]),
        ("truncation_distinct", _distinct_count_titles(20)),  # 20 distinct words, top_k=18 cut
        ("empty_list", []),
    ]


def _distinct_count_titles(n):
    """Titles yielding word00..word{n-1} with counts n..1 (all distinct)."""
    titles = []
    for i in range(n):
        count = n - i
        titles += [f"word{i:02d}"] * count
    return titles


def categorize_scenarios():
    return [
        "gaming", "minecraft", "GAMING", "  gaming  ",   # exact (with case/strip)
        "videogame",     # substring -> 'game' -> gaming
        "workouts",      # substring -> 'work' (labor) BEFORE 'workout' (fitness)
        "myjobsearch",   # substring -> 'job' -> labor
        "cryptocurrency",  # substring -> 'crypto' -> finance
        "xyzzy",         # no match -> None
        "",              # empty -> None
    ]


def top_category_scenarios():
    return [
        ("dominant_gaming", [
            {"term": "minecraft", "count": 10},
            {"term": "gaming", "count": 5},
            {"term": "recipe", "count": 2},
        ]),
        ("no_category_returns_humor_default", [
            {"term": "xyzzy", "count": 3},
            {"term": "qwerty", "count": 1},
        ]),
        ("empty", []),
        ("tie_first_inserted_wins", [   # labor and finance both weight 4
            {"term": "work", "count": 4},
            {"term": "money", "count": 4},
        ]),
        ("count_defaults_to_1_when_missing", [
            {"term": "gaming"},          # count missing -> float 1
            {"term": "game", "count": 3},
        ]),
    ]


def main():
    payload = {
        "_comment": "Golden parity fixture for the WP-1.1 psychographic port. "
                    "Regenerate only on an intentional Python change: "
                    "python3 scripts/gen_psychographic_parity_fixture.py",
        "theme_cases": [
            {"name": n, "input": {"titles": t}, "expected": extract_themes(t)}
            for n, t in theme_scenarios()
        ],
        "categorize_cases": [
            {"name": kw or "empty_string", "input": {"keyword": kw}, "expected": categorize(kw)}
            for kw in categorize_scenarios()
        ],
        "top_category_cases": [
            {"name": n, "input": {"keywords": kws}, "expected": list(top_category(kws))}
            for n, kws in top_category_scenarios()
        ],
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "algorithmic-mirror", "engine", "__fixtures__", "psychographic_parity.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    n = sum(len(payload[k]) for k in ("theme_cases", "categorize_cases", "top_category_cases"))
    print(f"wrote {n} cases → {out_path}")


if __name__ == "__main__":
    main()
