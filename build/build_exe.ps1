# Build a standalone Clip2Tube Windows package (no repo required to run).
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File .\build\build_exe.ps1
#
# Output:
#   dist\Clip2Tube\Clip2Tube.exe   (+ _internal, ffmpeg, config, …)
#   dist\Clip2Tube-Portable.zip    (à copier sur n'importe quel PC Windows)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "============================================"
Write-Host " Clip2Tube — build portable Windows (.exe)"
Write-Host "============================================"

# Prefer project venv if present
$Py = "python"
$Pip = "pip"
if (Test-Path ".\.venv\Scripts\python.exe") {
    $Py = ".\.venv\Scripts\python.exe"
    $Pip = ".\.venv\Scripts\pip.exe"
}

Write-Host "==> Dépendances build"
& $Pip install -r requirements.txt --quiet
& $Pip install pyinstaller --quiet

Write-Host "==> Nettoyage"
Remove-Item -Recurse -Force .\dist\Clip2Tube -ErrorAction SilentlyContinue
Remove-Item -Force .\dist\Clip2Tube-Portable.zip -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\build\pyinstaller -ErrorAction SilentlyContinue

Write-Host "==> PyInstaller (peut prendre plusieurs minutes)…"
& $Py -m PyInstaller `
  --noconfirm `
  --clean `
  --distpath .\dist `
  --workpath .\build\pyinstaller `
  .\build\Clip2Tube.spec

$Out = Join-Path $Root "dist\Clip2Tube"
if (-not (Test-Path (Join-Path $Out "Clip2Tube.exe"))) {
    throw "Build échoué : Clip2Tube.exe introuvable dans $Out"
}

# Remove incomplete PyInstaller work copy — launching it fails with
# "Failed to load Python DLL" because _internal is incomplete there.
$WorkCopy = Join-Path $Root "build\pyinstaller\Clip2Tube"
if (Test-Path $WorkCopy) {
    Write-Host "==> Suppression du dossier de travail incomplet (ne pas lancer celui-là)"
    Remove-Item -Recurse -Force $WorkCopy -ErrorAction SilentlyContinue
}

Write-Host "==> Dossiers runtime"
@(
    "config",
    "data",
    "output",
    "music",
    "temp",
    "ffmpeg"
) | ForEach-Object {
    New-Item -ItemType Directory -Force -Path (Join-Path $Out $_) | Out-Null
}

Copy-Item (Join-Path $Root "config\config.example.json") (Join-Path $Out "config\config.example.json") -Force
if (-not (Test-Path (Join-Path $Out "config\config.json"))) {
    Copy-Item (Join-Path $Root "config\config.example.json") (Join-Path $Out "config\config.json") -Force
}

Write-Host "==> FFmpeg embarqué"
& powershell -ExecutionPolicy Bypass -File (Join-Path $Root "build\download_ffmpeg.ps1") -DestDir (Join-Path $Out "ffmpeg")

# Starter + docs for end users (no repo knowledge needed)
@"
@echo off
cd /d "%~dp0"
start "" "%~dp0Clip2Tube.exe"
"@ | Set-Content -Path (Join-Path $Out "Lancer_Clip2Tube.bat") -Encoding ASCII

Copy-Item (Join-Path $Root "build\LISEZMOI_INSTALLATION.txt") (Join-Path $Out "LISEZMOI.txt") -Force

Write-Host "==> Archive ZIP portable"
$Zip = Join-Path $Root "dist\Clip2Tube-Portable.zip"
if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path $Out -DestinationPath $Zip -CompressionLevel Optimal

Write-Host ""
Write-Host "OK — package prêt :"
Write-Host "  Exe   : $Out\Clip2Tube.exe"
Write-Host "  ZIP   : $Zip"
Write-Host ""
Write-Host "Copiez le dossier dist\Clip2Tube (ou le ZIP) sur n'importe quel PC Windows."
Write-Host "Internet requis au 1er lancement pour télécharger le modèle Whisper."
