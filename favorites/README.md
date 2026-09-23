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
| YouTube | Playlists and likes via the Data API — but **not Watch later**, which the API has returned empty since 2016. Takeout has it |
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

**Every command says which file it is using.** The server prints a `library:`
line when it starts, and so does every import and backfill, with how many items
are in it — or `NEW -- created just now` if there was nothing there. That line
is the whole defence against ending up with two libraries, where an import
succeeds into one and the museum keeps showing the other. If you keep the
library somewhere other than the default, make it permanent so every command
agrees:

```bash
echo 'export FAVORITES_DB="$HOME/favorites.db"' >> ~/.zshrc
```

Then set up one-tap capture from your phone: **[SHARE_SHEET.md](SHARE_SHEET.md)**.

## What you get per platform

Nothing here downloads media, which keeps the whole thing on the right side of
every platform's terms. It also sets a hard ceiling on what is knowable:

| | Title | Creator | Thumbnail | Caption | Transcript |
|---|---|---|---|---|---|
| YouTube | yes | yes | yes | yes | **yes** |
| TikTok | caption | yes | yes | yes | no |
| Instagram | caption | yes | yes | yes | no |
| Reddit, Bluesky, Vimeo, Spotify | yes | yes | usually | yes | no |
| Blogs, newsletters, news | yes | usually | usually | yes | n/a |

Two mechanisms do the work: a platform's **oEmbed** endpoint where one exists,
and the **OpenGraph** tags every page publishes so that chat apps can show a
preview. The second is the reason this works on a Substack post as well as on a
TikTok.

When both fail, the item is still saved. The link and your own note are the
parts that cannot be recovered later anyway.

**Shorts open as Shorts.** A YouTube Short and a long video share one identity
(`watch?v=<id>`), so the same Short shared from your phone and from a desktop
files once. But a Short opened at `watch?v=` plays letterboxed in the landscape
player, so the library remembers which ones are Shorts and links those to the
Shorts player instead. A `/shorts/` link says so on its face; for anything else,
resolution asks YouTube once, and if the answer is unclear it leaves the format
unknown rather than guessing.

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

### Pictures are kept, not linked

A platform's thumbnail link is not permanent. TikTok signs each one with an
expiry — on a real library, every one of 738 lapsed on the same day, a day or
two after it was fetched — and a lapsed link turns a card blank without any
error to notice.

So the library keeps the picture itself, inside the library file, at the moment
it is saved or backfilled. The library stays one file you can back up by
copying, works offline, and keeps a picture even after the original video is
deleted. For a library resolved before this existed, catch up once:

```bash
python -m favorites.thumbnails
```

It keeps a copy of every picture it can. Where a link has already lapsed, it
asks the platform for a fresh one first — so running it late still recovers
every video that still exists. `--stats` shows how many are kept, per platform.

### Instagram pictures come from the link-preview route

Instagram sends a logged-out browser a page with no picture in it: 20 of 20 on
a real library, and 20 of 20 of the embed pages news sites use. It sends the
picture to **link-preview fetchers** — what iMessage, Slack and Facebook use to
draw the preview when you paste a link — and asked that way, 5 of 5 came back
with one.

So for Instagram only, the museum reads the page the way a chat app does,
introducing itself with the same wording iMessage uses. It is doing the same
job: one preview for one link you chose to keep. The picture is kept at once,
because Instagram's picture links expire too. In a bulk run Instagram goes one
post at a time with a pause between each (`bulk_pause` in `platforms.py`),
about 280 posts in roughly 15 minutes, rather than the usual handful at once.

This is a courtesy Instagram extends, not a promise: if it stops, Instagram
saves keep their captions and whatever pictures were already kept.

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

### Your categories

YouTube's save button and TikTok's favourites both offer the same choice: just
save it, or file it under something. The library keeps that choice. Anything
you file under a category — a YouTube playlist, a name picked in the share
sheet, or one typed on an item's page — gets a page of its own, becomes
searchable by that name, and can turn up on the front page as a shelf.

Just-saved things (Watch later, a plain favourite) stay uncategorised, and
every item page has a box to file them later.

That shelf is the only one on the front page you curated yourself rather than
one the library inferred.

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

## Backfilling your YouTube saves from Google Takeout

The same idea as the TikTok export: bring in what you saved before this existed.

**1. Request the export.** At <https://takeout.google.com>, click **Deselect
all**, tick **YouTube and YouTube Music**, then open **All YouTube data
included**, deselect everything and tick only **playlists**. Leave the rest out
— the full YouTube export includes every video you ever uploaded. Google emails
you a link to a `.zip`, sometimes within minutes, sometimes hours later.

**2. Look before importing.**

```bash
python -m favorites.importers.youtube_takeout ~/Downloads/takeout.zip --list
```

(Your file will have a longer name.) This reads the export, imports nothing,
and lists every playlist it found with its size. Takeout's layout has changed
over the years, so this is the cheapest way to confirm yours reads the way the
importer expects.

**3. Import, then resolve.**

```bash
python -m favorites.importers.youtube_takeout ~/Downloads/takeout.zip
python -m favorites.backfill --limit 100
```

### How playlists map onto the library

| In YouTube | In the library |
|---|---|
| **Watch later** | Just saved — imported, no category |
| **A playlist you made** | A category of the same name |
| **Liked videos** | Left out unless you add `--include-likes` — same rule as TikTok's likes |

A video in several playlists is one item, filed under each of them, dated by
the earliest time you saved it. Use `--only "Watch later"` to bring in just one
playlist, or `--skip NAME` to leave one out — a long YouTube Music playlist, say.

Importing twice is safe. Anything already in the library is left exactly as it
is, note and all, and just gains any categories it was missing.

### Transcripts during a big backfill

Every YouTube video that resolves also gets its caption track fetched, which
makes what was said searchable. That is one extra request per video, and a few
thousand in a row is the kind of volume YouTube has been known to block. For a
first large run, consider:

```bash
python -m favorites.backfill --all --no-transcripts
```

Transcripts for those items can come later; everything else resolves the same.

### Watch the hit rate

Unavailable YouTube videos — deleted, private, removed — still answer with a
page, titled ` - YouTube`. Those are treated as unresolved, the same guard that
caught TikTok's placeholder pages. Old Watch later lists tend to hold a lot of
them, so a hit rate well under 100% is expected; one at 100% is worth a second
look.

## Backfilling your Instagram saves

Request the export in Instagram under **Accounts Center → Your information and
permissions → Download your information**. Choose **Some of your information**,
tick **Saved**, and set **Format: JSON** — the default is HTML, which is far
harder to read reliably.

```bash
python -m favorites.importers.instagram_export ~/Downloads/instagram-export --list
python -m favorites.importers.instagram_export ~/Downloads/instagram-export
```

Point it at `saved_posts.json`, the `saved` folder, or a `.zip` of it. If
`saved_collections.json` is beside it, your collections become categories of
the same name — the same way YouTube playlists do.

**This one arrives ready.** Unlike TikTok's, Instagram's export carries each
post's caption, author, hashtags and the date you saved it — so imported posts
are searchable and on the shelves immediately, with no backfill.

**What it cannot carry is the picture.** Fetch those once after importing:

```bash
python -m favorites.thumbnails
```

It asks Instagram for each post's preview picture, slowly — see *Instagram
pictures come from the link-preview route* above. Posts since deleted or made
private have none to give, and keep their caption card.

Reels are recorded as short-form video, the same as TikToks and YouTube Shorts.

**Meta's exports garble every accent and emoji** — an apostrophe arrives as
`â€™`, an emoji as four symbols of noise. The importer repairs this as it reads,
so captions, names, hashtags and collection names come through as written, and
stay searchable: `don’t` stored as `donâ€™t` would match nothing anyone types.

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
| `importers/` | One-time backfills: a TikTok export, a YouTube Takeout, an Instagram export |
| `tagging.py` | Hashtags and themes, no model required |
| `transcript.py` | YouTube captions, where available |
| `thumbnails.py` | Keeps each picture, because platform links expire |
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
