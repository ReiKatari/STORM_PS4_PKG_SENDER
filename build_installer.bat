@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_installer.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo Error during build!
    exit /b %ERRORLEVEL%
)
