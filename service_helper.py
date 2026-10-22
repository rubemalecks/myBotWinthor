"""Executa operações fixas de instalação do serviço Windows com UAC."""
import ctypes
import sys
import time
import traceback

import win32service
import win32serviceutil

from servico_windows import (
    BASE_DIR,
    SERVICE_DESCRIPTION,
    SERVICE_DISPLAY_NAME,
    SERVICE_NAME,
)

PYTHON_ENV = BASE_DIR / ".venv"
SITE_PACKAGES = PYTHON_ENV / "Lib" / "site-packages"
SERVICE_PTH = SITE_PACKAGES / "mybotwinthor_service.pth"


def _abrir_servico():
    manager = win32service.OpenSCManager(
        None, None, win32service.SC_MANAGER_ALL_ACCESS
    )
    try:
        handle = win32service.OpenService(
            manager,
            SERVICE_NAME,
            win32service.SERVICE_QUERY_STATUS
            | win32service.SERVICE_STOP
            | win32service.SERVICE_CHANGE_CONFIG
            | win32service.DELETE,
        )
    except win32service.error:
        win32service.CloseServiceHandle(manager)
        raise
    return manager, handle


def _parar_se_necessario(handle):
    status = win32service.QueryServiceStatus(handle)
    if status[1] == win32service.SERVICE_STOPPED:
        return
    win32service.ControlService(handle, win32service.SERVICE_CONTROL_STOP)
    for _ in range(30):
        if win32service.QueryServiceStatus(handle)[1] == win32service.SERVICE_STOPPED:
            return
        time.sleep(1)
    raise RuntimeError("O serviço não parou dentro do tempo permitido.")


def executar(acao):
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError("A confirmação administrativa do Windows é necessária.")

    if acao == "install":
        if not SITE_PACKAGES.is_dir():
            raise RuntimeError(
                "Não encontrei .venv\\Lib\\site-packages. Instale as dependências "
                "do projeto antes de ativar o serviço."
            )
        SERVICE_PTH.write_text(str(BASE_DIR) + "\n", encoding="utf-8")
        try:
            win32serviceutil.QueryServiceStatus(SERVICE_NAME)
        except win32service.error as erro:
            if erro.winerror != 1060:
                SERVICE_PTH.unlink(missing_ok=True)
                raise
            try:
                win32serviceutil.InstallService(
                    "bot_service.BotWindowsService",
                    SERVICE_NAME,
                    SERVICE_DISPLAY_NAME,
                    startType=win32service.SERVICE_AUTO_START,
                    exeName=win32serviceutil.LocatePythonServiceExe(),
                    description=SERVICE_DESCRIPTION,
                )
            except Exception:
                SERVICE_PTH.unlink(missing_ok=True)
                raise
        else:
            win32serviceutil.ChangeServiceConfig(
                "bot_service.BotWindowsService",
                SERVICE_NAME,
                startType=win32service.SERVICE_AUTO_START,
                exeName=win32serviceutil.LocatePythonServiceExe(),
                description=SERVICE_DESCRIPTION,
            )
        return "Serviço instalado para iniciar automaticamente no próximo boot."

    try:
        manager, handle = _abrir_servico()
    except win32service.error as erro:
        if erro.winerror == 1060 and acao in {"disable", "remove"}:
            return "O serviço já não está instalado."
        raise
    try:
        _parar_se_necessario(handle)
        if acao == "disable":
            win32service.ChangeServiceConfig(
                handle,
                win32service.SERVICE_NO_CHANGE,
                win32service.SERVICE_DISABLED,
                win32service.SERVICE_NO_CHANGE,
                None,
                None,
                0,
                None,
                None,
                None,
                None,
            )
            return "Serviço parado e desativado na inicialização do Windows."
        if acao == "remove":
            win32service.DeleteService(handle)
            SERVICE_PTH.unlink(missing_ok=True)
            return "Serviço removido do Windows."
    finally:
        win32service.CloseServiceHandle(handle)
        win32service.CloseServiceHandle(manager)
    raise ValueError("Ação de serviço inválida.")


def main():
    argumentos = sys.argv[1:]
    quiet = argumentos[-1:] == ["--quiet"]
    if quiet:
        argumentos.pop()
    if len(argumentos) != 1 or argumentos[0] not in {"install", "disable", "remove"}:
        raise SystemExit("Ação inválida.")
    try:
        mensagem = executar(argumentos[0])
    except Exception as erro:
        if quiet:
            with (BASE_DIR / "service-management.log").open(
                "a", encoding="utf-8"
            ) as arquivo:
                arquivo.write(f"{erro}\n{traceback.format_exc()}\n")
            raise SystemExit(1) from erro
        ctypes.windll.user32.MessageBoxW(
            None, str(erro), SERVICE_DISPLAY_NAME, 0x10
        )
        raise
    if not quiet:
        ctypes.windll.user32.MessageBoxW(
            None, mensagem, SERVICE_DISPLAY_NAME, 0x40
        )


if __name__ == "__main__":
    main()
