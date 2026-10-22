"""Restrições de filial e região para consultas autorizadas."""
CHAVES_ESCOPO = {'filiais_permitidas', 'tabelas_permitidas'}


def validar_escopo(dados):
    for chave in CHAVES_ESCOPO & dados.keys():
        valores = dados[chave]
        if valores is not None:
            if not isinstance(valores, list) or len(valores) > 500:
                raise ValueError('Informe uma lista de códigos ou todas as opções.')
            if any(type(v) not in (str, int) or not str(v).isascii() or not str(v).isdecimal() or int(v) <= 0 for v in valores):
                raise ValueError('Códigos de filiais e tabelas devem ser números positivos.')
            dados[chave] = sorted(set(str(int(v)) for v in valores))
    return dados


def filtros_escopo(escopo, params, filial=None, regiao=None):
    partes = []
    for chave, coluna, prefixo in (('filiais_permitidas', filial, 'AC_FIL'), ('tabelas_permitidas', regiao, 'AC_TAB')):
        valores = (escopo or {}).get(chave)
        if coluna is False or valores is None:
            continue
        if not valores:
            partes.append('1=0')
            continue
        binds = []
        for indice, valor in enumerate(valores):
            nome = f'{prefixo}_{indice}'
            params[nome] = str(valor) if chave == 'filiais_permitidas' else int(valor)
            binds.append(':' + nome)
        lista = ', '.join(binds)
        if coluna:
            partes.append(f'{coluna} IN ({lista})')
        elif chave == 'filiais_permitidas':
            partes.append(f'EXISTS (SELECT 1 FROM PCEST AF WHERE AF.CODPROD = P.CODPROD AND AF.CODFILIAL IN ({lista}))')
        else:
            partes.append(f"EXISTS (SELECT 1 FROM PCTABPR ATB JOIN PCREGIAO AR ON AR.NUMREGIAO = ATB.NUMREGIAO WHERE ATB.CODPROD = P.CODPROD AND AR.STATUS = 'A' AND ATB.NUMREGIAO IN ({lista}))")
    return ''.join(' AND ' + parte for parte in partes)
