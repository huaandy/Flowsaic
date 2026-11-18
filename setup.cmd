@echo off
rem Flowsaic setup (Windows): backend, database and React front end. Double-click this file. Safe to run again.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend\setup.ps1" %*
echo.
pause
