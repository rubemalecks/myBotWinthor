"""Entrada compatível para instalação e execução do serviço Windows."""
from modulos.bot_service import BotWindowsService


if __name__ == '__main__':
    import win32serviceutil
    win32serviceutil.HandleCommandLine(BotWindowsService)
