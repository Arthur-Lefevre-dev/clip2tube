"""Hidden subprocess helpers — prevent console window flashes on Windows."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Optional, Sequence


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
    flags = 0
    flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return {
        "startupinfo": startupinfo,
        "creationflags": flags,
    }


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
    kwargs: dict[str, Any] = {
        "args": list(cmd),
        "capture_output": True,
        "text": text,
        "timeout": timeout,
        "check": check,
        "cwd": cwd,
        "env": env,
    }
    kwargs.update(windows_hidden_kwargs())
    return subprocess.run(**kwargs)
