# Download FFmpeg essentials into a target folder (ffmpeg.exe + ffprobe.exe).
param(
    [Parameter(Mandatory = $true)]
    [string]$DestDir
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

$ffmpegExe = Join-Path $DestDir "ffmpeg.exe"
$ffprobeExe = Join-Path $DestDir "ffprobe.exe"
if ((Test-Path $ffmpegExe) -and (Test-Path $ffprobeExe)) {
    Write-Host "FFmpeg déjà présent dans $DestDir"
    return
}

$Url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$Zip = Join-Path $env:TEMP "ffmpeg-essentials-clip2tube.zip"
$Extract = Join-Path $env:TEMP "ffmpeg-essentials-clip2tube"

Write-Host "==> Téléchargement FFmpeg (essentials)…"
Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing

if (Test-Path $Extract) { Remove-Item -Recurse -Force $Extract }
Expand-Archive -Path $Zip -DestinationPath $Extract -Force

$found = Get-ChildItem -Path $Extract -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
if (-not $found) { throw "ffmpeg.exe introuvable dans l'archive" }
$binDir = $found.Directory.FullName

Copy-Item (Join-Path $binDir "ffmpeg.exe") $ffmpegExe -Force
Copy-Item (Join-Path $binDir "ffprobe.exe") $ffprobeExe -Force

Write-Host "FFmpeg installé : $ffmpegExe"
