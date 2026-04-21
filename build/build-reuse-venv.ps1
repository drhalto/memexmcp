#
# Workaround build for WDAC-blocked fresh venv.
# Uses the already-approved pyinstaller.exe from ..\datastreammcp\.venv.
# Source path is this project's ../src, so we just invoke pyinstaller directly
# against the .spec files - the editable install isn't needed since specs
# set pathex explicitly.
#

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$RepoRoot = Get-Location
$BuildDir = "$RepoRoot\build"
$DistDir  = "$RepoRoot\dist"
$PyInstaller = "C:\Users\Dustin\datastreammcp\.venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $PyInstaller)) {
    Write-Error "reused pyinstaller not found at $PyInstaller"
    exit 1
}

Write-Host "[1/3] pyinstaller: MemexMCP-Server.exe"
& $PyInstaller --noconfirm --distpath $DistDir --workpath "$BuildDir\_work" "$BuildDir\MemexMCP-Server.spec"

Write-Host "[2/3] pyinstaller: memex-cli.exe"
& $PyInstaller --noconfirm --distpath $DistDir --workpath "$BuildDir\_work" "$BuildDir\memex-cli.spec"

Write-Host "[3/3] pyinstaller: Memex.exe (GUI)"
& $PyInstaller --noconfirm --distpath $DistDir --workpath "$BuildDir\_work" "$BuildDir\Memex.spec"

Write-Host "done."
