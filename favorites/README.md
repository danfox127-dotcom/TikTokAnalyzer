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
| `resolve.py` | A shared link → title, creator, thumbnail |
| `tagging.py` | Hashtags and themes, no model required |
| `transcript.py` | YouTube captions, where available |
| `db.py` | SQLite storage and full-text search |
| `museum.py` | The digest and the rotating shelves |
| `app.py` | The web app and the `/save` endpoint |

Tests are in `tests/test_favorites_*.py` and run with the rest of the repo's
suite (`pytest tests/`).

## Not built yet

- **Backfilling history from exports.** `parsers/tiktok.py` in this repo
  already reads `FavoriteVideoList` and `FavoriteCollectionList` out of a
  TikTok export, so the hard part is done; it needs wiring to `upsert_item`.
  Expect thin results — expired media, no transcripts.
- **A native app.** The share sheet works today through an iOS Shortcut and an
  installed PWA on Android, which is enough to find out whether you actually
  use this before anyone builds a real one.
- **A model pass over the digest.** The numbers are already assembled for it.
