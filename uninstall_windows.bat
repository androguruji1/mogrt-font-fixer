@echo off
rem Mogrt Font Fixer poora hatane ke liye (Windows). Is file pe double-click karo.
setlocal EnableExtensions
title Mogrt Font Fixer - Uninstall
set "TARGET=%LOCALAPPDATA%\MogrtFontFixer"
set "PY=%TARGET%\python\python.exe"

echo.
echo == Mogrt Font Fixer hata rahe hain ==
if exist "%PY%" "%PY%" "%TARGET%\mogrt_font_fixer.py" unsetup-windows
echo Auto-start, shortcut aur stand-in fonts hata diye.
echo Tool ne jo asli fonts install kiye the wo waise hi rahenge.
echo Tool ka folder bhi hat jayega: %TARGET%
echo.
pause
cd /d "%TEMP%"
start "" /b cmd /c "timeout /t 3 /nobreak >nul & rmdir /s /q "%TARGET%""
exit
