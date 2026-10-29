#!/bin/bash
# Move your Faves library into the cloud (Supabase). On a Mac, double-click this file.
#
# It copies everything -- saves, notes, categories, the rooms you chose,
# pictures -- from the library file on this Mac into the cloud library. The
# first time, it asks for the cloud library's address and keeps it in
# ~/.favorites.env, so Faves on this Mac uses the cloud library from then on.
#
# The file on this Mac is only read, never changed: it stays a complete backup.
# Running this again is safe -- it only fills in what the cloud is missing.
#
# At the end it opens Vercel's settings page and puts the two settings the
# cloud copy of Faves needs on the clipboard, one at a time, to paste in.
#
# See "Moving to the cloud" in favorites/README.md.

set -u
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
ENV_FILE="$HOME/.favorites.env"
VENV="$ROOT/favorites/.venv"

# Where the cloud copy of Faves keeps its settings.
VERCEL_SETTINGS="https://vercel.com/danfox127-dotcoms-projects/tik-tok-analyzer/settings/environment-variables"

say() { printf '%s\n' "$*"; }
finish() { printf '\nPress Return to close.'; read -r _; exit "$1"; }

load_settings() {
  [ -f "$ENV_FILE" ] || return 0
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
}

# Put one setting's value on the clipboard, for pasting into Vercel.
copy_setting() {
  printf '\n  Name:  %s\n  Press Return to copy its value... ' "$1"
  read -r _
  printf '%s' "${!1}" | pbcopy
  say "  Copied. Paste it into Value."
}

# The cloud copy of Faves needs the same two settings as this Mac. Copy each
# to the clipboard in turn, rather than leaving anyone to dig through a hidden
# file for them.
hand_over() {
  command -v pbcopy >/dev/null 2>&1 || return 0
  say ""
  say "Last step: the cloud copy of Faves needs two of these settings too."
  printf 'Copy them for Vercel now? Press Return for yes, or type n then Return to skip: '
  read -r answer
  case "$answer" in [nN]*) return 0 ;; esac
  if [ -z "${FAVORITES_TOKEN:-}" ]; then
    FAVORITES_TOKEN="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c 32)"
    printf '\n# The Faves password, for your phone and the cloud copy.\nFAVORITES_TOKEN="%s"\n' \
      "$FAVORITES_TOKEN" >> "$ENV_FILE"
    say "Faves had no password yet, so it has one now (FAVORITES_TOKEN in $ENV_FILE)."
  fi
  say ""
  say "Vercel's settings page is opening in your browser. For each setting below,"
  say "add an environment variable there: type the name, paste the value, keep"
  say "all environments ticked, and tick Sensitive."
  command -v open >/dev/null 2>&1 && open "$VERCEL_SETTINGS"
  copy_setting DATABASE_URL
  copy_setting FAVORITES_TOKEN
  printf '\n  When both are saved, press Return to clear the clipboard... '
  read -r _
  pbcopy </dev/null
  say "  Cleared."
  say ""
  say "Then, in Vercel: Deployments, the newest one's ... menu, Redeploy."
  say "Sign in on your phone with the same password (FAVORITES_TOKEN)."
}

say "Faves: move to the cloud"
say "========================"
say ""

load_settings

if [ ! -x "$VENV/bin/python" ]; then
  say "Faves isn't set up on this Mac yet. Double-click start.command once,"
  say "then double-click this again."
  finish 1
fi

# The same check start.command makes, so a fresh update has what it needs.
REQS="$ROOT/favorites/requirements.txt"
STAMP="$VENV/.requirements.sha"
if command -v shasum >/dev/null; then want="$(shasum -a 256 "$REQS" | cut -d' ' -f1)"
else want="$(sha256sum "$REQS" | cut -d' ' -f1)"; fi
if [ "$(cat "$STAMP" 2>/dev/null)" != "$want" ]; then
  say "Installing what Faves needs..."
  "$VENV/bin/python" -m pip install --quiet -r "$REQS" || { say "Installing failed -- see the messages above."; finish 1; }
  printf '%s' "$want" > "$STAMP"
  say ""
fi

"$VENV/bin/python" -m favorites.cloud_move
code=$?
if [ "$code" = 0 ]; then
  load_settings  # the move may have just saved the cloud library's address
  hand_over
  say ""
  say "Next: double-click start.command. Faves on this Mac then switches to the"
  say "cloud library (if it's running, it restarts itself onto it)."
fi
finish "$code"
