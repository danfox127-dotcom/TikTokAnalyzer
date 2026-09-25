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
from typing import Iterable, Optional

from .tagging import STOPWORDS, TOKEN_RE, is_noise

THEMES: dict[str, str] = {
    "Dogs": """dog dogs puppy puppies pup pups pupper puppers doggo doggos doggy canine
        goldenretriever labrador corgi pitbull husky dachshund poodle beagle
        greyhound huskies cutedog cutedogs mydogiscutest #siberian
        dogsoftiktok dogsofinstagram dogmom doglover #woof""",
    "Cats": """cat cats kitten kittens kitty catsoftiktok catsofinstagram catmom catlover
        feline meow""",
    "Animals & wildlife": """animal animals wildlife bird birds birding horse horses
        cow cows goat goats sheep pig pigs chicken chickens duck ducks bunny rabbit
        hamster reptile snake turtle frog fish aquarium zoo elephant #bear #bears
        otter otters raccoon squirrel owl whale shark octopus capybara #pet #pets""",
    "Food & cooking": """food foodie foodtok recipe recipes cooking cook cooks baking
        bake baked bakery bread sourdough dumpling dumplings pasta noodle noodles ramen
        dinner lunch breakfast brunch dessert desserts cake cakes cookie cookies soup
        salad chef kitchen meal meals mealprep restaurant eats snack snacks pizza taco
        tacos bbq barbecue grill grilling vegan vegetarian cuisine spicy delicious yummy
        tasty sushi cheese chocolate homemade airfryer sandwich burger steak tomato
        tomatoes potato potatoes egg eggs appetizer appetizers garlic foodgif foodgifs nycfood nyceats""",
    "Drinks": """coffee espresso latte cocktail cocktails mixology bartender wine beer
        brewery whiskey tequila matcha boba smoothie #tea #drinks""",
    "Comedy & humour": """funny comedy comedian humor humour joke jokes lol lmao meme
        memes skit skits standup prank pranks satire parody sketch""",
    "Music": """music song songs singer singing guitar piano drums drummer band concert
        rap rapper hiphop jazz dj producer lyrics musician bass vinyl album livemusic
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
    "How-to & learning": """tutorial howto tips lifehack lifehacks hack hacks learn
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
        seo advertising copywriting communications newsletter
        radio podcast podcasts broadcasting #content #media #pr""",
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


def _vocabulary() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """(anywhere, tags_only): normalised word -> the themes it signals."""
    anywhere: dict[str, set[str]] = {}
    tags_only: dict[str, set[str]] = {}
    for theme, words in THEMES.items():
        for raw in words.split():
            table = tags_only if raw.startswith("#") else anywhere
            table.setdefault(_norm(raw.lstrip("#")), set()).add(theme)
    return anywhere, tags_only


ANYWHERE, TAGS_ONLY = _vocabulary()
TAG_WORDS = {**{w: set(t) for w, t in ANYWHERE.items()}}
for _w, _t in TAGS_ONLY.items():
    TAG_WORDS.setdefault(_w, set()).update(_t)



# Recognised only as a whole hashtag, never inside one: "rock" is in #rocket
# and #shamrock.
_WHOLE_ONLY = frozenset({"rock"})


def _compound_words() -> dict[str, set[str]]:
    """Words long enough to recognise inside a compound hashtag.

    Shorter ones find themselves everywhere: "art" in #party, "car" in #scary.
    A plural is kept as written as well as folded, because folding changes its
    start: #huskiesofinstagram begins with "huskies", not "husky".
    """
    table = {w: set(t) for w, t in TAG_WORDS.items() if len(w) >= 4 and w not in _WHOLE_ONLY}
    for theme, words in THEMES.items():
        for raw in words.split():
            raw = raw.lstrip("#")
            if len(raw) >= 5 and raw != _norm(raw):
                table.setdefault(raw, set()).add(theme)
    return table


def _prefix_words() -> dict[str, set[str]]:
    """Four-letter plurals, recognised only at the start of a hashtag.

    #dogslife and #carsofinstagram start with one; at the end they mislead
    ("eats" in #treats, "cars" in #oscars, "dogs" in #hotdogs).
    """
    table: dict[str, set[str]] = {}
    for theme, words in THEMES.items():
        for raw in words.split():
            raw = raw.lstrip("#")
            if len(raw) == 4 and raw != _norm(raw):
                table.setdefault(raw, set()).add(theme)
    return table


_COMPOUND = _compound_words()
_PREFIXES = _prefix_words()

#: Bumped when the way words are matched changes, as VERSION's hash cannot see it.
_MATCHING = 3

#: Changes whenever the vocabulary or the matching does, so a library
#: re-themes itself on the next start after an edit here, with nothing to run.
VERSION = hashlib.sha1(
    json.dumps([_MATCHING, THEMES], sort_keys=True).encode()).hexdigest()[:12]


def _from_tag(tag: str) -> set[str]:
    tag = tag.lower().lstrip("#")
    if not tag:
        return set()
    exact = TAG_WORDS.get(_norm(tag))
    if exact:
        return set(exact)
    found: set[str] = set()
    for word, signalled in _COMPOUND.items():
        if tag.startswith(word) or tag.endswith(word) or _norm(tag).endswith(word):
            found |= signalled
    for word, signalled in _PREFIXES.items():
        if tag.startswith(word):
            found |= signalled
    return found


def themes_for(
    tags: Iterable[str] = (),
    texts: Iterable[Optional[str]] = (),
    categories: Iterable[str] = (),
) -> list[str]:
    """The themes an item belongs to, most strongly signalled first.

    ``tags`` are its hashtags; ``texts`` its title, caption and your note;
    ``categories`` the names you filed it under, read like hashtags because
    you chose those words deliberately.
    """
    hits: Counter[str] = Counter()
    for tag in tags or ():
        for theme in _from_tag(tag):
            hits[theme] += 2
    for name in categories or ():
        for word in _WORD.findall(name.lower()):
            for theme in TAG_WORDS.get(_norm(word), ()):
                hits[theme] += 2
    words = {_norm(w) for text in texts or () for w in _WORD.findall((text or "").lower())}
    for word in words:
        for theme in ANYWHERE.get(word, ()):
            hits[theme] += 1
    order = list(THEMES)
    return sorted(hits, key=lambda t: (-hits[t], order.index(t)))


def for_row(row, categories: Iterable[str] = ()) -> list[str]:
    """Themes for a stored item (an ``items`` row or dict)."""
    raw_tags = row["tags"] if row["tags"] else "[]"
    tags = json.loads(raw_tags) if isinstance(raw_tags, str) else list(raw_tags)
    return themes_for(tags, (row["title"], row["description"], row["note"]), categories)


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
    rows = conn.execute("SELECT themes, tags, creator_name, creator_handle, title, description"
                        " FROM items"
                        " WHERE resolve_status = 'ok'").fetchall()
    per_theme: Counter[str] = Counter()
    unthemed_tags: Counter[str] = Counter()
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
            if not _from_tag(tag):
                unthemed_tags[tag] += 1
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
    finally:
        conn.close()
    pct = round(100 * r["themed"] / r["items"]) if r["items"] else 0
    print(f"{r['themed']} of {r['items']} identified saves have at least one theme ({pct}%)\n")
    for theme, n in r["per_theme"]:
        print(f"  {n:>5}  {theme}")
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
        print("\nWords worth adding go in THEMES in favorites/themes.py;"
              " the library re-themes itself on the next start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
