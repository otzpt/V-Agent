# V-Agent Windows Installer (PowerShell)
# Run: powershell -ExecutionPolicy Bypass -File install.ps1
#Requires -Version 5.0
param(
    [switch]$Venv,
    [switch]$NoShortcut
)

$VERSION    = "0.7.1"
$INSTALL_DIR = "$env:LOCALAPPDATA\VAgent"
$SCRIPT_DIR  = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Write-Step { param($msg) Write-Host "→ $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Err  { param($msg) Write-Host "❌ $msg" -ForegroundColor Red; exit 1 }

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
Write-Host "  V-Agent $VERSION — Windows Installer" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue

# ── Check Python ──────────────────────────────────────────────────────────────
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Err "Python 3.10+ not found. Download from https://python.org"
}

$pyver = & $python.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$pyok  = & $python.Source -c "import sys; print(1 if sys.version_info >= (3,10) else 0)"
if ($pyok -ne "1") { Write-Err "Python 3.10+ required (found $pyver)" }
Write-OK "Python $pyver"

# ── Copy files ────────────────────────────────────────────────────────────────
Write-Step "Installing to $INSTALL_DIR..."
if (Test-Path $INSTALL_DIR) { Remove-Item $INSTALL_DIR -Recurse -Force }
Copy-Item $SCRIPT_DIR -Destination $INSTALL_DIR -Recurse -Force
Write-OK "Files copied"

# ── Virtual environment ───────────────────────────────────────────────────────
$PYTHON_RUN = $python.Source
if ($Venv) {
    Write-Step "Creating virtual environment..."
    & $python.Source -m venv "$INSTALL_DIR\venv"
    $PYTHON_RUN = "$INSTALL_DIR\venv\Scripts\python.exe"
    Write-OK "Venv created"
}

# ── Dependencies ──────────────────────────────────────────────────────────────
Write-Step "Installing Python dependencies..."
& $PYTHON_RUN -m pip install --quiet --upgrade pip
& $PYTHON_RUN -m pip install --quiet -r "$INSTALL_DIR\requirements.txt"
Write-OK "Dependencies installed"

# ── Launcher batch ────────────────────────────────────────────────────────────
$bat = "@echo off`r`n`"$PYTHON_RUN`" `"$INSTALL_DIR\vagent.py`" %*"
$bat | Set-Content "$INSTALL_DIR\vagent.bat" -Encoding ASCII

# Add to user PATH
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$INSTALL_DIR*") {
    [Environment]::SetEnvironmentVariable("PATH", "$userPath;$INSTALL_DIR", "User")
    Write-OK "Added to PATH"
}

# ── Desktop shortcut ─────────────────────────────────────────────────────────
if (-not $NoShortcut) {
    Write-Step "Creating desktop shortcut..."
    $WshShell  = New-Object -ComObject WScript.Shell
    $Shortcut  = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\V-Agent.lnk")
    $Shortcut.TargetPath       = $PYTHON_RUN
    $Shortcut.Arguments        = "`"$INSTALL_DIR\vagent.py`""
    $Shortcut.WorkingDirectory = $INSTALL_DIR
    $Shortcut.IconLocation     = "$INSTALL_DIR\assets\icon.ico,0"
    $Shortcut.Description      = "V-Agent — Professional Agentic IDE"
    $Shortcut.Save()
    Write-OK "Desktop shortcut created"
}

Write-Host ""
Write-Host "✅ V-Agent $VERSION installed!" -ForegroundColor Green
Write-Host ""
Write-Host "Launch: vagent  (in a new terminal)" -ForegroundColor White
Write-Host "    or: double-click the desktop shortcut" -ForegroundColor White
