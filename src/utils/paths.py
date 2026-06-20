"""Filesystem path helpers — frozen-exe detection, bundled-resource resolution,
and per-user data directories. Centralizes logic that used to be reimplemented
in several places (app.py, update_checker.py, tunnel_manager.py, the storages)."""

import os
import sys
from pathlib import Path

APP_NAME = "iFakeGPS"


def is_frozen() -> bool:
    """True when running as a PyInstaller-frozen exe (vs. from source)."""
    return bool(getattr(sys, "frozen", False))


def resource_path(*relative: str) -> str:
    """Resolve a bundled resource (e.g. ``app.ico``, ``docs``).

    In a frozen exe resources live under ``sys._MEIPASS``; from source they live
    at the project root (two levels above this file: ``src/utils/``).
    """
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *relative)


def get_app_data_dir() -> Path:
    """Return the per-user application data directory (created lazily by callers)."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME
    return Path.home() / ".cache" / APP_NAME


def get_cache_dir() -> Path:
    """Return (and create) the cache subdirectory for map tiles and SQLite stores."""
    cache_dir = get_app_data_dir() / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir
