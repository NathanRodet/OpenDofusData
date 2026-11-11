"""Replace the running executable with the downloaded one and restart it (Windows only)."""

import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
RETRY_COUNT = 50
RETRY_DELAY_MILLISECONDS = 200
RESET_ENVIRONMENT_KEY = "PYINSTALLER_RESET_ENVIRONMENT"
SCRIPT_TEMPLATE = (
    "Wait-Process -Id {pid} -ErrorAction SilentlyContinue; "
    "for ($attempt = 0; $attempt -lt {retries}; $attempt++) {{ "
    "try {{ Move-Item -LiteralPath '{new}' -Destination '{target}' -Force -ErrorAction Stop; break }} "
    "catch {{ Start-Sleep -Milliseconds {delay} }} }}; "
    "Start-Process -FilePath '{target}'"
)
Spawn = Callable[..., object]


def can_self_update() -> bool:
    """True only for a frozen Windows build (a source checkout updates with git or pip)."""
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def _quoted(path: Path) -> str:
    return str(path).replace("'", "''")


def replacement_script(new_path: Path, target_path: Path, pid: int) -> str:
    """PowerShell text: wait for the process, move the new file over the old one, start it."""
    return SCRIPT_TEMPLATE.format(pid=pid, retries=RETRY_COUNT, delay=RETRY_DELAY_MILLISECONDS,
                                  new=_quoted(new_path), target=_quoted(target_path))


def launch_replacement(
    new_path: Path, target_path: Path | None = None, pid: int | None = None,
    spawn: Spawn = subprocess.Popen, environ: Mapping[str, str] = os.environ,
) -> None:
    """Start the detached helper; the caller must then close the application."""
    script = replacement_script(new_path, target_path or Path(sys.executable),
                                os.getpid() if pid is None else pid)
    spawn(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
          creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
          env={**environ, RESET_ENVIRONMENT_KEY: "1"}, close_fds=True)
