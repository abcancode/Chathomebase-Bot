@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

title ChatHomeBase Bot Updater

echo =======================================
echo ChatHomeBase Bot Updater
echo =======================================
echo.

:: 1. Check if curl is installed
where curl >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 'curl' is not installed on this system.
    echo Please install curl or update your PATH environment variable.
    echo.
    pause
    exit /b 1
)
echo [OK] curl found.

:: 2. Check if PowerShell is installed
where powershell >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 'powershell' is not installed on this system.
    echo Please install Windows PowerShell.
    echo.
    pause
    exit /b 1
)
echo [OK] PowerShell found.

:: 3. Check if Python is installed (Required for the bot)
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Python is not installed. The bot will not run.
    echo Please install Python from python.org
    echo.
) else (
    echo [OK] Python found.
)

:: ==========================================
:: SETTINGS
:: ==========================================
:: Replace with your actual GitHub repository URLs
set VERSION_URL=https://raw.githubusercontent.com/abcancode/Chathomebase-Bot/main/version.txt
set DOWNLOAD_URL=https://github.com/abcancode/Chathomebase-Bot/releases/download/v1.1.14/latest.zip
:: ==========================================

echo.
echo Target URL: %VERSION_URL%
echo.

if not exist "version.txt" (
    echo Creating local version.txt...
    echo 0.0.0 > version.txt
)

echo Downloading version info...
curl -s -L "%VERSION_URL%" > .latest_version 2>&1

if not exist ".latest_version" (
    echo [ERROR] Failed to download version info. Check internet/connection.
    echo The file does not exist on GitHub.
    echo.
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
    echo.
    pause
    exit /b 0
)

echo =======================================
echo Update available: %CURRENT% -^> %LATEST%
echo =======================================
echo.

:: 1. Backup Settings
if exist "config\settings.json" (
    echo [1/5] Backing up settings...
    copy "config\settings.json" "config\settings.json.backup" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to backup settings to config\settings.json.backup
        pause
        exit /b 1
    )
    echo     OK
) else (
    echo [1/5] No settings to backup
)

:: 2. Download Update
echo [2/5] Downloading update package...
curl -L -o update.zip "%DOWNLOAD_URL%" 2>&1

if not exist update.zip (
    echo [ERROR] Download failed. Check URL and internet connection.
    echo The file download might have been interrupted.
    del .latest_version 2>nul
    pause
    exit /b 1
)
echo     OK

:: 3. Extract Update
echo [3/5] Extracting update package...
powershell -Command "Expand-Archive -Path 'update.zip' -DestinationPath '.' -Force"
if errorlevel 1 (
    echo [ERROR] Extraction failed. The zip file might be corrupted or missing.
    echo Please check the 'update.zip' file size.
    del update.zip 2>nul
    del .latest_version 2>nul
    pause
    exit /b 1
)
echo     OK

:: 4. Restore Settings
if exist "config\settings.json.backup" (
    echo [4/5] Restoring settings...
    copy "config\settings.json.backup" "config\settings.json" >nul 2>&1
    del "config\settings.json.backup" 2>nul
    echo     OK
)

:: 5. Update Version File
copy .latest_version version.txt >nul 2>&1
del update.zip 2>nul
del .latest_version 2>nul

echo.
echo =======================================
echo Update complete! Version %LATEST%
echo =======================================
echo You can now run LAUNCH.bat
echo.
echo Press any key to close this window...
pause >nul