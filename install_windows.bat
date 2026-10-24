@echo off
rem Mogrt Font Fixer installer (Windows 10 / 11). Is file pe double-click karo.
setlocal EnableExtensions
title Mogrt Font Fixer - Install
set "SRC=%~dp0"
set "TARGET=%LOCALAPPDATA%\MogrtFontFixer"
set "PY=%TARGET%\python\python.exe"
set "PYURL=https://github.com/astral-sh/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-x86_64-pc-windows-msvc-install_only.tar.gz"

echo.
echo == Mogrt Font Fixer install ==
echo.
if not exist "%SRC%mogrt_font_fixer.py" goto nozip

if not exist "%TARGET%" mkdir "%TARGET%"
if /I "%SRC%"=="%TARGET%\" goto copied
copy /Y "%SRC%mogrt_font_fixer.py" "%TARGET%\" >nul
if errorlevel 1 goto copyfail
copy /Y "%SRC%install_windows.bat" "%TARGET%\" >nul
copy /Y "%SRC%uninstall_windows.bat" "%TARGET%\" >nul
if exist "%SRC%README.txt" copy /Y "%SRC%README.txt" "%TARGET%\" >nul
:copied

if exist "%PY%" goto havepy
echo Python download ho raha hai. Ye sirf pehli baar hota hai, lagbhag 40 MB...
where curl.exe >nul 2>&1
if errorlevel 1 goto psdownload
curl.exe -L --fail -o "%TARGET%\python.tar.gz" "%PYURL%"
if errorlevel 1 goto pyfail
goto unpack
:psdownload
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = 'Tls12'; Invoke-WebRequest -UseBasicParsing -Uri $env:PYURL -OutFile (Join-Path $env:TARGET 'python.tar.gz')"
if errorlevel 1 goto pyfail
:unpack
tar -xzf "%TARGET%\python.tar.gz" -C "%TARGET%"
if errorlevel 1 goto pyfail
del "%TARGET%\python.tar.gz" >nul 2>&1
if not exist "%PY%" goto pyfail
:havepy

echo Auto-start aur shortcut lag rahe hain...
"%PY%" "%TARGET%\mogrt_font_fixer.py" setup-windows
if errorlevel 1 goto setupfail

echo.
echo Pehla full scan chal raha hai. Isme 2-10 minute lag sakte hain, window band mat karna...
echo.
"%PY%" "%TARGET%\mogrt_font_fixer.py" scan --force --open-report
"%PY%" "%TARGET%\mogrt_font_fixer.py" start-watch

echo.
echo == Ho gaya. Report browser me khul gayi hogi. ==
echo Ab ye window band kar sakte ho. Tool background me chalta rahega
echo aur PC start hote hi apne aap chalu ho jayega.
echo.
pause
exit /b 0

:nozip
echo ERROR: Pehle zip ko "Extract All" karke kholo, phir extract hue folder me se
echo install_windows.bat chalao. Zip ke andar se seedha mat chalao.
goto fail
:copyfail
echo ERROR: Files copy nahi hui: %TARGET%
goto fail
:pyfail
echo ERROR: Python download ya unpack nahi hua. Internet check karke dobara chalao.
del "%TARGET%\python.tar.gz" >nul 2>&1
goto fail
:setupfail
echo ERROR: Setup fail hua. Ye file bhej do: %TARGET%\log.txt
goto fail
:fail
echo.
pause
exit /b 1
