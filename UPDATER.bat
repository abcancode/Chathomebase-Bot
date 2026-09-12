@echo off
cd /d "%~dp0"
title ChatHomeBase Bot Updater

:: Prevent immediate close on error
setlocal enabledelayedexpansion

echo =======================================
echo ChatHomeBase Bot Updater
echo =======================================
echo.

:: Your GitHub URLs - UPDATE THESE
set VERSION_URL=https://raw.githubusercontent.com/abcancode/Chathomebase-Bot/main/version.txt
set DOWNLOAD_URL=https://github.com/abcancode/Chathomebase-Bot/releases/download/v1.0.0/latest.zip

echo Checking for updates...
echo From: %VERSION_URL%
echo.

:: Check if version.txt exists locally
if not exist "version.txt" (
    echo Creating version.txt...
    echo 0.0.0 > version.txt
)

:: Download latest version
echo Downloading version info...
curl -s -L "%VERSION_URL%" > .latest_version 2>&1

if not exist ".latest_version" (
    echo [ERROR] Failed to download version info
    echo Check your internet connection
    pause
    exit /b 1
)

:: Read versions
set /p LATEST=<.latest_version
set /p CURRENT=<version.txt

echo Current version: %CURRENT%
echo Latest version: %LATEST%
echo.

:: Compare
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

:: Backup settings
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

:: Download update
echo [2/4] Downloading update...
curl -L -o update.zip "%DOWNLOAD_URL%" 2>&1

if not exist update.zip (
    echo [ERROR] Download failed
    del .latest_version 2>nul
    pause
    exit /b 1
)
echo     OK

:: Extract
echo [3/4] Extracting update...
powershell -Command "Expand-Archive -Path 'update.zip' -DestinationPath '.' -Force"
if errorlevel 1 (
    echo [ERROR] Extraction failed
    del update.zip 2>nul
    del .latest_version 2>nul
    pause
    exit /b 1
)
echo     OK

:: Restore settings
if exist "config\settings.json.backup" (
    echo [4/4] Restoring settings...
    copy "config\settings.json.backup" "config\settings.json" >nul
    del "config\settings.json.backup" 2>nul
    echo     OK
)

:: Update version
copy .latest_version version.txt >nul

:: Cleanup
del update.zip 2>nul
del .latest_version 2>nul

echo.
echo =======================================
echo Update complete! Version %LATEST%
echo =======================================
echo You can now run LAUNCH.bat
echo.
pause