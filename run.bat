@echo off
:: iFakeGPS Launcher - Auto-elevates to administrator and runs the app

:: Check if already running as admin
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :run
) else (
    goto :elevate
)

:elevate
echo Requesting administrator privileges...
powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b

:run
cd /d "%~dp0"
echo Starting iFakeGPS...
echo.

:: Activate venv and run the app
:: call .venv\Scripts\activate.bat
uv run python run.py

pause
