"""Regras locais de margem com ajustes guiados e filtros SQL compilados."""
import ast
import re
from decimal import Decimal, InvalidOperation

from modulos.permissoes import ler_regras_margem, gravar_regra_margem

TABELAS = {'PCPRODUT': 'P', 'PCEST': 'E', 'PCTABPR': 'T', 'PCREGIAO': 'R'}
ALIASES = {**{nome: nome for nome in TABELAS}, **{alias: nome for nome, alias in TABELAS.items()}}
PADRAO = '(Preço de venda − Custo de entrada) ÷ Custo de entrada × 100'
LIMITE_REGRAS = 50
TOKEN = re.compile(r"\s*(?:('(?:[^']|'')*')|(\d+(?:\.\d+)?)|([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)?)|(<>|!=|<=|>=|[=<>(),+-]))")


def referencia(campo):
    if not isinstance(campo, str):
        raise ValueError('Informe uma coluna das tabelas disponíveis.')
    partes = campo.strip().upper().split('.')
    if len(partes) != 2 or partes[0] not in ALIASES or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}', partes[1]):
        raise ValueError('Use TABELA.COLUNA, por exemplo PCEST.CUSTOREAL.')
    return f'{ALIASES[partes[0]]}.{partes[1]}'


def numero(valor):
    if isinstance(valor, bool):
        raise ValueError('Informe um número válido.')
    try:
        convertido = Decimal(str(valor).strip().replace(',', '.'))
        if not convertido.is_finite() or abs(convertido) > Decimal('1000000000'):
            raise ValueError('O valor deve ser finito e não pode exceder um bilhão.')
        return convertido
    except (InvalidOperation, TypeError) as erro:
        raise ValueError('Informe um número válido, por exemplo 2,50 ou 5.') from erro


def analisar_where(texto):
    if not isinstance(texto, str) or len(texto) > 1000:
        raise ValueError('O WHERE aceita até 1.000 caracteres.')
    texto = re.sub(r'^\s*WHERE\s+', '', texto, flags=re.I).strip()
    if not texto:
        return None
    tokens = []
    posicao = 0
    while posicao < len(texto):
        match = TOKEN.match(texto, posicao)
        if not match:
            raise ValueError('WHERE inválido. Use comparações, IN, LIKE, IS NULL, AND, OR e NOT, sem comandos ou subconsultas.')
        literal, numerico, palavra, operador = match.groups()
        if literal is not None:
            tokens.append(repr(literal[1:-1].replace("''", "'")))
        elif numerico is not None:
            tokens.append(numerico)
        elif palavra is not None:
            tokens.append({'AND': 'and', 'OR': 'or', 'NOT': 'not', 'IN': 'in', 'IS': 'is', 'NULL': 'None'}.get(palavra.upper(), palavra))
        else:
            tokens.append({'=': '==', '<>': '!='}.get(operador, operador))
        posicao = match.end()
    # LIKE aceita coluna/variável à esquerda e literal à direita.
    i = 0
    while i < len(tokens):
        if tokens[i].upper() == 'LIKE':
            negado = i >= 2 and tokens[i - 1] == 'not'
            inicio = i - 2 if negado else i - 1
            if inicio < 0 or i + 1 >= len(tokens):
                raise ValueError('LIKE deve comparar uma coluna com um texto.')
            tokens[inicio:i + 2] = [f'{"not " if negado else ""}like({tokens[inicio]}, {tokens[i + 1]})']
            i = inicio
        i += 1
    try:
        arvore = ast.parse(' '.join(tokens), mode='eval').body
        if sum(1 for _ in ast.walk(arvore)) > 200:
            raise ValueError('WHERE muito complexo.')
    except (SyntaxError, RecursionError) as erro:
        raise ValueError('Sintaxe do WHERE inválida.') from erro
    compilador = CompiladorSQL()
    compilador.filtro(arvore)
    return arvore


def normalizar_regra(dados, salvar=True):
    chaves = {'id', 'nome', 'ativa', 'prioridade', 'produtos', 'where', 'todos_produtos', 'ajustes', 'campo_custo'}
    if not isinstance(dados, dict) or not set(dados).issubset(chaves):
        raise ValueError('Regra contém campos inválidos.')
    nome = dados.get('nome', '').strip() if isinstance(dados.get('nome', ''), str) else ''
    if salvar and not nome or len(nome) > 100:
        raise ValueError('Informe um nome com até 100 caracteres.')
    prioridade = dados.get('prioridade', 100)
    if type(prioridade) is not int or not 0 <= prioridade <= 10000:
        raise ValueError('Prioridade deve estar entre 0 e 10000; números menores têm preferência.')
    produtos = dados.get('produtos', [])
    if not isinstance(produtos, list) or len(produtos) > 500:
        raise ValueError('Informe uma lista com até 500 CODPRODs.')
    if any(type(codigo) not in (str, int) or not str(codigo).isascii() or not str(codigo).isdecimal() or not 0 < int(codigo) < 10**15 for codigo in produtos):
        raise ValueError('Os produtos devem ser CODPRODs numéricos positivos.')
    produtos = sorted({str(int(codigo)) for codigo in produtos}, key=int)
    where = dados.get('where', '')
    analisar_where(where)
    where = re.sub(r'^\s*WHERE\s+', '', where, flags=re.I).strip()
    todos = dados.get('todos_produtos', False)
    ativa = dados.get('ativa', False)
    if type(todos) is not bool or type(ativa) is not bool:
        raise ValueError('Ativação e seleção de todos os produtos devem ser booleanas.')
    if todos and (produtos or where):
        raise ValueError('Escolha todos os produtos ou use a lista/WHERE.')
    if salvar and not todos and not produtos and not where:
        raise ValueError('Vincule produtos, informe um WHERE ou marque Todos os produtos.')
    campo_custo = referencia(dados.get('campo_custo', 'PCEST.CUSTOULTENT'))
    if not campo_custo.startswith('PCEST.'):
        raise ValueError('O campo base do custo deve ser uma coluna de PCEST.')
    ajustes = dados.get('ajustes', [])
    if not isinstance(ajustes, list) or len(ajustes) > 20:
        raise ValueError('A regra aceita até 20 ajustes.')
    resultado = []
    for ajuste in ajustes:
        if not isinstance(ajuste, dict) or not set(ajuste).issubset({'alvo', 'operacao', 'tipo', 'valor', 'campo'}):
            raise ValueError('Ajuste inválido.')
        if ajuste.get('alvo') not in ('preco', 'custo', 'resultado') or ajuste.get('operacao') not in ('+', '-') or ajuste.get('tipo') not in ('valor', 'percentual', 'campo', 'campo_percentual'):
            raise ValueError('Escolha o alvo, a operação e o tipo do ajuste.')
        novo = {chave: ajuste[chave] for chave in ('alvo', 'operacao', 'tipo')}
        if novo['tipo'].startswith('campo'):
            novo['campo'] = referencia(ajuste.get('campo'))
        else:
            novo['valor'] = str(numero(ajuste.get('valor')))
        resultado.append(novo)
    regra = {'nome': nome or 'Simulação', 'ativa': ativa, 'prioridade': prioridade,
             'produtos': produtos, 'where': where, 'todos_produtos': todos, 'ajustes': resultado}
    if campo_custo != 'PCEST.CUSTOULTENT':
        regra['campo_custo'] = campo_custo
    return regra


def obter_regras(ativas=False):
    regras = []
    for salvo in ler_regras_margem():
        try:
            regra = normalizar_regra(salvo)
            identificador = salvo.get('id')
            if not isinstance(identificador, str) or not re.fullmatch('[a-f0-9]{24}', identificador):
                raise ValueError('Identificador inválido.')
            regras.append({'id': identificador, **regra})
        except (ValueError, AttributeError) as erro:
            raise RuntimeError('Uma regra de formulas_margem.json está inválida. Corrija o arquivo ou restaure um backup.') from erro
    regras.sort(key=lambda regra: (regra['prioridade'], regra['id']))
    return [regra for regra in regras if regra['ativa']] if ativas else regras


def validar_catalogo(regra, catalogo):
    compilador = CompiladorSQL()
    compilador.condicao(regra)
    compilador.ajustes(regra)
    disponiveis = {item['campo']: item for item in catalogo}
    for campo in compilador.referencias:
        if campo not in disponiveis:
            raise ValueError(f'Campo não disponível: {campo}. Atualize o catálogo.')
    if regra.get('campo_custo') and not disponiveis[regra['campo_custo']]['numerico']:
        raise ValueError('O campo base do custo deve ser numérico.')
    for ajuste in regra['ajustes']:
        if ajuste['tipo'].startswith('campo') and not disponiveis[ajuste['campo']]['numerico']:
            raise ValueError('Parâmetros usados nos cálculos devem ser colunas numéricas.')


def salvar_regra(dados, catalogo, identificador=None):
    regra = normalizar_regra(dados)
    validar_catalogo(regra, catalogo)
    return gravar_regra_margem('salvar' if identificador else 'criar', regra, identificador)


def expressao_regra(regra=None):
    if not regra:
        return PADRAO
    valores = {'preco': 'preco', 'custo': regra.get('campo_custo', 'custo')}
    for ajuste in regra['ajustes']:
        if ajuste['alvo'] in valores:
            valores[ajuste['alvo']] = _ajuste_texto(valores[ajuste['alvo']], ajuste)
    texto = f'(({valores["preco"]}) - ({valores["custo"]})) / ({valores["custo"]}) * 100'
    for ajuste in regra['ajustes']:
        if ajuste['alvo'] == 'resultado':
            texto = _ajuste_texto(texto, ajuste)
    return texto


def _ajuste_texto(base, ajuste):
    valor = ajuste.get('campo', ajuste.get('valor', '0'))
    if ajuste['tipo'] in ('percentual', 'campo_percentual'):
        return f'({base}) * (1 {ajuste["operacao"]} {valor}/100)'
    return f'({base}) {ajuste["operacao"]} {valor}'


class CompiladorSQL:
    def __init__(self):
        self.parametros = {}
        self.referencias = set()

    def bind(self, valor):
        nome = f'FM_{len(self.parametros)}'
        self.parametros[nome] = valor
        return ':' + nome

    def coluna(self, campo):
        campo = referencia(campo)
        self.referencias.add(campo)
        tabela, coluna = campo.split('.')
        return f'{TABELAS[tabela]}.{coluna}'

    def operando(self, no):
        if isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name):
            return self.coluna(f'{no.value.id}.{no.attr}')
        if isinstance(no, ast.Name) and no.id.lower() in ('preco', 'custo'):
            return 'T.PVENDA' if no.id.lower() == 'preco' else 'E.CUSTOULTENT'
        if isinstance(no, ast.Constant) and type(no.value) in (str, int, float):
            return self.bind(no.value if isinstance(no.value, str) else numero(no.value))
        if isinstance(no, ast.UnaryOp) and isinstance(no.op, (ast.USub, ast.UAdd)) and isinstance(no.operand, ast.Constant) and type(no.operand.value) in (int, float):
            return self.bind(numero(no.operand.value) * (-1 if isinstance(no.op, ast.USub) else 1))
        raise ValueError('WHERE aceita somente colunas, números e textos como valores.')

    def filtro(self, no):
        if no is None:
            return '1=1'
        if isinstance(no, ast.BoolOp) and isinstance(no.op, (ast.And, ast.Or)):
            operador = ' AND ' if isinstance(no.op, ast.And) else ' OR '
            return '(' + operador.join(self.filtro(valor) for valor in no.values) + ')'
        if isinstance(no, ast.UnaryOp) and isinstance(no.op, ast.Not):
            return '(NOT ' + self.filtro(no.operand) + ')'
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == 'like' and len(no.args) == 2 and not no.keywords:
            return f'({self.operando(no.args[0])} LIKE {self.operando(no.args[1])})'
        if isinstance(no, ast.Compare) and len(no.ops) == 1:
            esquerda = self.operando(no.left)
            direita = no.comparators[0]
            operador = no.ops[0]
            if isinstance(operador, (ast.Is, ast.IsNot)) and isinstance(direita, ast.Constant) and direita.value is None:
                return f'({esquerda} IS {"NOT " if isinstance(operador, ast.IsNot) else ""}NULL)'
            if isinstance(operador, (ast.In, ast.NotIn)):
                valores = direita.elts if isinstance(direita, ast.Tuple) else [direita]
                if not valores or len(valores) > 100:
                    raise ValueError('IN aceita de 1 a 100 valores.')
                lista = ', '.join(self.operando(valor) for valor in valores)
                return f'({esquerda} {"NOT " if isinstance(operador, ast.NotIn) else ""}IN ({lista}))'
            sinais = {ast.Eq: '=', ast.NotEq: '<>', ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>='}
            if type(operador) in sinais:
                return f'({esquerda} {sinais[type(operador)]} {self.operando(direita)})'
        raise ValueError('Condição WHERE não permitida. Use comparações, IN, LIKE, IS NULL, AND, OR e NOT.')

    def condicao(self, regra):
        partes = []
        if regra['produtos']:
            partes.append('P.CODPROD IN (' + ', '.join(self.bind(int(codigo)) for codigo in regra['produtos']) + ')')
        if regra['where']:
            partes.append(self.filtro(analisar_where(regra['where'])))
        return '(' + ' AND '.join(partes) + ')' if partes else '(1=1)'

    def aplicar(self, base, ajuste):
        valor = self.coluna(ajuste['campo']) if ajuste['tipo'].startswith('campo') else self.bind(numero(ajuste['valor']))
        if ajuste['tipo'] in ('percentual', 'campo_percentual'):
            return f'(({base}) * (1 {ajuste["operacao"]} ({valor}) / 100))'
        return f'(({base}) {ajuste["operacao"]} ({valor}))'

    def ajustes(self, regra=None):
        preco, custo = 'T.PVENDA', 'E.CUSTOULTENT'
        if (regra or {}).get('campo_custo'):
            campo_custo = referencia(regra['campo_custo'])
            if not campo_custo.startswith('PCEST.'):
                raise ValueError('O campo base do custo deve ser uma coluna de PCEST.')
            custo = self.coluna(campo_custo)
        for ajuste in (regra or {}).get('ajustes', []):
            if ajuste['alvo'] == 'preco':
                preco = self.aplicar(preco, ajuste)
            elif ajuste['alvo'] == 'custo':
                custo = self.aplicar(custo, ajuste)
        percentual = f'((({preco}) - ({custo})) / NULLIF(({custo}), 0) * 100)'
        for ajuste in (regra or {}).get('ajustes', []):
            if ajuste['alvo'] == 'resultado':
                percentual = self.aplicar(percentual, ajuste)
        valido = f'({preco}) > 0 AND ({custo}) > 0'
        return {'preco': preco, 'custo': custo,
                'percentual': f'CASE WHEN {valido} THEN {percentual} ELSE NULL END',
                'base': f'CASE WHEN {valido} THEN ({custo}) ELSE NULL END'}

    def regras(self, regras):
        padrao = self.ajustes()
        condicoes = [(regra, self.condicao(regra), self.ajustes(regra)) for regra in regras]
        saida = {}
        for campo in ('preco', 'custo', 'percentual', 'base'):
            casos = ' '.join(f'WHEN {condicao} THEN ({ajustes[campo]})' for _, condicao, ajustes in condicoes)
            saida[campo] = f'CASE {casos} ELSE ({padrao[campo]}) END' if casos else padrao[campo]
        casos = ' '.join(f'WHEN {condicao} THEN {self.bind(regra["id"])}' for regra, condicao, _ in condicoes)
        saida['id'] = f"CASE {casos} ELSE 'padrao' END" if casos else "'padrao'"
        return saida
