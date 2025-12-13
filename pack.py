#!/usr/bin/env python3
"""
iFakeGPS Packer Script
Creates a Windows executable with administrator privileges.

Usage:
    python pack.py

This script uses PyInstaller to create a standalone Windows executable
that automatically requests administrator privileges when launched.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def check_pyinstaller():
    """Check if PyInstaller is installed, install if not."""
    try:
        import PyInstaller

        print(f"[INFO] PyInstaller version: {PyInstaller.__version__}")
        return True
    except ImportError:
        print("[INFO] PyInstaller not found. Installing...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"[ERROR] Failed to install PyInstaller: {result.stderr}")
            return False
        print("[INFO] PyInstaller installed successfully.")
        return True


def clean_build():
    """Clean previous build artifacts."""
    dirs_to_clean = ["build", "dist", "__pycache__"]
    files_to_clean = ["iFakeGPS.spec"]

    for dir_name in dirs_to_clean:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"[INFO] Cleaning {dir_name}/...")
            shutil.rmtree(dir_path)

    for file_name in files_to_clean:
        file_path = Path(file_name)
        if file_path.exists():
            print(f"[INFO] Removing {file_name}...")
            file_path.unlink()


def create_exe():
    """Create the Windows executable with admin privileges."""
    print("\n" + "=" * 50)
    print("       iFakeGPS - Windows EXE Packer")
    print("=" * 50 + "\n")

    # Check and install PyInstaller
    if not check_pyinstaller():
        return False

    # Get the script directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)

    # Clean previous builds
    clean_build()

    print("[INFO] Building Windows executable...")
    print("[INFO] This may take a few minutes...\n")

    # PyInstaller command arguments
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",  # Single executable
        "--windowed",  # GUI app, no console
        "--uac-admin",  # Request admin privileges
        "--name",
        "iFakeGPS",  # Executable name
        # Hidden imports for proper bundling
        "--hidden-import=PIL",
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=tkintermapview",
        "--hidden-import=customtkinter",
        "--hidden-import=pymobiledevice3",
        "--hidden-import=pymobiledevice3.services.dvt.dvt_secure_socket_proxy",
        "--hidden-import=pymobiledevice3.services.dvt.instruments.location_simulation",
        "--hidden-import=pymobiledevice3.remote.remote_service_discovery",
        "--hidden-import=pymobiledevice3.lockdown",
        "--hidden-import=pymobiledevice3.usbmux",
        "--hidden-import=gpxpy",
        "--hidden-import=requests",
        "--hidden-import=zeroconf",
        "--hidden-import=ctypes",
        "--hidden-import=asyncio",
        # Collect all data files for UI frameworks
        "--collect-all",
        "customtkinter",
        "--collect-all",
        "tkintermapview",
        # Main script
        "ifakegps.py",
    ]

    # Add docs directory if it exists
    docs_dir = script_dir / "docs"
    if docs_dir.exists():
        cmd.insert(-1, "--add-data")
        cmd.insert(-1, f"docs{os.pathsep}docs")

    # Run PyInstaller
    result = subprocess.run(cmd, cwd=script_dir)

    if result.returncode != 0:
        print("\n[ERROR] Build failed!")
        return False

    # Verify the output
    exe_path = script_dir / "dist" / "iFakeGPS.exe"
    if exe_path.exists():
        exe_size_mb = exe_path.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 50)
        print("           Build Complete!")
        print("=" * 50)
        print("\n[SUCCESS] Executable created at:")
        print(f"          {exe_path}")
        print(f"          Size: {exe_size_mb:.1f} MB")
        print("\n[INFO] This executable will automatically request")
        print("       administrator privileges when launched.")
        print("\n[INFO] You can distribute the 'dist' folder or")
        print("       just the iFakeGPS.exe file.")
        print("=" * 50 + "\n")
        return True
    else:
        print("\n[ERROR] Executable not found after build!")
        return False


def main():
    """Main entry point."""
    try:
        success = create_exe()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[INFO] Build cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
