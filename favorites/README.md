# Faves

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

**On a Mac, double-click `favorites/start.command`.** It updates the code (when
this is a clean checkout of `main`), keeps a private Python environment in
`favorites/.venv` up to date, starts Faves and opens it in your browser.
Leave its window open while you use Faves; close it to stop. It needs
Python 3.10 or newer — the Mac's built-in one is too old; install one from
python.org or with `brew install python`. (If macOS refuses to open it the
first time, right-click it and choose **Open**.)

Double-clicking it while Faves is already running updates the code and, if
the running Faves is behind, restarts it on the new version, so a double-click
always gives you the latest Faves (a running server keeps its old code in
memory but reads its page templates fresh, which is how an update made a page
fail with "Internal Server Error" until a restart).

While it runs, a plugged-in Mac stays awake, and if Faves stops with an
error it starts again in the same window (it gives up, and says why, after
three failed starts in a row). If an older copy of Faves is stuck on port 8000
-- still holding it but no longer answering, which the phone sees as a white
screen -- `start.command` stops that copy and takes over. If some other program
has the port, it names it; set `FAVORITES_PORT` in `~/.favorites.env` to use
another.

**Always on.** Double-click `favorites/always-on.command` once and the Faves
window opens by itself whenever you log in to the Mac, so your phone can
always reach it. Double-click it again to switch that off. (It is a
LaunchAgent that opens `start.command` in Terminal, so Faves keeps Terminal's
permission to read your Downloads folder.) **A white screen on the phone's
Faves icon means Faves isn't running on the Mac**: the Mac restarted or is
asleep, or the window was closed.

Its settings live in `~/.favorites.env`, created with notes on the first run:
`FAVORITES_DB` for which library file to use, and `FAVORITES_TOKEN`, the
password that lets your phone save to it. Switching the password on is also
what makes Faves reachable from other devices; the start window then
prints the addresses to use.

By hand, anywhere:

```bash
pip install -r favorites/requirements.txt
uvicorn favorites.app:app --reload --port 8000
```

Open <http://localhost:8000>. The library is one SQLite file — by default
`favorites.db` in your home folder (`~/favorites.db`), or wherever you point
`FAVORITES_DB`. Back it up by copying that file.

**Every command says which file it is using.** The server prints a `library:`
line when it starts, and so does every import and backfill, with how many items
are in it — or `NEW -- created just now` if there was nothing there. That line
is the whole defence against ending up with two libraries, where an import
succeeds into one and Faves keeps showing the other.

The default used to be a file inside the project folder, which is exactly how
that happened. If an older library is still there and there is none in your
home folder, it keeps being used, and the `library:` line says how to move it.

If you keep the library somewhere other than the default, make it permanent so
every command agrees:

```bash
echo 'export FAVORITES_DB="$HOME/favorites.db"' >> ~/.zshrc
```

Then set up one-tap capture from your phone: **[SHARE_SHEET.md](SHARE_SHEET.md)**
(the Keep it in sync page installs ready-made iPhone shortcuts, and an inbox in
iCloud Drive catches links shared while the Mac is away),
and from Chrome on your computer: **[the Faves extension](extension/README.md)**.

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

So for Instagram only, Faves reads the page the way a chat app does,
introducing itself with the same wording iMessage uses. It is doing the same
job: one preview for one link you chose to keep. The picture is kept at once,
because Instagram's picture links expire too. In a bulk run Instagram goes one
post at a time with a pause between each (`bulk_pause` in `platforms.py`),
about 280 posts in roughly 15 minutes, rather than the usual handful at once.

This is a courtesy Instagram extends, not a promise: if it stops, Instagram
saves keep their captions and whatever pictures were already kept.

### Your note is the best field in the database

Every item has a one-line note — a note. It is optional, it takes three
seconds at save time, and no API will ever give you it. Six months later it is
the difference between a link and a reason.

## The front page

A search box is a fine way to find something you already remember, and useless
for being reminded of something you forgot. So the front page leads with search
and then behaves like this:

- **Search first.** One question — *What are you looking for?* — and one big
  field. As you type it suggests saves (with their pictures), topics, hashtags,
  creators and dates (`/suggest.json`). Under it, a row of ways in: *On this
  day*, *Surprise me* (Shuffle, below) and your biggest topics.
- **On this day.** Things you saved on today's date in earlier years, stacked
  by year. A quiet date widens to the week around it; a date with nothing even
  then shows nothing. The same hook is a filter on the search page
  (`?day=09-27`, or `&week=1` for the week around it), a badge on any card
  saved on this date, and a thread on every item's page.
- **The catalogue.** Topics, creators and platforms, one tap each into search.
- **A creator, everywhere.** A creator's page (`/search?creator=@handle`) gathers their saves from every platform, matching handles in any capitals, and offers "Find them on TikTok · Instagram · YouTube" links. The links are built from a pattern (an idea borrowed from Sherlock's profile table) and never looked up.
- **A digest of the last month.** Not just a count — a comparison. *"Nine saves
  this past month, up from four. Spread across TikTok, YouTube and Instagram.
  Recurring threads: housing, localgov. One creator is new to the library."*
- **Rotating shelves**, as swipeable carousels with a description under every
  picture. Recently saved, then some combination of a theme, a month, a creator
  you keep returning to, *This time last year* (six weeks either side of today,
  a year ago) and *Throwbacks* — a random handful of things saved more than
  four months ago.
- **Topics.** Themes as tiles, each framed by three of its own pictures; every
  topic is on `/topics`.
- **On your shelf.** The creators you keep saving, like books on a shelf.

- **This week.** How this week compares with last, the topic it leaned towards,
  and one old save worth another look (the same one all week).
- **This season.** The current season as a topic — every autumn (or winter…) you
  have kept things through — on the front page and first on `/topics`.
- **Rabbit hole** (`/wander`, and *Keep going* on every save). Follows one of the
  save's threads — its topic, creator, date, season or a hashtag — to somewhere
  you have not just been, and says which thread it took. It never dead-ends.
- **Your year** (`/year`, `/year/2025`). A Wrapped-style page: top topics and
  creators, busiest month, longest saving streak, favourite day, first and latest
  saves, and how the year compares with the last.

Every item page ends with **Connected by**: its topics, its creator, the same date
in other years, its season, and hashtags it shares — each a way on to more saves.

The arrangement is seeded by the date, so it holds still through the day and
looks different tomorrow.

None of this needs a language model. Every sentence in the digest is computed
from counts the library already holds, which means it works on day one with no
API key and never invents a fact. `museum.digest()` returns its components
alongside the prose, so a model can be added later to rewrite the wording
without having to re-derive any of the numbers.

## On your phone

Added to the home screen, Faves opens with no browser around it: no Back
button, no address bar. So it carries its own.

- **Tabs:** Home · Search · **Shuffle** · Topics · **More**. More is a sheet
  holding everything else — Keep a link, Give saves a topic, Notes, Sort things
  out, Your year, Rabbit hole, Keep it in sync, and Day/Night. (`/more` is the
  same list as a page.)
- **Back goes where you came from.** Every page below the tabs has a Back in
  the top bar, named for the page before it — "‹ Undefined saves", say, after
  opening a save from that list. Each page notes itself on a trail kept for the
  visit (`sessionStorage`); a tab's own page starts the trail afresh. With no
  script, Back is a plain link to the page's parent.
- **Saving stays put.** Topics, notes and categories on a save's page are saved
  in place, so Back (and the iPhone's edge swipe) still goes to the list you
  came from, and a list you return to is redrawn if something on it changed.
- **Search results keep coming** as you scroll, and the Filters/sort bar rides
  along under the top bar.
- **Shuffle** (`/shuffle`) is your saves one screen at a time, flicked up like a
  reel: the picture on a blurred wash of itself, its label, and *Watch*,
  *Topics*, *Note* and *Details* within a thumb's reach. It is the phone's own
  scrolling, snapping a screen at a time, with no gesture code.
  - It takes the same filters as search, so any list has **Swipe through these**
    (in its own order); the tab deals everything at random.
  - A shuffle is seeded (`?seed=`), and the address follows the card on screen
    (`&at=`), so reloading — or coming back from a save's page — lands on the
    same card. More cards load as you near the end (`/shuffle/cards`).
  - **Untagged saves** (`/shuffle?theme=Undefined&order=newest`) come with the
    topics to tap, most-used first. Tap one or two, *Done*, and it moves on to
    the next; the counter in the top bar goes down as you go.
- **Watching in Faves.** Where the platform publishes an embed player
  (YouTube, TikTok and Instagram), a save's picture carries a play button, on
  its page and in Shuffle. A tap swaps in the platform's own player, right
  there; the close button puts the picture back, and flicking on in Shuffle
  stops it. The way out to the app ("Open on TikTok", "Watch the Short") stays
  where it always was, and beside the player too.
  - Nothing loads from the platform until you press play, and YouTube plays
    from its privacy-enhanced `youtube-nocookie.com` domain. Faves never copies
    a video: the platform streams it, as it would on any page that embeds it.
  - Players: `youtube-nocookie.com/embed/<id>`, `tiktok.com/player/v1/<id>` and
    Instagram's `/reel/<code>/embed/` (`platforms.embed`). TikTok photo
    slideshows, other platforms and anything without an id link out as before.
  - Some videos won't play embedded -- the owner turned embedding off, the
    account is private, or the video is gone -- and the player then says so;
    the link out still works. On an iPhone a video may need a second tap, in
    the player, to start with sound.
- Touch details: every tap target is at least 44 points, fields are 16px so iOS
  doesn't zoom in on them, sheets pull down to close, and pages crossfade where
  the browser supports it (iOS 18.2 and later).

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

## Search and filters

`/search` is the whole library, narrowed as far as you like. With nothing chosen
it is everything, newest first. **Search** in the top bar goes there from every
page, and the front page has a *Browse the collection* strip with your biggest
themes, creators and platforms, each one click into the filtered view.

Beside the results, every way the library can be cut, each with a count —
in the order people reach for them:

| Filter | What it reads |
|---|---|
| Platform | Where it came from |
| Creators | Who made it |
| Themes | What it is about — see below; *Undefined*, at the top, is the saves no theme covers yet |
| Hashtags | The creator's own hashtags, minus distribution noise like #fyp |
| Your categories | Playlists, collections, and anything you filed |
| Length | Under a minute, 1–3, 3–10, 10–30, over 30 minutes — YouTube and TikTok |
| Year saved | The day you saved it, by year |
| Kind | Short-form or long-form video, where known |
| Season saved | The same day, by season across every year (northern hemisphere; winter is December–February) |
| Your notes | Only the saves you wrote a note on |

Filters combine, and the words in the search box combine with them. Each count
is what that option would leave *given the other filters*, so choosing 2024
shows how much of each platform is in 2024 instead of greying the rest out.
Clicking a chosen option again, or the × on its chip, removes it.

Hashtags on only one save are left out of the list: at that point they describe
a video, not a pattern. They are still searchable.

Every view is a web address, so a view worth keeping — *TikTok saves about
Dogs from summers* — can be bookmarked, and the back button undoes a filter.
Nothing here needs JavaScript.

### Themes

A theme is a subject in plain words — *Dogs*, *Food & cooking*, *Cities &
urbanism* — defined in `favorites/themes.py` by the words that signal it. Each
save's evidence is weighed:

| Evidence | Counts |
|---|---|
| You put it in the topic yourself | always wins |
| You filed everything by its creator there | 4 |
| A hashtag you taught it, or a word in a category name you chose | 3 |
| A hashtag that is a vocabulary word (`#dogs`), or splits cleanly into one (`#dogsoftiktok`) | 2 |
| The creator's handle (`@thepastaqueen`), or most of that creator's other saves being there | 2 |
| A word in the caption, title or your note; a word said twice in a transcript | 1 |

A save goes in every topic with at least half the evidence of its strongest,
up to three. A caption that brushes past three or more subjects once each
files nothing: it isn't sure of any of them. A compound hashtag is read only
when *all* of it splits into known words (`#dogs`+`of`+`tiktok`), which keeps
`#husband` out of Music and `#snowflake` out of Nature. Words that mean too
many things in a sentence — *work*, *home*, *budget*, *train* — count only as
hashtags, and words for where something was said (*radio*, *podcast*) are not
subjects at all.

Saves no theme recognises are gathered under **Undefined**, first in the Themes
filter and last in the front page's theme row. It is a to-do list rather than a
subject.

**Fixing a topic.** Every save's page says why it is in each topic ("#concert ·
'song' in the caption") and has **Change topics**: tick the topics it belongs in,
and optionally *do the same for everything by this creator*. Only the
difference from what Faves worked out is kept, so improvements to the
vocabulary still reach it.

**Sort things out** (`/topics/sort`) is where a few minutes fix hundreds of saves:
the hashtags on two or more saves that it doesn't know yet — tap a topic to
teach one, or *Not a subject* to stop it being listed — and the saves it filed
on a hunch (one word in passing), to confirm or move. Everything you teach is
kept in the library file (`theme_rules`), and every answer re-sorts the whole
library at once.

It is a vocabulary, not a model: local, instant, and it can always say why. The
cost is that it only knows the words it has been given — or that you teach it.
To see what it covers and what it is missing from the command line:

```bash
python -m favorites.themes
```

That prints how many saves have a theme, how many each theme holds, how many
are on a hunch, the hashtags on your saves that no theme recognises yet, and --
for the saves with no theme -- how many have no hashtags at all and which
caption words recur among them. Teach them at `/topics/sort`, or add words to
`THEMES`; the library re-themes itself the next time anything opens it.
The list leaves out hashtags about reach rather than subject (`#fyp` in all its
spellings, `#fypシ` included) and creators tagging their own name, which the
Creator filter already covers.

### Captions on labels

The platforms' captions are not written for a label: TikTok's title is the
whole caption with its hashtag pile, Instagram's is wrapped in "1,204 likes, 31
comments - …". `favorites/blurb.py` cleans them — no wrapper, no trailing
hashtags or @mentions, no YouTube chapter lists or "Subscribe" lines — and
trims at a whole sentence, so a label never stops mid-word. The headline is the
first sentence; the description carries on from there. The stored text is
unchanged, so search still finds every hashtag, and each save's page keeps the
original caption one tap away.

Search results and lists hang as a **salon wall**: each picture keeps its own
shape (vertical video tall, long-form video wide, Instagram posts square), labels
run as long as they need to, and saves with your note stand out.

### Video length

No quick lookup or data export says how long a video is, but YouTube's and
TikTok's own pages do, so the library reads it from there: new saves as they
are shared, and an existing library once with

```bash
python -m favorites.lengths
```

which reads one page at a time with a pause between — about 20 minutes for
several hundred TikToks. Run it again after a backfill to cover the new ones.
Instagram's pages do not state a length (none of three on a real library did),
so Instagram saves have none and sit outside the Length filter rather than
being guessed at. Cards show the length in the corner, the way video sites do.

### Hashtags and search words

Hashtags come straight from the caption. The library also pulls content words
and two-word phrases from the title, description, note and transcript, and
those make the search box find more. They used to be offered as "keywords" to
filter by, and on a real library they were noise — "five minutes", "went
sideways" — so the themes above replaced them.

## Keeping it in sync

The platforms don't let another app read your saves, so Faves does the
next-best things, all on the **Keep it in sync** page (`/sync`, in the footer):

- **The watched folder.** Started with `start.command`, Faves looks in
  `~/Downloads` every minute for a TikTok, Instagram or Google Takeout export
  and imports it by itself — favourites and saves only, never likes — then fills
  in titles and pictures for the first 50. Files are never moved or deleted;
  each is imported once. Watch other folders (a Google Drive folder, say) with
  `FAVORITES_WATCH` in `~/.favorites.env`, separated by `:`; set it to `""` to
  switch watching off. By hand: `python -m favorites.watch ~/Downloads`.
  The first time, macOS may ask whether Terminal can use your Downloads folder:
  say OK.
- **Reminders.** When a platform's last export is more than 60 days old, the
  front page says so, with a link to request a fresh one ("Later" hides it for
  30 days). Only platforms you have imported from before.
- **YouTube, signed in.** Connect Google once and every playlist you made syncs
  daily, filed under its name. Google closed Watch later and Liked videos to
  apps in 2016; a Takeout scheduled *every 2 months* to Drive covers Watch
  later. Setup (about 10 minutes, once): a Google Cloud project with the YouTube
  Data API on, an OAuth client of type *Desktop app*, and its ID and secret in
  `~/.favorites.env` as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`. Publish the
  consent screen, or Google signs you out every 7 days. Read-only; Disconnect
  revokes it. Connecting only works on the Mac itself.
- **Your phone.** The page shows the address and (on the Mac only) the password
  for the one-tap share-sheet Shortcut in `SHARE_SHEET.md`.
- **TikTok's sharing tool.** TikTok's Data Portability API can send favourites
  straight to an app — but only for accounts in the EEA and UK, after an app
  review. Outside those, the export is the way.

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
what lets Faves show months, recurring creators and *Throwbacks*
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
  the digest needs. Faves starts working after the first batch.
- **Resumable.** Progress lives in the database. Stop it, re-run it, do it over a
  week -- it continues where it left off.
- **It gives up eventually.** An item that fails three times is left alone. A
  video deleted three years ago is not coming back, and re-asking costs budget
  that live items need.

Check progress any time with `python -m favorites.backfill --stats`.

Saves that gave up can be tried once more without a terminal: on the Mac, open
**Keep it in sync** and press **Look them up again** under *Titles and pictures*.
It gives every save still missing its details one more try, in the
background, and the band says how many it found. Worth doing after a platform
changes what it shares, as TikTok's oEmbed did in October 2026.

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

## The library in Postgres

By default the library is one SQLite file. Set `DATABASE_URL` to a Postgres
database (Supabase's, say) and it lives there instead, in a schema of its own
called `faves` (`FAVORITES_PG_SCHEMA` to change it), set up on first use. This
is the first step towards running Faves in the cloud, where there is no disk to
keep a file on.

The code is the same either way: `pg.py` gives Postgres a connection that
answers like SQLite's, and the few SQLite functions the queries use
(`json_each`, `json_array_length`, `julianday`, `COLLATE NOCASE`) are defined in
the schema under the same names. Full-text search is the one place with two
versions: FTS5 in SQLite, a `tsvector` column in Postgres (`db.fts_hits`).

The whole test suite runs against both. To run it on Postgres, point it at a
throwaway database: every test gets an empty schema of its own, dropped after.

    FAVES_TEST_DATABASE_URL=postgresql://postgres@localhost:5432/postgres pytest tests/test_favorites_*.py

### Moving to the cloud

To move the library on your Mac into Supabase:

1. Have your **Supabase database password** ready: the one you chose when you
   made the Supabase project. It's not your Faves password, and not your
   Supabase login. If you've forgotten it, open your project on supabase.com
   and go to Project Settings → Database → Reset database password.
2. Double-click **`move-to-cloud.command`**. The first time, it asks for the
   cloud library's address: in Supabase, click **Connect** at the top, choose
   **Session pooler**, and copy the address that starts `postgresql://`.
   Paste it in, then type the Supabase database password when asked (it
   won't show as you type). It checks the address connects before keeping it, in
   `~/.favorites.env`, the same settings file `start.command` reads.
3. It copies everything, showing progress, then a table: each kind of thing on
   this Mac next to the same in the cloud, and how much of the free plan's
   500 MB the database now uses.
4. Double-click **`start.command`**. Faves on this Mac now uses the cloud
   library. If it was already running, it restarts itself onto it.

What it does, and doesn't:

- **It copies everything**: saves, notes, categories, the rooms you picked
  for a save, a creator or a hashtag, the imports it remembers, and the
  pictures.
- **Pictures go up phone-sized**: no more than 720 pixels on the long side,
  as WebP. A full-size TikTok cover can be several megabytes; the copy is
  tens of kilobytes. From then on, pictures fetched for the cloud library
  are kept phone-sized too. The file on the Mac keeps its originals.
- **The file on your Mac is never changed.** It is opened read-only. It stays
  as it was, a complete backup. To go back to it, take the `DATABASE_URL`
  line out of `~/.favorites.env` and double-click `start.command`.
- **It is safe to run again.** Saves are matched by their link, never by
  number, so nothing is duplicated. Where the cloud already has something,
  the cloud's version wins: a note written on your phone after the move
  is never replaced by the Mac's older copy. The Mac only fills gaps, such
  as a note the cloud doesn't have, or a save the cloud couldn't look up.
  If Faves saved anything to the Mac's file after you moved, run it once
  more to bring those across.
- **The address holds your password**, so `~/.favorites.env` is readable
  only by you. Use the **Session pooler** address, which works on any
  network. The **Direct** one needs IPv6, which many networks lack, and the
  **Transaction** one doesn't keep Faves' settings between queries.

From the Terminal, the same move is `python -m favorites.cloud_move`, with
`--from PATH` to move a library file other than the usual one.

### Faves in the cloud

The same app also runs on Vercel, at **https://tik-tok-analyzer.vercel.app**,
reading the library in Supabase. Your phone reaches it anywhere, with no
Tailscale, whether or not the Mac is awake.

To switch it on, in one sitting:

0. Once, in Vercel: open the **tik-tok-analyzer** project, then **Settings →
   Build and Deployment**. Set **Framework Preset** to **FastAPI**, empty the
   **Root Directory** box (it said `algorithmic-mirror`, the old analyzer),
   and save each. From then on the project builds Faves instead.
1. Double-click **`move-to-cloud.command`** (above). When the move is done,
   it opens Vercel's settings page and puts the two settings the cloud copy
   needs on your clipboard, one at a time: `DATABASE_URL` (the library's
   address) and `FAVORITES_TOKEN` (your Faves password). Paste each into
   Vercel as an environment variable.
2. In Vercel, **Redeploy** the newest deployment, so it picks the settings up.
3. On your phone, open the address and sign in with the password. Then
   **Share → Add to Home Screen**.
4. Install a fresh **Save to Faves**, ready-made and already pointed at the
   cloud. On the phone, delete the old one first: in Shortcuts, press and
   hold it, then Delete. Then, on the Mac, open Faves → More → **Keep it in
   sync** → **Install Save to Faves**, and choose **Add Shortcut**. iCloud
   puts it on your phone. (Or edit the old one's address to
   `https://tik-tok-analyzer.vercel.app/save`; the password stays the same.)
5. On the Mac, double-click **`start.command`**. Faves there becomes the
   helper (below).

**It shows nothing without the password.** Every page asks for it once per
phone or browser, then remembers it for a year. If a setting is missing it
says which one, and shows nothing else: it never falls back to being open.
Change `FAVORITES_TOKEN` (on the Mac and in Vercel) to sign every browser out.

**What happens where.** The cloud copy only answers requests. It can't watch a
folder or wake up every minute, so Faves on the Mac keeps doing that, into
the same library:

| In the cloud | On the Mac (the helper) |
|---|---|
| Browsing, search, Shuffle, notes, topics | Imports exports that land in Downloads |
| Saving from the phone's share sheet | Reads the phone's inbox file in iCloud Drive |
| Saving from the Keep page and the Chrome extension | Syncs YouTube playlists |
| | Fills in shared saves the cloud couldn't look up |

The last one matters most for Instagram, which can refuse requests from
cloud servers. The save is kept either way, and the Mac fills in its title
and picture the next time it runs.

**How it's put together.** `pyproject.toml` tells Vercel what to install and
to run `favorites.app`. `vercel.json` runs it in Portland (`pdx1`), next to
the database in Oregon. `.vercelignore` uploads only `favorites/`, so the
rest of the repo stays out. `cloud.py` holds the sign-in rules.

## Privacy

The library is a file on your machine, or with `DATABASE_URL` set, in the
Postgres database you pointed it at. Nothing else is uploaded, and the only
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
| `pg.py` | The library in Postgres (Supabase), answering like SQLite |
| `cloud.py` | Faves on Vercel: the sign-in, and what the cloud copy leaves to the Mac |
| `cloud_move.py`, `move-to-cloud.command` | Moves the Mac's library into the cloud |
| `museum.py` | The digest, the rotating shelves and the hooks (On this day, topics, threads) |
| `explore.py` | Search and filters, including On this day |
| `looks.py` | Each theme's band colour, icon and emoji |
| `templates/`, `static/` | The pages, in the *Faves* design system (version 2, "Sweet Spot"): lavender, candy-colour section bands, round type, subtle scroll motion.: `style.css` holds its tokens and components, `museum.js` the little behaviour a plain page cannot do (carousel dots, the phone filter sheet, suggestions, the colour mode, Back's trail, sheets, saving in place, Shuffle's feed). Every page works without it |
| `app.py` | The web app and the `/save` endpoint |

Tests are in `tests/test_favorites_*.py` and run with the rest of the repo's
suite (`pytest tests/`).

## Not built yet

- **A native app.** The share sheet works today through an iOS Shortcut and an
  installed PWA on Android, which is enough to find out whether you actually
  use this before anyone builds a real one.
- **A model pass over the digest.** The numbers are already assembled for it.
