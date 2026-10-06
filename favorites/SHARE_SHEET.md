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

## iOS — a Shortcut in the share sheet

About three minutes, once. Faves' **Keep it in sync** page (`/sync`,
opened on the Mac) shows the exact address and password to use below.

1. Open **Shortcuts** → **+** to create a new shortcut.
2. Add the action **Get Contents of URL**.
3. Set the URL to `http://YOUR-ADDRESS/save`.
4. Tap **Show More** and set:
   - **Method**: `POST`
   - **Headers**: add `Authorization` = `Bearer YOUR-TOKEN` *(skip if no token)*
   - **Request Body**: `JSON`
   - Add a field: type **Text**, key `url`, value **Shortcut Input**
     (tap the value box and pick it from the variable bar).
5. Tap the **ⓘ** / settings icon → turn on **Show in Share Sheet**.
6. Under **Share Sheet Types**, leave **URLs** and **Text** enabled and turn
   the rest off.
7. Add **Get Dictionary Value** (key `title`), then **Show Notification** with
   the text `Kept ✓` and that value. You see the video's title a second after
   tapping; if the phone cannot reach the library, Shortcuts stops with a
   connection error instead — the other thing worth knowing straight away.
8. Name it something short — **Keep** works well, because the name is what you
   will be tapping.

Now: any app → Share → **Keep**. One tap, no typing, nothing to confirm.

**Put Keep first.** In the share sheet, scroll the row of apps to the end →
**Edit Actions** → add **Keep** to Favourites, so it sits at the top of the
list instead of below the fold.

### Optional: save what you copied, with a double-tap on the back of the phone

Some apps' share sheets bury Shortcuts. Duplicate **Keep**, name the copy
**Keep copied**, and put **Get Clipboard** in place of Shortcut Input. Then
**Settings → Accessibility → Touch → Back Tap → Double Tap → Keep copied**:
copy a link anywhere, double-tap the back of the phone, and it is saved. (On an
iPhone with an Action button, you can give it to that instead.)

### Optional: a second shortcut that files it under a category

YouTube's save button asks whether to just save or to pick a playlist. The same
choice here is two shortcuts side by side in the share sheet: **Keep** stays the
one-tap save, and **Keep in…** asks where.

1. Duplicate **Keep** and rename the copy **Keep in…**.
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
