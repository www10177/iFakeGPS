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

:: Change to script directory
cd /d "%~dp0"

:: No need to manually activate venv when using uv run
:: But we can ensure we are in the right directory


echo [INFO] Creating Windows executable...
echo.

:: Create the spec file content for admin privileges
echo [INFO] Generating PyInstaller spec file with UAC admin manifest...

:: Run PyInstaller with options
:: --onefile: Create a single executable
:: --windowed: Don't show console window (GUI app)
:: --uac-admin: Request admin privileges on Windows
:: --icon: Use a custom icon if available
:: --name: Name of the output executable

uv run python -m PyInstaller ^
    --onefile ^
    --uac-admin ^
    --name "iFakeGPS" ^
    --icon "app.ico" ^
    --add-data "docs;docs" ^
    --add-data "app.ico;." ^
    --hidden-import=PIL ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=tkintermapview ^
    --hidden-import=customtkinter ^
    --hidden-import=python_multipart ^
    --hidden-import=pymobiledevice3 ^
    --hidden-import=gpxpy ^
    --hidden-import=requests ^
    --hidden-import=zeroconf ^
    --hidden-import=uvicorn ^
    --hidden-import=fastapi ^
    --hidden-import=starlette ^
    --hidden-import=click ^
    --hidden-import=h11 ^
    --hidden-import=websockets ^
    --collect-all uvicorn ^
    --collect-all fastapi ^
    --collect-all starlette ^
    --collect-all pydantic ^
    --collect-all pymobiledevice3 ^
    --collect-all pytun_pmd3 ^
    --collect-all customtkinter ^
    --collect-all tkintermapview ^
    --copy-metadata readchar ^
    --copy-metadata inquirer3 ^
    --copy-metadata pymobiledevice3 ^
    ifakegps.py

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
