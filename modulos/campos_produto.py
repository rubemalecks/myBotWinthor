"""Colunas adicionais de PCPRODUT habilitadas pelo administrador local."""
import logging
import re
from datetime import date, datetime
from decimal import Decimal

from modulos.permissoes import obter_configuracao_campos_produto, salvar_configuracao_campos_produto

logger = logging.getLogger(__name__)
LIMITE_CAMPOS = 20
COLUNAS_FIXAS = {'CODPROD', 'DESCRICAO', 'DTEXCLUSAO'}
CAMPOS_PUBLICOS = {'CODAUXILIAR', 'CODAUXILIAR2', 'CODEPTO', 'CODFORNEC', 'CODMARCA',
                   'CODFAB', 'EMBALAGEM', 'UNIDADE', 'NBM'}
PERMISSOES_CAMPOS = {'consulta_preco', 'ver_custos'}


def coluna_valida(coluna):
    return isinstance(coluna, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}', coluna) is not None and coluna not in COLUNAS_FIXAS


def permissao_padrao(coluna):
    return 'consulta_preco' if coluna in CAMPOS_PUBLICOS else 'ver_custos'


def validar_campos(campos):
    if not isinstance(campos, list) or len(campos) > LIMITE_CAMPOS:
        raise ValueError(f'Selecione até {LIMITE_CAMPOS} campos do produto.')
    resultado = []
    usados = set()
    for campo in campos:
        if not isinstance(campo, dict) or not set(campo).issubset({'coluna', 'permissao'}) or not coluna_valida(campo.get('coluna')):
            raise ValueError('Selecione uma coluna válida de PCPRODUT. Expressões SQL não são permitidas.')
        coluna = campo['coluna']
        if coluna in usados:
            raise ValueError('A mesma coluna não pode ser selecionada duas vezes.')
        permissao = campo.get('permissao', permissao_padrao(coluna))
        if not isinstance(permissao, str) or permissao not in PERMISSOES_CAMPOS:
            raise ValueError('Permissão de visualização do campo inválida.')
        usados.add(coluna)
        resultado.append({'coluna': coluna, 'permissao': permissao})
    return resultado


def obter_campos_produto(estrito=False):
    try:
        return validar_campos(obter_configuracao_campos_produto())
    except (RuntimeError, ValueError) as erro:
        if estrito:
            raise RuntimeError('Não foi possível ler campos_produto.json. Verifique o arquivo ou restaure um backup.') from erro
        logger.warning('Configuração dos campos do produto inválida. Usando somente os campos padrão.')
        return []


def salvar_campos_produto(campos, catalogo):
    campos = validar_campos(campos)
    disponiveis = {item['coluna'] for item in catalogo}
    if any(campo['coluna'] not in disponiveis for campo in campos):
        raise ValueError('Uma coluna selecionada não está disponível em PCPRODUT. Atualize a lista de campos.')
    salvar_configuracao_campos_produto(campos)
    return campos


def exemplos_campos_produto():
    exemplos = {'CODAUXILIAR': '7891234567890', 'CODAUXILIAR2': '7899876543210', 'CODEPTO': '108'}
    return {campo['coluna'].lower(): exemplos.get(campo['coluna'], 'EXEMPLO') for campo in obter_campos_produto()}


def valores_campos_produto(produto, permissoes=('consulta_preco',)):
    resultado = {}
    for variavel, campo in produto.get('campos_personalizados', {}).items():
        if campo['permissao'] not in permissoes:
            resultado[variavel] = '🔒 Sem permissão'
            continue
        valor = campo['valor']
        if valor is None:
            valor = 'Não informado'
        elif isinstance(valor, (datetime, date)):
            valor = valor.strftime('%d/%m/%Y')
        elif isinstance(valor, Decimal):
            valor = format(valor, 'f')
        resultado[variavel] = str(valor)
    return resultado
