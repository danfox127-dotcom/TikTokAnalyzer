# Favorites

A searchable library of the things you save, across every platform, that you
never have to file by hand.

You share a link into it. It works out what the thing is, who made it, and what
it looks like, and shelves it. Later you either search for it, or you open the
front page and it shows you things you had forgotten you kept.

## Why it works this way

The obvious design is to connect to each platform's API and pull down your
saved items on a schedule. That design does not survive contact with reality:

| Platform | Can an app read your saves? |
|---|---|
| YouTube | Yes — playlists and likes, via the Data API |
| Reddit | Yes — saved posts, via OAuth |
| Pinterest | Yes |
| X | Bookmarks, on paid API tiers only |
| **TikTok** | **No.** Favorites appear only in a data export |
| **Instagram** | **No.** Saved posts appear only in a data export |

And the exports are worse than they look: by the time you download one, the
media URLs inside it have expired, so there is nothing left to read a
transcript from.

Sharing at the moment you save routes around all of it. Every platform has a
share sheet, the link is alive when you send it, and it takes two taps. So the
share sheet is the front door, and a data export is only ever a one-time
backfill of history.

## Running it

```bash
pip install -r favorites/requirements.txt
uvicorn favorites.app:app --reload --port 8000
```

Open <http://localhost:8000>. The library is one SQLite file — by default
`favorites/favorites.db`, or wherever you point `FAVORITES_DB`. Back it up by
copying that file.

Then set up one-tap capture from your phone: **[SHARE_SHEET.md](SHARE_SHEET.md)**.

## What you get per platform

Nothing here downloads media, which keeps the whole thing on the right side of
every platform's terms. It also sets a hard ceiling on what is knowable:

| | Title | Creator | Thumbnail | Caption | Transcript |
|---|---|---|---|---|---|
| YouTube | yes | yes | yes | yes | **yes** |
| TikTok | caption | yes | yes | yes | no |
| Instagram | sometimes | sometimes | sometimes | sometimes | no |
| Reddit, Bluesky, Vimeo, Spotify | yes | yes | usually | yes | no |
| Blogs, newsletters, news | yes | usually | usually | yes | n/a |

Two mechanisms do the work: a platform's **oEmbed** endpoint where one exists,
and the **OpenGraph** tags every page publishes so that chat apps can show a
preview. The second is the reason this works on a Substack post as well as on a
TikTok.

When both fail, the item is still saved. The link and your own note are the
parts that cannot be recovered later anyway.

### Adding a platform

Everything a platform needs is one descriptor in `platforms.py`: the hosts it
owns, how to derive a stable **identity** from a URL, how to build a
**browsable link**, its oEmbed endpoint if it has one, where the @handle lives,
and whether transcripts exist.

Identity and link are deliberately two fields, because they are two jobs. A
TikTok's identity is its video id alone — the same video files once whether it
arrived from a data export (handle stripped) or a share sheet (handle present).
But `tiktok.com/video/<id>` is not a route TikTok serves, so the link has to be
rebuilt with the handle. They used to live in separate functions that quietly
stopped agreeing, and every link in the library 404'd. Now they sit in one
object, and a test asserts they still match.

### Your note is the best field in the database

Every item has a one-line note — a placard. It is optional, it takes three
seconds at save time, and no API will ever give you it. Six months later it is
the difference between a link and a reason.

## The front page

A search box is a fine way to find something you already remember, and useless
for being reminded of something you forgot. So the front page is arranged like
a small museum:

- **A digest of the last month.** Not just a count — a comparison. *"Nine saves
  this past month, up from four. Spread across TikTok, YouTube and Instagram.
  Recurring threads: housing, localgov. One creator is new to the library."*
- **Rotating shelves.** Recently saved, then some combination of a theme, a
  month, a creator you keep returning to, and *From the vault* — a random
  handful of things saved more than four months ago.

The arrangement is seeded by the date, so it holds still through the day and
looks different tomorrow.

None of this needs a language model. Every sentence in the digest is computed
from counts the library already holds, which means it works on day one with no
API key and never invents a fact. `museum.digest()` returns its components
alongside the prose, so a model can be added later to rewrite the wording
without having to re-derive any of the numbers.

### How themes are worked out

Hashtags come straight from the caption. Everything else is content words and
two-word phrases pulled from the title, description, note and transcript.

On a single item that signal is weak — a ten-word caption is not much to go on.
It earns its keep across the collection, where a term that recurs in several
different saves becomes a theme. That is the honest version of "what am I into
lately": it emerges from repetition rather than from one model's guess about
one video.

## Backfilling your history from a TikTok export

The share sheet only captures from today onward. To bring in what you saved
before this existed, import a data export.

```bash
python -m favorites.importers.tiktok_export ~/Downloads/user_data_tiktok.json
python -m favorites.backfill --limit 100     # see how many resolve
python -m favorites.backfill --all           # then let it run
```

**What an export actually gives you is two fields** -- a date and a link -- and
the link is an id-only URL on `tiktokv.com` with the @handle stripped. So the
import cannot produce a title or a creator. It produces dated URLs, and a
second pass fetches the rest one at a time.

**The date is the part worth having.** Favourites go back years. That history is
what lets the museum show months, recurring creators and *From the vault*
immediately, instead of after six months of collecting.

### Favourites, not likes

An export carries both, and they are not the same thing. A favourite is a
deliberate "keep this". A like is a tap. The like list is also usually **capped**
and covers only recent months, so importing it buries a multi-year collection of
deliberate saves under a short burst of taps.

Likes are therefore opt-in (`--include-likes`) and tagged `source='export-like'`
so you can tell them apart or delete them later.

### Resolution is slow, and that is fine

TikTok throttles hard -- expect roughly **700 an hour**. A few thousand
favourites is a few hours of a script running unattended, not a few hours of
your attention. Three things make that survivable:

- **Newest first.** Recent videos are likeliest to still exist, and they are what
  the digest needs. The museum starts working after the first batch.
- **Resumable.** Progress lives in the database. Stop it, re-run it, do it over a
  week -- it continues where it left off.
- **It gives up eventually.** An item that fails three times is left alone. A
  video deleted three years ago is not coming back, and re-asking costs budget
  that live items need.

Check progress any time with `python -m favorites.backfill --stats`.

### A 100% hit rate means something is wrong

A deleted video, a private account and a login wall all answer **200 with a
well-formed page** whose title is just `TikTok`. An early version of this
accepted that as a successful resolution, and cheerfully reported that every
link in a five-year-old library was still alive.

Resolution now refuses a title that is only the site's own name, and refuses a
creator taken from the same place. If you resolved a library before that guard
existed, correct it in place:

```bash
python -m favorites.backfill --recheck --all
```

That clears the junk titles and puts the genuinely dead links back in the queue,
where they will fail honestly. Expect the reported hit rate to drop -- that is
the repair working, not breaking.

### Items that never resolve are still kept

Deleted videos and private accounts cannot be recovered by any method. Those
rows stay in the library with their link and date, and stay off the shelves --
a wall of untitled URLs is worse than an empty shelf. They still count, and the
front page tells you how many are outstanding.

### What this does not cover

Instagram. `parsers/instagram.py` does not extract saved posts at all, so an
Instagram backfill means writing that parser first.

## Privacy

The library is a file on your machine. Nothing is uploaded, and the only
outbound requests are to the platforms themselves, to read the public metadata
for a link you just shared.

If you put this on an address your phone can reach from anywhere, **set
`FAVORITES_TOKEN`** — without it, the save endpoint is an open write to your
library.

## Layout

| File | What it does |
|---|---|
| `platforms.py` | What we know about each platform, one descriptor each |
| `resolve.py` | A shared link → title, creator, thumbnail |
| `tagging.py` | Hashtags and themes, no model required |
| `transcript.py` | YouTube captions, where available |
| `db.py` | SQLite storage and full-text search |
| `museum.py` | The digest and the rotating shelves |
| `app.py` | The web app and the `/save` endpoint |

Tests are in `tests/test_favorites_*.py` and run with the rest of the repo's
suite (`pytest tests/`).

## Not built yet

- **A native app.** The share sheet works today through an iOS Shortcut and an
  installed PWA on Android, which is enough to find out whether you actually
  use this before anyone builds a real one.
- **A model pass over the digest.** The numbers are already assembled for it.
