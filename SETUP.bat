@echo off
cd /d "%~dp0"
title ChatHomeBase Bot - Setup

echo =======================================
echo ChatHomeBase Bot Setup
echo =======================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo Please install Python 3.9+ from python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

if exist "config\settings.json" (
    echo Account already configured.
    echo.
    choice /C YN /M "Do you want to update the existing configuration"
    if errorlevel 2 (
        echo.
        echo Nothing changed. Run LAUNCH.bat to start the bot.
        pause
        exit /b 0
    )
    echo.
)

echo Checking dependencies...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

if not exist ".installed" (
    echo Installing browser... (this may take a few minutes)
    python -m playwright install chromium
    if errorlevel 1 (
        echo ERROR: Failed to install browser
        pause
        exit /b 1
    )
    echo. > .installed
    echo.
    echo =======================================
    echo Installation complete!
    echo =======================================
    echo.
)

python bootstrap\first_run_wizard.py

echo.
pause