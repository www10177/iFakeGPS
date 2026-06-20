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
:: cd to the project root (this script lives in scripts/)
cd /d "%~dp0.."
echo Starting iFakeGPS...
echo.

:: uv run resolves the project from the root and puts deps on the path
uv run python scripts/run.py

pause
