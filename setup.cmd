@echo off
rem Flowsaic backend setup (Windows). Double-click this file. Safe to run again.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend\setup.ps1" %*
echo.
pause
