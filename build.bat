@echo off
REM V-Agent v0.7 — Build Setup
REM Compiles Python scripts to .exe and prepares for installer
REM Requires: PyInstaller (pip install pyinstaller)

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ════════════════════════════════════════════════════════════════
echo  V-Agent v0.7 — Build
echo ════════════════════════════════════════════════════════════════
echo.

REM ── Check PyInstaller ──────────────────────────────────────────────
echo [1/5] Checking PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    python -m pip install pyinstaller --quiet
)
echo [OK] PyInstaller ready.
echo.

REM ── Install dependencies ───────────────────────────────────────────
echo [2/5] Installing dependencies...
python -m pip install requests watchdog --quiet
echo [OK] Dependencies installed.
echo.

REM ── Build vagent.exe ───────────────────────────────────────────────
echo [3/5] Building vagent.exe...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist vagent.spec del vagent.spec

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "V-Agent" ^
    --icon=assets\vagent.ico ^
    --add-data "config.json;." ^
    --hidden-import=tkinter ^
    --hidden-import=requests ^
    --collect-submodules tkinter ^
    vagent.py

if not exist "dist\V-Agent.exe" (
    echo [ERROR] Failed to build vagent.exe
    pause
    exit /b 1
)
echo [OK] vagent.exe built.
echo.

REM ── Build automator.exe ────────────────────────────────────────────
echo [4/5] Building automator.exe...
if exist build rmdir /s /q build
if exist automator.spec del automator.spec

pyinstaller ^
    --onefile ^
    --console ^
    --name "V-Agent-Automator" ^
    --hidden-import=requests ^
    --hidden-import=watchdog ^
    automator.py

if not exist "dist\V-Agent-Automator.exe" (
    echo [ERROR] Failed to build automator.exe
    pause
    exit /b 1
)
echo [OK] automator.exe built.
echo.

REM ── Create dist folder structure ───────────────────────────────────
echo [5/5] Preparing distribution...

REM Copy files to dist
if exist dist\Input  rmdir /s /q dist\Input
if exist dist\Output rmdir /s /q dist\Output
mkdir dist\Input
mkdir dist\Output

REM Copy config, scripts, docs
copy config.json dist\ >nul
copy README.md dist\ >nul
copy LICENSE dist\ >nul
copy start.bat dist\ >nul
copy automator.py dist\ >nul

REM Copy bin folder if it exists
if exist bin (
    if not exist dist\bin mkdir dist\bin
    copy bin\V-Agent.exe dist\bin\ >nul 2>&1
    copy bin\WebView2Loader.dll dist\bin\ >nul 2>&1
)

REM Copy assets if it exists
if exist assets (
    if not exist dist\assets mkdir dist\assets
    xcopy assets\* dist\assets\ /Y >nul 2>&1
)

echo [OK] Distribution ready at: dist\
echo.

REM ── Summary ────────────────────────────────────────────────────────
echo ════════════════════════════════════════════════════════════════
echo  Build Complete!
echo ════════════════════════════════════════════════════════════════
echo.
echo Next steps:
echo  1. Download and install Inno Setup 6.x from:
echo     https://jrsoftware.org/isinfo.php
echo.
echo  2. Double-click setup.iss to create the installer
echo.
echo  3. Your V-Agent-Setup.exe will be in the current folder
echo.
pause
