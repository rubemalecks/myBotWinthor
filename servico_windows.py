"""Consultas e solicitações do serviço Windows do bot."""
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SERVICE_NAME = "MyBotWinthorBot"
SERVICE_DISPLAY_NAME = "Bot WinThor"
SERVICE_DESCRIPTION = "API, painel administrativo e bot Telegram WinThor."
SERVICE_MODULE = BASE_DIR / "bot_service.py"


def obter_status_servico():
    if os.name != "nt":
        return {"available": False, "installed": False}

    import win32service
    import win32serviceutil

    try:
        status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)
    except win32service.error as erro:
        if erro.winerror == 1060:
            return {
                "available": True,
                "installed": False,
                "state": "not_installed",
                "automatic": False,
            }
        raise RuntimeError(
            f"Não foi possível consultar o serviço do Windows: {erro}"
        ) from erro

    try:
        manager = win32service.OpenSCManager(
            None, None, win32service.SC_MANAGER_CONNECT
        )
        try:
            handle = win32service.OpenService(
                manager, SERVICE_NAME, win32service.SERVICE_QUERY_CONFIG
            )
            try:
                configuracao = win32service.QueryServiceConfig(handle)
            finally:
                win32service.CloseServiceHandle(handle)
        finally:
            win32service.CloseServiceHandle(manager)
    except win32service.error as erro:
        raise RuntimeError(
            f"Não foi possível consultar a configuração do serviço: {erro}"
        ) from erro

    estados = {
        win32service.SERVICE_STOPPED: "stopped",
        win32service.SERVICE_START_PENDING: "starting",
        win32service.SERVICE_STOP_PENDING: "stopping",
        win32service.SERVICE_RUNNING: "running",
        win32service.SERVICE_CONTINUE_PENDING: "starting",
        win32service.SERVICE_PAUSE_PENDING: "stopping",
        win32service.SERVICE_PAUSED: "stopped",
    }
    return {
        "available": True,
        "installed": True,
        "state": estados.get(status[1], "unknown"),
        "automatic": configuracao[1] == win32service.SERVICE_AUTO_START,
    }


def solicitar_acao_servico(acao):
    if os.name != "nt":
        raise RuntimeError("O serviço automático está disponível somente no Windows.")
    if acao not in {"install", "disable", "remove"}:
        raise ValueError("Ação de serviço inválida.")

    import ctypes

    if ctypes.windll.shell32.IsUserAnAdmin():
        subprocess.Popen(
            [
                sys.executable,
                str(BASE_DIR / "service_helper.py"),
                acao,
                "--quiet",
            ],
            cwd=BASE_DIR,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return {
            "message": (
                "Solicitação administrativa enviada. Atualize o painel em alguns "
                "instantes para conferir o estado do serviço."
            )
        }

    argumentos = subprocess.list2cmdline(
        [str(BASE_DIR / "service_helper.py"), acao]
    )
    resultado = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        argumentos,
        str(BASE_DIR),
        1,
    )
    if resultado <= 32:
        raise RuntimeError(
            "Não foi possível abrir a confirmação administrativa do Windows."
        )
    return {
        "message": (
            "Confirme a solicitação administrativa na máquina que hospeda a API. "
            "Após a ativação, o serviço iniciará automaticamente no próximo boot."
        )
    }
