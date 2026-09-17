@echo off
REM Double-click to install Claude Token Indicator (per-user, no admin).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install.ps1"
echo.
pause
