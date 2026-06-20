"""
Self-update for the single-file portable Windows build.

A running .exe is locked by Windows and cannot overwrite itself, and the frozen
tunneld child process holds an additional lock on it. So we cannot replace the
exe from within the running app. Instead:

    1. Download the new exe into a temp folder.
    2. Write a tiny batch helper and launch it detached.
    3. Exit the app.
    4. The helper waits for this process to die, kills any lingering iFakeGPS.exe
       (e.g. a leftover tunneld child) to release the file lock, overwrites the
       old exe, relaunches it, and deletes itself.

Auto-update only applies to the frozen Windows exe; from source there is nothing
to replace, so callers fall back to opening the release page.
"""

import os
import subprocess
import sys
import tempfile
from typing import Callable, Optional

import requests

from src.utils.logger import logger

# Below this the download is almost certainly an error page, not the ~58 MB exe.
_MIN_EXE_BYTES = 1_000_000


def is_supported() -> bool:
    """True only when running as the frozen Windows exe (the only updatable form)."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def current_exe_path() -> str:
    return os.path.abspath(sys.executable)


def download_update(
    url: str,
    expected_size: int = 0,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> str:
    """Stream the new exe to a temp file and return its path.

    Raises on network failure or if the payload does not look like a Windows exe.
    ``progress_cb(downloaded_bytes, total_bytes)`` is called as data arrives
    (total may be 0 if the server omits Content-Length).
    """
    tmp_dir = tempfile.mkdtemp(prefix="ifakegps_update_")
    dest = os.path.join(tmp_dir, "iFakeGPS_new.exe")

    with requests.get(
        url,
        stream=True,
        timeout=30,
        headers={"User-Agent": "iFakeGPS Updater"},
    ) as resp:
        resp.raise_for_status()
        total = expected_size or int(resp.headers.get("Content-Length", 0) or 0)
        written = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                if not chunk:
                    continue
                f.write(chunk)
                written += len(chunk)
                if progress_cb:
                    progress_cb(written, total)

    # Sanity-check the payload: non-trivial size and a valid PE ("MZ") header.
    if written < _MIN_EXE_BYTES:
        raise ValueError(f"Downloaded file is too small ({written} bytes)")
    with open(dest, "rb") as f:
        if f.read(2) != b"MZ":
            raise ValueError("Downloaded file is not a valid Windows executable")

    logger.info("Downloaded update to %s (%s bytes)", dest, written)
    return dest


def apply_update_and_exit(new_exe_path: str) -> None:
    """Launch the detached swap helper. The caller MUST exit the app immediately
    afterwards so the helper can overwrite the (now unlocked) exe."""
    target = current_exe_path()
    image = os.path.basename(target)
    pid = os.getpid()

    bat_path = os.path.join(os.path.dirname(new_exe_path), "apply_update.bat")
    script = _BATCH_TEMPLATE.format(pid=pid, image=image)
    with open(bat_path, "w", encoding="ascii", errors="ignore") as f:
        f.write(script)

    # DETACHED_PROCESS keeps the helper alive after we exit and gives it no console
    # (so it is invisible). We pass the exe paths as quoted args to survive spaces.
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(
        subprocess, "DETACHED_PROCESS", 0x00000008
    )
    logger.info("Launching update helper %s (target=%s)", bat_path, target)
    subprocess.Popen(
        ["cmd", "/c", bat_path, target, new_exe_path],
        creationflags=creationflags,
        close_fds=True,
        cwd=os.path.dirname(new_exe_path),
    )


# NOTE: `timeout` needs a console, which a DETACHED_PROCESS batch does not have,
# so we sleep with `ping` instead (~1s per call). {pid}/{image} are filled in by
# str.format; everything else is literal batch (no other braces allowed here).
_BATCH_TEMPLATE = r"""@echo off
setlocal
set "TARGET=%~1"
set "SOURCE=%~2"

rem --- wait for the launching app (pid {pid}) to fully exit (max ~60s) ---
set /a n=0
:waitpid
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul
if not errorlevel 1 (
  set /a n+=1
  if %n% lss 60 ( ping -n 2 127.0.0.1 >nul & goto waitpid )
)

rem --- kill any lingering {image} (e.g. tunneld child) still locking the file ---
taskkill /F /IM "{image}" >nul 2>&1
ping -n 2 127.0.0.1 >nul

rem --- overwrite the exe, retrying while the lock clears (max ~30s) ---
set /a r=0
:copyloop
copy /Y "%SOURCE%" "%TARGET%" >nul 2>&1
if errorlevel 1 (
  set /a r+=1
  if %r% lss 30 ( ping -n 2 127.0.0.1 >nul & goto copyloop )
)

rem --- relaunch the app and clean up the temp folder (incl. this script) ---
start "" "%TARGET%"
(goto) 2>nul & rmdir /s /q "%~dp0"
"""
