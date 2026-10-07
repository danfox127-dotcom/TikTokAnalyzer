#!/bin/bash
# Start Footprint. On a Mac, double-click this file.
#
# Each time it:
#   1. updates the code, if this is a clean checkout of main (never touches
#      work in progress);
#   2. keeps a private Python environment in footprint/.venv up to date;
#   3. starts Footprint and opens it in your browser.
#
# Footprint keeps its site lists and what it has learned in ~/.footprint.
# It only listens on this Mac.
#
# Leave the window open while you use Footprint; close it to stop.

set -u
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
PORT="${FOOTPRINT_PORT:-8010}"
VENV="$ROOT/footprint/.venv"

say()  { printf '%s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$*"; printf 'Press Return to close.'; read -r _; exit 1; }

say "Footprint"
say "========="

# ---- already running? ------------------------------------------------------
if curl -fsS -o /dev/null "http://127.0.0.1:$PORT/healthz" 2>/dev/null; then
  say ""
  say "Footprint is already running: http://localhost:$PORT"
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

REQS="$ROOT/footprint/requirements.txt"
STAMP="$VENV/.requirements.sha"
if command -v shasum >/dev/null; then want="$(shasum -a 256 "$REQS" | cut -d' ' -f1)"
else want="$(sha256sum "$REQS" | cut -d' ' -f1)"; fi
if [ "$(cat "$STAMP" 2>/dev/null)" != "$want" ]; then
  say "   Installing what Footprint needs..."
  "$VENV/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1
  "$VENV/bin/python" -m pip install --quiet -r "$REQS" || fail "Installing failed -- see the messages above."
  printf '%s' "$want" > "$STAMP"
fi
say "   Ready."

# ---- 3. start --------------------------------------------------------------
step "3. Starting Footprint"
say "   Open it here: http://localhost:$PORT"
say "   The first start downloads the site lists (a few seconds). The first"
say "   search each day also re-tests every site quietly in the background."
say ""
say "   Leave this window open while you use Footprint. Close it to stop."
say ""

# Open the browser once the server answers.
(
  for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "http://127.0.0.1:$PORT/healthz" 2>/dev/null; then
      command -v open >/dev/null && open "http://localhost:$PORT"
      exit 0
    fi
    sleep 0.5
  done
) &

exec "$VENV/bin/python" -m uvicorn footprint.app:app --host 127.0.0.1 --port "$PORT"
