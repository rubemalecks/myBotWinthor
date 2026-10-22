@echo off
setlocal
chcp 65001 >nul
title myBotWinthor - Configuracao
pushd "%~dp0"
call "%~dp0myBotWinthor.bat" /nopause
if not exist ".venv\Scripts\python.exe" goto sem_ambiente
".venv\Scripts\python.exe" -m modulos.configurar
set "config_exit_code=%errorlevel%"
echo.
pause
popd
exit /b %config_exit_code%

:sem_ambiente
echo Ambiente virtual nao encontrado.
echo Na pasta do projeto, execute:
echo   python -m venv .venv
echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
popd
exit /b 1
