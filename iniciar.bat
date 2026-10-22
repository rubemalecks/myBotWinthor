@echo off
setlocal
chcp 65001 >nul
title myBotWinthor - Iniciar API
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" goto sem_ambiente
rem Executa em terminal próprio, sem um BAT aguardando Ctrl+C.
start "myBotWinthor - API" /d "%~dp0" "%~dp0.venv\Scripts\python.exe" -m modulos.iniciar --manter-aberto
set "iniciar_exit_code=%errorlevel%"
popd
exit /b %iniciar_exit_code%

:sem_ambiente
echo Ambiente virtual nao encontrado.
echo Na pasta do projeto, execute:
echo   python -m venv .venv
echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
popd
exit /b 1
