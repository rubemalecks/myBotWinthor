"""Resolve variáveis de PCPRODUT sem cadastro manual de campos."""
import re
from string import Formatter
from modulos.mensagens import MODELOS, validar_modelo
from modulos.campos_produto import obter_campos_produto, validar_campos, permissao_padrao


def preparar_mensagens(alteracoes, catalogo=None):
    if not isinstance(alteracoes, dict) or not alteracoes or not set(alteracoes).issubset(MODELOS):
        raise ValueError('Informe os tipos de mensagem que deseja alterar.')
    campos = {campo['coluna']: campo for campo in obter_campos_produto(estrito=True)}
    novos = set()
    catalogo_custos = None
    custos_validados = set()
    textos = {}
    for chave, texto in alteracoes.items():
        if texto is None:
            textos[chave] = None
            continue
        if not isinstance(texto, str) or not texto.strip() or len(texto) > 2500:
            raise ValueError('O texto deve ter de 1 a 2500 caracteres.')
        partes = []
        for literal, campo, formato, conversao in Formatter().parse(texto):
            partes.append(literal.replace('{', '{{').replace('}', '}}'))
            if campo is None:
                continue
            if formato or conversao or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}', campo):
                raise ValueError('Use somente variáveis como {embalagem}, sem expressões ou formatação.')
            variavel = campo.lower()
            if variavel not in MODELOS[chave]['exemplo']:
                if chave == 'custos':
                    from modulos.campos_custos import validar_variavel_custo
                    if variavel not in custos_validados:
                        if catalogo_custos is None and variavel.startswith('pcest_'):
                            from modulos.database import listar_colunas_custos
                            catalogo_custos = listar_colunas_custos()
                        validar_variavel_custo(variavel, catalogo_custos)
                        custos_validados.add(variavel)
                    partes.append('{' + variavel + '}')
                    continue
                if chave not in ('produto', 'formula_produto'):
                    raise ValueError(f'Variável não permitida neste bloco: {campo}.')
                coluna = variavel.upper()
                if coluna not in campos:
                    novos.add(coluna)
                    campos[coluna] = {'coluna': coluna, 'permissao': permissao_padrao(coluna)}
            partes.append('{' + variavel + '}')
        textos[chave] = ''.join(partes)
    validar_campos(list(campos.values()))
    if novos and catalogo is None:
        return textos, list(campos.values()), True
    if novos:
        disponiveis = {campo['coluna'] for campo in catalogo}
        invalidos = novos - disponiveis
        if invalidos:
            raise ValueError('Coluna não disponível em PCPRODUT: ' + ', '.join(sorted(invalidos)))
    for chave, texto in textos.items():
        if texto is not None:
            validar_modelo(chave, texto, list(campos.values()))
    return textos, list(campos.values()), False
