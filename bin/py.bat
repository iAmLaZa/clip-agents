@echo off
REM Portable python launcher (cmd / PowerShell)
set "D=%~dp0.."
if exist "%D%\.venv\Scripts\python.exe" ( "%D%\.venv\Scripts\python.exe" %* & exit /b %errorlevel% )
if exist "%D%\..\.venv\Scripts\python.exe" ( "%D%\..\.venv\Scripts\python.exe" %* & exit /b %errorlevel% )
python %*
