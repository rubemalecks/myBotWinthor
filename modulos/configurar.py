"""Configuração local interativa, compartilhada com o painel web."""
import getpass
import ipaddress
import re
import warnings

from modulos.database import ErroAcessoWinthor, testar_conexao_oracle
from modulos.permissoes import ARQUIVO_DADOS, obter_configuracao, salvar_configuracoes
from modulos.rede import enderecos_painel
from modulos.iniciar import iniciar_e_abrir_painel


def validar_porta(valor):
    if not valor.isascii() or not valor.isdecimal() or not 1 <= int(valor) <= 65535:
        raise ValueError('Informe uma porta entre 1 e 65535.')
    return str(int(valor))


def validar_host(valor):
    if not valor:
        raise ValueError('Informe o IP ou nome do servidor Oracle.')
    if ':' in valor or re.fullmatch(r'[0-9.]+', valor):
        try:
            ipaddress.ip_address(valor)
        except ValueError as erro:
            raise ValueError('Endereço IP inválido. Exemplo: 192.168.0.10.') from erro
    return valor


def perguntar(rotulo, atual='', validar=None):
    while True:
        valor = input(f'{rotulo}' + (f' [{atual}]' if atual else '') + ': ').strip()
        valor = re.sub(r'\s+', '', valor) if valor else atual
        try:
            if validar:
                return validar(valor)
            if not valor:
                raise ValueError('Este campo é obrigatório.')
            return valor
        except ValueError as erro:
            print(f'  {erro}')


def confirmar(texto):
    return input(f'{texto} [s/N]: ').strip().lower() in ('s', 'sim')


def configurar_oracle():
    atual = obter_configuracao()
    print('\nBANCO ORACLE — Enter mantém o valor atual.')
    novos = {
        'ORACLE_HOST': perguntar('IP ou nome do servidor', atual['ORACLE_HOST'], validar_host),
        'ORACLE_PORT': perguntar('Porta Oracle', atual['ORACLE_PORT'], validar_porta),
        'ORACLE_SERVICE': perguntar('Service name', atual['ORACLE_SERVICE']),
        'ORACLE_USER': perguntar('Usuário Oracle', atual['ORACLE_USER']),
    }
    # Interrompe em terminais incapazes de ocultar a senha, em vez de exibi-la.
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        senha = getpass.getpass('Senha Oracle (oculta; Enter mantém a atual): ')
    if senha:
        novos['ORACLE_PASSWORD'] = senha
    elif not atual['ORACLE_PASSWORD']:
        print('Nenhuma senha configurada. Operação cancelada; nada foi salvo.')
        return
    if not confirmar('Salvar a configuração Oracle?'):
        print('Cancelado; nada foi salvo.')
        return
    salvar_configuracoes(novos)
    print(f'Configuração salva em {ARQUIVO_DADOS.with_name("config_oracle.json")}')
    if confirmar('Testar conexão e acesso à consulta de produtos?'):
        print('Testando Oracle...')
        try:
            if testar_conexao_oracle():
                print('ORACLE: OK — conexão e consulta de produtos validadas.')
            else:
                print('ORACLE: OFF — teste sem o resultado esperado.')
        except ErroAcessoWinthor as erro:
            print(f'ORACLE: OFF — {erro}')
        except Exception as erro:
            codigos = ', '.join(re.findall(r'(?:ORA|DPI|DPY)-\d+', str(erro)))
            print(f'ORACLE: OFF — {type(erro).__name__}' + (f' ({codigos})' if codigos else '') +
                  '. Confira servidor, porta, serviço, credenciais e Oracle Client.')
        print('As configurações continuam salvas, mesmo se o teste falhar.')


def mostrar_enderecos(porta, host='0.0.0.0'):
    local, rede = enderecos_painel(porta, host)
    if local:
        print(f'Na própria máquina: {local}')
    if rede:
        print(f'Em outras máquinas da mesma rede: {rede}')
        print('O acesso pela rede depende da liberação da porta no firewall.')
    else:
        print('Acesso pela rede indisponível: confira o IP e WEB_ADMIN_HOST no .env/configurações.')
    if not local and rede:
        print('Nesta máquina, use também o endereço de rede acima.')


def configurar_porta_api():
    atual = obter_configuracao()
    print('\nPORTA DA API / PAINEL WEB')
    porta = perguntar('Porta HTTP', atual['WEB_ADMIN_PORT'], validar_porta)
    mostrar_enderecos(porta, atual.get('WEB_ADMIN_HOST', '0.0.0.0'))
    atualizar = {'WEB_ADMIN_PORT': porta}
    if atual['WEB_ADMIN_URL'].strip() and porta != atual['WEB_ADMIN_PORT']:
        print('Existe uma URL de anúncio personalizada. Ela pode conter a porta antiga.')
        if confirmar('Limpar essa URL para o sistema anunciar o endereço automaticamente?'):
            atualizar['WEB_ADMIN_URL'] = ''
        else:
            print('A URL de anúncio será mantida; confira sua configuração separadamente.')
    if confirmar('Salvar esta porta?'):
        salvar_configuracoes(atualizar)
        print(f'Porta salva em {ARQUIVO_DADOS.with_name("config_bot.json")}')
        print('A nova porta será aplicada na próxima execução da API.')
    else:
        print('Cancelado; nada foi salvo.')


def main():
    print('myBotWinthor — Configuração local')
    print('Pare o bot e o painel antes de alterar os arquivos.')
    print('Este assistente usa os mesmos dados do painel. Senhas não são exibidas.')
    try:
        atual = obter_configuracao()
        print('\nENDEREÇOS CONFIGURADOS DA API')
        mostrar_enderecos(atual['WEB_ADMIN_PORT'], atual.get('WEB_ADMIN_HOST', '0.0.0.0'))
        print('Os endereços ficam disponíveis quando a API estiver em execução.\n')
        if not confirmar('O projeto está parado e você deseja continuar?'):
            return 0
        while True:
            print('\n1 — Configurar banco Oracle\n2 — Configurar porta da API\n0 — Sair')
            opcao = input('Escolha: ').strip()
            if opcao == '0':
                break
            if opcao == '1':
                configurar_oracle()
            elif opcao == '2':
                configurar_porta_api()
            else:
                print('Opção inválida.')
        if confirmar('Deseja iniciar o bot e a API neste terminal e abrir o painel agora?'):
            return iniciar_e_abrir_painel()
        print('Para iniciar depois: .venv\\Scripts\\python.exe bot.py')
        return 0
    except (KeyboardInterrupt, EOFError):
        print('\nOperação interrompida. Alterações já confirmadas permanecem salvas.')
        return 1
    except getpass.GetPassWarning:
        print('Este terminal não permite ocultar a senha. Use um terminal Windows ou o painel web.')
        return 1
    except (OSError, RuntimeError, ValueError) as erro:
        # Não imprime valores de configuração nem credenciais em mensagens de erro.
        print(f'Não foi possível concluir ({type(erro).__name__}). Confira acesso aos arquivos e formato dos JSONs.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
