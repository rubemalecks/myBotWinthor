"""Campos de PCEST para mensagens restritas de custo."""
import re
from string import Formatter
from modulos.permissoes import obter_mensagens_personalizadas


def variaveis_custos(texto):
    return {campo.lower() for _, campo, _, _ in Formatter().parse(texto)
            if campo and re.fullmatch(r'pcest_[A-Za-z][A-Za-z0-9_]{0,127}', campo)}


def exemplos_custos():
    texto = obter_mensagens_personalizadas().get('custos', '')
    return {v: 'EXEMPLO' for v in variaveis_custos(texto)}


def validar_variavel_custo(variavel, catalogo=None):
    from modulos.database import listar_colunas_custos
    if not re.fullmatch(r'pcest_[a-z][a-z0-9_]{0,127}', variavel):
        raise ValueError('Use uma coluna de PCEST, como {pcest_custoreal}.')
    if variavel not in {c['variavel'] for c in (listar_colunas_custos() if catalogo is None else catalogo)}:
        raise ValueError('Coluna não disponível em PCEST: ' + variavel[6:].upper())


def valores_custos(item):
    from modulos.bot import formatar_moeda
    from datetime import date, datetime
    from decimal import Decimal
    resultado = {}
    for chave, valor in item.items():
        if not chave.startswith('pcest_'):
            continue
        if valor is None:
            valor = 'Não informado'
        elif isinstance(valor, (date, datetime)):
            valor = valor.strftime('%d/%m/%Y')
        elif isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
            valor = formatar_moeda(valor, 5)
        resultado[chave] = str(valor)
    return resultado
