@echo off
setlocal
title Instalar Hackomon
if not exist "%~dp0tools\Instalar-Hackomon.ps1" (
    echo Extraia TODO o ZIP antes de abrir este arquivo.
    echo Use a opcao Extrair tudo do Windows.
    pause
    exit /b 2
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Instalar-Hackomon.ps1"
set "HACKOMON_RESULT=%ERRORLEVEL%"
echo.
if not "%HACKOMON_RESULT%"=="0" echo A instalacao precisa de atencao. Leia a mensagem acima.
pause
exit /b %HACKOMON_RESULT%
