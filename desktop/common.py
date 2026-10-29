"""Caminhos e instalação sem incluir dados de clientes no pacote."""
import json, os, sys, hashlib
from pathlib import Path

ARQUIVOS_DADOS = ('dados_bot.json', 'config_bot.json', 'config_oracle.json', 'mensagens.json', 'campos_produto.json', 'formulas_margem.json')

def padrao_dados():
    return Path(os.environ['LOCALAPPDATA']) / 'myBotWinthor' / 'dados'

def validar_dados(pasta):
    pasta = Path(pasta).resolve()
    if str(pasta).replace('\\','/').startswith('//'):
        raise ValueError('Escolha uma pasta local para os dados.')
    for nome in ARQUIVOS_DADOS:
        arquivo = pasta / nome
        if arquivo.exists():
            if arquivo.stat().st_size > 10 * 1024 * 1024:
                raise ValueError('Arquivo de dados muito grande: ' + nome)
            valor = json.loads(arquivo.read_text(encoding='utf-8'))
            if not isinstance(valor, dict):
                raise ValueError('Formato inválido: ' + nome)
    return pasta

def pasta_dados():
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
    arquivo = base / 'desktop.json'
    return validar_dados(json.loads(arquivo.read_text(encoding='utf-8'))['data_dir']) if arquivo.exists() else padrao_dados()

def identificador(pasta):
    return 'Local\\myBotWinthor-' + hashlib.sha256(str(Path(pasta).resolve()).casefold().encode()).hexdigest()[:24]
