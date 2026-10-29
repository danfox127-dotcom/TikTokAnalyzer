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
# See "Moving to the cloud" in favorites/README.md.

set -u
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
ENV_FILE="$HOME/.favorites.env"
VENV="$ROOT/favorites/.venv"

say() { printf '%s\n' "$*"; }
finish() { printf '\nPress Return to close.'; read -r _; exit "$1"; }

say "Faves: move to the cloud"
say "========================"
say ""

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

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
  say ""
  say "Next: double-click start.command. Faves on this Mac then switches to the"
  say "cloud library (if it's running, it restarts itself onto it)."
fi
finish "$code"
