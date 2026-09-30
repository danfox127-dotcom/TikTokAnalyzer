"""Themes: what a save is about, in words a person would use.

Extracted keywords turned out useless as a way in: a caption yields "five
minutes" and "went sideways", which describe nothing. A theme is the opposite
-- a small, fixed set of subjects ("Dogs", "Food & cooking", "Cities &
urbanism"), each defined by the words that signal it.

Matching is by vocabulary, not by a model. That keeps it local, instant and
explainable: a save is in "Dogs" because its hashtags, caption or your own
category name say dog, puppy or pupper, and the item page says so. The cost is
that the vocabulary is finite. ``python -m favorites.themes`` reports how much
of the library it covers and which of your hashtags it does not recognise yet,
which is how the list grows.

Two kinds of word:

* plain words match anywhere -- a hashtag, the caption, your category names;
* ``#words`` match only in a hashtag or a category name you chose, because in a
  sentence they mean too many things ("this doesn't *work*", "back *home*").

Compound hashtags are read too: ``#dogsoftiktok`` starts with "dogs", and
``#easyrecipes`` ends with "recipes". A hashtag that is itself a vocabulary
word is taken at its word, so ``#homemade`` is food, not home decor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Optional

from .tagging import STOPWORDS, TOKEN_RE, is_noise

#: The one "theme" that is not a subject: the saves no theme recognises yet.
#: Offered as a filter so they can be found, looked through and filed.
UNDEFINED = "Undefined"

THEMES: dict[str, str] = {
    "Dogs": """dog dogs puppy puppies pup pups pupper puppers doggo doggos doggy canine
        goldenretriever labrador corgi pitbull husky dachshund poodle beagle
        greyhound huskies cutedog cutedogs mydogiscutest #siberian
        dogsoftiktok dogsofinstagram dogmom doglover #woof""",
    "Cats": """cat cats kitten kittens kitty catsoftiktok catsofinstagram catmom catlover
        feline meow""",
    "Animals & wildlife": """animal animals wildlife bird birds birding horse horses
        cow cows babygoat sheep pig pigs chicken chickens duck ducks bunny rabbit
        hamster reptile snake turtle frog fish aquarium zoo elephant #bear #bears
        otter otters raccoon squirrel owl whale shark octopus capybara #pet #pets""",
    "Food & cooking": """food foodie foodtok recipe recipes cooking cook cooks baking
        bake baked bakery bread sourdough dumpling dumplings pasta noodle noodles ramen
        dinner lunch breakfast brunch dessert desserts cake cakes cookie cookies soup
        salad chef kitchen meal meals mealprep restaurant eats snack snacks pizza taco
        tacos bbq barbecue grill grilling vegan vegetarian cuisine spicy delicious yummy
        tasty sushi cheese chocolate homemade foodporn airfryer sandwich burger steak tomato
        tomatoes potato potatoes egg eggs appetizer appetizers garlic foodgif foodgifs nycfood nyceats""",
    "Drinks": """coffee espresso latte cocktail cocktails mixology bartender wine beer
        brewery whiskey tequila matcha boba smoothie #tea #drinks""",
    "Comedy & humour": """funny comedy comedian humor humour joke jokes lol lmao meme
        memes skit skits standup prank pranks satire parody sketch""",
    "Music": """music song songs singer singing guitar piano drums drummer band concert
        rap rapper hiphop jazz dj producer lyrics musician #bass vinyl album livemusic
        radiohead spotify playlist charlixcx taylorswift rollingstone raptok
        brucespringsteen kendricklamar courtneylove hayleywilliams wolfalice #oasis
        #u2 #rock #pop #cover #beat""",
    "Dance": """dance dancing dancer choreography ballet tapdance salsa""",
    "Film & TV": """movie movies film films cinema netflix trailer actor actress
        filmmaking director anime hbomax bluey sopranos pauliewalnuts spiderman #hbo #tv #series #show""",
    "Books & writing": """book books booktok reading reader novel novels author writing
        writer poetry poem poems bookstagram #library""",
    "Art & design": """artist drawing painting illustration typography graphicdesign
        sculpture pottery ceramics calligraphy watercolor sketchbook printmaking
        illustrator digitalart procreate arttips dailyart artreels artwork arttok
        diseño #portrait #art #design #designer #craft #crafts""",
    "Photography & editing": """photography photographer photographers photoshop
        lightroom photoediting retouching videoediting capcut #photo #photos
        #camera #cameras #editing #adobe #portrait فوتوشوب""",
    "Fashion & beauty": """fashion outfit outfits ootd makeup beauty skincare hairstyle
        #nails thrift thrifting vintage streetwear sneakers #style #hair""",
    "Home & DIY": """diy decor interiordesign interior renovation furniture cleaning
        cleantok organization organizing apartment woodworking homedecor nycapartment #home
        #house""",
    "Gardening & plants": """garden gardening gardener plant plants houseplant houseplants
        flower flowers seeds vegetables compost farm farming homestead #bean #beans""",
    "Travel": """travel traveling travelling trip vacation hotel beach roadtrip tourism
        wanderlust backpacking airport flight""",
    "Sport & fitness": """workout gym fitness #running runner yoga exercise training
        sport sports football soccer basketball baseball nba nfl tennis golf climbing
        bouldering cycling skateboarding skateboard surfing swimming frisbee #ultimate
        hockey boxing marathon pilates #run""",
    "Nature & outdoors": """nature hiking hike camping outdoors mountain mountains forest
        ocean sunset sunrise nationalpark waterfall lake river wilderness""",
    "Science & tech": """science tech technology ai coding programming engineering physics
        chemistry biology astronomy nasa robot robotics gadget gadgets computer software
        chatgpt openai artificialintelligence onlinetools #google #claude #website #websites #apps #space""",
    "How-to & learning": """tutorial howto tips lifehack lifehacks hack hacks learn homework
        learning education explained facts didyouknow todayilearned
        #tricks علمني""",
    "History": """history historical ancient archaeology museum medieval""",
    "News & politics": """news politics political election government policy localgov
        council vote voting congress senate president protest democracy journalism
        homeless leftist""",
    "Cities & urbanism": """urbanism urbanplanning transit architecture housing zoning
        bike bikes cycling #trains #train subway streetscape walkable nycsubway #city #cities""",
    "New York": """nyc newyork newyorkcity brooklyn bronx harlem statenisland #manhattan
        nyclife nycfood nyceats nyctiktok nycsubway nycapartment""",
    "Money & work": """money finance investing career careers job jobs business
        entrepreneur productivity economy jobsearch jobhunting powerpoint
        #excel #resume #budget #budgeting #work""",
    "Marketing & media": """marketing socialmedia contentcreator contentcreation branding
        seo advertising copywriting communications newsletter radiohost
        #content #media #pr""",
    "Parenting & family": """parenting #mom #dad #baby #babies kid kids toddler momlife
        dadlife bluey #parent #parents #family""",
    "Wellness": """mentalhealth therapy anxiety wellness selfcare adhd mindfulness
        meditation somatic vagusnerve nervoussystem thesafemethod #healing #sleep #health""",
    "Gaming": """gaming gamer videogame videogames nintendo playstation xbox minecraft
        fortnite pokemon zelda""",
    "Cars & vehicles": """car cars truck trucks motorcycle motorcycles racing f1 formula1
        jeep #auto""",
    "Satisfying & ASMR": """asmr satisfying oddlysatisfying""",
    "Nostalgia & retro": """nostalgia nostalgic throwback retro genx millennial millennials
        #tbt #y2k #grunge""",
    "Language": """language languages linguistics #spanish #french grammar etymology""",
}

_WORD = re.compile(r"[a-z0-9]+")


# Words that end in "s" without being plurals, where folding them would make
# another word: "news" became "new", and every "my new couch" was news.
_NOT_PLURAL = frozenset({"news"})


def _norm(word: str) -> str:
    """Fold simple plurals, so "puppies" and "puppy" are one word."""
    if word in _NOT_PLURAL:
        return word
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


# Recognised only as a whole hashtag, never inside one: "rock" is in #rocket
# and #shamrock.
_WHOLE_ONLY = frozenset({"rock"})

#: The glue of compound hashtags: words that say nothing about a subject but
#: let a hashtag split cleanly around one -- #dogsoftiktok, #easyrecipes,
#: #booktoker, #tipsandtricks. A compound is only read when *all* of it splits
#: into these and vocabulary words, which is what keeps #husband out of Music
#: and #snowflake out of Nature.
AFFIXES = frozenset("""
    a an and the of my our your in on for to with at by is this that
    tiktok tok toker tokers instagram insta ig gram youtube reels shorts
    life lifestyle lover lovers love loves mom moms mum dad dads daily
    goals ideas idea inspo inspiration time day days week community club
    easy quick healthy cute best good great little mini simple perfect fun cool
    amazing beautiful official page fan fans core aesthetic vibes vibe world
    addict addicts things stuff hack hacks tip tips video videos clip clips
    girl girls boy boys guy guys man men woman women lady queen king
    new old era pov story storytime check lessons lesson
""".split())


def _vocabulary() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """(anywhere, tags_only): normalised word -> the themes it signals."""
    anywhere: dict[str, set[str]] = {}
    tags_only: dict[str, set[str]] = {}
    for theme, words in THEMES.items():
        for raw in words.split():
            table = tags_only if raw.startswith("#") else anywhere
            table.setdefault(_norm(raw.lstrip("#")), set()).add(theme)
    return anywhere, tags_only


def _pieces() -> dict[str, set[str]]:
    """Every vocabulary word as written and folded -> its themes, for splitting
    compounds. Plurals are kept as written because folding changes a word's
    start: #huskiesofinstagram begins with "huskies", not "husky"."""
    table: dict[str, set[str]] = {}
    for theme, words in THEMES.items():
        for raw in words.split():
            raw = raw.lstrip("#")
            if raw in _WHOLE_ONLY or not raw.isascii():
                continue
            for form in {raw, _norm(raw)}:
                table.setdefault(form, set()).add(theme)
    return table


def _rebuild() -> None:
    """Work the lookup tables out from THEMES (again, after an edit to it)."""
    global ANYWHERE, TAGS_ONLY, TAG_WORDS, _PIECES, VERSION
    ANYWHERE, TAGS_ONLY = _vocabulary()
    TAG_WORDS = {w: set(t) for w, t in ANYWHERE.items()}
    for w, t in TAGS_ONLY.items():
        TAG_WORDS.setdefault(w, set()).update(t)
    _PIECES = _pieces()
    VERSION = hashlib.sha1(json.dumps(
        [_MATCHING, THEMES, sorted(AFFIXES)], sort_keys=True).encode()).hexdigest()[:12]
    _split.cache_clear()


#: Bumped when the way words are matched or weighed changes, as VERSION's hash
#: cannot see it.
_MATCHING = 4


@lru_cache(maxsize=4096)
def _split(tag: str) -> Optional[tuple[str, ...]]:
    """The fewest pieces a hashtag splits into, or None if it does not split.

    Every piece must be a vocabulary word, an affix or a number. #dogtraining
    is dog + training; #husband is nothing, because "hus" is not a word.
    """
    n = len(tag)
    best: list[Optional[tuple[str, ...]]] = [None] * (n + 1)
    best[0] = ()
    for i in range(n):
        if best[i] is None:
            continue
        for j in range(i + 1, n + 1):
            piece = tag[i:j]
            if piece in _PIECES or piece in AFFIXES or piece.isdigit():
                cand = best[i] + (piece,)
                if best[j] is None or len(cand) < len(best[j]):
                    best[j] = cand
    return best[n]


def _tag_hits(tag: str) -> tuple[set[str], bool]:
    """(themes, exact) for one hashtag.

    ``exact`` when the hashtag is itself a vocabulary word; otherwise the
    themes come from splitting it, which needs at least one subject word of
    four letters or more -- three-letter ones find themselves in too much
    (#cowboy is not about cows).
    """
    tag = tag.lower().lstrip("#")
    if not tag:
        return set(), False
    exact = TAG_WORDS.get(_norm(tag))
    if exact:
        return set(exact), True
    parts = _split(tag) or _split(_norm(tag))
    if not parts or len(parts) < 2:
        return set(), False
    subjects = [p for p in parts if p in _PIECES and p not in AFFIXES]
    if not any(len(p) >= 4 for p in subjects):
        return set(), False
    found: set[str] = set()
    for p in subjects:
        found |= _PIECES[p]
    return found, False


def _from_tag(tag: str) -> set[str]:
    return _tag_hits(tag)[0]


# --- weighing the evidence ---------------------------------------------------

#: How much each kind of evidence counts. A theme is kept when it has at
#: least half the evidence of the strongest one -- so a word said once in
#: passing rides along with a hashtag, but not with a room you chose.
WEIGHTS = {
    "you": 100,         # you put it in this room yourself
    "creator rule": 4,  # you said everything by this creator belongs here
    "taught": 3,        # a hashtag you taught the museum
    "category": 3,      # a word in a category name you chose
    "hashtag": 2,       # a hashtag that is a vocabulary word
    "compound": 2,      # a hashtag that splits into one
    "creator": 2,       # the creator's handle says it
    "regular": 2,       # most of this creator's other saves are here
    "caption": 1,       # a word in the title, caption or your placard
    "transcript": 1,    # a word said at least twice (at most 2 per theme)
}
MAX_THEMES = 3
#: Captions that brush past this many subjects once each say nothing sure
#: about any of them: "on the radio talking about surfing and his new song".
SCATTERED = 3


@dataclass
class Rules:
    """What you have taught the museum, as read from the ``theme_rules`` table."""
    tags: dict[str, set[str]] = field(default_factory=dict)      # hashtag -> themes
    ignore: set[str] = field(default_factory=set)                # hashtags that are no subject
    creator_add: dict[str, set[str]] = field(default_factory=dict)
    creator_remove: dict[str, set[str]] = field(default_factory=dict)
    item_add: dict[int, set[str]] = field(default_factory=dict)
    item_remove: dict[int, set[str]] = field(default_factory=dict)

    @classmethod
    def from_rows(cls, rows: Iterable) -> "Rules":
        r = cls()
        for kind, key, theme, action in rows:
            if kind == "tag" and action == "ignore":
                r.ignore.add(key)
            elif kind == "tag":
                r.tags.setdefault(key, set()).add(theme)
            elif kind == "creator":
                (r.creator_add if action == "add" else r.creator_remove).setdefault(key, set()).add(theme)
            elif kind == "item":
                (r.item_add if action == "add" else r.item_remove).setdefault(int(key), set()).add(theme)
        return r


NO_RULES = Rules()


def creator_key(handle: Optional[str], name: Optional[str] = None) -> str:
    """How a creator is known to the rules: their handle, else their name."""
    return (handle or "").lower().lstrip("@").strip() or (name or "").lower().strip()


def tag_key(tag: str) -> str:
    return tag.lower().lstrip("#").strip()


def weigh(
    tags: Iterable[str] = (),
    texts: Iterable[Optional[str]] = (),
    categories: Iterable[str] = (),
    *,
    transcript: Optional[str] = None,
    creator: Optional[str] = None,
    regular: Iterable[str] = (),
    rules: Rules = NO_RULES,
    item_id: Optional[int] = None,
) -> dict[str, list[tuple[str, str, int]]]:
    """Every piece of evidence for every theme: theme -> [(kind, word, weight)]."""
    ev: dict[str, list[tuple[str, str, int]]] = {}
    tags = list(tags or ())

    def add(theme: str, kind: str, word: str, weight: Optional[int] = None) -> None:
        ev.setdefault(theme, []).append((kind, word, WEIGHTS[kind] if weight is None else weight))

    for raw in tags or ():
        tag = tag_key(raw)
        if not tag or tag in rules.ignore:
            continue
        if tag in rules.tags:
            for theme in rules.tags[tag]:
                add(theme, "taught", "#" + tag)
            continue
        found, exact = _tag_hits(tag)
        for theme in found:
            add(theme, "hashtag" if exact else "compound", "#" + tag)
    for name in categories or ():
        for word in _WORD.findall(name.lower()):
            for theme in TAG_WORDS.get(_norm(word), ()):
                add(theme, "category", name)
    key = creator_key(creator)
    if key:
        for part in re.split(r"[^a-z0-9]+", key):
            if len(part) >= 3 and part not in rules.ignore:
                for theme in _tag_hits(part)[0]:
                    add(theme, "creator", "@" + key)
        for theme in rules.creator_add.get(key, ()):
            add(theme, "creator rule", "@" + key)
    for theme in regular or ():
        add(theme, "regular", "@" + key if key else "this creator")
    # A caption quotes its own hashtags ("... #localgov"): those count once, as hashtags.
    hashed = {_norm(tag_key(t)) for t in tags or ()}
    words = {_norm(w) for text in texts or () for w in _WORD.findall((text or "").lower())}
    for word in sorted(words - hashed):
        for theme in ANYWHERE.get(word, ()):
            add(theme, "caption", word)
    if transcript:
        said = Counter(_norm(w) for w in _WORD.findall(transcript.lower()))
        per_theme: Counter[str] = Counter()
        for word, n in said.most_common():
            if n < 2:
                break
            for theme in ANYWHERE.get(word, ()):
                if per_theme[theme] < 2:
                    per_theme[theme] += 1
                    add(theme, "transcript", word)
    # Your own fixes come last and win.
    blocked = set(rules.creator_remove.get(key, ())) if key else set()
    if item_id is not None:
        blocked |= rules.item_remove.get(item_id, set())
        for theme in rules.item_add.get(item_id, ()):
            add(theme, "you", "your choice")
    for theme in blocked:
        if not any(k == "you" for k, _, _ in ev.get(theme, ())):
            ev.pop(theme, None)
    return {t: e for t, e in ev.items() if t in THEMES}


def score(evidence: list[tuple[str, str, int]]) -> int:
    return sum(w for _, _, w in evidence)


def decide(ev: dict[str, list[tuple[str, str, int]]]) -> list[str]:
    """The themes the evidence is strong enough for, strongest first.

    A theme is kept at half the strongest theme's evidence or more. When all
    there is are single words in passing, up to two are kept; three or more
    subjects mentioned once each is a caption wandering, and files nothing.
    """
    if not ev:
        return []
    order = list(THEMES)
    scores = {t: score(e) for t, e in ev.items()}
    ranked = sorted(scores, key=lambda t: (-scores[t], order.index(t)))
    top = scores[ranked[0]]
    if top <= 1 and len(ranked) >= SCATTERED:
        return []
    return [t for t in ranked if scores[t] * 2 >= top][:MAX_THEMES]


def themes_for(
    tags: Iterable[str] = (),
    texts: Iterable[Optional[str]] = (),
    categories: Iterable[str] = (),
    **kw,
) -> list[str]:
    """The themes an item belongs to, most strongly signalled first.

    ``tags`` are its hashtags; ``texts`` its title, caption and your note;
    ``categories`` the names you filed it under, read like hashtags because
    you chose those words deliberately. Keywords are passed on to :func:`weigh`.
    """
    return decide(weigh(tags, texts, categories, **kw))


def _row_args(row) -> dict:
    raw_tags = row["tags"] if row["tags"] else "[]"
    tags = json.loads(raw_tags) if isinstance(raw_tags, str) else list(raw_tags)
    keys = row.keys() if hasattr(row, "keys") else ()
    get = (lambda k: row[k] if k in keys else None)
    return {
        "tags": tags,
        "texts": (row["title"], row["description"], row["note"]),
        "transcript": get("transcript"),
        "creator": creator_key(get("creator_handle"), get("creator_name")),
        "item_id": get("id"),
    }


def evidence_for_row(row, categories: Iterable[str] = (), *, rules: Rules = NO_RULES,
                     regular: Iterable[str] = ()) -> dict[str, list[tuple[str, str, int]]]:
    a = _row_args(row)
    return weigh(a["tags"], a["texts"], categories, transcript=a["transcript"],
                 creator=a["creator"], regular=regular, rules=rules, item_id=a["item_id"])


def for_row(row, categories: Iterable[str] = (), *, rules: Rules = NO_RULES,
            regular: Iterable[str] = ()) -> list[str]:
    """Themes for a stored item (an ``items`` row or dict)."""
    return decide(evidence_for_row(row, categories, rules=rules, regular=regular))


#: A creator leans towards a room when this share of their themed saves is in it.
LEAN_SHARE = 0.6
LEAN_MIN = 3


def lean(themed: Iterable[list[str]]) -> list[str]:
    """The rooms a creator's saves mostly sit in, from each save's themes."""
    lists = [t for t in themed if t]
    if len(lists) < LEAN_MIN:
        return []
    counts = Counter(theme for t in lists for theme in set(t))
    return [t for t, n in counts.most_common() if n >= LEAN_SHARE * len(lists)]


_KIND_WORDS = {
    "you": "you put it here", "creator rule": "you filed everything by {w} here",
    "taught": "{w} (you taught this)", "hashtag": "{w}", "category": "your category “{w}”",
    "compound": "{w}", "creator": "{w}", "regular": "most saves by {w} are here",
    "caption": "“{w}” in the caption", "transcript": "“{w}” said in it",
}


def explain(ev: dict[str, list[tuple[str, str, int]]], kept: Iterable[str]) -> list[dict]:
    """Why each kept theme is kept, in words: for the item page."""
    out = []
    for theme in kept:
        seen: list[str] = []
        for kind, word, _ in sorted(ev.get(theme, ()), key=lambda e: -e[2]):
            line = _KIND_WORDS[kind].format(w=word)
            if line not in seen:
                seen.append(line)
        total = score(ev.get(theme, []))
        out.append({"theme": theme, "reasons": seen[:4],
                    "hunch": total < 2 and not any(
                        k in ("you", "creator rule", "taught") for k, _, _ in ev.get(theme, ()))})
    return out


_rebuild()

# --- the coverage report -----------------------------------------------------

def _caption_words(*texts: Optional[str]) -> set[str]:
    """Words in a caption that could name a subject: no filler, no numbers,
    nothing the vocabulary already knows (a hashtag-only word like "work" is
    left out of sentences on purpose, so listing it would only tempt)."""
    words = {w.lower() for text in texts for w in TOKEN_RE.findall(text or "")}
    return {w for w in words if len(w) >= 4 and not w.isdigit() and not is_noise(w)
            and w not in STOPWORDS and w not in _PREVIEW_WORDS and _norm(w) not in TAG_WORDS}


# The wording link previews wrap a caption in ("1,204 likes, 31 comments -
# City Desk on March 3, 2024: ..."), and TikTok's "Replying to @someone".
_PREVIEW_WORDS = frozenset("""likes replying january february march april june july august
september october november december""".split())


def report(conn: sqlite3.Connection, top: int = 30) -> dict:
    rows = conn.execute("SELECT id, themes, tags, creator_name, creator_handle, title, description"
                        " FROM items"
                        " WHERE resolve_status = 'ok' ORDER BY saved_at DESC").fetchall()
    rules = Rules.from_rows(tuple(r) for r in conn.execute(
        "SELECT kind, key, theme, action FROM theme_rules"))
    known = set(rules.tags) | rules.ignore
    per_theme: Counter[str] = Counter()
    unthemed_tags: Counter[str] = Counter()
    examples: dict[str, list[int]] = {}
    unthemed_words: Counter[str] = Counter()
    themed = untagged = 0
    for row in rows:
        mine = json.loads(row["themes"] or "[]")
        per_theme.update(mine)
        themed += bool(mine)
        # A creator tagging their own name (#redavisuals on redavisuals' posts)
        # says who, not what; the Creator filter already covers who.
        own = (row["creator_handle"] or "").lower().lstrip("@")
        tags = [t for t in json.loads(row["tags"] or "[]")
                if t.lower() != own and not is_noise(t)]
        for tag in tags:
            if tag_key(tag) not in known and not _from_tag(tag):
                unthemed_tags[tag] += 1
                examples.setdefault(tag, []).append(row["id"])
        if not mine:
            untagged += not tags
            # Less the hashtags (listed above) and the creator's own name.
            said = _caption_words(row["title"], row["description"])
            said -= {t.lower() for t in tags} | _caption_words(row["creator_name"], own)
            unthemed_words.update(said)
    return {
        "items": len(rows), "themed": themed,
        "per_theme": per_theme.most_common(),
        "unrecognised_hashtags": [(t, n) for t, n in unthemed_tags.most_common(top) if n >= 2],
        # The saves carrying each of them, newest first: what the tidy page shows.
        "examples": {t: examples[t] for t, n in unthemed_tags.most_common(top) if n >= 2},
        # Of the saves with no theme, how many have no hashtag to go on at all,
        # and the words that recur in their captions -- where the rest are.
        "unthemed_without_hashtags": untagged,
        "unthemed_caption_words": [(w, n) for w, n in unthemed_words.most_common(top) if n >= 3],
    }


def main(argv: Optional[list[str]] = None) -> int:
    from . import db  # imported here: db imports this module

    ap = argparse.ArgumentParser(description="How well the themes cover your library.")
    ap.add_argument("--db", help="library path (default: ~/favorites.db)")
    ap.add_argument("--top", type=int, default=30, help="how many unrecognised hashtags to list")
    args = ap.parse_args(argv)
    conn, where = db.connect_announced(args.db)
    print(where + "\n")
    try:
        r = report(conn, args.top)
        _, hunch_count = db.hunches(conn, limit=0)
    finally:
        conn.close()
    pct = round(100 * r["themed"] / r["items"]) if r["items"] else 0
    print(f"{r['themed']} of {r['items']} identified saves have at least one theme ({pct}%)\n")
    for theme, n in r["per_theme"]:
        print(f"  {n:>5}  {theme}")
    if hunch_count:
        print(f"\n{hunch_count} of them are filed on a hunch (one word in passing):"
              " settle them at /rooms/tidy.")
    if r["unrecognised_hashtags"]:
        print("\nHashtags on 2+ saves that no theme recognises yet:")
        for tag, n in r["unrecognised_hashtags"]:
            print(f"  {n:>5}  #{tag}")
    unthemed = r["items"] - r["themed"]
    if unthemed:
        print(f"\nOf the {unthemed} saves with no theme, {r['unthemed_without_hashtags']}"
              " have no hashtags at all, only a caption to go on.")
    if r["unthemed_caption_words"]:
        print("Words that recur in their captions (on 3+ saves):")
        for word, n in r["unthemed_caption_words"]:
            print(f"  {n:>5}  {word}")
    if r["unrecognised_hashtags"] or r["unthemed_caption_words"]:
        print("\nTeach the hashtags at /rooms/tidy, or add words to THEMES in"
              " favorites/themes.py; the library re-themes itself on the next start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
