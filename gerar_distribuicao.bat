@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado. Configure as dependencias primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m desktop.build_windows
if errorlevel 1 (
  echo Falha ao gerar distribuicao. Confira os erros acima.
  pause
  exit /b 1
)
echo Distribuicao gerada em %CD%\distribuicao
pause
