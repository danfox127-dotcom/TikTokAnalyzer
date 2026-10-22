#!/bin/bash
# Always on: the Faves window opens by itself whenever you log in to this
# Mac, so the Faves icon on your phone finds it instead of a white screen.
#
# Double-click to switch it on. Double-click again to switch it off.
#
# How: a LaunchAgent (~/Library/LaunchAgents/app.faves.plist) that, at login,
# opens start.command in Terminal -- the same window you would open by hand,
# so Faves keeps Terminal's permission to read your Downloads folder.
#   --on / --off     switch it on or off without asking
#   --print-plist    show the LaunchAgent it would write, and change nothing

set -u
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
PORT="${FAVORITES_PORT:-8000}"
LABEL="app.faves"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SUPPORT="$HOME/Library/Application Support/Faves"
OPENER="$SUPPORT/open-at-login.command"
DOMAIN="gui/$(id -u)"

say() { printf '%s\n' "$*"; }
finish() { say ""; printf 'Press Return to close.'; read -r _; exit "${1:-0}"; }
xml() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }

plist() {
  cat <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/open</string>
    <string>-a</string>
    <string>Terminal</string>
    <string>$(xml "$OPENER")</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>LimitLoadToSessionType</key><string>Aqua</string>
</dict>
</plist>
PLIST
}

# What Terminal runs at login: start.command, told not to open a browser tab.
opener() {
  cat <<OPENER
#!/bin/bash
# Written by Faves' always-on.command. It opens Faves when you log in.
# To stop that, double-click always-on.command again.
FAVES_AT_LOGIN=1 exec "$ROOT/favorites/start.command"
OPENER
}

switch_on() {
  mkdir -p "$(dirname "$PLIST")" "$SUPPORT"
  opener > "$OPENER" && chmod +x "$OPENER"
  plist > "$PLIST"
  launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1
  if ! launchctl bootstrap "$DOMAIN" "$PLIST" 2>/dev/null && ! launchctl load "$PLIST" 2>/dev/null; then
    say "Couldn't switch it on -- macOS said no. Try once more; if it still fails,"
    say "add start.command under System Settings -> General -> Login Items instead."
    finish 1
  fi
  say "Always on: ON"
  say ""
  say "Whenever you log in to this Mac, the Faves window opens by itself."
  say "If Faves hits an error it starts again, and while it runs a plugged-in"
  say "Mac stays awake. Two things still stop it:"
  say "  - closing the Faves window (it comes back at your next login), and"
  say "  - closing a laptop's lid. Leave it open, or plugged into a screen."
  say ""
  say "macOS may show a 'Background Items Added' notice. That's this."
  if curl -fsS --max-time 5 -o /dev/null "http://127.0.0.1:$PORT/healthz" 2>/dev/null; then
    :  # already running
  elif pgrep -f 'favorites/start[.]command' >/dev/null 2>&1; then
    say ""
    say "Faves is already starting in another window -- leave that one open."
  else
    say ""
    say "Faves isn't running right now, so opening it..."
    open -a Terminal "$OPENER"
  fi
  finish 0
}

switch_off() {
  launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || launchctl unload "$PLIST" >/dev/null 2>&1
  rm -f "$PLIST" "$OPENER"
  say "Always on: OFF"
  say ""
  say "Faves won't open by itself any more. Double-click start.command to use it."
  finish 0
}

case "${1:-}" in
  --print-plist) plist; exit 0 ;;
  --print-opener) opener; exit 0 ;;
  --on) switch_on ;;
  --off) switch_off ;;
esac

say "Faves -- always on"
say "=================="
if [ -f "$PLIST" ]; then
  say "Always on is ON: the Faves window opens by itself when you log in."
  printf 'Switch it off? Type y and press Return (anything else keeps it on): '
  read -r answer
  case "$answer" in y|Y|yes|Yes) switch_off ;; *) say "Left on."; finish 0 ;; esac
else
  switch_on
fi
