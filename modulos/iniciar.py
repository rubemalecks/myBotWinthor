"""Inicia o serviço ou a execução manual e abre o painel quando disponível."""
import json
import subprocess
import sys
import time
import webbrowser
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from modulos.permissoes import BASE_DIR, obter_configuracao
from modulos.rede import enderecos_painel
from modulos.servico_windows import SERVICE_NAME, obter_status_servico
from modulos.banner import mostrar_banner


def painel_disponivel(url):
    try:
        # A verificação local não deve passar pelo proxy corporativo.
        with build_opener(ProxyHandler({})).open(url.rstrip('/') + '/health', timeout=1) as resposta:
            return resposta.status == 200 and json.loads(resposta.read(4096)).get('status') == 'ok'
    except (OSError, URLError, ValueError, AttributeError):
        return False


def _iniciar_servico_windows():
    import win32serviceutil
    win32serviceutil.StartService(SERVICE_NAME)


def orientar_reparo_servico(caminho=None):
    if caminho:
        print(f'Arquivo do serviço não encontrado: {caminho}')
    print('O registro do serviço precisa ser reparado usando o ambiente atual do projeto.')
    print('Abra o PowerShell como administrador na pasta do projeto e execute:')
    print('  .\\.venv\\Scripts\\python.exe service_helper.py install')
    print('Depois, execute iniciar.bat novamente.')


def aguardar_processo(processo):
    try:
        return processo.wait()
    except KeyboardInterrupt:
        print('\nEncerrando myBotWinthor... Aguarde a finalização do painel.')
        try:
            return processo.wait(timeout=15)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            processo.terminate()
            processo.wait(timeout=5)
            return 0


def iniciar_e_abrir_painel(abrir_navegador=True):
    configuracao = obter_configuracao()
    local, rede = enderecos_painel(configuracao['WEB_ADMIN_PORT'], configuracao['WEB_ADMIN_HOST'])
    url = local or rede
    if not url:
        print('Não foi possível determinar o endereço do painel. Confira o host configurado.')
        return 1
    processo = None
    if painel_disponivel(url):
        print('O painel já está em execução; nenhuma nova instância será iniciada.')
    else:
        try:
            servico = obter_status_servico()
            if servico.get('installed'):
                if servico.get('binary_exists') is False:
                    orientar_reparo_servico(servico.get('binary_path'))
                    return 1
                if servico.get('state') not in ('running', 'starting', 'start_pending'):
                    print('Iniciando o serviço Windows...')
                    _iniciar_servico_windows()
                else:
                    print('O serviço já está iniciado; aguardando o painel...')
            else:
                print('Serviço Windows não instalado. Iniciando bot e API neste terminal...')
                processo = subprocess.Popen([sys.executable, str(BASE_DIR / 'bot.py')], cwd=BASE_DIR)
        except Exception as erro:
            codigo = getattr(erro, 'winerror', None)
            detalhe = getattr(erro, 'strerror', None)
            print(f'Não foi possível iniciar: erro Windows {codigo} — {detalhe or type(erro).__name__}.'
                  if codigo is not None else f'Não foi possível iniciar ({type(erro).__name__}). Confira o serviço e as configurações.')
            if codigo in (2, 3):
                orientar_reparo_servico()
            elif codigo == 5:
                print('Acesso negado. Execute iniciar.bat como administrador para iniciar o serviço.')
            elif codigo == 1058:
                print('O serviço está desativado. Ative a inicialização automática na guia Bot do painel ou reinstale o serviço.')
            elif codigo is not None:
                print('Confira a configuração do serviço e os eventos do Windows para esse código de erro.')
            return 1
        limite = time.monotonic() + 30
        while time.monotonic() < limite:
            if processo is not None and processo.poll() is not None:
                print('O bot encerrou antes de abrir o painel. Confira o erro no terminal.')
                return 1
            if painel_disponivel(url):
                break
            time.sleep(0.5)
        else:
            print(f'O painel ainda não respondeu. Confira o terminal/log do serviço e tente acessar {url}')
            if processo is not None:
                print('A execução manual continua neste terminal. Use Ctrl+C para parar.')
                return aguardar_processo(processo)
            return 1
    if abrir_navegador:
        print(f'Abrindo o painel no navegador: {url}')
        try:
            if not webbrowser.open(url, new=2):
                print(f'Abra o navegador manualmente em {url}')
        except webbrowser.Error:
            print(f'Abra o navegador manualmente em {url}')
    else:
        print(f'Painel disponível em {url}')
    if processo is not None:
        print('Bot e API em execução neste terminal. Use Ctrl+C para parar.')
        return aguardar_processo(processo)
    return 0


def main():
    print('myBotWinthor — Iniciar API e bot')
    try:
        abrir = input('Deseja abrir o painel no navegador também? [s/N]: ').strip().lower() in ('s', 'sim')
        return iniciar_e_abrir_painel(abrir_navegador=abrir)
    except KeyboardInterrupt:
        print('\nEncerramento solicitado. Aguarde a finalização da API.')
        return 0
    except EOFError:
        print('\nInicialização cancelada.')
        return 0
    except (OSError, RuntimeError, ValueError) as erro:
        print(f'Não foi possível iniciar ({type(erro).__name__}). Confira as configurações e o acesso aos arquivos.')
        return 1


if __name__ == '__main__':
    mostrar_banner()
    codigo_saida = main()
    if codigo_saida and '--manter-aberto' in sys.argv:
        try:
            input('Falha na inicialização. Confira a mensagem acima e pressione Enter para fechar...')
        except (EOFError, KeyboardInterrupt):
            pass
    raise SystemExit(codigo_saida)
