@echo off
cd /d "%~dp0"
title ChatHomeBase Bot - Setup

echo =======================================
echo ChatHomeBase Bot Setup
echo =======================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo Please install Python 3.9+ from python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Check if already configured
if exist "config\settings.json" (
    echo.
    echo =======================================
    echo Account already configured!
    echo =======================================
    echo.
    echo To reconfigure, delete config\settings.json
    echo To start the bot, run LAUNCH.bat
    echo.
    pause
    exit /b 0
)

:: Install dependencies (only first time)
if not exist ".installed" (
    echo Installing dependencies... (this may take a few minutes)
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
    
    echo Installing browser...
    playwright install chromium
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

:: Run setup wizard
python -c "from bootstrap.first_run_wizard import run_wizard; from pathlib import Path; run_wizard(Path('config/settings.json'))"

echo.
pause