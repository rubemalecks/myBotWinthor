
import os
from pathlib import Path
from threading import Lock, BoundedSemaphore, Timer, Event
from contextlib import contextmanager
import re

import oracledb
from dotenv import load_dotenv
from modulos.permissoes import obter_configuracao
from modulos.escopo import filtros_escopo

# ==========================================
# CONFIGURAÇÕES ORACLE
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

_oracle_client_lock = Lock()
_oracle_client_inicializado = False


class ErroAcessoWinthor(RuntimeError):
    """A sessão Oracle abriu, mas a consulta de produtos não está acessível."""


def validar_diretorio_cliente(caminho):
    if not isinstance(caminho, str) or '\x00' in caminho or caminho.replace('\\', '/').startswith('//') or '://' in caminho:
        raise ValueError('Oracle Client deve estar em uma pasta local confiável, sem caminho de rede ou URL.')
    if os.name == 'nt' and caminho:
        import ctypes
        from pathlib import PureWindowsPath
        raiz = PureWindowsPath(caminho).anchor
        if raiz and ctypes.windll.kernel32.GetDriveTypeW(raiz) == 4:
            raise ValueError('Oracle Client não pode ser carregado de uma unidade de rede.')


def _inicializar_oracle_client(configuracao):
    global _oracle_client_inicializado
    if _oracle_client_inicializado:
        return
    caminho_cliente = configuracao['ORACLE_CLIENT_DIR'].strip()
    validar_diretorio_cliente(caminho_cliente)
    if not caminho_cliente and (BASE_DIR / "oracle_client").is_dir():
        caminho_cliente = str(BASE_DIR / "oracle_client")
    if not caminho_cliente:
        return
    pasta_cliente = Path(caminho_cliente).expanduser()
    if not pasta_cliente.is_absolute():
        pasta_cliente = BASE_DIR / pasta_cliente
    caminho_cliente = str(pasta_cliente.resolve())
    with _oracle_client_lock:
        if not _oracle_client_inicializado:
            oracledb.init_oracle_client(lib_dir=caminho_cliente)
            _oracle_client_inicializado = True


def _abrir_conexao(tcp_connect_timeout=5):
    configuracao = obter_configuracao()
    _inicializar_oracle_client(configuracao)
    host = configuracao['ORACLE_HOST'].strip()
    usuario = configuracao['ORACLE_USER'].strip()
    service_name = configuracao['ORACLE_SERVICE'].strip()
    if not host or not usuario or not service_name or not configuracao['ORACLE_PASSWORD']:
        raise RuntimeError(
            "Configure host, serviço, usuário e senha Oracle no painel administrativo."
        )
    try:
        porta = int(configuracao['ORACLE_PORT'])
    except ValueError as erro:
        raise RuntimeError("A porta do Oracle precisa ser numérica.") from erro
    if not 1 <= porta <= 65535:
        raise RuntimeError("A porta do Oracle precisa estar entre 1 e 65535.")
    opcoes = {}
    if tcp_connect_timeout is not None:
        opcoes["tcp_connect_timeout"] = tcp_connect_timeout
    return oracledb.connect(
        user=usuario,
        password=configuracao['ORACLE_PASSWORD'],
        host=host,
        port=porta,
        service_name=service_name,
        **opcoes,
    )


# Limites por processo, compartilhados entre bot, painel e catálogos.
_MAX_CONEXOES = BoundedSemaphore(4)
TEMPO_CHAMADA_MS = 8000
TEMPO_OPERACAO_S = 20
MAX_LINHAS = 5000


@contextmanager
def conectar(tcp_connect_timeout=5):
    if not _MAX_CONEXOES.acquire(blocking=False):
        raise RuntimeError('Limite de consultas Oracle simultâneas atingido. Tente novamente.')
    temporizador = None
    expirado = Event()
    try:
        with _abrir_conexao(tcp_connect_timeout=tcp_connect_timeout) as conexao:
            conexao.call_timeout = TEMPO_CHAMADA_MS
            def cancelar():
                expirado.set()
                try:
                    conexao.cancel()
                except Exception:
                    pass
            temporizador = Timer(TEMPO_OPERACAO_S, cancelar)
            temporizador.daemon = True
            temporizador.start()
            with conexao.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
            try:
                yield conexao
                if expirado.is_set():
                    raise RuntimeError('Consulta Oracle excedeu o tempo permitido.')
            finally:
                temporizador.cancel()
                # Aguarda um cancelamento já iniciado antes de fechar/reutilizar a sessão.
                temporizador.join(timeout=1)
    finally:
        if temporizador is not None:
            temporizador.cancel()
        _MAX_CONEXOES.release()


def validar_select(sql):
    if not isinstance(sql, str) or len(sql) > 256000:
        raise ValueError('Consulta excede o tamanho permitido.')
    texto = re.sub(r"'(?:[^']|'')*'", "''", sql)
    if not re.match(r'^\s*(SELECT|WITH)\b', texto, re.I) or re.search(
        r';|--|/\*|\b(INSERT|UPDATE|DELETE|MERGE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|BEGIN|DECLARE|EXECUTE|COMMIT|ROLLBACK|LOCK)\b', texto, re.I):
        raise ValueError('Somente SELECTs internos de leitura são permitidos.')


def testar_conexao_oracle():
    with conectar(tcp_connect_timeout=5) as conexao:
        conexao.call_timeout = 5000
        with conexao.cursor() as cursor:
            cursor.execute("SELECT 1 FROM DUAL")
            if cursor.fetchone() != (1,):
                return False
            sql, parametros = _montar_consulta_produto("0")
            # Valida a mesma consulta do bot, sem buscar dados de produtos.
            try:
                cursor.execute(sql.replace("WHERE (", "WHERE 1=0 AND ("), parametros)
            except oracledb.DatabaseError as erro:
                codigo = getattr(erro.args[0], "code", None) if erro.args else None
                if codigo in (942, 1031):
                    raise ErroAcessoWinthor(
                        "Conexão Oracle estabelecida, mas o usuário não consegue acessar "
                        "PCPRODUT, PCTABPR ou PCREGIAO. Verifique permissões SELECT e "
                        "sinônimos/esquema no Oracle (ORA-00942/ORA-01031)."
                    ) from erro
                raise
            return True


def executar_consulta(sql, parametros):
    validar_select(sql)
    with conectar() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(sql, parametros)

            colunas = [
                coluna[0].lower()
                for coluna in cursor.description
            ]

            linhas = cursor.fetchmany(MAX_LINHAS + 1)
            if len(linhas) > MAX_LINHAS:
                raise RuntimeError('Consulta excedeu o limite de registros. Refine os filtros.')
            return [dict(zip(colunas, linha)) for linha in linhas]


# ==========================================
# CONSULTA DE PREÇOS
# ==========================================

def _montar_consulta_produto(codigo, campos=None, escopo=None, campos_retorno=None):
    from modulos.campos_produto import obter_campos_produto, validar_campos
    campos_retorno = obter_campos_produto() if campos_retorno is None else validar_campos(campos_retorno)
    adicionais = ''.join(f', P.{campo["coluna"]} AS EXTRA_{i}' for i, campo in enumerate(campos_retorno))
    campos_validos = {
        "codprod": "P.CODPROD",
        "codauxiliar": "P.CODAUXILIAR",
        "codauxiliar2": "P.CODAUXILIAR2",
    }
    campos = tuple(campos_validos) if campos is None else tuple(campos)
    if not campos or any(campo not in campos_validos for campo in campos):
        raise ValueError("Informe ao menos um campo de busca válido.")

    condicoes = " OR ".join(
        f"{campos_validos[campo]} = :{campo.upper()}" for campo in campos
    )
    sql = """
        SELECT
            P.CODPROD,
            P.DESCRICAO,
            R.NUMREGIAO,
            R.REGIAO AS NOME_TABELA,
            T.PTABELA,
            T.PVENDA{adicionais}

        FROM PCPRODUT P

        INNER JOIN PCTABPR T
            ON T.CODPROD = P.CODPROD

        INNER JOIN PCREGIAO R
            ON R.NUMREGIAO = T.NUMREGIAO

        WHERE ({condicoes})

        AND P.DTEXCLUSAO IS NULL
        AND R.STATUS = 'A'

        ORDER BY R.NUMREGIAO
    """.format(condicoes=condicoes, adicionais=adicionais)

    parametros = {campo.upper(): int(codigo) for campo in campos}
    sql = sql.replace("ORDER BY R.NUMREGIAO", "AND T.PVENDA > 0 " + filtros_escopo(escopo, parametros, regiao="T.NUMREGIAO") + " ORDER BY R.NUMREGIAO")
    return sql, parametros


def consultar_produto(codigo, campos=None, escopo=None):
    from modulos.campos_produto import obter_campos_produto
    campos_retorno = obter_campos_produto()
    sql, parametros = _montar_consulta_produto(codigo, campos, escopo, campos_retorno)
    produtos = executar_consulta(sql, parametros)
    if campos_retorno:
        for produto in produtos:
            produto['campos_personalizados'] = {
                campo['coluna'].lower(): {'valor': produto.pop(f'extra_{i}', None), 'permissao': campo['permissao']}
                for i, campo in enumerate(campos_retorno)
            }
    return produtos


def consultar_produto_previa(codprod, campos=None):
    """Dados de identificação para prévia administrativa, inclusive sem preço."""
    from modulos.campos_produto import obter_campos_produto, validar_campos
    campos = obter_campos_produto(estrito=True) if campos is None else validar_campos(campos)
    extras = ''.join(f', P.{campo["coluna"]} AS EXTRA_{i}' for i, campo in enumerate(campos))
    linhas = executar_consulta(f'''SELECT P.CODPROD, P.DESCRICAO{extras}
        FROM PCPRODUT P WHERE P.CODPROD = :CODPROD
        AND P.DTEXCLUSAO IS NULL AND ROWNUM = 1''', {'CODPROD': int(codprod)})
    if not linhas:
        return None
    produto = linhas[0]
    produto['campos_personalizados'] = {campo['coluna'].lower():
        {'valor': produto.pop(f'extra_{i}', None), 'permissao': campo['permissao']}
        for i, campo in enumerate(campos)}
    return produto


def listar_colunas_produto():
    """Inspeciona a tabela/sinônimo acessível sem recuperar produtos."""
    from modulos.campos_produto import coluna_valida, permissao_padrao
    tipos = {'DB_TYPE_VARCHAR', 'DB_TYPE_NVARCHAR', 'DB_TYPE_CHAR', 'DB_TYPE_NCHAR',
             'DB_TYPE_NUMBER', 'DB_TYPE_DATE', 'DB_TYPE_TIMESTAMP', 'DB_TYPE_TIMESTAMP_TZ',
             'DB_TYPE_TIMESTAMP_LTZ', 'DB_TYPE_BINARY_DOUBLE', 'DB_TYPE_BINARY_FLOAT'}
    with conectar(tcp_connect_timeout=5) as conexao:
        conexao.call_timeout = 5000
        with conexao.cursor() as cursor:
            cursor.execute('SELECT * FROM PCPRODUT WHERE 1=0')
            colunas = []
            for descricao in cursor.description:
                coluna = descricao[0]
                tipo = getattr(descricao[1], 'name', '')
                if coluna_valida(coluna) and tipo in tipos:
                    colunas.append({'coluna': coluna, 'variavel': coluna.lower(),
                                    'tipo': tipo.removeprefix('DB_TYPE_'), 'permissao_padrao': permissao_padrao(coluna)})
            return sorted(colunas, key=lambda item: item['coluna'])


def listar_colunas_custos():
    """Metadados das colunas simples de PCEST; sem ler registros."""
    import re
    with conectar(tcp_connect_timeout=5) as conexao:
        conexao.call_timeout = 5000
        with conexao.cursor() as cursor:
            cursor.execute('SELECT * FROM PCEST WHERE 1=0')
            tipos = {'DB_TYPE_NUMBER', 'DB_TYPE_BINARY_DOUBLE', 'DB_TYPE_BINARY_FLOAT',
                     'DB_TYPE_VARCHAR', 'DB_TYPE_NVARCHAR', 'DB_TYPE_CHAR', 'DB_TYPE_NCHAR',
                     'DB_TYPE_DATE', 'DB_TYPE_TIMESTAMP'}
            return sorted([{'coluna': d[0], 'variavel': 'pcest_' + d[0].lower()}
                for d in cursor.description if re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}', d[0])
                and getattr(d[1], 'name', '') in tipos], key=lambda c: c['coluna'])


def listar_catalogo_formulas():
    from modulos.regras_margem import TABELAS
    numericos = {'DB_TYPE_NUMBER', 'DB_TYPE_BINARY_DOUBLE', 'DB_TYPE_BINARY_FLOAT'}
    simples = numericos | {'DB_TYPE_VARCHAR', 'DB_TYPE_NVARCHAR', 'DB_TYPE_CHAR', 'DB_TYPE_NCHAR'}
    import re
    campos = []
    with conectar(tcp_connect_timeout=5) as conexao:
        conexao.call_timeout = 5000
        with conexao.cursor() as cursor:
            for tabela in TABELAS:
                cursor.execute(f'SELECT * FROM {tabela} WHERE 1=0')
                for descricao in cursor.description:
                    coluna = descricao[0]
                    tipo = getattr(descricao[1], 'name', '')
                    if re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}', coluna) and tipo in simples:
                        campos.append({'campo': f'{tabela}.{coluna}', 'numerico': tipo in numericos,
                                       'tipo': tipo.removeprefix('DB_TYPE_')})
    return campos


def consultar_calculos_formulas_produto(codprod, escopo=None, regras=None, rascunho=None):
    from modulos.regras_margem import CompiladorSQL, obter_regras, expressao_regra, TABELAS
    regras = obter_regras(ativas=True) if regras is None else regras
    compilador = CompiladorSQL()
    atual = compilador.regras(regras)
    selecoes = [f'{sql} AS ATUAL_{chave}' for chave, sql in atual.items()]
    if rascunho is not None:
        simulacao = compilador.ajustes(rascunho)
        selecoes.extend(f'{sql} AS SIM_{chave}' for chave, sql in simulacao.items())
        selecoes.append(f'CASE WHEN {compilador.condicao(rascunho)} THEN 1 ELSE 0 END AS SIM_APLICA')
    campos = sorted({ajuste['campo'] for regra in [*regras, *([rascunho] if rascunho else [])]
                     for ajuste in regra['ajustes'] if ajuste['tipo'].startswith('campo')})
    campos = sorted(set(campos) | {regra['campo_custo']
        for regra in [*regras, *([rascunho] if rascunho else [])] if regra.get('campo_custo')})
    for i, campo in enumerate(campos):
        tabela, coluna = campo.split('.')
        selecoes.append(f'{TABELAS[tabela]}.{coluna} AS VALOR_{i}')
    parametros = {**compilador.parametros, 'FM_CODPROD': int(codprod)}
    sql = f'''SELECT P.CODPROD, P.DESCRICAO, E.CODFILIAL, T.NUMREGIAO,
                     R.REGIAO AS NOME_TABELA, T.PVENDA AS PRECO, E.CUSTOULTENT AS CUSTO,
                     {', '.join(selecoes)}
              FROM PCPRODUT P
              JOIN PCTABPR T ON T.CODPROD = P.CODPROD
              JOIN PCREGIAO R ON R.NUMREGIAO = T.NUMREGIAO
              JOIN PCEST E ON E.CODPROD = P.CODPROD
              WHERE P.CODPROD = :FM_CODPROD AND P.DTEXCLUSAO IS NULL
                AND R.STATUS = 'A' AND T.PVENDA > 0'''
    sql += filtros_escopo(escopo, parametros, filial='E.CODFILIAL', regiao='T.NUMREGIAO')
    linhas = executar_consulta(sql + ' ORDER BY E.CODFILIAL, T.NUMREGIAO', parametros)
    por_id = {regra['id']: regra for regra in regras}
    for linha in linhas:
        regra = por_id.get(linha.pop('atual_id'))
        linha['atual'] = {chave: linha.pop('atual_' + chave) for chave in ('preco', 'custo', 'percentual', 'base')}
        linha['atual'].update({'nome': regra['nome'] if regra else 'Padrão',
                               'personalizada': regra is not None, 'expressao': expressao_regra(regra)})
        linha['parametros'] = {campo: linha.pop(f'valor_{i}') for i, campo in enumerate(campos)}
        if rascunho is not None:
            linha['simulacao'] = {chave: linha.pop('sim_' + chave) for chave in ('preco', 'custo', 'percentual', 'base')}
            linha['simulacao'].update({'nome': rascunho['nome'], 'expressao': expressao_regra(rascunho),
                                      'aplicavel': bool(linha.pop('sim_aplica')),
                                      'escopo_definido': bool(rascunho['todos_produtos'] or rascunho['produtos'] or rascunho['where'])})
    return linhas


# ==========================================
# CONSULTA RESTRITA DE CUSTOS
# ==========================================

def consultar_custos(codprod, escopo=None, texto=None):
    from modulos.campos_custos import variaveis_custos
    from modulos.permissoes import obter_mensagens_personalizadas
    if texto is None:
        texto = obter_mensagens_personalizadas().get('custos', '')
    variaveis = sorted(variaveis_custos(texto))
    extras = ''.join(f', E.{v[6:].upper()} AS {v.upper()}' for v in variaveis)
    sql = """
        WITH ULTIMA_NF AS (
            SELECT
                M.CODPROD,
                N.CODFILIAL,
                N.NUMTRANSENT,
                N.NUMNOTA,
                N.CODFORNEC,
                N.DTENT,
                N.DTEMISSAO,

                ROW_NUMBER() OVER (
                    PARTITION BY M.CODPROD, E.CODFILIAL
                    ORDER BY
                        N.DTENT DESC,
                        N.NUMTRANSENT DESC
                ) AS RN

            FROM PCMOV M

            INNER JOIN PCNFENT N
                ON N.NUMTRANSENT = M.NUMTRANSENT

            INNER JOIN PCEST E
                ON E.CODPROD = M.CODPROD
               AND E.CODFILIAL = N.CODFILIAL

            WHERE M.CODPROD = :CODPROD_CTE
              AND TRUNC(N.DTENT) = TRUNC(E.DTULTENT)
        )

        SELECT
            P.CODPROD,
            P.DESCRICAO,
            E.CODFILIAL,

            E.CUSTOREAL,
            E.CUSTOULTENT,
            E.DTULTENT,

            U.NUMTRANSENT,
            U.NUMNOTA,
            U.CODFORNEC,

            F.FORNECEDOR AS NOME_FORNECEDOR,

            U.DTENT,
            U.DTEMISSAO

        FROM PCPRODUT P

        INNER JOIN PCEST E
            ON E.CODPROD = P.CODPROD

        LEFT JOIN ULTIMA_NF U
            ON U.CODPROD = P.CODPROD
           AND U.CODFILIAL = E.CODFILIAL
           AND U.RN = 1

        LEFT JOIN PCFORNEC F
            ON F.CODFORNEC = U.CODFORNEC

        WHERE P.CODPROD = :CODPROD_PRINCIPAL
          AND P.DTEXCLUSAO IS NULL

        ORDER BY E.CODFILIAL
    """

    sql = sql.replace("E.CUSTOREAL,", "E.CUSTOREAL" + extras + ",")
    params = {"CODPROD_CTE": int(codprod), "CODPROD_PRINCIPAL": int(codprod)}
    sql = sql.replace('ORDER BY E.CODFILIAL', filtros_escopo(escopo, params, filial='E.CODFILIAL', regiao=False) + ' ORDER BY E.CODFILIAL')
    return executar_consulta(sql, params)


def pesquisar_produtos(nome, escopo=None):
    sql = """
        SELECT CODPROD, DESCRICAO
        FROM (
            SELECT DISTINCT
                P.CODPROD,
                P.DESCRICAO
            FROM PCPRODUT P
            INNER JOIN PCTABPR T
                ON T.CODPROD = P.CODPROD
            INNER JOIN PCREGIAO R
                ON R.NUMREGIAO = T.NUMREGIAO
            WHERE R.STATUS = 'A'
              AND P.DTEXCLUSAO IS NULL
              AND UPPER(P.DESCRICAO)
                  LIKE :NOME ESCAPE '\\'
            ORDER BY P.DESCRICAO, P.CODPROD
        )
        WHERE ROWNUM <= 11
    """

    nome = nome.upper().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    params = {"NOME": f"%{nome}%"}
    sql = sql.replace('ORDER BY P.DESCRICAO', filtros_escopo(escopo, params, regiao='T.NUMREGIAO') + ' ORDER BY P.DESCRICAO')
    return executar_consulta(sql, params)


def listar_filiais_produto(codprod, escopo=None):
    params = {'CODPROD': int(codprod)}
    sql = 'SELECT DISTINCT E.CODFILIAL FROM PCEST E JOIN PCPRODUT P ON P.CODPROD=E.CODPROD WHERE P.CODPROD=:CODPROD AND P.DTEXCLUSAO IS NULL'
    sql += filtros_escopo(escopo, params, filial='E.CODFILIAL', regiao=False)
    return executar_consulta(sql + ' ORDER BY E.CODFILIAL', params)


def listar_opcoes_acesso():
    """Catálogo para seleção administrativa, sem consultar preços ou custos."""
    with conectar(tcp_connect_timeout=5) as conexao:
        conexao.call_timeout = 5000
        with conexao.cursor() as cursor:
            cursor.execute('SELECT DISTINCT CODFILIAL FROM PCEST ORDER BY CODFILIAL')
            filiais = [{'codigo': str(linha[0]), 'nome': f'Filial {linha[0]}'}
                       for linha in cursor.fetchmany(MAX_LINHAS + 1) if linha[0] is not None]
            cursor.execute('SELECT NUMREGIAO, REGIAO, STATUS FROM PCREGIAO ORDER BY NUMREGIAO')
            tabelas = [{'codigo': str(linha[0]), 'nome': str(linha[1] or ''),
                        'ativa': str(linha[2] or '').strip() == 'A'} for linha in cursor.fetchmany(MAX_LINHAS + 1)]
            if len(filiais) > MAX_LINHAS or len(tabelas) > MAX_LINHAS:
                raise RuntimeError('Catálogo excede o limite de registros.')
    return {'filiais_permitidas': filiais, 'tabelas_permitidas': tabelas}


def produto_existe(codigo, campos, escopo=None):
    permitidos = {"codprod": "P.CODPROD", "codauxiliar": "P.CODAUXILIAR", "codauxiliar2": "P.CODAUXILIAR2"}
    if not campos or any(campo not in permitidos for campo in campos):
        raise ValueError("Campos inv?lidos.")
    params = {"CODIGO": int(codigo)}
    condicao = ' OR '.join(permitidos[campo] + ' = :CODIGO' for campo in campos)
    sql = 'SELECT P.CODPROD FROM PCPRODUT P WHERE (' + condicao + ') AND P.DTEXCLUSAO IS NULL'
    # N?o filtra pre?o ou regi?o: diferencia produto inexistente de produto sem pre?o permitido.
    sql += filtros_escopo(escopo, params, regiao=False)
    sql += ' AND ROWNUM = 1'
    return bool(executar_consulta(sql, params))
