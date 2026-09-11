@echo off
cd /d "%~dp0"
title ChatHomeBase Bot Updater

:: CONFIGURE THESE URLS
set VERSION_URL=https://raw.githubusercontent.com/abcancode/Chathomebase-Bot/main/version.txt
set DOWNLOAD_URL=https://github.com/abcancode/Chathomebase-Bot/releases/download/v1.0.0/latest.zip

echo =======================================
echo ChatHomeBase Bot Updater
echo =======================================
echo.

:: Check for curl
where curl >nul 2>&1
if errorlevel 1 (
    echo ERROR: curl not found. Please update manually.
    pause
    exit /b 1
)

echo Checking for updates...

:: Download version
curl -s -L "%VERSION_URL%" > .latest_version 2>nul

if not exist .latest_version (
    echo ERROR: Could not check for updates.
    pause
    exit /b 1
)

set /p LATEST=<.latest_version
set /p CURRENT=<version.txt 2>nul
if not defined CURRENT set CURRENT=0.0.0

echo Current: %CURRENT%
echo Latest: %LATEST%

if "%CURRENT%"=="%LATEST%" (
    echo.
    echo =======================================
    echo You are up to date!
    echo =======================================
    del .latest_version
    pause
    exit /b 0
)

echo.
echo Update available: %CURRENT% -^> %LATEST%
echo.

:: Backup settings
if exist "config\settings.json" (
    copy "config\settings.json" "config\settings.json.backup" >nul
    echo [OK] Settings backed up
)

:: Download update
echo Downloading update...
curl -L -o update.zip "%DOWNLOAD_URL%" 2>nul

if not exist update.zip (
    echo ERROR: Download failed
    del .latest_version
    pause
    exit /b 1
)

:: Extract
echo Extracting...
powershell -Command "Expand-Archive -Path 'update.zip' -DestinationPath '.' -Force"

:: Restore settings
if exist "config\settings.json.backup" (
    copy "config\settings.json.backup" "config\settings.json" >nul
    del "config\settings.json.backup"
    echo [OK] Settings restored
)

:: Update version
copy .latest_version version.txt >nul

:: Cleanup
del update.zip
del .latest_version

echo.
echo =======================================
echo Update complete! Version %LATEST%
echo =======================================
pause