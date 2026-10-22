@echo off
setlocal
chcp 65001 >nul
title myBotWinthor - RBTech Solucoes
if not exist "%~dp0.venv\Scripts\python.exe" goto sem_python
"%~dp0.venv\Scripts\python.exe" "%~dp0modulos\banner.py"
goto fim_banner

:sem_python
echo.
echo     myBotWinthor - RBTech Solucoes
echo.

:fim_banner
if /I "%~1"=="/nopause" goto fim
echo     Pressione qualquer tecla para sair...
pause >nul
:fim
endlocal
exit /b 0
