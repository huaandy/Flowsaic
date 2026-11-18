@echo off
rem Start the Flowsaic backend (Windows) and open http://127.0.0.1:8000/
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend\start.ps1" %*
echo.
pause
