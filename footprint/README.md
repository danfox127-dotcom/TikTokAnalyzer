# Footprint

Where a username — or a brand — exists across the web, how sure we are, and
whether it looks like the same person or brand everywhere.

It started as a look at [Sherlock](https://github.com/sherlock-project/sherlock),
the best-known open-source username checker, and at why it is slow and
sometimes wrong. Footprint keeps Sherlock's idea and its site list, and changes
how the checking is done.

## Running it

**On a Mac, double-click `footprint/start.command`.** It keeps a private Python
environment in `footprint/.venv` up to date, starts Footprint and opens it in
your browser at <http://localhost:8010>. Leave the window open while you use it;
close it to stop. It needs Python 3.10 or newer (`brew install python`, or
python.org). If macOS refuses to open it the first time, right-click it and
choose **Open**.

By hand, anywhere:

```bash
pip install -r footprint/requirements.txt
uvicorn footprint.app:app --port 8010
```

The first start downloads the two site lists (about 360 KB) into
`~/.footprint`. They refresh themselves weekly. Footprint only listens on your
own computer.

## What it does differently from Sherlock

| | Sherlock | Footprint |
|---|---|---|
| **Waiting** | Up to 60 seconds per site; the whole run waits for the slowest | 10 seconds until a site's speed is known, then twice its usual slow answer (3–12 s). Sites that keep timing out go in a slow lane, checked last with a 4-second limit |
| **Results** | Printed in alphabetical order, so a slow site near the top freezes the screen | Shown the moment each site answers |
| **Order** | Every site the same | The ~56 big platforms first, in their own band. "Big platforms only" answers in a few seconds |
| **Reading** | Whole pages | Only as much of a page as the verdict needs; a quick `HEAD` request where the status code is enough |
| **Verdicts** | Found / not found | Found or not found, **confirmed** or **likely**, or **unclear** — with the reason in words |
| **Broken sites** | Volunteers notice and report them | Re-tested every day; broken ones are set aside automatically |
| **Beyond "exists"** | — | Public profile details, a same-person score, a time-zone hint, a brand report |

## The verdicts

Each site's recipe describes what a page looks like when an account **exists**
and when it's **missing**. The site list from
[WhatsMyName](https://github.com/WebBreacher/WhatsMyName) records both;
Sherlock's records only the "missing" side.

- **Found · confirmed** — the page looks like a profile, *and* not like a "no
  such account" page.
- **Found · likely** — no "not found" message, but this site only has one sign
  to check, so it isn't confirmed.
- **Not found** — confirmed or likely, the same way.
- **Unclear** — a bot wall (Cloudflare and the like), a refusal, a timeout, or a
  page that looks like neither answer. Sherlock calls most of these "found".
  Footprint never does.
- **Can't exist here** — the site doesn't allow names like this one, so it
  wasn't asked.
- **Set aside** — the daily health check found this site giving wrong answers.

## The daily health check

The first time you use Footprint each day, it re-tests every site in the
background with two names: an account known to exist (it should be found) and
twelve random letters (they shouldn't be). Sites that fail are skipped until
they pass again. If most sites fail at once, that's your connection rather than
the sites. Footprint then keeps yesterday's results and tries again in an hour.
Adult sites are never contacted in the background. The **Site health** page
lists every site, its state, how fast it usually answers and its current time
limit, with a **Re-check now** button.

## Profile details and "same person?"

For each account found, Footprint reads only what the platform shows anyone.
It never signs in. If a platform shows a profile only to signed-in visitors,
the profile is marked as hidden and left at that.

- GitHub, Bluesky, Mastodon and Reddit run open endpoints. These give a name, a
  bio, a photo, links, and recent post times. GitHub and Mastodon can also
  give a **self-reported location**.
- GitLab now gives only a name and a photo to anonymous visitors.
- TikTok includes the profile in its own page.
- Everything else falls back to the page's preview tags: name, description and
  picture.

Then each pair of accounts is scored on evidence that they belong to the same
person or brand. Every point comes with its reason:

| Evidence | Points |
|---|---|
| One profile links straight to the other | 40 |
| Both link to the same outside page (not just a bare platform address) | 25 |
| Profile photos match (a 64-bit picture fingerprint, so a resized or recompressed copy still matches) | 25 |
| Same display name (near-identical: 5) | 15 |
| Bios share distinctive wording | 10 |
| Same self-reported location | 5 |

60+ is **very likely the same**, 30–59 **possibly**, under 30 **no evidence**.
A different location is noted, never penalised.

## Location and the time-zone hint

- **Self-reported location** is shown only where someone typed it into a public
  profile: GitHub, Mastodon profile fields, and anything else a page states.
  TikTok, Instagram, Bluesky and Reddit don't show one publicly.
- **The time-zone hint** reads the times of public posts (GitHub, Bluesky,
  Mastodon, Reddit). People sleep, so the quietest five hours in a row are
  taken as about 4 am local time. It needs at least 30 posts. It is always
  given as a band of ±2 hours, with example regions, and never narrowed to a
  place. An account that posts around the clock (a scheduler or a team) has
  no clear rhythm, and the hint says so.
- For a brand, the same chart answers a more useful question: when do our
  accounts actually post?

## The brand consistency report

Give it a brand name, the official website, and up to five handles.

1. **The website is the source of truth.** A profile is *confirmed ours* if the
   site links to it (a plain link, a `rel="me"` link, or its JSON-LD `sameAs`).
   A profile that links back to the site, or names it in its bio, also counts.
2. Every other account with your handle is scored against the confirmed ones:
   *probably ours*, *possibly ours — check*, or *taken — no link to the brand*
   (a squatter or an impersonator).
3. Where the handle is free, it says so. Where the website links to a profile
   that no longer exists, it says that too.
4. **What to fix:**
   - different names, photos or locations across your profiles
   - profiles that don't link back to the site
   - different handles on different platforms
   - accounts with no public post in 180 days
   - profiles that are probably yours but missing from the website
5. **When your accounts post**, as a 24-hour chart.
6. **A ready-to-paste JSON-LD block** with the `sameAs` list. Search engines and
   AI assistants use it to tie your accounts to your organisation. Untick
   anything that isn't yours before copying.

Download it as a single self-contained HTML file to share. It has no outside
fonts, scripts or pictures, so it opens the same in an email attachment. You
can also download the data as JSON.

## Using it responsibly

Finding where a name exists is how journalists start an investigation, how
brands find impersonators, and how people audit their own footprint. It is also
how stalkers start. Footprint reads only public pages, never signs in, keeps
no record of the people you look up (only the brand reports you choose to make),
and gives location only as people stated it or as a deliberately broad
time-zone guess.

## Credits

Site lists from [Sherlock](https://github.com/sherlock-project/sherlock) (MIT)
and [WhatsMyName](https://github.com/WebBreacher/WhatsMyName) (CC BY-SA 4.0).
They are downloaded to your computer at run time, not copied into this
repository. Bot-wall fingerprints are Sherlock's.

## For developers

| File | What it does |
|---|---|
| `manifest.py` | Downloads and merges the two lists into one `Site` per domain, each with every `Probe` (recipe) known for it |
| `tiers.py` | The big platforms, in order |
| `check.py` | The engine: `judge()` turns a response into a verdict; `search()` streams results |
| `store.py` | SQLite memory in `~/.footprint/footprint.db`: timings, health, reports |
| `health.py` | The daily self-test |
| `profile.py`, `match.py`, `timezone.py` | Profile details, the same-person score, the time-zone hint |
| `brand.py` | The brand report |
| `app.py` | The web app; results stream as Server-Sent Events |

Tests: `pytest tests/test_footprint_*.py`. They use made-up sites and mocked
responses, and never touch `~/.footprint` (`tests/conftest.py` points
`FOOTPRINT_HOME` at a temporary folder).
