# Faves for Chrome

Keep the page you're on, or any link, in your Faves library in one click.
It works in Chrome, Edge, Arc and Brave.

## Install (about two minutes, once)

1. Open `chrome://extensions` (in Edge, `edge://extensions`).
2. Switch on **Developer mode** (top right).
3. Click **Load unpacked** and choose this folder, `favorites/extension`.
4. Click the puzzle-piece icon in the toolbar and **pin** Faves.
5. The settings page opens by itself. Enter the **Address** and **Password**
   from the *Keep it in sync* page on your Mac (under "Your phone"), then
   **Save and test**. Choose **Allow** when Chrome asks.

The extension stays installed. If you move the folder, load it again from
its new place.

## Using it

- **Toolbar button.** Click the Faves icon, add a note if you like, then **Keep**.
- **Right-click a link.** Choose **Keep link in Faves**, for example on a TikTok in a feed.
- **Keyboard.** **⌘⇧K** on a Mac, Ctrl+Shift+K on Windows. It keeps the page with no clicks.

## How it works

It sends the link to Faves' `/save` with your password, the same way the
iPhone Shortcut does. The address and password stay in this browser
(`chrome.storage.local`). Chrome only lets the extension talk to the one
address you entered.
