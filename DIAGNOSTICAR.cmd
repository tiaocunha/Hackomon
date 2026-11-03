@echo off
setlocal
title Diagnosticar Hackomon
if not exist "%~dp0tools\Diagnosticar-Hackomon.ps1" (
    echo Extraia TODO o ZIP antes de abrir este arquivo.
    pause
    exit /b 2
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Diagnosticar-Hackomon.ps1"
set "HACKOMON_RESULT=%ERRORLEVEL%"
pause
exit /b %HACKOMON_RESULT%
