@echo off
rem Start Flowsaic (Windows): backend + React front end, opens http://localhost:8443/
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend\start.ps1" %*
echo.
pause
