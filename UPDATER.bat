@echo off
cd /d "%~dp0"
title ChatHomeBase Bot Updater

:: Prevent immediate close on error
setlocal enabledelayedexpansion

echo =======================================
echo ChatHomeBase Bot Updater
echo =======================================
echo.

:: Check if curl is installed (Required for the script)
where curl >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 'curl' is not installed on this system.
    echo Please install curl or update your PATH environment variable.
    echo.
    echo Alternatively, you can use PowerShell to check for updates.
    pause
    exit /b 1
)

:: ==========================================
:: IMPORTANT: UPDATE THESE TO YOUR REPO URL
:: Replace with the actual GitHub repository URL where you host the bot
:: ==========================================
set VERSION_URL=https://raw.githubusercontent.com/https://github.com/abcancode/Chathomebase-Bot/blob/main/version.txt
set DOWNLOAD_URL=https://github.com/abcancode/Chathomebase-Bot/releases/download/v1.0.0/latest.zip
:: ==========================================

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

:: Check if download was successful (not empty and not 404)
if not exist ".latest_version" (
    echo [ERROR] Failed to download version info. Check internet/connection.
    pause
    exit /b 1
)

:: Read versions
set /p LATEST=<.latest_version
set /p CURRENT=<version.txt

:: Handle 404 or Empty download
if "%LATEST%"=="" (
    echo [WARNING] Version file returned empty or 404.
    echo The GitHub repository might be private, empty, or the URL is wrong.
    echo Skipping update check. Proceeding with local version.
    echo.
    goto :SKIP_UPDATE
)

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
    echo [ERROR] Download failed. Check URL and internet.
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

:SKIP_UPDATE
del .latest_version 2>nul
pause