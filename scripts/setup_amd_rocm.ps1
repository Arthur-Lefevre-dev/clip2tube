# Install AMD ROCm runtime + CTranslate2 ROCm wheel for faster-whisper (Windows).
# Requires: Python 3.10–3.14 venv already created (.venv).

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvPip = Join-Path $Root ".venv\Scripts\pip.exe"
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPip)) {
    throw "Missing .venv — create it first (python -m venv .venv)"
}

$PyTag = & $VenvPy -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}')"
Write-Host "Python tag: $PyTag"

Write-Host "Installing ROCm 7.2 SDK wheels…"
& $VenvPip install --no-cache-dir `
    "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/rocm_sdk_core-7.2.0.dev0-py3-none-win_amd64.whl" `
    "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/rocm_sdk_libraries_custom-7.2.0.dev0-py3-none-win_amd64.whl" `
    "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/rocm-7.2.0.dev0.tar.gz"

$Cache = Join-Path $Root ".cache\rocm_ct2"
New-Item -ItemType Directory -Force -Path $Cache | Out-Null
$Zip = Join-Path $Cache "rocm-python-wheels-Windows.zip"
$Ct2Ver = "v4.9.0"
if (-not (Test-Path $Zip)) {
    Write-Host "Downloading CTranslate2 $Ct2Ver ROCm Windows wheels…"
    Invoke-WebRequest `
        -Uri "https://github.com/OpenNMT/CTranslate2/releases/download/$Ct2Ver/rocm-python-wheels-Windows.zip" `
        -OutFile $Zip
}
$Extract = Join-Path $Cache "wheels"
Expand-Archive -Path $Zip -DestinationPath $Extract -Force
$Whl = Get-ChildItem -Path $Extract -Recurse -Filter "ctranslate2-*-$PyTag-*-win_amd64.whl" |
    Where-Object { $_.Name -notmatch "cp\d+t-" } |
    Select-Object -First 1
if (-not $Whl) {
    throw "No CTranslate2 ROCm wheel for $PyTag in $Extract"
}

Write-Host "Replacing ctranslate2 with ROCm wheel: $($Whl.Name)"
& $VenvPip uninstall -y ctranslate2
& $VenvPip install --force-reinstall --no-deps $Whl.FullName

$env:CT2_CUDA_ALLOCATOR = "cub_caching"
& $VenvPy -c @"
import os
os.environ['CT2_CUDA_ALLOCATOR'] = 'cub_caching'
import ctranslate2
from app.utils.gpu import detect_gpu, resolve_whisper_device
detect_gpu.cache_clear()
print('devices', ctranslate2.get_cuda_device_count())
print(detect_gpu())
print(resolve_whisper_device(True))
"@
Write-Host "Done. Whisper will use AMD ROCm when GPU is enabled in settings."
