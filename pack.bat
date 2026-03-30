@echo off
REM Offline pack: thin launcher only. All logic is in pack.ps1.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0pack.ps1" %*
exit /b %ERRORLEVEL%
