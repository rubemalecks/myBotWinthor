"""Leitura contínua do log do serviço, sem iniciar ou modificar a aplicação."""
import argparse
import codecs
import os
import sys
import time
from pathlib import Path

from modulos.banner import mostrar_banner

LOG_FILE = Path(__file__).resolve().parent.parent / 'bot-service.log'


def _posicionar_cauda(arquivo, linhas):
    """Busca apenas os blocos finais necessários, sem carregar o log inteiro."""
    posicao = arquivo.seek(0, os.SEEK_END)
    if linhas == 0:
        return posicao
    dados = b''
    while posicao > 0 and dados.count(b'\n') <= linhas:
        tamanho = min(8192, posicao)
        posicao -= tamanho
        arquivo.seek(posicao)
        dados = arquivo.read(tamanho) + dados
    cauda = b''.join(dados.splitlines(keepends=True)[-linhas:])
    return posicao + len(dados) - len(cauda)


class LeitorLog:
    def __init__(self, caminho, linhas=50):
        self.caminho = Path(caminho)
        self.linhas = linhas
        self.primeira_leitura = True
        self.identidade = None
        self.posicao = 0
        self._reiniciar_texto()

    def _reiniciar_texto(self):
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.pendente = ''

    def ler_novas(self):
        try:
            # Fecha a cada leitura para não bloquear remoção/rotação no Windows.
            with self.caminho.open('rb') as arquivo:
                estado = os.fstat(arquivo.fileno())
                identidade = (estado.st_dev, estado.st_ino)
                if self.primeira_leitura:
                    self.posicao = _posicionar_cauda(arquivo, self.linhas)
                    self.primeira_leitura = False
                elif identidade != self.identidade or estado.st_size < self.posicao:
                    self.posicao = 0
                    self._reiniciar_texto()
                self.identidade = identidade
                arquivo.seek(self.posicao)
                dados = arquivo.read(262144)
                self.posicao = arquivo.tell()
        except FileNotFoundError:
            self.identidade = None
            self.posicao = 0
            self._reiniciar_texto()
            return []
        texto = self.pendente + self.decoder.decode(dados)
        partes = texto.split('\n')
        self.pendente = partes.pop()
        return [linha.removesuffix('\r') for linha in partes]


def main(argumentos=None):
    parser = argparse.ArgumentParser(description='Acompanhar consultas e requisições do serviço myBotWinthor.')
    parser.add_argument('--linhas', type=int, default=50, help='Quantidade de linhas recentes ao abrir (padrão: 50; zero: só novas).')
    parser.add_argument('--somente-consultas', action='store_true', help='Mostrar somente eventos estruturados CONSULTA do bot.')
    parser.add_argument('--manter-aberto', action='store_true', help=argparse.SUPPRESS)
    opcoes = parser.parse_args(argumentos)
    if not 0 <= opcoes.linhas <= 10000:
        parser.error('--linhas deve estar entre 0 e 10000.')
    print('myBotWinthor — Monitor de consultas e requisições')
    print(f'Arquivo: {LOG_FILE}')
    print(f'Exibindo as últimas {opcoes.linhas} linhas e acompanhando novas entradas.')
    if opcoes.somente_consultas:
        print('Filtro ativo: somente eventos CONSULTA do bot.')
    print('CONSULTA informa usuário/ID, busca, etapa, resultado e duração.')
    print('Ctrl+C encerra somente o monitor. O serviço continua funcionando.\n')
    leitor = LeitorLog(LOG_FILE, opcoes.linhas)
    try:
        if not LOG_FILE.exists():
            print('O log ainda não existe. Aguardando a execução do serviço Windows...', flush=True)
        while True:
            for linha in leitor.ler_novas():
                if not opcoes.somente_consultas or 'CONSULTA ' in linha:
                    print(linha, flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print('\nMonitor encerrado. O serviço permanece em execução.')
        return 0
    except OSError as erro:
        print(f'Não foi possível ler o log ({type(erro).__name__}). Confira a pasta do projeto e a permissão de leitura.')
        return 1


if __name__ == '__main__':
    mostrar_banner()
    codigo_saida = main()
    if codigo_saida and '--manter-aberto' in sys.argv:
        try:
            input('Pressione Enter para fechar o monitor...')
        except (EOFError, KeyboardInterrupt):
            pass
    raise SystemExit(codigo_saida)
