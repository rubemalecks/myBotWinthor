
import os
from pathlib import Path
from threading import Lock

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


def _inicializar_oracle_client(configuracao):
    global _oracle_client_inicializado
    if _oracle_client_inicializado:
        return
    caminho_cliente = configuracao['ORACLE_CLIENT_DIR'].strip()
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


def conectar(tcp_connect_timeout=None):
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
    with conectar() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(sql, parametros)

            colunas = [
                coluna[0].lower()
                for coluna in cursor.description
            ]

            return [
                dict(zip(colunas, linha))
                for linha in cursor.fetchall()
            ]


# ==========================================
# CONSULTA DE PREÇOS
# ==========================================

def _montar_consulta_produto(codigo, campos=None, escopo=None):
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
            T.PVENDA

        FROM PCPRODUT P

        INNER JOIN PCTABPR T
            ON T.CODPROD = P.CODPROD

        INNER JOIN PCREGIAO R
            ON R.NUMREGIAO = T.NUMREGIAO

        WHERE ({condicoes})

        AND P.DTEXCLUSAO IS NULL
        AND R.STATUS = 'A'

        ORDER BY R.NUMREGIAO
    """.format(condicoes=condicoes)

    parametros = {campo.upper(): int(codigo) for campo in campos}
    sql = sql.replace("ORDER BY R.NUMREGIAO", "AND T.PVENDA > 0 " + filtros_escopo(escopo, parametros, regiao="T.NUMREGIAO") + " ORDER BY R.NUMREGIAO")
    return sql, parametros


def consultar_produto(codigo, campos=None, escopo=None):
    sql, parametros = _montar_consulta_produto(codigo, campos, escopo)
    return executar_consulta(sql, parametros)


# ==========================================
# CONSULTA RESTRITA DE CUSTOS
# ==========================================

def consultar_custos(codprod, escopo=None):
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
                  LIKE :NOME
            ORDER BY P.DESCRICAO, P.CODPROD
        )
        WHERE ROWNUM <= 11
    """

    params = {"NOME": f"%{nome.upper()}%"}
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
                       for linha in cursor.fetchall() if linha[0] is not None]
            cursor.execute('SELECT NUMREGIAO, REGIAO, STATUS FROM PCREGIAO ORDER BY NUMREGIAO')
            tabelas = [{'codigo': str(linha[0]), 'nome': str(linha[1] or ''),
                        'ativa': str(linha[2] or '').strip() == 'A'} for linha in cursor.fetchall()]
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
