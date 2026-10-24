#!/bin/bash
# Mogrt Font Fixer installer (sirf Mac). Terminal me likho:  bash  (space ke saath), phir ye file Terminal me drag karke Enter dabao.
DIR="$(cd "$(dirname "$0")" && pwd)"
# Tool hamesha yahan rehta hai. Zip kahin bhi khola ho (Downloads, Desktop), files yahan copy ho jati hain.
TARGET="$HOME/Applications/MogrtFontFixer"
if [ "$DIR" != "$TARGET" ]; then
  mkdir -p "$TARGET"
  cp "$DIR/mogrt_font_fixer.py" "$DIR/install.sh" "$DIR/uninstall.sh" "$TARGET/" || { echo "ERROR: files copy nahi hui"; exit 1; }
  [ -f "$DIR/README.txt" ] && cp "$DIR/README.txt" "$TARGET/"
  DIR="$TARGET"
fi
LABEL="com.vikas.mogrtfontfixer"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SCRIPT="$DIR/mogrt_font_fixer.py"
APPPATH="$HOME/Applications/Mogrt Font Scan.app"
echo "== Mogrt Font Fixer install =="

PY=""
try_py() {
  [ -z "$PY" ] && [ -x "$1" ] && "$1" -c 'import sys,zipfile,json,struct; sys.exit(0 if sys.version_info>=(3,8) else 1)' >/dev/null 2>&1 && PY="$1"
}
try_py "$DIR/python/bin/python3"
if xcode-select -p >/dev/null 2>&1; then try_py /usr/bin/python3; fi
for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do try_py "$c"; done

if [ -z "$PY" ]; then
  echo "Python nahi mila, tool ke folder me apna Python download kar raha hun (lagbhag 20 MB)..."
  if [ "$(uname -m)" = "arm64" ]; then A="aarch64"; else A="x86_64"; fi
  URL="https://github.com/astral-sh/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-${A}-apple-darwin-install_only.tar.gz"
  if curl -L --fail --progress-bar -o "$DIR/python.tar.gz" "$URL" && tar -xzf "$DIR/python.tar.gz" -C "$DIR"; then
    rm -f "$DIR/python.tar.gz"
    try_py "$DIR/python/bin/python3"
  fi
fi
if [ -z "$PY" ]; then
  echo "ERROR: Python set nahi ho paya. Ye poora message Claude ko bhej do."
  echo "python_setup_failed $(uname -m) $(sw_vers -productVersion)" >> "$DIR/log.txt"
  exit 1
fi
echo "Python: $PY"
echo "install: python=$PY macos=$(sw_vers -productVersion) arch=$(uname -m)" >> "$DIR/log.txt"

# purana watcher band karo
launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1
rm -f "$DIR/scan.lock"

echo
echo "Pehla full scan chal raha hai (saare installed mogrt). Isme kuch minute lag sakte hain..."
"$PY" "$SCRIPT" scan --force --open-report

# background watcher
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$SCRIPT</string><string>watch</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$DIR/daemon.log</string>
  <key>StandardErrorPath</key><string>$DIR/daemon.log</string>
</dict></plist>
PL
if launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>>"$DIR/log.txt" || launchctl load -w "$PLIST" 2>>"$DIR/log.txt"; then
  echo "Background watcher chalu ho gaya (Mac start hote hi khud chalega)."
  echo "install: watcher loaded" >> "$DIR/log.txt"
else
  echo "WARNING: watcher chalu nahi hua. Claude ko batao."
  echo "install: watcher load FAILED" >> "$DIR/log.txt"
fi

# Scan Now app (double-click = full scan, ya .mogrt/.prproj file is pe drop karo)
rm -rf "$APPPATH"
osacompile -o "$APPPATH" 2>>"$DIR/log.txt" <<AS
on run
  do shell script "'$PY' '$SCRIPT' gui > /dev/null 2>&1 &"
end run
on open theFiles
  set args to ""
  repeat with f in theFiles
    set args to args & " " & quoted form of POSIX path of f
  end repeat
  do shell script "'$PY' '$SCRIPT' gui" & args & " > /dev/null 2>&1 &"
end open
AS
[ -d "$APPPATH" ] && echo "App ban gaya: Applications (home wala) > Mogrt Font Scan" && echo "install: app ok" >> "$DIR/log.txt"

echo
echo "== Ho gaya. Report browser me khul gayi hogi. =="
