"""Captions made readable: a headline and a short description that end cleanly.

What the platforms give us is not written to be shown on a label. TikTok's
"title" is the whole caption, hashtag pile and all; Instagram's arrives wrapped
in "1,204 likes, 31 comments - citydesk on March 3, 2024: "..."". Clamping that
to three lines cut it off mid-word. Here it is cleaned first and then trimmed
at a sentence, so a placard always reads as something a person wrote.

The stored text is never changed: search still sees every hashtag.
"""

from __future__ import annotations

import re
from typing import Optional

HEADLINE_CHARS = 90
BLURB_CHARS = 160

_WRAPPERS = (
    # 1,204 likes, 31 comments - citydesk on March 3, 2024: "...".
    re.compile(r"^\s*[\d.,]+\s*[KkMm]?\s+likes?(?:,\s*[\d.,]+\s*[KkMm]?\s+comments?)?"
               r"\s*[-–—]\s*.{1,80}?\s+on\s+[A-Z][a-z]+\s+\d{1,2},\s*\d{4}\s*:\s*", re.S),
    # City Desk on Instagram: "...".
    re.compile(r"^\s*.{1,80}?\s+on\s+(?:Instagram|TikTok|Threads)\s*:\s*", re.S),
    # TikTok's reply videos: "Replying to @someone".
    re.compile(r"^\s*Replying to @[\w.]+\s*", re.I),
)
_TAG = r"[#@][^\s#@]+"
_TAG_RUN_END = re.compile(rf"(?:\s*{_TAG})+[\s.,!]*$")
_TAG_RUN_START = re.compile(rf"^(?:\s*{_TAG})+\s+")
_TAG_INLINE = re.compile(r"#([^\W\d_][\w-]*)")
_URL = re.compile(r"https?://\S+|www\.\S+")
_TIMESTAMP_LINE = re.compile(r"^\s*\(?\d{1,2}:\d{2}(?::\d{2})?\)?\s")
# A YouTube description's housekeeping, not its subject.
_CHROME_LINE = re.compile(
    r"^\s*(?:subscribe|follow (?:me|us)|like and subscribe|links?\s*:|shop\b|merch\b"
    r"|business (?:inquiries|enquiries)|contact\s*:|patreon|instagram\s*:|twitter\s*:"
    r"|tiktok\s*:|music\s*:|chapters\s*:|timestamps\s*:|#ad\b|sponsored)", re.I)
_SENTENCE_END = re.compile(r"(?<=[.!?…])[\"”’)]*\s+")
_CLAUSE = re.compile(r"[,;:–—]\s")


def _unquote(text: str) -> str:
    text = text.strip()
    if len(text) > 1 and text[0] in "\"“" and text.rstrip(". ")[-1:] in "\"”":
        text = text[1:].rstrip(". ")[:-1]
    return text.strip()


def clean_caption(text: Optional[str]) -> str:
    """A caption as a person would write it: no preview wrapper, no hashtag pile."""
    if not text:
        return ""
    for wrapper in _WRAPPERS:
        stripped = wrapper.sub("", text, count=1)
        if stripped != text:
            text = _unquote(stripped)
    lines = []
    for line in text.splitlines():
        line = _URL.sub("", line)
        line = _TAG_RUN_END.sub("", line)
        line = _TAG_RUN_START.sub("", line)
        if not line.strip() or re.fullmatch(rf"(?:\s*{_TAG})+\s*", line):
            continue
        if _TIMESTAMP_LINE.match(line) or _CHROME_LINE.match(line):
            continue
        lines.append(_TAG_INLINE.sub(r"\1", line).strip())
    return re.sub(r"\s+", " ", " ".join(_end(l) for l in lines)).strip()


def _end(line: str) -> str:
    """A caption's line breaks are its full stops; keep them as a pause."""
    return line if not line or line[-1] in ".!?…:;,\"”)" or _only_symbols(line[-1]) else line + "."


def _only_symbols(ch: str) -> bool:
    return not ch.isalnum() and ch not in "\"'"


# A full stop after these ends a word, not a sentence: "Cat vs. cardboard box".
_ABBREVIATIONS = frozenset("""vs v mr mrs ms dr st mt no vol ep pt ft jr sr etc approx
    eg ie e g i fig inc ltd co""".split())


def sentences(text: str) -> list[str]:
    out, start = [], 0
    for m in _SENTENCE_END.finditer(text):
        before = text[start:m.start()].rstrip("\"”’)")
        last = re.split(r"[\s(]", before)[-1].replace(".", "").lower()
        if before.endswith(".") and (last in _ABBREVIATIONS or len(last) == 1):
            continue
        out.append(text[start:m.start()])
        start = m.end()
    out.append(text[start:])
    return [s.strip() for s in out if s.strip()]


def _cut(text: str, limit: int) -> str:
    """One overlong sentence: stop at a clause if one is late enough, else a word."""
    if len(text) <= limit:
        return text
    clauses = [m.start() + 1 for m in _CLAUSE.finditer(text) if limit * 0.5 <= m.start() < limit]
    if clauses:
        return text[:clauses[-1] - 1].rstrip() + "…"
    head = text[:limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:–—-")
    return head + "…"


def trim(text: Optional[str], limit: int = BLURB_CHARS) -> str:
    """Whole sentences up to ``limit`` characters; never a word cut in half."""
    parts = sentences(text or "")
    if not parts:
        return ""
    out = parts[0]
    if len(out) > limit:
        return _cut(out, limit)
    for s in parts[1:]:
        if len(out) + 1 + len(s) > limit:
            break
        out += " " + s
    return out


def _parts(item) -> tuple[str, str]:
    """(headline, the rest of the caption) for an item or row."""
    get = item.get if hasattr(item, "get") else (lambda k: item[k])
    title = clean_caption(get("title"))
    desc = clean_caption(get("description"))
    parts = sentences(title)
    head = parts[0] if parts else ""
    # Where the title *is* the caption (TikTok), the description repeats it:
    # the headline is its first sentence and the blurb carries on from there.
    rest = " ".join(parts[1:])
    if desc and not (title and (desc.startswith(title) or title.startswith(desc))):
        rest = desc
    elif desc.startswith(title) and len(desc) > len(title):
        rest = (rest + " " + desc[len(title):]).strip()
    if len(head) > HEADLINE_CHARS:
        head = _cut(head, HEADLINE_CHARS)
    # A label's headline needs no full stop; a question or a shout keeps its mark.
    if head.endswith(".") and not head.endswith(".."):
        head = head[:-1]
    return head, rest


def headline(item) -> str:
    """The first sentence of the caption, short enough for a label."""
    head, _ = _parts(item)
    if head:
        return head
    get = item.get if hasattr(item, "get") else (lambda k: item[k])
    who = get("creator_name") or get("creator_handle")
    return f"A save from {who}" if who else ""


def blurb(item, limit: int = BLURB_CHARS) -> str:
    """What else the caption says, in whole sentences up to ``limit``."""
    _, rest = _parts(item)
    return trim(rest, limit)


def detail(item, limit: int = 700) -> str:
    """The caption for a save's own page: everything after the headline --
    and, where the headline had to stop short, its whole first sentence too."""
    head, rest = _parts(item)
    if head.endswith("…"):
        get = item.get if hasattr(item, "get") else (lambda k: item[k])
        first = sentences(clean_caption(get("title")))[:1]
        rest = " ".join(first + [rest]).strip()
    return trim(rest, limit)
