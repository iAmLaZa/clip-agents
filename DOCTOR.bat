@echo off
REM ===== Check that everything is installed =====
cd /d "%~dp0"
call bin\py.bat tools\doctor.py
echo.
pause
