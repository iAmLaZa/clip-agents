@echo off
REM ===== One-time setup on a new PC (double-click) =====
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
echo.
pause
