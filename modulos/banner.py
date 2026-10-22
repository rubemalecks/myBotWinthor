"""Desenha a marca no Python para o CMD não interpretar os caracteres do logo."""
import sys


def mostrar_banner():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    colorido = sys.stdout.isatty()
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
