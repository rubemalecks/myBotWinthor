"""Hospeda bot.py como serviço do Windows."""
import subprocess
import sys
import os
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil

BASE_DIR = Path(__file__).resolve().parent.parent
PYTHON = BASE_DIR / ".venv" / "Scripts" / "python.exe"
BOT_SCRIPT = BASE_DIR / "bot.py"
LOG_FILE = BASE_DIR / "bot-service.log"


class BotWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = "MyBotWinthorBot"
    _svc_display_name_ = "Bot WinThor"
    _svc_description_ = "API, painel administrativo e bot Telegram WinThor."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("Iniciando o bot WinThor.")
        python = PYTHON if PYTHON.is_file() else Path(sys.executable)
        ambiente = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1'}
        try:
            with LOG_FILE.open("a", encoding="utf-8") as log:
                self.process = subprocess.Popen(
                    [str(python), '-u', str(BOT_SCRIPT)],
                    cwd=BASE_DIR,
                    env=ambiente,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                while True:
                    resultado = win32event.WaitForSingleObject(self.stop_event, 1000)
                    if resultado == win32event.WAIT_OBJECT_0:
                        break
                    codigo = self.process.poll()
                    if codigo is not None:
                        servicemanager.LogErrorMsg(
                            f"bot.py terminou com código {codigo}."
                        )
                        return
                try:
                    self.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
        except OSError as erro:
            servicemanager.LogErrorMsg(f"Não foi possível iniciar bot.py: {erro}")
            raise


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(BotWindowsService)
