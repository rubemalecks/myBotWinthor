"""Consulta de margem estimada do mix por departamento no WinThor.

Cada produto contribui com UMA unidade por filial e região.
Não é lucro realizado, nem leva em conta quantidade em estoque/vendida.
"""
from decimal import Decimal
from modulos.database import executar_consulta
from modulos.escopo import filtros_escopo
from modulos.calculos import ganho_sobre_custo
from modulos.mensagens import renderizar_mensagem

def _consultar_escopo(sql, params, escopo, filial, regiao, marcador):
    sql = sql.replace(marcador, filtros_escopo(escopo, params, filial, regiao) + " " + marcador, 1)
    return executar_consulta(sql, params)



def listar_departamentos(termo=None):
    """Retorna até 20 departamentos (21 para detectar excesso)."""
    filtro = "AND (TO_CHAR(D.CODEPTO) = :COD OR UPPER(D.DESCRICAO) LIKE :TERMO)" if termo else ""
    sql = f"""
        SELECT CODEPTO, DESCRICAO FROM (
            SELECT D.CODEPTO, D.DESCRICAO
            FROM PCDEPTO D
            WHERE 1=1 {filtro}
            ORDER BY D.DESCRICAO, D.CODEPTO
        ) WHERE ROWNUM <= 21
    """
    params = {"COD": termo, "TERMO": f"%{termo.upper()}%"} if termo else {}
    return executar_consulta(sql, params)


def obter_departamento(codigo):
    linhas = executar_consulta(
        "SELECT CODEPTO, DESCRICAO FROM PCDEPTO WHERE CODEPTO = :COD",
        {"COD": int(codigo)},
    )
    return linhas[0] if linhas else None


def listar_filiais_departamento(codigo_departamento, escopo=None):
    """Filiais com registro de estoque de produtos do departamento."""
    return _consultar_escopo("""
        SELECT DISTINCT E.CODFILIAL
        FROM PCEST E
        JOIN PCPRODUT P ON P.CODPROD = E.CODPROD
        WHERE P.CODEPTO = :DEPTO
          AND P.DTEXCLUSAO IS NULL
        ORDER BY E.CODFILIAL
    """, {"DEPTO": int(codigo_departamento)}, escopo, 'E.CODFILIAL', None, 'ORDER BY E.CODFILIAL')


def listar_regioes_ativas(codigo_departamento, escopo=None):
    """Somente regiões ativas que tenham preço para o departamento."""
    return _consultar_escopo("""
        SELECT DISTINCT R.NUMREGIAO, R.REGIAO AS NOME_TABELA
        FROM PCREGIAO R
        JOIN PCTABPR T ON T.NUMREGIAO = R.NUMREGIAO
        JOIN PCPRODUT P ON P.CODPROD = T.CODPROD
        WHERE R.STATUS = 'A' AND P.CODEPTO = :DEPTO
          AND P.DTEXCLUSAO IS NULL
        ORDER BY R.NUMREGIAO
    """, {"DEPTO": int(codigo_departamento)}, escopo, None, 'R.NUMREGIAO', 'ORDER BY R.NUMREGIAO')


def calcular_margens_departamento(codigo_departamento, codigo_filial, regiao=None, escopo=None):
    """Uma linha por região; não multiplica custos entre regiões.

    Só produtos com PVENDA > 0 e CUSTOULTENT não nulo são somados.
    Custo 0 é incluído e informado na contagem de custo zero.
    """
    sql = """
        WITH BASE AS (
            SELECT T.NUMREGIAO, R.REGIAO AS NOME_TABELA,
                   P.CODPROD, T.PVENDA, E.CUSTOULTENT
            FROM PCPRODUT P
            JOIN PCTABPR T ON T.CODPROD = P.CODPROD
            JOIN PCREGIAO R ON R.NUMREGIAO = T.NUMREGIAO
            JOIN PCEST E ON E.CODPROD = P.CODPROD
            WHERE P.CODEPTO = :DEPTO
              AND P.DTEXCLUSAO IS NULL
              AND E.CODFILIAL = :FILIAL
              AND R.STATUS = 'A'
              AND (:REGIAO IS NULL OR T.NUMREGIAO = :REGIAO)
        )
        SELECT NUMREGIAO, NOME_TABELA,
               COUNT(*) AS TOTAL_PRODUTOS,
               SUM(CASE WHEN PVENDA > 0 AND CUSTOULTENT IS NOT NULL
                        THEN 1 ELSE 0 END) AS PRODUTOS_VALIDOS,
               SUM(CASE WHEN PVENDA IS NULL OR PVENDA <= 0
                        THEN 1 ELSE 0 END) AS SEM_PRECO,
               SUM(CASE WHEN CUSTOULTENT IS NULL
                        THEN 1 ELSE 0 END) AS SEM_CUSTO,
               SUM(CASE WHEN CUSTOULTENT = 0 THEN 1 ELSE 0 END) AS CUSTO_ZERO,
               SUM(CASE WHEN PVENDA > 0 AND CUSTOULTENT IS NOT NULL
                        THEN PVENDA ELSE 0 END) AS TOTAL_PRECOS,
               SUM(CASE WHEN PVENDA > 0 AND CUSTOULTENT IS NOT NULL
                        THEN CUSTOULTENT ELSE 0 END) AS TOTAL_CUSTOS
        FROM BASE
        GROUP BY NUMREGIAO, NOME_TABELA
        ORDER BY NUMREGIAO
    """
    return _consultar_escopo(sql, {
        "DEPTO": int(codigo_departamento),
        "FILIAL": str(codigo_filial),
        "REGIAO": int(regiao) if regiao is not None else None,
    }, escopo, 'E.CODFILIAL', 'T.NUMREGIAO', '\n        )')


def consultar_margens_departamento_produto(codprod, escopo=None):
    """Margem do mix nas mesmas tabelas e filiais do produto consultado."""
    return _consultar_escopo("""
        SELECT P.CODEPTO, E.CODFILIAL, T.NUMREGIAO, R.REGIAO AS NOME_TABELA,
               SUM(T.PVENDA) AS TOTAL_PRECOS,
               SUM(E.CUSTOULTENT) AS TOTAL_CUSTOS,
               COUNT(*) AS PRODUTOS_VALIDOS
        FROM PCPRODUT P
        JOIN PCTABPR T ON T.CODPROD = P.CODPROD
        JOIN PCREGIAO R ON R.NUMREGIAO = T.NUMREGIAO
        JOIN PCEST E ON E.CODPROD = P.CODPROD
        WHERE P.CODEPTO = (SELECT CODEPTO FROM PCPRODUT WHERE CODPROD = :CODPROD AND DTEXCLUSAO IS NULL)
          AND P.DTEXCLUSAO IS NULL
          AND R.STATUS = 'A'
          AND T.PVENDA > 0 AND E.CUSTOULTENT IS NOT NULL
          AND EXISTS (SELECT 1 FROM PCTABPR TP
                      WHERE TP.CODPROD = :CODPROD AND TP.NUMREGIAO = T.NUMREGIAO)
          AND EXISTS (SELECT 1 FROM PCEST EP
                      WHERE EP.CODPROD = :CODPROD AND EP.CODFILIAL = E.CODFILIAL)
        GROUP BY P.CODEPTO, E.CODFILIAL, T.NUMREGIAO, R.REGIAO
        ORDER BY E.CODFILIAL, T.NUMREGIAO
    """, {"CODPROD": int(codprod)}, escopo, 'E.CODFILIAL', 'T.NUMREGIAO', 'GROUP BY')


def formatar_relatorio(departamento, filial, linhas, incluir_custos=True):
    def moeda(valor):
        valor = Decimal(str(valor or 0))
        return 'R$ ' + f'{valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    texto = renderizar_mensagem('departamento', codigo=departamento['codepto'],
        departamento=departamento['descricao'], filial=filial)
    if not linhas:
        return texto + renderizar_mensagem('departamento_vazio')

    for item in linhas:
        preco = Decimal(str(item['total_precos'] or 0))
        custo = Decimal(str(item['total_custos'] or 0))
        diferenca = preco - custo
        margem = ganho_sobre_custo(preco, custo)
        margem_txt = (f'{margem:.2f}'.replace('.', ',') + '%') if margem is not None else 'Indisponível'
        texto += renderizar_mensagem('departamento_tabela', regiao=item['numregiao'],
            tabela=item['nome_tabela'], precos=moeda(preco), lucro=margem_txt)
        if incluir_custos:
            texto += renderizar_mensagem('departamento_custos', custos=moeda(custo), diferenca=moeda(diferenca),
                validos=item['produtos_validos'] or 0, total=item['total_produtos'],
                sem_preco=item['sem_preco'] or 0, sem_custo=item['sem_custo'] or 0, custo_zero=item['custo_zero'] or 0)
        texto += '\n'
    texto += renderizar_mensagem('departamento_rodape')
    return texto
