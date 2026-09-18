"""Work out what a saved item is *about*, without asking a model.

Two kinds of signal come out of here:

* **tags** -- hashtags lifted straight from the caption. High precision, free,
  and on short-form video they are often the only description that exists.
* **terms** -- content words and two-word phrases from the title, description,
  note and transcript, with function words removed.

Neither is reliable on a single item; a ten-word caption is not much to go on.
They earn their keep at collection level, where :mod:`favorites.museum` treats
a term that recurs across many saves as a theme. That is the honest version of
"what am I into lately" -- it emerges from repetition rather than from one
model's guess about one video.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Optional

HASHTAG_RE = re.compile(r"#([^\W\d_][\w\-]{1,48})", re.UNICODE)
TOKEN_RE = re.compile(r"[^\W_]+(?:'[a-z]+)?", re.UNICODE)

STOPWORDS = frozenset("""
a about above after again against all am an and any are aren't as at be because
been before being below between both but by can cannot can't could couldn't did
didn't do does doesn't doing don't down during each few for from further had
hadn't has hasn't have haven't having he her here hers herself him himself his
how i if in into is isn't it its itself let's me more most mustn't my myself no
nor not of off on once only or other ought our ours ourselves out over own same
shan't she should shouldn't so some such than that that's the their theirs them
themselves then there these they this those through to too under until up very
was wasn't we were weren't what when where which while who whom why with won't
would wouldn't you your yours yourself yourselves
just like really get got make makes made go goes going going come comes way
things thing lot new now know think see look looks looking want need use using
one two three first best top good great big small much many via https http www
com net org html amp video watch subscribe follow link bio comment comments
share shares tag tagged part full original sound audio reply duet stitch fyp
foryou foryoupage viral trending shorts reel reels tiktok youtube instagram
""".split())

# Hashtags that describe distribution rather than subject matter. Without this
# every short-form save collapses into one enormous "fyp" theme.
TAG_NOISE = frozenset("""
fyp foryou foryoupage foryoupages viral trending explore explorepage reels reel
shorts short tiktok instagram youtube ig capcut trend follow followme like
likeforlike duet stitch greenscreen fy parati viralvideo tiktokviral xyzbca
""".split())


def hashtags(*texts: Optional[str]) -> list[str]:
    """Hashtags from the given text, lowercased, de-noised, order preserved."""
    seen: list[str] = []
    for text in texts:
        for raw in HASHTAG_RE.findall(text or ""):
            tag = raw.lower()
            if tag in TAG_NOISE or tag in seen:
                continue
            seen.append(tag)
    return seen


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def terms(*texts: Optional[str], limit: int = 24) -> list[str]:
    """Content words and two-word phrases, most frequent first.

    Phrases are kept because they carry the subject where single words do not:
    "local government" is a theme, while "local" and "government" apart are
    noise that will collide with unrelated saves.
    """
    counts: Counter[str] = Counter()
    for text in texts:
        toks = _tokens(text)
        keep = [
            t for t in toks
            if len(t) >= 3 and not t.isdigit() and t not in STOPWORDS
        ]
        counts.update(keep)
        # Bigrams are built from the original sequence so that a dropped
        # stopword breaks the phrase instead of joining unrelated words.
        for a, b in zip(toks, toks[1:]):
            if (a in STOPWORDS or b in STOPWORDS
                    or len(a) < 3 or len(b) < 3
                    or a.isdigit() or b.isdigit()):
                continue
            counts[f"{a} {b}"] += 1

    # A phrase always beats its parts at equal frequency: "climate policy"
    # mentioned twice is more useful than "climate" mentioned twice.
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], " " not in kv[0], kv[0]))
    return [term for term, _ in ranked[:limit]]


def enrich(
    title: Optional[str] = None,
    description: Optional[str] = None,
    note: Optional[str] = None,
    transcript: Optional[str] = None,
) -> tuple[list[str], list[str]]:
    """Return ``(tags, terms)`` for an item.

    The note is weighted by being passed twice: it is the only text you wrote
    yourself, so it says more about why the item matters than any caption does.
    A transcript is truncated -- the opening of a video states its subject, and
    the rest mostly dilutes the counts.
    """
    tags = hashtags(description, title, note)
    body = terms(title, description, note, note, (transcript or "")[:4000])
    # A term that merely repeats the hashtags is redundant. That covers both
    # the single word ("housing" next to #housing) and the phrase two adjacent
    # hashtags produce ("localgov housing" from "#localgov #housing").
    tagset = set(tags)
    body = [
        t for t in body
        if t.replace(" ", "") not in tagset
        and not all(word in tagset for word in t.split())
    ]
    return tags, body


def collection_themes(
    items: Iterable[dict], min_items: int = 2, limit: int = 12
) -> list[tuple[str, int]]:
    """Terms and tags that recur across *different* saves.

    Counted by item, not by mention, so one very chatty transcript cannot
    invent a theme on its own.
    """
    doc_counts: Counter[str] = Counter()
    for item in items:
        seen = set()
        for tag in item.get("tags") or []:
            seen.add(tag)
        for term in (item.get("terms") or [])[:8]:
            seen.add(term)
        doc_counts.update(seen)

    ranked = [
        (term, n) for term, n in doc_counts.most_common()
        if n >= min_items and term not in TAG_NOISE
    ]
    # Prefer phrases over the single words they contain, when both survive.
    phrases = {t for t, _ in ranked if " " in t}
    covered = {word for phrase in phrases for word in phrase.split()}
    deduped = [
        (t, n) for t, n in ranked
        if " " in t or t not in covered
    ]
    return deduped[:limit]
