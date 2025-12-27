# iFakeGPS Development Guide

This project uses `uv` for dependency management and execution.

## Key Instructions for Agents

1.  **Usage of `uv`**:
    *   ALWAYS use `uv` for managing dependencies and running the application or scripts.
    *   Do NOT use `pip` directly unless absolutely necessary (and justified).
    *   To run the app: `uv run ifakegps.py` or `uv run ifakegps` (if installed as script).
    *   To add packages: `uv add <package_name>`
    *   To add dev packages: `uv add --dev <package_name>`
    *   To run build scripts: `uv run pack.bat` (essentially just runs the bat which calls `uv run pyinstaller`)

2.  **Platform specifics**:
    *   **Windows**: The project is primarily targeted for Windows (handling admin privileges, `pythonw` for GUI, etc.).
    *   **iOS 17+ Support**: The app uses `pymobiledevice3`'s RSD tunnel which requires `tunneld` to handle device communication.
        *   The app tries to start `tunneld` automatically if not running.
        *   This requires Administrator privileges on Windows.
        *   **Frozen App (EXE)**: When running as a PyInstaller frozen exe, the app spawns a subprocess with `--internal-tunneld` to avoid infinite recursion. BE CAREFUL when modifying the `if __name__ == "__main__":` block or `TunneldManager.start`.

3.  **Code Structure**:
    *   `ifakegps.py`: The main entry point and single-file application logic.
    *   `pack.bat`: The build script to generate a standalone Windows executable.
    *   `pyproject.toml`: Project configuration and dependencies.

4.  **Documentation**:
    *   Documentation is in `README.md` (Main English) and `docs/README_zh-TW.md`.
    *   Keep user-facing instructions simple.
