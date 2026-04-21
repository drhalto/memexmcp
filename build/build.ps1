#
# Build pipeline for MemexMCP.
#
#  1. Create a build venv (uv preferred, falls back to python -m venv)
#  2. Install runtime + build deps
#  3. PyInstaller three exes (GUI, MCP server, CLI)
#  4. (Optional) Run Inno Setup: iscc MemexMCP.iss
#
# Ollama is NOT bundled - install.ps1 / the Inno installer fetch it on demand.
#
#  Requires: Python 3.12+ on PATH. Inno Setup 6 is optional - only needed for
#  the installer step.
#

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$RepoRoot = Get-Location
$BuildDir = "$RepoRoot\build"
$DistDir  = "$RepoRoot\dist"
$AssetsDir = "$DistDir\assets"

Write-Host "[1/5] venv + deps"
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv venv .venv --python 3.12 --seed
    & .venv\Scripts\Activate.ps1
    uv pip install -e ".[gui,dev]"
} else {
    if (-not (Test-Path .venv)) { python -m venv .venv }
    & .venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -e ".[gui,dev]"
}

Write-Host "[2/4] pyinstaller: MemexMCP-Server.exe"
pyinstaller --noconfirm --distpath $DistDir --workpath "$BuildDir\_work" "$BuildDir\MemexMCP-Server.spec"

Write-Host "[3a/4] pyinstaller: memex-cli.exe"
pyinstaller --noconfirm --distpath $DistDir --workpath "$BuildDir\_work" "$BuildDir\memex-cli.spec"

Write-Host "[3b/4] pyinstaller: Memex.exe (GUI)"
pyinstaller --noconfirm --distpath $DistDir --workpath "$BuildDir\_work" "$BuildDir\Memex.spec"

Write-Host "[4/4] (optional) build installer"
if (Get-Command iscc -ErrorAction SilentlyContinue) {
    iscc "$BuildDir\MemexMCP.iss"
    Write-Host "installer: $DistDir\MemexMCP-Setup.exe"
} else {
    Write-Host "  iscc not on PATH - skipping installer step."
    Write-Host "  install Inno Setup 6, then: iscc $BuildDir\MemexMCP.iss"
}

Write-Host "done."
