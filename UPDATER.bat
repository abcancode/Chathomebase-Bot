@echo off
cd /d "%~dp0"
title ChatHomeBase Bot Updater

setlocal enabledelayedexpansion

echo =======================================
echo ChatHomeBase Bot Updater
echo =======================================
echo.

:: Check if curl is installed
where curl >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 'curl' is not installed on this system.
    echo Please install curl or update your PATH environment variable.
    pause
    exit /b 1
)

:: ==========================================
:: IMPORTANT: UPDATE THESE TO YOUR REPO URL
:: Replace with the actual GitHub repository URLs
:: ==========================================
:: Example: https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/version.txt
set VERSION_URL=https://raw.githubusercontent.com/abcancode/Chathomebase-Bot/main/version.txt

:: Example: https://github.com/YOUR_USERNAME/YOUR_REPO/releases/download/v1.0.0/latest.zip
set DOWNLOAD_URL=https://github.com/abcancode/Chathomebase-Bot/releases/download/v1.1.7/latest.zip
:: ==========================================

echo Checking for updates...
echo From: %VERSION_URL%
echo.

if not exist "version.txt" (
    echo Creating version.txt...
    echo 0.0.0 > version.txt
)

echo Downloading version info...
curl -s -L "%VERSION_URL%" > .latest_version 2>&1

if not exist ".latest_version" (
    echo [ERROR] Failed to download version info. Check internet/connection.
    pause
    exit /b 1
)

set /p LATEST=<.latest_version
set /p CURRENT=<version.txt

:: Handle Empty/404 download
if "%LATEST%"=="" (
    echo [ERROR] Version file returned empty or 404.
    echo The file does not exist on GitHub.
    echo Please ensure 'version.txt' exists in your repo at 'main/version.txt'.
    del .latest_version 2>nul
    pause
    exit /b 1
)

echo Current version: %CURRENT%
echo Latest version: %LATEST%
echo.

if "%CURRENT%"=="%LATEST%" (
    echo =======================================
    echo You are up to date!
    echo =======================================
    del .latest_version
    pause
    exit /b 0
)

echo =======================================
echo Update available: %CURRENT% -^> %LATEST%
echo =======================================
echo.

if exist "config\settings.json" (
    echo [1/4] Backing up settings...
    copy "config\settings.json" "config\settings.json.backup" >nul
    if errorlevel 1 (
        echo [ERROR] Failed to backup settings
        pause
        exit /b 1
    )
    echo     OK
) else (
    echo [1/4] No settings to backup
)

echo [2/4] Downloading update...
curl -L -o update.zip "%DOWNLOAD_URL%" 2>&1

if not exist update.zip (
    echo [ERROR] Download failed. Check URL and internet.
    del .latest_version 2>nul
    pause
    exit /b 1
)
echo     OK

echo [3/4] Extracting update...
powershell -Command "Expand-Archive -Path 'update.zip' -DestinationPath '.' -Force"
if errorlevel 1 (
    echo [ERROR] Extraction failed. The zip file might be corrupted or missing.
    del update.zip 2>nul
    del .latest_version 2>nul
    pause
    exit /b 1
)
echo     OK

if exist "config\settings.json.backup" (
    echo [4/4] Restoring settings...
    copy "config\settings.json.backup" "config\settings.json" >nul
    del "config\settings.json.backup" 2>nul
    echo     OK
)

copy .latest_version version.txt >nul
del update.zip 2>nul
del .latest_version 2>nul

echo.
echo =======================================
echo Update complete! Version %LATEST%
echo =======================================
echo You can now run LAUNCH.bat
echo.
pause