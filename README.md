# 🔤 Mogrt Font Fixer — FREE

**Stop hunting for missing fonts in Premiere Pro.**
Mogrt Font Fixer automatically finds, downloads and installs the fonts your MOGRT templates need — so every template looks the way it was designed.

> 🆓 **Free for everyone.** Made by an editor, for editors.

[![Download](https://img.shields.io/badge/⬇️_Download-Mogrt_Font_Fixer_v2.0-2EA043?style=for-the-badge)](https://github.com/androguruji1/mogrt-font-fixer/archive/refs/heads/main.zip)

---

## 😩 The Problem

You download a MOGRT pack, drop a template on your timeline… and Premiere Pro swaps the font for a default one. Now you're searching Google for the font name, downloading ZIPs, installing them one by one, and restarting Premiere.

Multiply that by hundreds of templates. That's hours wasted every month.

## ✅ The Fix

| Feature | What it means for you |
|---|---|
| 🔍 **Auto-detect fonts** | Reads every installed MOGRT and finds the fonts it uses |
| ⬇️ **Auto-download & install** | Gets missing fonts from free sources — Google Fonts, Font Squirrel, DaFont, 1001 Fonts, Befonts |
| 🪄 **Stand-in fonts** | Paid font not available for free? A similar free font is installed under the same name, so Premiere stops showing "missing font" |
| 🔁 **Runs in the background** | Starts with your computer. Install a new MOGRT and its fonts are checked within ~20 seconds |
| 📄 **Clear report** | HTML report of installed fonts, stand-ins, and fonts not found (with search links) |
| 🎯 **Check one file** | Drag a .mogrt, .prproj or .aep onto the "Mogrt Font Scan" icon |
| 🪶 **Lightweight** | ~15–25 MB RAM, cleans up its own logs and cache |
| 💻 **Mac + Windows 10/11** | No Python setup needed — the installer handles it |

---

## 🚀 Install

**Mac**
1. Download the ZIP above and double-click it.
2. Open **Terminal**, type `bash ` (with a space), drag `install.sh` into the window and press **Enter**.
3. The first scan takes 2–10 minutes. The report opens in your browser when done.

**Windows**
1. Download the ZIP, right-click → **Extract All**.
2. Double-click `install_windows.bat`. If you see "Windows protected your PC", click **More info → Run anyway**.
3. The first run downloads a small Python (~40 MB), then scans for 2–10 minutes. Keep the window open.

Full step-by-step guide (Hinglish): [README.txt](README.txt)

## 🗑️ Uninstall

- **Mac:** `bash ~/Applications/MogrtFontFixer/uninstall.sh`
- **Windows:** open `%LOCALAPPDATA%\MogrtFontFixer` and double-click `uninstall_windows.bat`

---

## ⚠️ Font licensing

- Many fonts on free sites (like DaFont) are **personal use only**. Check the licence before using a font in client or commercial work.
- A stand-in is **not** the real font — it only looks similar. If a client needs the exact font, buy it and delete the `STANDIN__` file.
- This tool never downloads paid fonts from pirated sites.

---

## 🐞 Support

Found a bug? Open an **[Issue](../../issues)** and attach your `log.txt` (inside the tool's folder).

## 📝 Changelog

- **v2.0** — Current release: Mac + Windows, background watcher, stand-in fonts, HTML report

---

## ❤️ Like it?

Subscribe on [YouTube @androguruji](https://www.youtube.com/@androguruji) and check out my other tools and packs for editors:

[![Shop Now](https://img.shields.io/badge/🛒_Shop_Now-superprofile.bio%2Fandroguruji-7C3AED?style=for-the-badge)](https://superprofile.bio/androguruji)

---

Made by **[Vikas Singh — Androguruji](https://github.com/androguruji1)** · Built with AI for editors 🎬🤖
