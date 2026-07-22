<#
  Builds the V-Agent Windows MSI from an existing release binary.

  Requires: the WiX v5 dotnet tool (`dotnet tool install --global wix`) and a
  release build at $TargetDir\release\v-agent.exe.

  Runtime siblings (conpty.dll, OpenConsole.exe) come from the same release
  directory. amd_ags_x64.dll is AMD's redistributable GPU-services library; if
  it is not beside the binary the script looks for it in an installed Zed, and
  warns if it cannot be found (AMD GPUs need it; NVIDIA/Intel do not).

  Usage:
    pwsh packaging/windows/build-msi.ps1 `
        -TargetDir C:\vagent-zed-target `
        -OutFile   $env:USERPROFILE\Downloads\V-Agent-1.0.0-x64.msi
#>
param(
    [string]$TargetDir = "C:\vagent-zed-target",
    [string]$OutFile   = "$env:USERPROFILE\Downloads\V-Agent-1.0.0-x64.msi"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$release   = Join-Path $TargetDir "release"
$stage     = Join-Path $TargetDir "msi-stage"
$icon      = Join-Path $scriptDir "..\..\crates\zed\resources\windows\app-icon.ico"

if (-not (Test-Path (Join-Path $release "v-agent.exe"))) {
    throw "v-agent.exe not found in $release. Build it first: cargo build --release --bin v-agent"
}

# Stage payload on this (ASCII) path so WiX never sees the repo's non-ASCII path.
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Copy-Item (Join-Path $release "v-agent.exe")   $stage
Copy-Item (Join-Path $release "conpty.dll")    $stage
Copy-Item (Join-Path $release "OpenConsole.exe") $stage
Copy-Item $icon (Join-Path $stage "v-agent.ico")

$amd = Join-Path $release "amd_ags_x64.dll"
if (-not (Test-Path $amd)) {
    $amd = Join-Path $env:LOCALAPPDATA "Programs\Zed\amd_ags_x64.dll"
}
if (Test-Path $amd) {
    Copy-Item $amd (Join-Path $stage "amd_ags_x64.dll")
} else {
    Write-Warning "amd_ags_x64.dll not found; AMD GPUs may fail. Continuing without it."
}

$wxs = Join-Path $scriptDir "v-agent.wxs"
Write-Host "Building MSI -> $OutFile"
& wix build $wxs -arch x64 -d "StageDir=$stage" -o $OutFile

if ($LASTEXITCODE -ne 0) { throw "wix build failed ($LASTEXITCODE)" }
Write-Host ("Done: {0} ({1:N1} MB)" -f $OutFile, ((Get-Item $OutFile).Length / 1MB))
