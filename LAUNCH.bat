@echo off
cd /d "%~dp0"
title ChatHomeBase Bot

:: Check if configured
if not exist "config\settings.json" (
    echo =======================================
    echo Account not configured!
    echo =======================================
    echo.
    echo Please run SETUP.bat first to enter your credentials.
    echo.
    pause
    exit /b 1
)

echo =======================================
echo Starting ChatHomeBase Bot...
echo =======================================
echo.

python launch_bot.py

echo.
echo Bot stopped.
echo.
pause