@echo off
cd /d "%~dp0"
title ChatHomeBase Bot - INSPECT
echo Inspection mode: small window, Playwright Inspector, nothing is sent.
echo.
call LAUNCH.bat --inspect --dry-run