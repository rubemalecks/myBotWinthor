"""Integração por usuário com Windows, sem comandos de shell fornecidos pelo usuário."""
import json, os, subprocess, sys, ctypes, time
from pathlib import Path
from desktop.common import identificador
PRODUCT='myBotWinthor.desktop.v1'
RUN=r'Software\Microsoft\Windows\CurrentVersion\Run'
UNINSTALL=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\myBotWinthor'

def kernel():
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    for nome in ('OpenMutexW','OpenEventW'):
        f=getattr(k,nome);f.restype=ctypes.c_void_p;f.argtypes=[ctypes.c_ulong,ctypes.c_bool,ctypes.c_wchar_p]
    k.CloseHandle.argtypes=[ctypes.c_void_p];k.SetEvent.argtypes=[ctypes.c_void_p]
    return k

def ativo(dados,gerenciador=False):
    k=kernel();h=k.OpenMutexW(0x100000,False,identificador(dados)+('-gui' if gerenciador else ''))
    if h:k.CloseHandle(h)
    return bool(h)

def sinalizar(dados,sufixo='-stop'):
    k=kernel();h=k.OpenEventW(2,False,identificador(dados)+sufixo)
    if h:k.SetEvent(h);k.CloseHandle(h)
    return bool(h)

def chave_inicio(exe):
    import hashlib
    return 'myBotWinthor-'+hashlib.sha256(str(Path(exe).resolve().parent.parent.parent).casefold().encode()).hexdigest()[:12]

def inicializacao(exe,habilitar):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,RUN) as chave:
        nome=chave_inicio(exe)
        if habilitar:
            winreg.SetValueEx(chave,nome,0,winreg.REG_SZ,subprocess.list2cmdline([str(Path(exe).resolve()),'--autostart']))
        else:
            try:winreg.DeleteValue(chave,nome)
            except FileNotFoundError:pass
    # Persiste a escolha para a interface e para a próxima atualização do instalador.
    for arquivo in (Path(exe).parent/'desktop.json',Path(exe).parent.parent.parent/'instalacao.json'):
        if arquivo.is_file():
            info=json.loads(arquivo.read_text(encoding='utf-8'));info['autostart']=bool(habilitar)
            temporario=arquivo.with_suffix('.tmp');temporario.write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8');temporario.replace(arquivo)

def registrar(programa,exe,dados,autostart):
    import winreg,win32security,win32api,win32con
    programa=Path(programa).resolve()
    token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32con.TOKEN_QUERY)
    try:
        sid=win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token,win32security.TokenUser)[0])
    finally:token.Close()
    inicializacao(exe,autostart)
    desinstalador=programa/'Desinstalar-myBotWinthor.exe'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,UNINSTALL) as chave:
        for nome,valor in {'DisplayName':'myBotWinthor','Publisher':'RBTech Soluções','InstallLocation':str(programa),'DisplayIcon':str(exe),'UninstallString':subprocess.list2cmdline([str(desinstalador)]),'QuietUninstallString':'','DisplayVersion':'Desktop'}.items():
            winreg.SetValueEx(chave,nome,0,winreg.REG_SZ,valor)
        for nome in ('NoModify','NoRepair'):winreg.SetValueEx(chave,nome,0,winreg.REG_DWORD,1)
    return sid

def servico_existe():
    import win32service
    m=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
    try:
        try:h=win32service.OpenService(m,'MyBotWinthorBot',win32service.SERVICE_QUERY_STATUS)
        except win32service.error as e:
            if e.winerror==1060:return False
            raise
        win32service.CloseServiceHandle(h);return True
    finally:win32service.CloseServiceHandle(m)

def remover_servico():
    import win32service
    m=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
    try:
        try:h=win32service.OpenService(m,'MyBotWinthorBot',win32service.SERVICE_STOP|win32service.SERVICE_QUERY_STATUS|win32service.DELETE)
        except win32service.error as e:
            if e.winerror==1060:return
            raise
        try:
            if win32service.QueryServiceStatus(h)[1]!=win32service.SERVICE_STOPPED:
                try:win32service.ControlService(h,win32service.SERVICE_CONTROL_STOP)
                except win32service.error as e:
                    if e.winerror!=1062:raise
                for _ in range(40):
                    if win32service.QueryServiceStatus(h)[1]==win32service.SERVICE_STOPPED:break
                    time.sleep(.5)
                else:raise RuntimeError('O serviço antigo não parou. Nenhum arquivo foi apagado.')
            win32service.DeleteService(h)
        finally:win32service.CloseServiceHandle(h)
    finally:win32service.CloseServiceHandle(m)
