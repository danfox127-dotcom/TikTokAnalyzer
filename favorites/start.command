#!/bin/bash
# Start the Favorites museum. On a Mac, double-click this file.
#
# Each time it:
#   1. updates the code, if this is a clean checkout of main (never touches
#      work in progress);
#   2. keeps a private Python environment in favorites/.venv up to date;
#   3. starts the museum and opens it in your browser.
#
# Your settings live in ~/.favorites.env -- which library file to use, and a
# password (FAVORITES_TOKEN) that lets your phone save to it. Double-clicking
# does not read ~/.zshrc, so that file is what keeps the double-click and the
# Terminal using the same library. It is created, with notes, on first run.
#
# Leave the window open while you use the museum; close it to stop.

set -u
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
PORT="${FAVORITES_PORT:-8000}"
ENV_FILE="$HOME/.favorites.env"
VENV="$ROOT/favorites/.venv"

say()  { printf '%s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$*"; printf 'Press Return to close.'; read -r _; exit 1; }

say "Favorites museum"
say "================"

# ---- settings -------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  suggested="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c 32)"
  cat > "$ENV_FILE" <<EOF
# Settings for the Favorites museum, read by favorites/start.command.
# Lines starting with # are switched off. Remove the # to switch one on.

# Which library file to use. Leave it off to use ~/favorites.db.
# FAVORITES_DB="\$HOME/favorites.db"

# A password so your phone can save to the museum (see favorites/SHARE_SHEET.md).
# Switch this on and other devices can reach the museum: your phone over the
# same wi-fi, or from anywhere with Tailscale. The password guards saving;
# anyone on your wi-fi could still browse, so use it on networks you trust.
# Without it, only this Mac can open the museum. Use the same value in your
# phone's Shortcut.
# FAVORITES_TOKEN="$suggested"
EOF
  chmod 600 "$ENV_FILE"
  say "Created your settings file: $ENV_FILE"
fi
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

# ---- already running? ------------------------------------------------------
if curl -fsS -o /dev/null "http://127.0.0.1:$PORT/healthz" 2>/dev/null; then
  say ""
  say "The museum is already running: http://localhost:$PORT"
  command -v open >/dev/null && open "http://localhost:$PORT"
  exit 0
fi

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
  say "   Installing what the museum needs..."
  "$VENV/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1
  "$VENV/bin/python" -m pip install --quiet -r "$REQS" || fail "Installing failed -- see the messages above."
  printf '%s' "$want" > "$STAMP"
fi
say "   Ready."

# ---- 3. start --------------------------------------------------------------
step "3. Starting the museum"
if [ -n "${FAVORITES_TOKEN:-}" ]; then
  HOST="0.0.0.0"
  say "   Open it here:      http://localhost:$PORT"
  wifi="$( (ipconfig getifaddr en0 || ipconfig getifaddr en1) 2>/dev/null)"
  [ -n "$wifi" ] && say "   On the same wi-fi: http://$wifi:$PORT"
  ts="$(tailscale ip -4 2>/dev/null | head -n1)"
  [ -z "$ts" ] && ts="$(/Applications/Tailscale.app/Contents/MacOS/Tailscale ip -4 2>/dev/null | head -n1)"
  [ -n "$ts" ] && say "   From anywhere:     http://$ts:$PORT   (Tailscale)"
  say "   Your phone needs the password from $ENV_FILE."
else
  HOST="127.0.0.1"
  say "   Open it here: http://localhost:$PORT"
  say "   Only this Mac can reach it. To save from your phone, switch on"
  say "   FAVORITES_TOKEN in $ENV_FILE and start again."
fi
say ""
say "   Leave this window open while you use the museum. Close it to stop."
say ""

# Open the browser once the server answers.
(
  for _ in $(seq 1 40); do
    if curl -fsS -o /dev/null "http://127.0.0.1:$PORT/healthz" 2>/dev/null; then
      command -v open >/dev/null && open "http://localhost:$PORT"
      exit 0
    fi
    sleep 0.5
  done
) &

exec "$VENV/bin/python" -m uvicorn favorites.app:app --host "$HOST" --port "$PORT"
