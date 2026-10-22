# One-tap capture from your phone

The whole design rests on saving being effortless. If it takes more than two
taps you will stop doing it, and an encyclopedia nobody adds to is just a
database.

This is the direct save: one video at a time, from the app you are watching
it in, at the moment you decide to keep it. The TikTok and YouTube backfills
are for history — everything from here on can come in this way instead, with
no second save inside the app and no export to wait for.

None of this needs an app store, an Apple developer account, or a native build.
The one real prerequisite is below: your phone has to be able to reach the
machine the library runs on.

---

## First: can your phone reach the app?

If you are only ever saving from the same laptop the app runs on,
`http://localhost:8000` is fine — skip to the Chrome extension near the bottom.

**On a Mac, the easy way:** double-click `favorites/start.command`. Switch on
`FAVORITES_TOKEN` in `~/.favorites.env` (the file it creates on first run,
with a password already filled in), start it again, and it prints the
addresses your phone can use — the wi-fi one and, if Tailscale is running,
the one that works from anywhere. That password is `YOUR-TOKEN` below.

To set it up by hand instead, the app needs an address the phone can reach:

- **Same wi-fi only** — run it with `uvicorn favorites.app:app --host 0.0.0.0
  --port 8000` and use your laptop's local address, e.g.
  `http://192.168.1.20:8000`. Works at home; stops working when you leave.
- **Anywhere** — [Tailscale](https://tailscale.com) is the least painful
  option. It gives the machine a stable private address your phone can reach
  from anywhere, without opening anything to the public internet.

**If the address is reachable from outside your own network, set a token
first**, or anyone who finds it can write to your library:

```bash
export FAVORITES_TOKEN="pick-a-long-random-string"
uvicorn favorites.app:app --host 0.0.0.0 --port 8000
```

**Which address? The Tailscale one, everywhere.** It starts with `100.` (for
example `100.101.102.103:8000`) and works on your phone and laptop at home
and away, as long as Tailscale is on on both ends. The `192.168…` address
only works on your home wi-fi. Both start with plain `http://`, not
`https://`. Faves' **Keep it in sync** page (`/sync`, opened on the Mac)
shows the right one, ready to copy.

Below, replace `YOUR-ADDRESS` with that address including the port (e.g.
`100.101.102.103:8000`) and `YOUR-TOKEN` with the password (or leave the
Authorization header out entirely if you did not set one).

---

## The no-setup way: copy, paste, keep

Open Faves on your phone and use the **Keep** tab (bottom right): in
TikTok, Instagram or YouTube tap **Share → Copy link**, then in Faves tap
**Paste** and **Keep it**. If Faves has a password, it asks for it once on
each phone and remembers it.

## iOS — Save to Faves, in one tap

**Why not in TikTok's or Instagram's own share panel?** Those panels are
built by the apps and only list their partners. Faves sits one tap further,
in the iPhone's own share sheet: **Share → More** in TikTok, **Share →
Share to…** in Instagram. (Even there, the top row of app icons is only for
App Store apps; shortcuts are in the list underneath, and you can pin one to
the top of it.)

### The easy way: install the ready-made shortcuts

On the phone, open Faves → **Keep it in sync** → **Your phone**. (Unlock the
phone on the **Keep** tab first, once.) Two buttons install shortcuts that
already know your address and password:

- **Save to Faves** — then **Share → Save to Faves** in any app. Pin it: in
  any share sheet, scroll the list of actions to the end → **Edit Actions** →
  tap **+** next to Save to Faves.
- **Save copied link** — give it to Back Tap: **Settings → Accessibility →
  Touch → Back Tap → Double Tap → Save copied link**. Then in TikTok or
  Instagram, tap **Copy link** (it's in their own panel) and double-tap the
  back of the phone.

The Mac signs these with macOS's own `shortcuts sign`, which needs macOS 12
or later and the Mac signed in to iCloud. Without that, the page shows the
build-it-yourself steps below.

### The safety net: the inbox

Both shortcuts first add the link to **Faves inbox.txt** in iCloud Drive's
Shortcuts folder, then send it to Faves. Writing the file needs no
connection, so a link shared while the Mac is asleep, off, or out of reach is
not lost: iCloud carries the file to the Mac, and Faves reads it every minute
and saves whatever never arrived, with the date you shared it. Links that did
arrive are skipped. (The first time, macOS may ask whether Terminal may use
iCloud Drive: choose **Allow**.) To read a different file, set
`FAVORITES_INBOX` in `~/.favorites.env`.

### Building it yourself

About five minutes, once. Faves' **Keep it in sync** page (`/sync`, opened
on the Mac) shows the exact address and password to use below.

1. Open **Shortcuts** → **+** to create a new shortcut.
2. Add a **Text** action containing **Current Date** (tap it: Date Format
   **ISO 8601**, include time), a tab, and **Shortcut Input**.
3. Add **Append to Text File**: append that Text to `Faves inbox.txt` (in the
   Shortcuts folder), making a new line. That's the safety net.
4. Add **Get Contents of URL** with the URL `http://YOUR-ADDRESS/save`, and
   tap **Show More**:
   - **Method**: `POST`
   - **Headers**: add `Authorization` = `Bearer YOUR-TOKEN` *(skip if no token)*
   - **Request Body**: `JSON`, one **Text** field, key `url`, value
     **Shortcut Input** (pick it from the variable bar).
5. Add **Show Notification** with the text `Saved to Faves ✓`.
6. Tap the **ⓘ** → turn on **Show in Share Sheet**, with **URLs** and
   **Text** as the types, and name it **Save to Faves**.

For Back Tap, duplicate it, name the copy **Save copied link**, and put **Get
Clipboard** first, using it everywhere Shortcut Input was.

### Optional: a second shortcut that files it under a category

YouTube's save button asks whether to just save or to pick a playlist. The same
choice here is two shortcuts side by side in the share sheet: **Save to Faves** stays the
one-tap save, and **Save to Faves in…** asks where.

1. Duplicate **Save to Faves** and rename the copy **Save to Faves in…**.
2. At the top, add **Get Contents of URL** with the URL
   `http://YOUR-ADDRESS/collections.json` (method `GET`, same
   `Authorization` header). It returns your categories, largest first.
3. Add **Choose from List** (prompt: *File under*).
4. In the existing save step, add a JSON field `collection` set to
   **Chosen Item**.

If the list comes up empty even though you have categories, put **Get
Dictionary from Input** between steps 2 and 3. To create a brand-new category
from your phone, swap **Choose from List** for **Ask for Input**; any name typed
that matches an existing category, in any capitalisation, files into it.

### Optional: capture the note at the same time

The note is the most valuable field in the library and the moment you save is
the only moment you actually know why. To be asked for one every time, insert
an **Ask for Input** action (Text, prompt *"Why?"*) before **Get Contents of
URL**, and add a second JSON field `note` set to **Provided Input**.

Worth trying for a week. If being asked every time starts to feel like friction,
take it out — you can always add notes later from the item page, and a save with
no note beats no save.

---

## Android — install the page, and it becomes a share target

1. Open your `https://….ts.net` address (see the note below) in Chrome.
2. Menu → **Add to Home screen** (or **Install app**).
3. Open it once from the home screen icon.

It now appears in the system share sheet. Android requires HTTPS for this,
and the plain `http://100.…` address is not HTTPS. Tailscale can give the Mac
an HTTPS name: run `tailscale serve --bg 8000` on the Mac and use the
`https://….ts.net` address it prints.

If you set a token, Android's share sheet cannot attach a header, so the app
must be started without `FAVORITES_TOKEN` or reached over a network you trust.

Android's share target cannot ask a question first, so every share is a plain
save. It opens the item's page afterwards, which has a **File under** box right
there.

---

## Desktop — the Chrome extension

For Chrome, Edge, Arc and Brave. Download it from the **Keep it in sync** page
(**Your computer** → *Download the Chrome extension*) and install it once;
its [README](extension/README.md) has the two-minute steps. Then:

- click the Faves icon in the toolbar to keep the page you're on, with an
  optional note;
- right-click any link → **Keep link in Faves**;
- or press **⌘⇧K** (Ctrl+Shift+K) to keep the page without a click.

It asks for the same address and password as the Shortcut.

### Or a bookmarklet (any browser, no install)

Make a new bookmark, put it on the bookmarks bar, and set its URL to:

```javascript
javascript:(function(){fetch('http://YOUR-ADDRESS/save',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer YOUR-TOKEN'},body:JSON.stringify({url:location.href,note:prompt('Why keep this?')||''})}).then(r=>r.ok?alert('Kept.'):alert('Failed: '+r.status)).catch(e=>alert('Failed: '+e))})()
```

Browsers block it on `https://` pages that talk to a plain `http://` address,
which is most pages, and that is why the extension exists.

---

## Checking it works

```bash
curl -X POST http://YOUR-ADDRESS/save \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR-TOKEN' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","note":"testing"}'
```

A `201` means it was saved for the first time; a `200` means you already had it
and the existing entry was refreshed. Add `"collection":"Recipes"` to the body
to file it in the same request. Then check `GET /healthz` for the item
count and whether transcripts are switched on.

---

## Things that will look like bugs and are not

- **A white screen when you open the Faves icon on your phone.** Faves isn't
  running on the Mac: it restarted, it's asleep, or the Faves window was
  closed. Double-click `start.command`, then swipe the Faves app closed on the
  phone and open it again. To stop it happening, double-click
  `always-on.command` once: the Faves window then opens by itself whenever
  you log in. (A closed laptop lid still sends the Mac to sleep.)
- **The same video shared twice does not duplicate.** Share links carry a
  session id that differs every time; those are stripped, so both shares
  resolve to the same item. The second one refreshes it and keeps your note.
- **An Instagram save's title is worded the way Instagram words its link
  previews**, which is where its picture comes from too, rather than being the
  bare caption. A private or deleted post has no preview to give; the link and
  your note still work.
- **Most things have no transcript.** Only YouTube publishes caption tracks.
  Getting spoken text out of a TikTok would mean downloading the video, which
  its terms do not allow.
