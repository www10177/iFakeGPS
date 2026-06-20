@echo off
:: iFakeGPS Packer - Creates a Windows EXE that requires admin privileges
:: This script uses PyInstaller to bundle the application

setlocal EnableDelayedExpansion

echo =============================================
echo        iFakeGPS - Windows EXE Packer
echo =============================================
echo.

:: Check if uv is installed
uv --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] uv is not installed. Please install uv first.
    echo Visit https://github.com/astral-sh/uv for installation instructions.
    pause
    exit /b 1
)

:: Sync dependencies to ensure pyinstaller is available
echo [INFO] Syncing dependencies...
uv sync
if %errorLevel% neq 0 (
    echo [ERROR] Failed to sync dependencies.
    pause
    exit /b 1
)

:: Change to the project root (this script lives in scripts/); the spec and
:: its relative data paths (docs, app.ico, CHANGELOG.md) resolve from here.
cd /d "%~dp0.."


echo [INFO] Creating Windows executable...
echo.

:: Build from the committed spec file (iFakeGPS.spec) so that local builds
:: and the GitHub Actions release workflow share a single source of truth.
:: All build options (onefile, windowed, uac-admin, icon, hidden-imports,
:: collect-all, copy-metadata, bundled data) live in iFakeGPS.spec.
echo [INFO] Building from iFakeGPS.spec ...

uv run python -m PyInstaller iFakeGPS.spec --clean --noconfirm

if %errorLevel% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo =============================================
echo        Build Complete!
echo =============================================
echo.
echo The executable has been created at:
echo   dist\iFakeGPS.exe
echo.
echo This executable will automatically request
echo administrator privileges when launched.
echo.
echo You can distribute the "dist" folder or just
echo the iFakeGPS.exe file.
echo =============================================

pause
