#
# Assembles MemexMCP-Portable.zip from the built artifacts.
#
# Run AFTER build.ps1 has produced dist/*.exe and dist/assets/OllamaSetup.exe.
# Output: dist/MemexMCP-Portable.zip
#

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$RepoRoot = Get-Location
$BuildDir = "$RepoRoot\build"
$DistDir  = "$RepoRoot\dist"
$StageDir = "$DistDir\_stage_portable"
$ZipOut   = "$DistDir\MemexMCP-Portable.zip"

# Preconditions ------------------------------------------------------------
# Setup is handled by the in-app first-launch wizard. No PowerShell needed,
# no install.ps1 in the zip. User just unblocks, extracts, double-clicks
# Memex.exe.
foreach ($f in @(
    "$DistDir\Memex.exe",
    "$DistDir\MemexMCP-Server.exe",
    "$DistDir\memex-cli.exe",
    "$BuildDir\README.txt"
)) {
    if (-not (Test-Path $f)) {
        Write-Error "missing artifact: $f  (did you run build.ps1 first?)"
        exit 1
    }
}

# Stage --------------------------------------------------------------------
if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null

Copy-Item "$DistDir\Memex.exe"                $StageDir
Copy-Item "$DistDir\MemexMCP-Server.exe"      $StageDir
Copy-Item "$DistDir\memex-cli.exe"            $StageDir
Copy-Item "$BuildDir\README.txt"              $StageDir

# Zip ----------------------------------------------------------------------
if (Test-Path $ZipOut) { Remove-Item $ZipOut -Force }
Write-Host "Compressing..."
Compress-Archive -Path "$StageDir\*" -DestinationPath $ZipOut -CompressionLevel Optimal

# Cleanup stage ------------------------------------------------------------
Remove-Item $StageDir -Recurse -Force

$size = (Get-Item $ZipOut).Length / 1MB
Write-Host ""
Write-Host ("Built: {0}  ({1:N0} MB)" -f $ZipOut, $size)
Write-Host ""
Write-Host "To distribute:"
Write-Host "  1. Upload $ZipOut somewhere your buddy can download it."
Write-Host "  2. Tell him: right-click zip -> Properties -> Unblock -> OK,"
Write-Host "     then extract, then double-click Memex.exe."
