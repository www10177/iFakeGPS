@echo off
:: iFakeGPS Packer - Creates a Windows EXE that requires admin privileges
:: This script uses PyInstaller to bundle the application

setlocal EnableDelayedExpansion

echo =============================================
echo        iFakeGPS - Windows EXE Packer
echo =============================================
echo.

:: Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if %errorLevel% neq 0 (
    echo [INFO] PyInstaller not found. Installing...
    pip install pyinstaller
    if %errorLevel% neq 0 (
        echo [ERROR] Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

:: Change to script directory
cd /d "%~dp0"

:: Activate virtual environment if exists
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call .venv\Scripts\activate.bat
)

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

pyinstaller ^
    --onefile ^
    --windowed ^
    --uac-admin ^
    --name "iFakeGPS" ^
    --add-data "docs;docs" ^
    --hidden-import=PIL ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=tkintermapview ^
    --hidden-import=customtkinter ^
    --hidden-import=pymobiledevice3 ^
    --hidden-import=gpxpy ^
    --hidden-import=requests ^
    --hidden-import=zeroconf ^
    --collect-all customtkinter ^
    --collect-all tkintermapview ^
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
