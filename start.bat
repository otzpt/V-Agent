@echo off
:: V-Agent v0.7 — Launcher
:: Run this from any location; it navigates to the script's folder automatically.
cd /d "%~dp0"
title V-Agent v0.7

:: ── Find Python ───────────────────────────────────────────────────────────────
set PYTHON=

where pythonw >nul 2>&1 && set PYTHON=pythonw && goto :found
where python  >nul 2>&1 && set PYTHON=python  && goto :found

for %%V in (313 312 311 310 39) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\pythonw.exe" (
        set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python%%V\pythonw.exe"
        goto :found
    )
)
for %%V in (313 312 311 310 39) do (
    if exist "C:\Python%%V\pythonw.exe" (
        set "PYTHON=C:\Python%%V\pythonw.exe"
        goto :found
    )
)

echo.
echo  [ERROR] Python not found.
echo  Install from: https://www.python.org/downloads/
echo  During install, check "Add Python to PATH".
echo.
pause
exit /b 1

:found
echo [OK] Python: %PYTHON%

:: ── Check Ollama (non-fatal) ───────────────────────────────────────────────────
curl -s --max-time 2 http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [WARN] Ollama not detected. Start it with: ollama serve
)

:: ── Install missing deps ───────────────────────────────────────────────────────
%PYTHON% -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing requests...
    python -m pip install requests --quiet
)

:: ── Launch ────────────────────────────────────────────────────────────────────
echo [OK] Launching V-Agent...
start "" %PYTHON% vagent.py
exit /b 0
