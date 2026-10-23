#!/bin/bash
# Start Faves. On a Mac, double-click this file.
#
# Each time it:
#   1. updates the code, if this is a clean checkout of main (never touches
#      work in progress);
#   2. keeps a private Python environment in favorites/.venv up to date;
#   3. starts Faves and opens it in your browser.
#
# Your settings live in ~/.favorites.env -- which library file to use, and a
# password (FAVORITES_TOKEN) that lets your phone save to it. Double-clicking
# does not read ~/.zshrc, so that file is what keeps the double-click and the
# Terminal using the same library. It is created, with notes, on first run.
#
# Double-clicking it while Faves is already running updates the code and, if
# the running Faves is now behind, restarts it on the new version -- so a
# double-click always means "give me the latest Faves".
#
# Leave the window open while you use Faves; close it to stop. If Faves
# itself stops with an error, it starts again in the same window. While it
# runs, a plugged-in Mac stays awake (caffeinate), so your phone can reach it.
#
# To have this window open by itself whenever you log in, double-click
# always-on.command once.

set -u
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
PORT="${FAVORITES_PORT:-8000}"
# Set when always-on opens this at login: no browser tab then.
AT_LOGIN="${FAVES_AT_LOGIN:-}"
ENV_FILE="$HOME/.favorites.env"
VENV="$ROOT/favorites/.venv"

say()  { printf '%s\n' "$*"; }
# This Mac's Tailscale address, if Tailscale is connected: the one address in
# 100.64.0.0/10 (100.64.x.x to 100.127.x.x).
tailscale_ip() {
  ifconfig 2>/dev/null | awk '$1 == "inet" { split($2, o, "."); if (o[1] == 100 && o[2] >= 64 && o[2] <= 127) { print $2; exit } }'
}

# Run a command, but give up after 3 seconds. Asking Tailscale for its address
# can wait forever when it is installed but not signed in, and that kept the
# Faves from ever starting.
quick() {
  local out pid watcher
  out="$(mktemp -t favorites.XXXXXX)"
  "$@" >"$out" 2>/dev/null </dev/null &
  pid=$!
  ( sleep 3; kill "$pid" 2>/dev/null ) >/dev/null 2>&1 &
  watcher=$!
  wait "$pid" 2>/dev/null
  kill "$watcher" 2>/dev/null
  head -n1 "$out"
  rm -f "$out"
}
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$*"; printf 'Press Return to close.'; read -r _; exit 1; }

# Is Faves answering on its port? Never wait more than a few seconds: a stuck
# copy accepts the connection and then says nothing.
answering() { curl -fsS --max-time 5 -o /dev/null "http://127.0.0.1:$PORT/healthz" 2>/dev/null; }

# Whatever is listening on Faves' port, as "PID command line" -- or nothing.
port_holder() {
  local pid
  command -v lsof >/dev/null 2>&1 || return 0
  pid="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -n1)"
  [ -n "$pid" ] && printf '%s %s\n' "$pid" "$(ps -o command= -p "$pid" 2>/dev/null)"
  return 0
}

# Stop a Faves process: politely, then firmly.
stop_faves() {
  kill "$1" 2>/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$1" 2>/dev/null || return 0; sleep 0.5; done
  kill -9 "$1" 2>/dev/null
  sleep 1
}

# The code on disk, and the code the running Faves started with (empty when
# unknown: not a git checkout, or a Faves from before it reported this).
code_version() { git rev-parse HEAD 2>/dev/null; }
running_version() {
  curl -fsS --max-time 5 "http://127.0.0.1:$PORT/healthz" 2>/dev/null |
    sed -n 's/.*"version":"\([0-9A-Za-z]*\)".*/\1/p'
}

# Make sure the port is free before starting. An older copy of Faves that has
# stopped answering (the phone sees a white screen) is stopped; anything else
# on the port is named, so you know what to quit.
free_the_port() {
  local holder pid cmd
  holder="$(port_holder)"
  [ -z "$holder" ] && return 0
  if answering; then
    say ""
    say "Faves is already running in another window, so this one isn't needed."
    say "You can close this window."
    exit 0
  fi
  pid="${holder%% *}"; cmd="${holder#* }"
  case "$cmd" in
    *favorites.app:app*)
      say "   An older copy of Faves (process $pid) is stuck and not answering."
      say "   Stopping it, so this one can take over..."
      stop_faves "$pid"
      return 0 ;;
    *)
      fail "Faves can't start: port $PORT is already in use by another program:
   $cmd   (process $pid)
Quit that program and double-click start.command again. Or give Faves a
different port: add the line  FAVORITES_PORT=8001  to $ENV_FILE
(and then use :8001 instead of :8000 on your phone)." ;;
  esac
}

say "Faves"
say "====="

# ---- settings -------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  suggested="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c 32)"
  cat > "$ENV_FILE" <<EOF
# Settings for Faves, read by favorites/start.command.
# Lines starting with # are switched off. Remove the # to switch one on.

# Which library file to use. Leave it off to use ~/favorites.db.
# FAVORITES_DB="\$HOME/favorites.db"

# A password so your phone can save to Faves (see favorites/SHARE_SHEET.md).
# Switch this on and other devices can reach Faves: your phone over the
# same wi-fi, or from anywhere with Tailscale. The password guards saving;
# anyone on your wi-fi could still browse, so use it on networks you trust.
# Without it, only this Mac can open Faves. Use the same value in your
# phone's Shortcut.
# FAVORITES_TOKEN="$suggested"

# Folders Faves watches for TikTok, Instagram and Google Takeout exports,
# importing each the moment it lands. Several: separate them with ":".
# Downloads is watched unless you change this; set it to "" to watch nothing.
# FAVORITES_WATCH="$HOME/Downloads"

# YouTube playlists, synced by signing in with Google. The setup steps are on
# Faves' Keep it in sync page.
# GOOGLE_CLIENT_ID=""
# GOOGLE_CLIENT_SECRET=""
EOF
  chmod 600 "$ENV_FILE"
  say "Created your settings file: $ENV_FILE"
fi
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
# Exports that land in Downloads import themselves (see favorites/watch.py).
FAVORITES_WATCH="${FAVORITES_WATCH-$HOME/Downloads}"
set +a
# The settings file may choose the port.
PORT="${FAVORITES_PORT:-$PORT}"

# ---- 1. update the code ----------------------------------------------------
step "1. Checking for updates"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$branch" != "main" ]; then
    say "   On branch '$branch', not main -- leaving the code as it is."
  elif [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    say "   You have unsaved changes to the code -- leaving it as it is."
  elif git pull --ff-only --quiet 2>/dev/null; then
    say "   Up to date ($(git log -1 --format='%h, %cr'))."
  else
    say "   Couldn't update (offline?) -- starting the version you have."
  fi
else
  say "   Not a git checkout -- skipping."
fi

# ---- already running? ------------------------------------------------------
# Up to date: nothing to do but open it. Behind the code just updated (or too
# old to say): get the new version ready, then swap it in.
RESTART=""
if answering; then
  have="$(code_version)"; runs="$(running_version)"
  if [ -z "$have" ] || [ "$runs" = "$have" ]; then
    say ""
    say "Faves is already running: http://localhost:$PORT"
    [ -z "$AT_LOGIN" ] && command -v open >/dev/null && open "http://localhost:$PORT"
    exit 0
  fi
  say ""
  say "   Faves is running an older version -- restarting it with the update..."
  RESTART=1
fi

# ---- 2. Python -------------------------------------------------------------
step "2. Getting Python ready"
# The Mac's built-in python3 is 3.9, which is too old. Prefer a newer one.
PY=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$candidate"; break
  fi
done
if [ ! -x "$VENV/bin/python" ]; then
  [ -n "$PY" ] || fail "Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/ (or: brew install python), then double-click this again."
  say "   First run: setting up (a minute or two)..."
  "$PY" -m venv "$VENV" || fail "Couldn't create the Python environment in $VENV."
fi

REQS="$ROOT/favorites/requirements.txt"
STAMP="$VENV/.requirements.sha"
if command -v shasum >/dev/null; then want="$(shasum -a 256 "$REQS" | cut -d' ' -f1)"
else want="$(sha256sum "$REQS" | cut -d' ' -f1)"; fi
if [ "$(cat "$STAMP" 2>/dev/null)" != "$want" ]; then
  say "   Installing what Faves needs..."
  "$VENV/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1
  "$VENV/bin/python" -m pip install --quiet -r "$REQS" || fail "Installing failed -- see the messages above."
  printf '%s' "$want" > "$STAMP"
fi
say "   Ready."

# ---- 3. start --------------------------------------------------------------
step "3. Starting Faves"
if [ -n "$RESTART" ]; then
  holder="$(port_holder)"
  case "${holder#* }" in
    *favorites.app:app*) stop_faves "${holder%% *}"; say "   Stopped the older version." ;;
  esac
fi
if [ -n "${FAVORITES_TOKEN:-}" ]; then
  HOST="0.0.0.0"
  say "   Open it here:      http://localhost:$PORT"
  wifi="$(quick ipconfig getifaddr en0)"
  [ -z "$wifi" ] && wifi="$(quick ipconfig getifaddr en1)"
  [ -n "$wifi" ] && say "   On the same wi-fi: http://$wifi:$PORT"
  # Tailscale's address is always in 100.64.0.0/10. Read it from the network
  # settings rather than asking the Tailscale app: running the app's own
  # program opens its window, and may not answer in time.
  ts="$(tailscale_ip)"
  [ -z "$ts" ] && command -v tailscale >/dev/null 2>&1 && ts="$(quick tailscale ip -4)"
  [ -n "$ts" ] && say "   From anywhere:     http://$ts:$PORT   (Tailscale)"
  say "   Your phone needs the password from $ENV_FILE."
else
  HOST="127.0.0.1"
  say "   Open it here: http://localhost:$PORT"
  say "   Only this Mac can reach it. To save from your phone, switch on"
  say "   FAVORITES_TOKEN in $ENV_FILE and start again."
fi
say ""
say "   Leave this window open while you use Faves. Close it to stop."
say ""

# Open the browser once the server answers.
(
  for _ in $(seq 1 40); do
    if answering; then
      [ -z "$AT_LOGIN" ] && command -v open >/dev/null && open "http://localhost:$PORT"
      exit 0
    fi
    sleep 0.5
  done
) &

# A sleeping Mac is a white screen on the phone: keep a plugged-in Mac awake
# for as long as this window runs (on battery it sleeps as usual).
command -v caffeinate >/dev/null 2>&1 && caffeinate -s -w $$ &

# If Faves stops with an error, start it again; a clean stop (Ctrl-C) ends here.
# If it can't even start three times running, stop and say so rather than
# trying forever.
failed_starts=0
while :; do
  free_the_port
  started=$(date +%s)
  FAVES_VERSION="$(code_version)" "$VENV/bin/python" -m uvicorn favorites.app:app --host "$HOST" --port "$PORT"
  code=$?
  [ "$code" -eq 0 ] && exit 0
  say ""
  if answering; then
    say "Faves is already running in another window, so this one isn't needed."
    say "You can close this window."
    exit 0
  fi
  if [ $(( $(date +%s) - started )) -lt 60 ]; then
    failed_starts=$((failed_starts + 1))
  else
    failed_starts=0
  fi
  if [ "$failed_starts" -ge 3 ]; then
    fail "Faves couldn't start (code $code), three times in a row. The messages above say why."
  fi
  say "Faves stopped unexpectedly (code $code). Starting it again in 10 seconds..."
  say "(Close this window to stop it for good.)"
  sleep 10
done
