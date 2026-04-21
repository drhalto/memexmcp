#
# Workaround build for environments where Windows Defender Application Control
# (WDAC) or AppLocker blocks freshly-installed pyinstaller.exe.
#
# Pass -PyInstaller pointing at an already-approved PyInstaller binary on
# your machine. Source path is this project's ../src, so the editable install
# isn't needed - specs set pathex explicitly.
#
# Usage:
#   .\build-reuse-venv.ps1 -PyInstaller "C:\path\to\some\.venv\Scripts\pyinstaller.exe"
#
# Or set the MEMEX_PYINSTALLER environment variable and run with no args.
#

param(
    [string]$PyInstaller = $env:MEMEX_PYINSTALLER
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$RepoRoot = Get-Location
$BuildDir = "$RepoRoot\build"
$DistDir  = "$RepoRoot\dist"

if (-not $PyInstaller) {
    Write-Error @"
No PyInstaller path provided.

Either pass it explicitly:
    .\build-reuse-venv.ps1 -PyInstaller "<path-to-pyinstaller.exe>"

Or set the env var:
    `$env:MEMEX_PYINSTALLER = "<path-to-pyinstaller.exe>"
    .\build-reuse-venv.ps1

If you don't have an approved PyInstaller (i.e. WDAC isn't blocking you),
just use .\build.ps1 instead - it creates a fresh venv and installs deps.
"@
    exit 1
}

if (-not (Test-Path $PyInstaller)) {
    Write-Error "PyInstaller not found at: $PyInstaller"
    exit 1
}

Write-Host "[1/3] pyinstaller: MemexMCP-Server.exe"
& $PyInstaller --noconfirm --distpath $DistDir --workpath "$BuildDir\_work" "$BuildDir\MemexMCP-Server.spec"

Write-Host "[2/3] pyinstaller: memex-cli.exe"
& $PyInstaller --noconfirm --distpath $DistDir --workpath "$BuildDir\_work" "$BuildDir\memex-cli.spec"

Write-Host "[3/3] pyinstaller: Memex.exe (GUI)"
& $PyInstaller --noconfirm --distpath $DistDir --workpath "$BuildDir\_work" "$BuildDir\Memex.spec"

Write-Host "done."
