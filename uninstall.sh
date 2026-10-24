#!/bin/bash
# Mogrt Font Fixer poora hatane ke liye (Mac):  bash ~/Applications/MogrtFontFixer/uninstall.sh
LABEL="com.vikas.mogrtfontfixer"
TOOL="$HOME/Applications/MogrtFontFixer"
launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
rm -rf "$HOME/Applications/Mogrt Font Scan.app"
rm -f "$HOME/Library/Fonts/STANDIN__"*
echo "Watcher, app aur stand-in fonts hata diye."
if [ -f "$TOOL/mogrt_font_fixer.py" ]; then
  rm -rf "$TOOL"
  echo "Tool ka folder (log, cache, sab) bhi hata diya."
fi
echo "Tool ne jo asli fonts install kiye the wo ~/Library/Fonts me waise hi rahenge."
