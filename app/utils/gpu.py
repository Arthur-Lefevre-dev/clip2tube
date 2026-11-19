"""Detect the user's GPU (NVIDIA CUDA / AMD ROCm) for Whisper acceleration."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from app.utils.process import run_hidden

Vendor = Literal["nvidia", "amd", "intel", "other", "none"]


@dataclass(frozen=True)
class GpuInfo:
    vendor: Vendor
    name: str
    cuda_available: bool
    """True when faster-whisper / CTranslate2 can use NVIDIA CUDA."""
    rocm_available: bool = False
    """True when faster-whisper / CTranslate2 can use AMD ROCm (device='cuda')."""

    @property
    def label(self) -> str:
        if self.vendor == "none":
            return "Aucun GPU détecté"
        name = self.name or self.vendor.upper()
        if self.vendor == "nvidia" and self.cuda_available:
            return f"NVIDIA — {name} (CUDA OK)"
        if self.vendor == "nvidia":
            return f"NVIDIA — {name} (CUDA indisponible)"
        if self.vendor == "amd" and self.rocm_available:
            return f"AMD — {name} (ROCm OK)"
        if self.vendor == "amd":
            return (
                f"AMD — {name} (ROCm indisponible — "
                "installez la wheel CTranslate2 ROCm)"
            )
        return f"{self.vendor.upper()} — {name}"


def _run(cmd: list[str], timeout: float = 8.0) -> str:
    try:
        proc = run_hidden(cmd, timeout=timeout, check=False)
        if proc.returncode != 0:
            return ""
        return (proc.stdout or "").strip()
    except Exception:
        return ""


def _detect_via_wmi() -> list[str]:
    """Return video controller names via PowerShell CIM (Windows)."""
    script = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object -ExpandProperty Name"
    )
    out = _run(
        [
            "powershell",
            "-NoProfile",
            "-WindowStyle",
            "Hidden",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ]
    )
    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _classify(name: str) -> Vendor:
    n = name.lower()
    if any(k in n for k in ("nvidia", "geforce", "rtx", "gtx", "quadro", "tesla")):
        return "nvidia"
    if any(k in n for k in ("amd", "radeon", "rx ", "vega", "instinct")):
        return "amd"
    if "intel" in n or "arc" in n or "uhd" in n or "iris" in n:
        return "intel"
    return "other"


def _ct2_gpu_device_count() -> int:
    """CTranslate2 reports ROCm devices via get_cuda_device_count() too."""
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count() or 0)
    except Exception:
        return 0


def _ct2_cuda_compute_types_ok() -> bool:
    try:
        import ctranslate2

        types = ctranslate2.get_supported_compute_types("cuda")
        return bool(types)
    except Exception:
        return False


def _cuda_runtime_ok() -> bool:
    """Check if NVIDIA CUDA is usable for CTranslate2 / faster-whisper."""
    if shutil.which("nvidia-smi"):
        smi = _run(["nvidia-smi", "-L"])
        if not (smi and "GPU" in smi):
            return False

    if _ct2_gpu_device_count() > 0 and _ct2_cuda_compute_types_ok():
        return True

    try:
        import torch  # type: ignore

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _hip_runtime_present() -> bool:
    """Best-effort: HIP/ROCm runtime DLLs or env paths on this machine."""
    if os.environ.get("ROCM_PATH") or os.environ.get("HIP_PATH"):
        return True
    for key in ("PATH",):
        path = os.environ.get(key, "")
        if any(tok in path.lower() for tok in ("\\rocm", "/rocm", "\\hip", "/hip")):
            return True
    # System HIP libs shipped with Adrenalin / ROCm on Windows
    windir = os.environ.get("WINDIR", r"C:\Windows")
    for name in ("amdhip64_7.dll", "amdhip64_6.dll", "amdhip64.dll"):
        if os.path.isfile(os.path.join(windir, "System32", name)):
            return True
    # pip rocm-sdk package
    try:
        import rocm_sdk  # type: ignore  # noqa: F401

        return True
    except Exception:
        pass
    return False


def _rocm_runtime_ok() -> bool:
    """
    True when CTranslate2 can run on AMD via ROCm/HIP.

    Official ROCm wheels still expose the device as ``cuda``.
    """
    count = _ct2_gpu_device_count()
    if count > 0:
        # Prefer real device enumeration; compute-types may throw on CUDA-only wheels
        if _ct2_cuda_compute_types_ok() or _hip_runtime_present():
            return True
        return True
    # CT2 not ready yet, but HIP/ROCm libs look installed
    return False


def prepare_rocm_env() -> None:
    """
    Tune env for AMD ROCm before creating WhisperModel.

    ``CT2_CUDA_ALLOCATOR=cub_caching`` avoids HIP hipMallocAsync bugs on many cards.
    """
    os.environ.setdefault("CT2_CUDA_ALLOCATOR", "cub_caching")


@lru_cache(maxsize=1)
def detect_gpu() -> GpuInfo:
    """Probe the machine once and cache the result."""
    names = _detect_via_wmi()
    if not names and shutil.which("nvidia-smi"):
        smi = _run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
        if smi:
            names = [line.strip() for line in smi.splitlines() if line.strip()]

    preferred: Vendor = "none"
    preferred_name = ""
    for name in names:
        vendor = _classify(name)
        # Prefer discrete NVIDIA, then AMD, over Intel iGPU
        if vendor == "nvidia":
            preferred, preferred_name = "nvidia", name
            break
        if vendor == "amd" and preferred not in ("nvidia",):
            preferred, preferred_name = "amd", name
        elif vendor == "intel" and preferred == "none":
            preferred, preferred_name = "intel", name
        elif preferred == "none":
            preferred, preferred_name = vendor, name

    has_nvidia = preferred == "nvidia" or any(
        _classify(n) == "nvidia" for n in names
    )
    has_amd = preferred == "amd" or any(_classify(n) == "amd" for n in names)

    cuda = False
    rocm = False

    if has_nvidia:
        cuda = _cuda_runtime_ok()
        if preferred != "nvidia":
            for name in names:
                if _classify(name) == "nvidia":
                    preferred, preferred_name = "nvidia", name
                    break

    if has_amd and preferred != "nvidia":
        # ROCm CT2 wheel reports devices via get_cuda_device_count()
        rocm = _rocm_runtime_ok() and not cuda
        # If CT2 sees GPU devices and we are on AMD without NVIDIA → ROCm wheel
        if preferred == "amd" and _ct2_gpu_device_count() > 0 and not has_nvidia:
            rocm = True
        # HIP present but CT2 still CUDA-only wheel → not usable yet
        if preferred == "amd" and _ct2_gpu_device_count() == 0:
            rocm = False

    if not names:
        if _cuda_runtime_ok():
            return GpuInfo(
                vendor="nvidia",
                name="CUDA device",
                cuda_available=True,
                rocm_available=False,
            )
        if _rocm_runtime_ok() and _ct2_gpu_device_count() > 0:
            return GpuInfo(
                vendor="amd",
                name="ROCm device",
                cuda_available=False,
                rocm_available=True,
            )
        return GpuInfo(
            vendor="none", name="", cuda_available=False, rocm_available=False
        )

    return GpuInfo(
        vendor=preferred,
        name=preferred_name,
        cuda_available=cuda if preferred == "nvidia" else False,
        rocm_available=rocm if preferred == "amd" else False,
    )


def resolve_whisper_device(use_gpu: bool = True) -> tuple[str, str, str]:
    """
    Choose faster-whisper device / compute_type.

    Returns ``(device, compute_type, reason)``.
    - NVIDIA + CUDA → ``cuda`` / ``float16``
    - AMD + ROCm → ``cuda`` / ``float16`` (CTranslate2 ROCm uses the cuda API)
    - else → ``cpu`` / ``int8``
    """
    if not use_gpu:
        return "cpu", "int8", "GPU désactivé dans les réglages"

    info = detect_gpu()
    if info.vendor == "nvidia" and info.cuda_available:
        return (
            "cuda",
            "float16",
            f"GPU NVIDIA (CUDA) : {info.name}",
        )
    if info.vendor == "nvidia" and not info.cuda_available:
        return (
            "cpu",
            "int8",
            f"NVIDIA détecté ({info.name}) mais CUDA indisponible → CPU",
        )
    if info.vendor == "amd" and info.rocm_available:
        prepare_rocm_env()
        return (
            "cuda",
            "float16",
            f"GPU AMD (ROCm) : {info.name}",
        )
    if info.vendor == "amd" and not info.rocm_available:
        return (
            "cpu",
            "int8",
            f"AMD détecté ({info.name}) mais ROCm/CTranslate2 ROCm indisponible → CPU",
        )
    if info.vendor == "none":
        return "cpu", "int8", "Pas de GPU utilisable → CPU"
    return (
        "cpu",
        "int8",
        f"{info.label} → CPU pour Whisper",
    )
