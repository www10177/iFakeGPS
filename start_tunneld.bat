@echo off
:: Start tunneld service - Auto-elevates to administrator

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
echo =============================================
echo        iFakeGPS - Tunneld Service
echo =============================================
echo.
echo Starting tunneld for iOS 17+ device connection...
echo Keep this window open while using iFakeGPS!
echo.

:: Activate venv and run tunneld
call .venv\Scripts\activate.bat
python -m pymobiledevice3 remote tunneld

pause
