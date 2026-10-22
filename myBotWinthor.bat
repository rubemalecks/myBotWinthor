@echo off
setlocal
chcp 65001 >nul
title myBotWinthor - RBTech Solucoes
rem Cores ANSI: Windows Terminal ou console moderno do Windows 10/11.
for /F %%e in ('echo prompt $E ^| cmd') do set "ESC=%%e"
set "BLUE=%ESC%[38;2;8;109;166m"
set "GRAY=%ESC%[38;2;190;196;204m"
set "RESET=%ESC%[0m"
cls
echo(
echo %BLUE%              ●
echo               █
echo         ▄███████████▄
echo       ▄██▀         ▀██▄
echo       ██    ▪   ▪    ██     %GRAY%my%BLUE%Bot%GRAY%Winthor%BLUE%
echo     ▐███▄           ▄███▌
echo     ▐███ ▀█████████▀ ███▌   %GRAY%RBTech Soluções%BLUE%
echo       ██▄  ▀██▄  ▄█████
echo       ████▄  ▀████▀  ██
echo       ██ ▀██▄  ▀██▄▄███
echo       ██   ▀██▄  ▀████▀
echo %RESET%
echo %GRAY%    ───────────────────────────────────────────────%RESET%
echo(
rem Para usar em outro BAT: call myBotWinthor.bat /nopause
if /I "%~1"=="/nopause" goto :end
echo %GRAY%    Pressione qualquer tecla para sair...%RESET%
pause >nul
:end
endlocal
exit /b 0
