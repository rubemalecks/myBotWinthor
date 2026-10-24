"""Desenha a marca no Python para o CMD não interpretar os caracteres do logo."""
import sys
import os


def habilitar_cores():
    if not sys.stdout.isatty() or os.environ.get('NO_COLOR') is not None:
        return False
    if os.name != 'nt':
        return True
    try:
        import ctypes
        import msvcrt
        from ctypes.wintypes import DWORD, HANDLE
        kernel = ctypes.windll.kernel32
        handle = HANDLE(msvcrt.get_osfhandle(sys.stdout.fileno()))
        modo = DWORD()
        if not kernel.GetConsoleMode(handle, ctypes.byref(modo)):
            return False
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING: consoles antigos usam texto simples.
        return bool(kernel.SetConsoleMode(handle, modo.value | 0x0004))
    except (OSError, ValueError, AttributeError):
        return False


def mostrar_banner():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    colorido = habilitar_cores()
    azul = '\033[38;2;8;109;166m' if colorido else ''
    cinza = '\033[38;2;190;196;204m' if colorido else ''
    reset = '\033[0m' if colorido else ''
    print(f'''
{azul}              ●
              █
        ▄███████████▄
      ▄██▀         ▀██▄
      ██    ▪   ▪    ██     {cinza}my{azul}Bot{cinza}Winthor{azul}
    ▐███▄           ▄███▌
    ▐███ ▀█████████▀ ███▌   {cinza}RBTech Soluções{azul}
      ██▄  ▀██▄  ▄█████
      ████▄  ▀████▀  ██
      ██ ▀██▄  ▀██▄▄███
      ██   ▀██▄  ▀████▀
{cinza}    ───────────────────────────────────────────────{reset}
''')


if __name__ == '__main__':
    mostrar_banner()
