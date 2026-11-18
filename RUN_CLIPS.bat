@echo off
REM ===== One-click autonomous clip run =====
REM Usage:  RUN_CLIPS.bat "VALORANT"   |   RUN_CLIPS.bat "Fortnite" clips=8 live=off   |   double-click
setlocal
cd /d "%~dp0"

where claude >nul 2>nul || (echo [!] Claude Code is not installed. Run SETUP.bat first. & pause & exit /b 1)
if not exist "models\whisper-base\.complete" (echo [!] Setup not finished. Run SETUP.bat first. & pause & exit /b 1)

set "GAME=%~1"
if "%GAME%"=="" set /p GAME=Which game? (e.g. VALORANT, Fortnite, CS2, GTA V, Minecraft):
if "%GAME%"=="" exit /b 1

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set STAMP=%%i
if not exist data\logs mkdir data\logs
set "LOG=data\logs\run_%STAMP%.log"

echo.
echo  ================================================
echo   Autonomous clip run for: %GAME%
echo   Live log : %LOG%
echo   Clips go : output\
echo   Keep this window open - it takes 30-180 min.
echo  ================================================
echo.

claude -p "/clip-run %GAME% %~2 %~3" --permission-mode acceptEdits --output-format text > "%LOG%" 2>&1
type "%LOG%"
echo.
echo  Done. Opening output folder...
start "" "%~dp0output"
pause
endlocal
