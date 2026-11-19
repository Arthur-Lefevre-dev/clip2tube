"""Hidden subprocess helpers — prevent console window flashes on Windows."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Optional, Sequence

# CREATE_NO_WINDOW = 0x08000000 — hide console for console-subsystem children
_CREATE_NO_WINDOW = 0x08000000


def windows_hidden_kwargs() -> dict[str, Any]:
    """
    Kwargs for subprocess.run / Popen so no console window flashes.

    CREATE_NO_WINDOW alone is not always enough (some tools still flash);
    STARTUPINFO + SW_HIDE is the reliable combo on Windows GUI apps.
    """
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    flags = int(getattr(subprocess, "CREATE_NO_WINDOW", _CREATE_NO_WINDOW))
    return {
        "startupinfo": startupinfo,
        "creationflags": flags,
    }


def patch_subprocess_no_window() -> None:
    """
    Globally force hidden consoles on every subprocess.Popen (yt-dlp, libs…).
    Safe to call multiple times.
    """
    if os.name != "nt":
        return
    if getattr(subprocess, "_clip2tube_hidden_patched", False):
        return
    hidden = windows_hidden_kwargs()
    if not hidden:
        return
    original_popen = subprocess.Popen

    def _popen(*args, **kwargs):  # type: ignore[no-untyped-def]
        for key, value in hidden.items():
            if key == "creationflags":
                kwargs["creationflags"] = int(kwargs.get("creationflags", 0)) | int(
                    value
                )
            else:
                kwargs.setdefault(key, value)
        return original_popen(*args, **kwargs)

    subprocess.Popen = _popen  # type: ignore[misc]
    subprocess._clip2tube_hidden_patched = True  # type: ignore[attr-defined]


def run_hidden(
    cmd: Sequence[str],
    *,
    timeout: Optional[float] = None,
    check: bool = False,
    text: bool = True,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """subprocess.run with stdout/stderr captured and no visible console."""
    patch_subprocess_no_window()
    kwargs: dict[str, Any] = {
        "args": list(cmd),
        "capture_output": True,
        "text": text,
        "timeout": timeout,
        "check": check,
        "cwd": cwd,
        "env": env,
        "stdin": subprocess.DEVNULL,
    }
    kwargs.update(windows_hidden_kwargs())
    return subprocess.run(**kwargs)
