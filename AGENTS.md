# iFakeGPS Development Guide

This project uses `uv` for dependency management and execution.

## Key Instructions for Agents

1.  **Usage of `uv`**:
    *   ALWAYS use `uv` for managing dependencies and running the application or scripts.
    *   Do NOT use `pip` directly unless absolutely necessary (and justified).
    *   To run the app from source: `uv run python scripts/run.py` (or double-click `scripts/run.bat`, which self-elevates to admin).
    *   To add packages: `uv add <package_name>`
    *   To add dev packages: `uv add --dev <package_name>`
    *   To build the Windows exe: `scripts/pack.bat` (runs `uv run python -m PyInstaller iFakeGPS.spec`).
    *   **WSL/Linux agent environment**: Do NOT use or modify the project-local `.venv`; it is reserved for the user's Windows environment. When running checks from WSL/Linux, point `uv` at an external virtualenv, for example:
        *   `UV_PROJECT_ENVIRONMENT=/tmp/ifakegps-check-venv uv run --no-sync python -m py_compile ...`

2.  **Platform specifics**:
    *   **Windows**: The project is primarily targeted for Windows (handling admin privileges, `pythonw` for GUI, etc.).
    *   **iOS 17+ Support**: The app uses `pymobiledevice3`'s RSD tunnel which requires `tunneld` to handle device communication.
        *   The app tries to start `tunneld` automatically if not running.
        *   This requires Administrator privileges on Windows.
        *   **Frozen App (EXE)**: When running as a PyInstaller frozen exe, the app spawns a subprocess with `--internal-tunneld` to avoid infinite recursion. BE CAREFUL when modifying the `if __name__ == "__main__":` block or `TunneldManager.start`.

3.  **Code Structure (Refactored)**:
    *   **Architecture**: The project follows Clean Architecture principles, split into:
        *   `src/core`: Business logic (`DeviceManager`, `TunneldManager`, `RouteWalker`, `models`).
        *   `src/ui`: User Interface (`iFakeGPSApp` in `app.py`).
        *   `src/utils`: Utilities (`logger`, helper functions).
    *   `src/main.py`: The production entry point (handles multiprocessing, args).
    *   `scripts/run.py`: The developer entry point (runs from source).
    *   `scripts/run.bat`: Self-elevating launcher for running from source as admin.
    *   `scripts/pack.bat`: Local build script — builds from `iFakeGPS.spec`.
    *   `scripts/extract_release_notes.py`: Used by CI to slice the matching `CHANGELOG.md` section.

4.  **New Features & Optimizations**:
    *   **Geolocation**: Uses **Windows Geolocation API (`winsdk`)** for high-precision location detection. Fallbacks to hardcoded default (Taipei).
    *   **Map Performance**:
        *   Default provider: **Google Maps** (Normal).
        *   Caching: **SQLite database** stored in `%LOCALAPPDATA%\iFakeGPS` (Windows) or `~/.cache` (Linux/Mac) for persistence and speed.
        *   Optimization: Reduced `max_zoom` to 19 to prevent 404 stalls.
    *   **Async/Threading**: Extensive use of threading for non-blocking UI (device scanning, location fetching).

    *   Documentation is in `README.md` (Main English) and `docs/README_zh-TW.md`.
    *   Keep user-facing instructions simple.

5.  **Tunneld & Packaging Knowledge (Crucial)**:
    *   **Single source of truth**: `iFakeGPS.spec` is the ONLY build config. Both `scripts/pack.bat` and the GitHub Actions release workflow run `PyInstaller iFakeGPS.spec --clean`. Do NOT add build flags to `pack.bat`; edit the spec instead.
    *   **Tunneld Components**: `tunneld` internally uses `fastapi`, `uvicorn`, `starlette`, `python-multipart`. These are "hidden imports" for PyInstaller and MUST be explicitly collected (`hiddenimports` + `collect_all` in the spec).
    *   **Metadata**: `tunneld` checks versions of `readchar`, `inquirer3`, and `pymobiledevice3` using `importlib.metadata`. PyInstaller strips this by default. You MUST `copy_metadata` these packages in the spec.
    *   **Drivers (DLLs)**: `pytun_pmd3` (used by `tunneld` for VPN creation) relies on `wintun.dll`. You MUST `collect_all('pytun_pmd3')` to bundle this DLL.
    *   **Icon**: `app.ico` is referenced by the spec via `icon=['app.ico']` and bundled via `datas`.

6.  **Developer Mode Logic**:
    *   The app now includes native Developer Mode management via `DeviceManager` class.
    *   **Status Check**: Uses `AmfiService.developer_mode_status`.
    *   **Enable Flow**:
        1.  Triggers `pymobiledevice3 mounter auto-mount` (via `auto_mount_developer_disk_image` helper) - required to make the menu appear on some devices.
        2.  Triggers `AmfiService.enable_developer_mode` - sends the command to the phone.
        3.  Shows a localized guide UI to the user.

7.  **Release & Changelog Rules (CI Parsed)**:
    *   Keep release-format instructions in this `AGENTS.md` (not in `CHANGELOG.md`).
    *   `CHANGELOG.md` 內容一律使用繁體中文撰寫。
    *   For each release, add a section in `CHANGELOG.md` using this exact header style:
        *   `## [X.Y.Z] - YYYY-MM-DD`
    *   Recommended subsections:
        *   `### Added`
        *   `### Changed`
        *   `### Fixed`
    *   Tag mapping rule:
        *   Use `X.Y.Z` tags only (for example `1.4.0`), not `vX.Y.Z`.
        *   Tag must match changelog section `[X.Y.Z]` exactly.
    *   CI behavior (`.github/workflows/release.yml`):
        *   **Does NOT run on ordinary pushes** — Windows runners are billed. Only two things trigger it:
            *   Pushing a version tag (`X.Y.Z`) → builds the exe and publishes a GitHub Release, using the matched `CHANGELOG.md` section as the body (the extract step fails the job if no matching section exists).
            *   Clicking **Run workflow** (manual `workflow_dispatch`) → a **dev build**: builds the exe and uploads it as a workflow artifact (`iFakeGPS-dev-<sha>`, 14-day retention). No Release is created.
